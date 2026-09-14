"""基于知乎直答大模型的语义匹配引擎。

与 content_match.py（TF-IDF 字面匹配）的区别：
    TF-IDF 衡量"用词重合度"，无法区分"同主题同立场"和"同主题对立立场"。
    本模块调用知乎直答，让大模型直接判断两段内容的议题相关性与立场一致性。

知乎开放平台未提供 embedding 接口，因此采用 LLM-as-Judge 而非向量余弦。

返回结构与 match_content() 保持字段兼容，便于页面复用：
    similarity / text_similarity / topic_similarity / text_weight
    evidence: [{"feature": ..., "contribution": ...}]
另外新增语义专有字段：
    stance_alignment / shared_points / divergence / reason
"""
from __future__ import annotations

import concurrent.futures
import hashlib
import json
import re
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from utils.content_match import clean_content

# ---------------- 直答调用限流 ----------------
# 实测密集串行调用会触发 Code=30001 rate limit exceeded，
# 这里用全局最小间隔 + 指数退避重试兜底。
_MIN_INTERVAL = 1.2
_rate_lock = threading.Lock()
_last_call_at = [0.0]


def _throttle() -> None:
    with _rate_lock:
        wait = _MIN_INTERVAL - (time.time() - _last_call_at[0])
        if wait > 0:
            time.sleep(wait)
        _last_call_at[0] = time.time()


# ---------------- 客户端 ----------------
_client_lock = threading.Lock()
_client_cache: List[Any] = []


def get_client():
    """惰性创建 ZhihuClient，复用同一 Session。"""
    with _client_lock:
        if not _client_cache:
            from zhihu_client import ZhihuClient

            _client_cache.append(ZhihuClient())
        return _client_cache[0]


# ---------------- 结果缓存 ----------------
# 同一对文本在调参过程中会被反复比较，缓存可显著节省额度。
_cache: Dict[str, Dict[str, Any]] = {}
_cache_lock = threading.Lock()


def _cache_key(a: str, b: str, model: str) -> str:
    raw = f"{model}||{a}||{b}".encode("utf-8", "ignore")
    return hashlib.sha256(raw).hexdigest()


def clear_cache() -> None:
    with _cache_lock:
        _cache.clear()


# ---------------- 提示词 ----------------
_PROMPT = """你是一个观点匹配分析器。请比较下面两段知乎内容，判断它们的语义关系。

【内容A（基准）】
{a}

【内容B（候选）】
{b}

请严格按下面的 JSON 格式输出，不要输出任何额外文字或代码块标记：
{{"topic_similarity": 0.0, "stance_alignment": 0.0, "shared_points": ["..."], "divergence": ["..."], "reason": "..."}}

字段要求：
- topic_similarity：两段内容讨论的是否为同一议题，0.0 完全无关，1.0 完全同一议题。
- stance_alignment：在共同议题上的立场是否一致，0.0 立场对立，0.5 无法判断或中立，1.0 立场高度一致。若议题无关则填 0.5。
- shared_points：两者共同关注的具体论点，最多 4 条，每条不超过 12 字。
- divergence：两者的分歧点，最多 3 条，每条不超过 12 字。没有分歧则为空数组。
- reason：一句话说明判断依据，不超过 50 字。

注意：讨论同一话题不等于立场一致，请分别独立评估两个分数。"""


def _extract_json(raw: str) -> Optional[Dict[str, Any]]:
    """从模型输出中容错解析 JSON。

    直答是对话模型，可能包裹 ```json 代码块或附加说明文字。
    """
    if not raw:
        return None
    text = raw.strip()
    # 去除 markdown 代码块围栏
    fence = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        pass
    # 回退：抓取第一个平衡的花括号片段
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    for pos in range(start, len(text)):
        if text[pos] == "{":
            depth += 1
        elif text[pos] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:pos + 1])
                except json.JSONDecodeError:
                    return None
    return None


def _clamp01(value: Any, default: float = 0.0) -> float:
    try:
        return float(min(1.0, max(0.0, float(value))))
    except (TypeError, ValueError):
        return default


def _str_list(value: Any, limit: int) -> List[str]:
    if not isinstance(value, list):
        return []
    out = []
    for item in value[:limit]:
        text = str(item).strip()
        if text:
            out.append(text[:30])
    return out


def judge_pair(
    text_a: str,
    text_b: str,
    model: str = "zhida-fast-1p5",
    max_chars: int = 1200,
    retries: int = 3,
) -> Dict[str, Any]:
    """调用直答判断一对文本的语义关系。失败时返回 ok=False，不抛出。"""
    a = clean_content(text_a)[:max_chars]
    b = clean_content(text_b)[:max_chars]
    if not a or not b:
        return {"ok": False, "error": "内容为空", "topic_similarity": 0.0,
                "stance_alignment": 0.5, "shared_points": [], "divergence": [], "reason": ""}

    key = _cache_key(a, b, model)
    with _cache_lock:
        if key in _cache:
            return dict(_cache[key])

    client = get_client()
    prompt = _PROMPT.format(a=a, b=b)
    last_error = ""

    for attempt in range(retries):
        try:
            _throttle()
            raw = client.answer(prompt, model=model)
            parsed = _extract_json(raw)
            if parsed is None:
                last_error = "模型未返回可解析 JSON"
                continue
            result = {
                "ok": True,
                "error": "",
                "topic_similarity": _clamp01(parsed.get("topic_similarity")),
                "stance_alignment": _clamp01(parsed.get("stance_alignment"), 0.5),
                "shared_points": _str_list(parsed.get("shared_points"), 4),
                "divergence": _str_list(parsed.get("divergence"), 3),
                "reason": str(parsed.get("reason", "")).strip()[:120],
            }
            with _cache_lock:
                _cache[key] = dict(result)
            return result
        except Exception as exc:  # 网络/限流/服务端错误统一退避重试
            last_error = f"{type(exc).__name__}: {exc}"
            if "rate limit" in str(exc).lower() and attempt < retries - 1:
                time.sleep(2 ** attempt * 3)
            elif attempt < retries - 1:
                time.sleep(1.5)

    return {"ok": False, "error": last_error, "topic_similarity": 0.0,
            "stance_alignment": 0.5, "shared_points": [], "divergence": [], "reason": ""}


def match_content_semantic(
    pool: List[Dict[str, Any]],
    base_index: int,
    topic_weight: float = 0.6,
    real_only: bool = True,
    top_k: int = 20,
    model: str = "zhida-fast-1p5",
    max_workers: int = 3,
    progress_callback=None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """使用知乎直答对候选池做语义匹配。

    综合分 = 议题相关性 × topic_weight + 立场一致性 × (1 - topic_weight)

    参数与 match_content() 对齐，便于页面切换引擎。
    progress_callback(done, total) 用于 Streamlit 进度条。
    """
    if not 0 <= base_index < len(pool):
        raise ValueError("基准对象不在候选池中")
    if not 0 <= topic_weight <= 1 or top_k < 0:
        raise ValueError("权重或推荐数量超出范围")

    texts = [clean_content(p.get("search_content", "")) for p in pool]
    eligible = [
        i for i, p in enumerate(pool)
        if texts[i] and (not real_only or p.get("is_real_search"))
    ]
    if base_index not in eligible:
        raise ValueError("基准对象没有符合来源条件的内容，请更换对象或关闭真实搜索筛选")
    if len(eligible) < 2:
        raise ValueError("至少需要两个包含有效内容且符合来源条件的对象")

    targets = [i for i in eligible if i != base_index]
    total = len(targets)
    done = [0]
    done_lock = threading.Lock()

    def worker(index: int):
        verdict = judge_pair(texts[base_index], texts[index], model=model)
        with done_lock:
            done[0] += 1
            if progress_callback:
                progress_callback(done[0], total)
        return index, verdict

    verdicts: Dict[int, Dict[str, Any]] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, max_workers)) as executor:
        for index, verdict in executor.map(worker, targets):
            verdicts[index] = verdict

    results = []
    failed = 0
    for index in targets:
        verdict = verdicts.get(index, {})
        if not verdict.get("ok"):
            failed += 1
            continue
        topic = verdict["topic_similarity"]
        stance = verdict["stance_alignment"]
        score = topic * topic_weight + stance * (1 - topic_weight)
        # 与 TF-IDF 版本保持字段兼容：evidence 用共同论点填充
        evidence = [
            {"feature": point, "contribution": round(topic / max(1, len(verdict["shared_points"])), 4)}
            for point in verdict["shared_points"]
        ]
        results.append({
            "index": index,
            "input": pool[index].get("input_text", "未命名"),
            "profile": pool[index],
            "similarity": round(score, 4),
            # 兼容字段：页面沿用同名列即可展示
            "text_similarity": round(topic, 4),
            "topic_similarity": round(stance, 4),
            "text_weight": topic_weight,
            "evidence": evidence,
            "shared_features": len(verdict["shared_points"]),
            # 语义引擎专有字段
            "issue_similarity": round(topic, 4),
            "stance_alignment": round(stance, 4),
            "shared_points": verdict["shared_points"],
            "divergence": verdict["divergence"],
            "reason": verdict["reason"],
        })

    results.sort(key=lambda item: (-item["similarity"], item["index"]))
    analysis = {
        "texts": texts,
        "documents": len(eligible),
        "features": 0,
        "method": f"知乎直答语义判定（{model}）",
        "model": model,
        "api_calls": total,
        "failed": failed,
        "topic_weight": topic_weight,
    }
    return results[:top_k], analysis
