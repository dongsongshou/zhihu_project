import numpy as np


def parse_user_profile(text_list):
    """
    根据用户文本列表，生成用户观点画像（模拟AI解析）
    :param text_list: 文本摘要列表（知乎API返回或者mock文本）
    :return: dict 用户画像，包含 domains、stance、style、risk_topics、embedding
    """
    # 模拟解析逻辑；参赛demo版本，真实项目这里替换成大模型调用
    domains = ["高等教育", "人工智能", "网络社区文化"]
    stance = "偏向理性中立，重视思辨与实践价值"
    style = "理性说理，注重逻辑，语言克制"
    risk_topics = ["极端立场争论", "情绪化站队话题"]
    embedding = np.array([0.12, 0.21, -0.05, 0.33, 0.41, -0.22, 0.18, 0.09])

    profile = {
        "domains": domains,
        "stance": stance,
        "style": style,
        "risk_topics": risk_topics,
        "embedding": embedding
    }
    return profile
