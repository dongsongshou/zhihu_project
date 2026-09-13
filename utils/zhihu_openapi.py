"""
知乎开放平台 v1 zhihu_search API
文档：https://developer.zhihu.com/api/v1/content/zhihu_search
鉴权：Authorization: Bearer {ACCESS_SECRET}
Header: X‑Request‑Timestamp: 秒级Unix时间戳
"""
import re
import requests
import numpy as np
import time
from urllib.parse import urlencode

ZHIHU_ACCESS_SECRET = "be85c5ce20f6a9dc1642d180cf08496420727e20"

VIEWPOINT_SEEDS = {
    "科技发展乐观": [
        "科技", "技术", "人工智能", "ai", "算法", "模型", "创新", "智能", "自动化",
        "研究", "工程", "效率", "数字", "数据", "发展"
    ],
    "关注社会公平": [
        "公平", "平等", "社会", "弱势", "福利", "贫富", "justice", "机会", "公正",
        "分配", "权益", "制度", "群体", "利益"
    ],
    "文化包容倾向": [
        "文化", "多元", "包容", "开放", "认同", "包容性", "多样", "交流", "传统",
        "价值观", "异同", "共存", "理解"
    ],
    "风险审慎态度": [
        "风险", "安全", "审慎", "监管", "稳定", "合规", "责任", "谨慎", "预防",
        "治理", "法治", "隐私", "可靠", "控制"
    ],
    "个人主义‑集体主义": [
        "个人", "自我", "独立", "自由", "成长", "团队", "集体", "合作", "社区",
        "协作", "组织", "共同", "群体" 
    ],
    "现实务实": [
        "现实", "务实", "实践", "落地", "经验", "成本", "效率", "结果", "执行",
        "商业", "现实问题", "可行", "投入"
    ],
    "创新接纳度": [
        "创新", "改革", "转型", "实验", "突破", "接受", "新事物", "前沿", "探索",
        "迭代", "发明", "尝试", "创意"
    ],
    "公共事务参与意愿": [
        "公共", "公益", "参与", "治理", "社会", "社区", "公共事务", "民生", "政策",
        "事务", "行动", "共建", "协同", "反馈"
    ],
}

VIEWPOINT_NAMES = list(VIEWPOINT_SEEDS.keys())

def zhihu_search(keyword: str, count=5):
    """
    调用知乎搜索接口
    :param keyword: 查询关键词
    :param count: [1‑10]
    :return (is_real: bool, content: str)
        is_real: True=成功调用接口拿到结果
        content: 拼接后的标题+摘要文本
    """
    if not ZHIHU_ACCESS_SECRET or ZHIHU_ACCESS_SECRET.strip() == "":
        return False, ""

    ts = int(time.time())
    headers = {
        "Authorization": f"Bearer {ZHIHU_ACCESS_SECRET}",
        "X-Request-Timestamp": str(ts),
        "Content-Type": "application/json"
    }
    count = min(count, 10)
    query_param = urlencode({"Query": keyword, "Count": count})
    url = f"https://developer.zhihu.com/api/v1/content/zhihu_search?{query_param}"

    try:
        resp = requests.get(url, headers=headers, timeout=12)
        resp_json = resp.json()
        code = resp_json.get("Code", -1)
        if code != 0:
            return False, ""
        data = resp_json.get("Data", {})
        items = data.get("Items", [])
        if len(items) == 0:
            return False, ""
        texts = []
        for item in items:
            title = item.get("Title", "")
            content_text = item.get("ContentText", "")
            texts.append(f"{title}\n{content_text}")
        full_text = "\n".join(texts)
        return True, full_text
    except Exception:
        return False, ""


def _tokenize_text(text: str, chinese_ngram_sizes=(2, 3, 4)):
    """中英文混合分词：中文保留完整短语并生成 2/3/4-gram。"""
    if not text:
        return []
    text = text.lower().replace("-", " ")
    tokens = []
    for segment in re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]+", text):
        if re.fullmatch(r"[\u4e00-\u9fff]+", segment):
            tokens.append(segment)
            for size in chinese_ngram_sizes:
                tokens.extend(segment[i:i + size] for i in range(max(0, len(segment) - size + 1)))
        else:
            tokens.append(segment)
    return tokens


def _seed_matches(seed: str, text: str) -> bool:
    """中文按原词/中文 n-gram 命中，英文按完整 token 命中。"""
    seed = str(seed).lower().strip()
    if not seed or not text:
        return False
    if re.search(r"[\u4e00-\u9fff]", seed):
        return seed in text or seed in _tokenize_text(text)
    return seed in set(_tokenize_text(text))



def build_semantic_embedding(text: str, dim: int = 8):
    """基于主题关键词的语义向量：用真实文本得到稳定的 8 维观点特征向量。"""
    if not text or not isinstance(text, str):
        return np.zeros(dim, dtype=float)

    text_norm = " ".join(_tokenize_text(text))
    if not text_norm:
        return np.zeros(dim, dtype=float)

    raw_scores = []
    for topic_name in VIEWPOINT_NAMES:
        seeds = VIEWPOINT_SEEDS[topic_name]
        score = 0.0
        for seed in seeds:
            # 每个主题词只计一次，避免原词和 token 命中重复加分。
            if _seed_matches(seed, text):
                score += 1.0

        raw_scores.append(score)

    raw_scores = np.array(raw_scores, dtype=float)
    if raw_scores.sum() == 0:
        # 无命中主题时返回纯空向量，避免无关文本被误判为“高度相似”
        return np.zeros(dim, dtype=float)

    norm = np.linalg.norm(raw_scores)
    if norm > 0:
        vec = raw_scores / norm
    else:
        vec = np.zeros(dim, dtype=float)
    return vec


def build_mock_embedding(text: str):
    """兼容旧逻辑的退化入口，仍保留为兜底实现。"""
    return build_semantic_embedding(text)


def generate_profile(input_text: str):
    is_real_search, search_content = zhihu_search(input_text)
    if is_real_search:
        use_text = search_content
        vec = build_semantic_embedding(search_content)
    else:
        use_text = input_text
        vec = build_semantic_embedding(input_text)

    # 用主题权重转成 0-100 的分数，且保证同一用户的 8 维议题占比可解释。
    token_text = " ".join(_tokenize_text(use_text)).lower()
    raw_scores = np.array([
        sum(1.0 for seed in VIEWPOINT_SEEDS[name] if seed.lower() in token_text)
        for name in VIEWPOINT_NAMES
    ], dtype=float)
    if raw_scores.sum() == 0:
        raw_scores = np.zeros(len(VIEWPOINT_NAMES), dtype=float)

    total = raw_scores.sum()
    scores = np.zeros(len(VIEWPOINT_NAMES), dtype=float)
    if total > 0:
        scores = (raw_scores / total * 100).round(2)
    else:
        scores = np.zeros(len(VIEWPOINT_NAMES), dtype=float)
    viewpoint_scores = list(zip(VIEWPOINT_NAMES, scores))

    profile = {
        "input_text": input_text,
        "search_content": use_text,
        "embedding": vec,
        "is_real_search": is_real_search,
        "viewpoint_scores": viewpoint_scores,
        "viewpoint_names": VIEWPOINT_NAMES
    }
    return profile

