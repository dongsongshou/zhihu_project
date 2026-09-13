"""
知乎 Search‑MCP API
文档：https://developer.zhihu.com/docs?key=zhihu_search_mcp
用于输入知乎用户主页URL，抓取该用户公开回答、文章文本
"""
import requests
import re
import streamlit as st
from .config import ZHIHU_MCP_API_KEY, ZHIHU_MCP_ENDPOINT, MCP_AVAILABLE

def extract_user_token_from_url(user_url: str) -> str | None:
    """
    从知乎用户主页url提取用户token
    e.g. https://www.zhihu.com/people/abc123xyz → abc123xyz
    """
    pattern = r"people/([^/?#]+)"
    match = re.search(pattern, user_url)
    if match:
        return match.group(1)
    return None

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_user_public_contents(user_profile_url: str, max_items: int = 8) -> list[str]:
    """
    调用知乎Search‑MCP，获取用户公开回答/文章文本片段
    :param user_profile_url: 知乎用户主页链接
    :param max_items: 返回最多几条内容
    :return: list文本，失败返回空列表
    """
    if not MCP_AVAILABLE:
        st.info("未配置ZHIHU_MCP_API_KEY，跳过MCP真实数据拉取")
        return []

    user_token = extract_user_token_from_url(user_profile_url.strip())
    if not user_token:
        st.warning("无法解析知乎用户链接，请输入类似：https://www.zhihu.com/people/xxxx 的主页地址")
        return []

    headers = {
        "Authorization": f"Bearer {ZHIHU_MCP_API_KEY}",
        "Content‑Type": "application/json"
    }

    payload = {
        "query": "",
        "filter": {
            "author_token": user_token
        },
        "page_size": max_items
    }

    try:
        resp = requests.post(
            ZHIHU_MCP_ENDPOINT,
            json=payload,
            headers=headers,
            timeout=25
        )
        resp.raise_for_status()
        json_data = resp.json()
        items = json_data.get("data", [])
        text_list = []
        for item in items:
            content = item.get("content", "").strip()
            if content:
                text_list.append(content)
        return text_list[:max_items]

    except requests.exceptions.RequestException as e:
        st.warning(f"知乎MCP接口调用异常: {str(e)}，将使用模拟数据")
        return []
