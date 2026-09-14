"""使用当前知乎直答模型进行可选的内容语义判断。"""
import json
import re
import requests
from zhihu_client import ZhihuClient


class SemanticJudgeError(RuntimeError):
    pass


def judge_pair(base_text, candidate_text, topic):
    prompt = f"""请判断下面两段关于“{topic}”的中文内容是否语义相关。只返回JSON，不要解释：
{{"related": true, "score": 0.0, "common_interest": "", "difference": "", "reason": ""}}
score为0到1。不要根据作者身份推断，不要判断谁正确，只判断讨论对象和核心语义是否相关。
基准内容：{base_text[:3000]}
候选内容：{candidate_text[:3000]}"""
    try:
        answer = ZhihuClient().answer(prompt, model="zhida-fast-1p5")
    except (requests.RequestException, RuntimeError, ValueError) as exc:
        raise SemanticJudgeError(f"知乎直答请求失败（可能触发 WAF/额度或接口限制）：{exc}") from exc
    text = str(answer or "").strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE).strip()
    # 模型偶尔会在 JSON 前后补充说明，截取首个完整对象。
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        # 模型偶尔只返回自然语言；保留其判断文本作为理由，使用保守中性分数，避免整批推荐失败。
        if text:
            return {"related": True, "score": 0.5, "common_interest": "", "difference": "", "reason": text}
        raise SemanticJudgeError("模型没有返回可解析的 JSON 语义判断结果。")
    try:
        data = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        # 尝试从非标准 JSON 文本中提取 score，其他字段用原文作为理由。
        score_match = re.search(r"(?:score|分数|相关度)\s*[=:：]\s*(0(?:\.\d+)?|1(?:\.0+)?)", text, re.IGNORECASE)
        score = float(score_match.group(1)) if score_match else 0.5
        return {"related": score >= 0.5, "score": score, "common_interest": "", "difference": "", "reason": text}

    if not isinstance(data, dict):
        raise SemanticJudgeError("模型返回的语义判断不是 JSON 对象。")
    score = max(0.0, min(1.0, float(data.get("score", 0))))
    data["score"] = score
    data["related"] = bool(data.get("related", score > 0.5))
    return data
