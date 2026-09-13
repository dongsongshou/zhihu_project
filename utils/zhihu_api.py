import streamlit as st
from .zhihu_openapi import fetch_user_content_by_search
from .config import ZHIHU_OPENAPI_AVAILABLE

# ❗删掉这里的 @st.cache_data，不要缓存这个函数！
def get_user_sample_answers(user_input: str):
    """
    用户输入知乎用户主页URL
    优先调用知乎开放zhihu_search API获取公开内容摘要
    未配置密钥 / API无结果 / 网络异常，会明确提示并回退模拟样例
    :param user_input: 用户主页url
    :return: 文本摘要列表
    """
    mock_answers = [
        "我认为大学学习重点在于构建知识框架，而不是死记硬背知识点。实践项目比卷面分数更能锻炼工程能力。",
        "AI工具可以极大提升效率，但不能替代人的思辨，独立思考依然非常关键。",
        "互联网社区应当鼓励理性讨论，对立观点也值得被尊重。"
    ]

    if ZHIHU_OPENAPI_AVAILABLE:
        # 调用带缓存的API请求函数
        real_texts = fetch_user_content_by_search(user_input)
        if real_texts:
            st.success(f"✅ 知乎开放API获取 {len(real_texts)} 条内容摘要")
            return real_texts
        else:
            st.warning("⚠️ API未搜索到该用户公开内容，回退模拟样例数据")
            return mock_answers
    else:
        st.warning("⚠️ ZHIHU_ACCESS_SECRET未配置，回退模拟样例数据")
        return mock_answers
