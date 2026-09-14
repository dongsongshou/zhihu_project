"""知乎直答：搜索结果相对基准内容的打分与排序。

场景：给定一段基准内容 + 一批知乎搜索结果，对每条结果打分并排序。

与 content_match.py（两两 TF-IDF）的区别：
    这里是"一对多"评分，且由大模型分别给出议题相关性与立场一致性，
    可以区分"同话题同立场"和"同话题对立立场"——TF-IDF 做不到这一点。

采用分批打分：一次请求评多条候选，显著节省额度与耗时。
知乎开放平台无 embedding 接口，故使用 LLM-as-Judge 而非向量余弦。
"""
from __future__ import annotations

import concurrent.futures
import json
import re
import threading
import time
from typing import Any, Callable, Dict, List, Optional

from utils.content_match import clean_content

_MIN_INTERVAL = 1.0
_rate_lock = threading.Lock()
_last_call = [0.0]


def _throttle() -> None:
    """全局最小调用间隔，规避 Code=30001 rate limit exceeded。"""
    with _rate_lock:
        wait = _MIN_INTERVAL - (time.time() - _last_call[0])
        if wait > 0:
            time.sleep(wait)
        _last_call[0] = time.time()


_client_lock = threading.Lock()
_client_box: List[Any] = []


def get_client():
    with _client_lock:
        if not _client_box:
            from zhihu_client import ZhihuClient
            _client_box.append(ZhihuClient())
        return _client_box[0]


_BATCH_PROMPT = """你是观点匹配评分器。下面给出一段【基准内容】和若干【候选内容】。
请逐条评估每个候选与基准的语义关系。

【基准内容】
{base}

【候选内容】
{candidates}

严格输出 JSON 数组，不要输出任何额外文字或代码块标记。数组长度必须等于候选条数，按候选编号顺序排列：
[{{"id": 1, "relevance": 0.0, "stance": 0.5, "shared": ["..."], "diff": ["..."], "reason": "..."}}]

字段要求：
- id：候选编号，必须与输入编号一致。
- relevance：与基准是否讨论同一议题。0.0 完全无关，1.0 完全同一议题。
- stance：在共同议题上的立场是否与基准一致。0.0 立场对立，0.5 中立或无法判断，1.0 立场高度一致。议题无关时填 0.5。
- shared：与基准共同的论点，最多 3 条，每条不超过 12 字。
- diff：与基准的分歧点，最多 2 条，每条不超过 12 字。无分歧填空数组。
- reason：一句话依据，不超过 40 字。

注意：同一议题不代表立场相同，relevance 与 stance 必须独立评估。"""


def _extract_json_array(raw: str) -> Optional[List[Dict[str, Any]]]:
    """容错解析模型输出的 JSON 数组。直答可能包裹代码块或附加说明。"""
    if not raw:
        return None
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict):
            for value in parsed.values():
                if isinstance(value, list):
                    return value
    except (json.JSONDecodeError, TypeError):
        pass
    # 回退：抓第一个平衡的中括号片段
    start = text.find("[")
    if start < 0:
        return None
    depth = 0
    for pos in range(start, len(text)):
        if text[pos] == "[":
            depth += 1
        elif text[pos] == "]":
            depth -= 1
            if depth == 0:
                try:
                    got = json.loads(text[start:pos + 1])
                    return got if isinstance(got, list) else None
                except json.JSONDecodeError:
                    return None
    return None


def _clamp(value: Any, default: float = 0.0) -> float:
    try:
        return float(min(1.0, max(0.0, float(value))))
    except (TypeError, ValueError):
        return default


def _short_list(value: Any, limit: int) -> List[str]:
    if not isinstance(value, list):
        return []
    out = []
    for item in value[:limit]:
        text = str(item).strip()
        if text:
            out.append(text[:24])
    return out


def item_to_text(item: Any) -> str:
    """把一条搜索结果规整成待评分文本。兼容 dict 与纯字符串。"""
    if isinstance(item, str):
        return clean_content(item)
    if not isinstance(item, dict):
        return ""
    title = str(item.get("Title") or item.get("title") or "").strip()
    body = str(
        item.get("ContentText")
        or item.get("content_text")
        or item.get("Summary")
        or item.get("search_content")
        or ""
    ).strip()
    return clean_content(f"{title}\n{body}" if title else body)


def _score_batch(
    base: str,
    batch: List[Dict[str, Any]],
    model: str,
    cand_chars: int,
    retries: int,
) -> Dict[int, Dict[str, Any]]:
    """评一批候选。返回 {原始下标: 评分结果}，失败返回空字典。"""
    blocks = []
    for order, entry in enumerate(batch, start=1):
        blocks.append(f"[候选{order}]\n{entry['text'][:cand_chars]}")
    prompt = _BATCH_PROMPT.format(base=base, candidates="\n\n".join(blocks))

    client = get_client()
    for attempt in range(retries):
        try:
            _throttle()
            raw = client.answer(prompt, model=model)
            parsed = _extract_json_array(raw)
            if not parsed:
                continue
            out: Dict[int, Dict[str, Any]] = {}
            for order, entry in enumerate(batch, start=1):
                row = None
                for candidate_row in parsed:
                    if isinstance(candidate_row, dict) and str(candidate_row.get("id")) == str(order):
                        row = candidate_row
                        break
                if row is None and order - 1 < len(parsed) and isinstance(parsed[order - 1], dict):
                    row = parsed[order - 1]
                if row is None:
                    continue
                out[entry["pos"]] = {
                    "relevance": _clamp(row.get("relevance")),
                    "stance": _clamp(row.get("stance"), 0.5),
                    "shared": _short_list(row.get("shared"), 3),
                    "diff": _short_list(row.get("diff"), 2),
                    "reason": str(row.get("reason", "")).strip()[:100],
                }
            if out:
                return out
        except Exception as exc:
            message = str(exc).lower()
            if "rate limit" in message and attempt < retries - 1:
                time.sleep(2 ** attempt * 3)
            elif attempt < retries - 1:
                time.sleep(1.5)
    return {}


def rank_search_results(
    base_content: str,
    search_items: List[Any],
    relevance_weight: float = 0.6,
    model: str = "zhida-fast-1p5",
    batch_size: int = 5,
    max_workers: int = 3,
    base_chars: int = 1000,
    cand_chars: int = 600,
    retries: int = 3,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> Dict[str, Any]:
    """对搜索结果按与基准内容的语义关系打分排序。

    综合分 = relevance × relevance_weight + stance × (1 - relevance_weight)

    返回 {"ranked": [...], "failed": [...], "stats": {...}}
    ranked 中每项含：rank / score / relevance / stance / shared / diff / reason
                    title / url / author / raw（原始搜索结果）
    """
    base = clean_content(base_content)[:base_chars]
    if not base:
        raise ValueError("基准内容为空，无法打分")
    if not search_items:
        raise ValueError("搜索结果为空，无可排序内容")
    if not 0 <= relevance_weight <= 1:
        raise ValueError("relevance_weight 必须在 0 到 1 之间")

    entries = []
    empty_positions = []
    for pos, item in enumerate(search_items):
        text = item_to_text(item)
        if text:
            entries.append({"pos": pos, "text": text})
        else:
            empty_positions.append(pos)

    if not entries:
        raise ValueError("所有搜索结果都没有可用文本")

    size = max(1, batch_size)
    batches = [entries[i:i + size] for i in range(0, len(entries), size)]
    total = len(batches)
    done = [0]
    done_lock = threading.Lock()

    def worker(batch):
        result = _score_batch(base, batch, model, cand_chars, retries)
        with done_lock:
            done[0] += 1
            if progress_callback:
                progress_callback(done[0], total)
        return result

    scores: Dict[int, Dict[str, Any]] = {}
    started = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, max_workers)) as executor:
        for partial in executor.map(worker, batches):
            scores.update(partial)

    ranked = []
    failed = []
    for pos, item in enumerate(search_items):
        source = item if isinstance(item, dict) else {}
        title = str(source.get("Title") or source.get("title") or "").strip()
        record_base = {
            "position": pos,
            "title": title or f"结果 {pos + 1}",
            "url": str(source.get("Url") or source.get("url") or ""),
            "author": str(source.get("AuthorName") or source.get("author") or ""),
            "raw": item,
        }
        verdict = scores.get(pos)
        if verdict is None:
            reason = "内容为空" if pos in empty_positions else "模型未返回有效评分"
            failed.append({**record_base, "error": reason})
            continue
        relevance = verdict["relevance"]
        stance = verdict["stance"]
        ranked.append({
            **record_base,
            "score": round(relevance * relevance_weight + stance * (1 - relevance_weight), 4),
            "relevance": round(relevance, 4),
            "stance": round(stance, 4),
            "shared": verdict["shared"],
            "diff": verdict["diff"],
            "reason": verdict["reason"],
        })

    ranked.sort(key=lambda row: (-row["score"], row["position"]))
    for order, row in enumerate(ranked, start=1):
        row["rank"] = order

    return {
        "ranked": ranked,
        "failed": failed,
        "stats": {
            "model": model,
            "total_items": len(search_items),
            "scored": len(ranked),
            "failed": len(failed),
            "api_calls": total,
            "batch_size": size,
            "relevance_weight": relevance_weight,
            "elapsed": round(time.time() - started, 2),
            "method": f"知乎直答分批语义评分（{model}）",
        },
    }


def rank_by_query(
    base_content: str,
    query: str,
    count: int = 10,
    **kwargs: Any,
) -> Dict[str, Any]:
    """便捷入口：先按 query 搜索知乎，再对结果打分排序。"""
    client = get_client()
    items = client.search_zhihu(query, count=count)
    if not items:
        raise ValueError(f"搜索「{query}」没有返回结果")
    result = rank_search_results(base_content, items, **kwargs)
    result["stats"]["query"] = query
    return result
