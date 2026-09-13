"""基于搜索摘要的可解释 TF-IDF 匹配。"""
import html
import re

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer


def clean_content(text):
    text = html.unescape(re.sub(r"<[^>]+>", " ", str(text or "")))
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(dict.fromkeys(line for line in lines if line))[:30000]


def content_features(text):
    # 中文采用连续 2～4 字片段；英文采用完整单词，避免中英分词依赖。
    for segment in re.findall(r"[\u4e00-\u9fff]+|[a-zA-Z]+", text.lower()):
        if segment.isascii():
            if len(segment) > 1:
                yield segment
        else:
            for width in (2, 3, 4):
                for start in range(len(segment) - width + 1):
                    yield segment[start:start + width]


def match_content(pool, base_index, text_weight=0.8, real_only=True, top_k=20):
    if not 0 <= base_index < len(pool):
        raise ValueError("基准对象不在候选池中")
    if not 0 <= text_weight <= 1 or top_k < 0:
        raise ValueError("权重或推荐数量超出范围")
    texts = [clean_content(p.get("search_content", "")) for p in pool]
    eligible = [i for i, p in enumerate(pool) if texts[i] and (not real_only or p.get("is_real_search"))]
    if base_index not in eligible:
        raise ValueError("基准对象没有符合来源条件的内容，请更换对象或关闭真实搜索筛选")
    if len(eligible) < 2:
        raise ValueError("至少需要两个包含有效内容且符合来源条件的对象")
    vectorizer = TfidfVectorizer(analyzer=content_features, sublinear_tf=True, max_features=12000, norm="l2")
    try:
        matrix = vectorizer.fit_transform([texts[i] for i in eligible])
    except ValueError as exc:
        raise ValueError("摘要中没有可提取的中英文文本特征") from exc
    row = eligible.index(base_index)
    if matrix[row].nnz == 0:
        raise ValueError("基准摘要未提取到有效特征，请补充内容")
    text_scores = (matrix @ matrix[row].T).toarray().ravel()
    feature_names = vectorizer.get_feature_names_out()

    def topic_vector(profile):
        v = np.asarray(profile.get("embedding", []), dtype=float)
        if v.ndim != 1 or not np.isfinite(v).all() or np.linalg.norm(v) == 0:
            return None
        return v / np.linalg.norm(v)

    base_topic = topic_vector(pool[base_index])
    results = []
    for local_index, index in enumerate(eligible):
        if index == base_index or matrix[local_index].nnz == 0:
            continue
        topic = topic_vector(pool[index])
        has_topic = base_topic is not None and topic is not None and topic.shape == base_topic.shape
        topic_score = float(np.clip(base_topic @ topic, 0, 1)) if has_topic else 0.0
        weight = text_weight if has_topic else 1.0
        text_score = float(np.clip(text_scores[local_index], 0, 1))
        contributions = matrix[row].multiply(matrix[local_index]).tocoo()
        order = np.argsort(-contributions.data, kind="stable")[:12]
        evidence = [{"feature": str(feature_names[contributions.col[j]]), "contribution": float(contributions.data[j])} for j in order]
        results.append({
            "index": index, "input": pool[index].get("input_text", "未命名"),
            "profile": pool[index], "similarity": weight * text_score + (1 - weight) * topic_score,
            "text_similarity": text_score, "topic_similarity": topic_score,
            "text_weight": weight, "evidence": evidence,
            "shared_features": contributions.nnz,
        })
    results.sort(key=lambda result: (-result["similarity"], result["index"]))
    return results[:top_k], {"texts": texts, "documents": len(eligible), "features": len(feature_names), "method": "TF-IDF 字符片段/英文单词 + 主题余弦"}
