import requests
import streamlit as st
from .config import ZHIHU_AGENT_API_KEY, ZHIHU_AGENT_BASE_URL, DEMO_MODE

HEADERS = {"Authorization": f"Bearer {ZHIHU_AGENT_API_KEY}"}

@st.cache_data(ttl=3600)
def get_user_sample_answers(user_id: str):
    """模拟获取用户公开回答；真实环境替换为知乎开放API"""
    if DEMO_MODE:
        mock_answers = [
            "我认为大学学习重点在于构建知识框架，而不是死记硬背知识点。实践项目比卷面分数更能锻炼工程能力。",
            "AI工具可以极大提升效率，但不能替代人的思辨，独立思考依然非常关键。",
            "互联网社区应当鼓励理性讨论，对立观点也值得被尊重。"
        ]
        return mock_answers
    # ==========真实接入知乎搜索/用户回答API在这里扩展==========
    resp = requests.get(f"{ZHIHU_AGENT_BASE_URL}/xxx", headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return [item["content"] for item in resp.json().get("data", [])]
