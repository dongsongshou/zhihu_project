import streamlit as st
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from utils.zhihu_openapi import generate_profile

st.set_page_config(page_title="用户画像构建", layout="wide")

if "user_candidate_pool" not in st.session_state:
    st.session_state["user_candidate_pool"] = []

st.title("用户画像构建")
st.caption("输入关键词，生成 8 维用户观点画像并加入候选池")

user_input = st.text_input("输入知乎链接或搜索关键词", value="人工智能")

if st.button("生成用户画像"):
    with st.spinner("正在请求知乎搜索并生成观点画像..."):
        # 防御：如果 generate_profile 返回 None，不写入 session_state
        result = generate_profile(user_input)
        if result is not None:
            st.session_state["current_profile"] = result
        else:
            st.error("画像生成失败，请检查网络或 API 配置")
            # 如果之前存过脏数据，建议清理掉
            if "current_profile" in st.session_state:
                del st.session_state["current_profile"]

    # 只有成功生成后才显示结果
    if "current_profile" in st.session_state:
        prof = st.session_state["current_profile"]
        if prof["is_real_search"]:
            st.success("用户画像生成完成，已调用知乎真实搜索接口")
        else:
            st.warning("未调用知乎真实搜索，当前使用模拟向量演示")

# ===== 修复处：同时判断键存在且值不为 None =====
if "current_profile" in st.session_state and st.session_state["current_profile"] is not None:
    prof = st.session_state["current_profile"]
    st.subheader("用户观点画像结果")
    st.write(f"原始输入：{prof['input_text']}")
    st.write(f"8维原始向量：{prof['embedding']}")

    st.markdown("**观点维度得分（0-100）**")
    for name, score in prof["viewpoint_scores"]:
        st.markdown(f"- **{name}**：{score} 分")

    with st.expander("查看知乎搜索返回摘要文本"):
        st.text(prof["search_content"])

    st.divider()
    st.info(f"当前候选池用户总数：{len(st.session_state['user_candidate_pool'])}")
    if st.button("将当前用户加入候选池"):
        exist = any(p["input_text"] == prof["input_text"] for p in st.session_state["user_candidate_pool"])
        if not exist:
            st.session_state["user_candidate_pool"].append(prof)
            st.success(f"已加入候选池，当前总数：{len(st.session_state['user_candidate_pool'])}")
        else:
            st.warning("该用户已存在于候选池")

if len(st.session_state["user_candidate_pool"]) > 0:
    if st.button("清空候选池"):
        st.session_state["user_candidate_pool"] = []
        st.warning("候选池已清空")