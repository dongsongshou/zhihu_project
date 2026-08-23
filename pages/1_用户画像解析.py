import streamlit as st
import numpy as np
from utils.zhihu_api import get_user_sample_answers
from utils.ai_parser import parse_user_view
from utils.visual_helper import plot_radar

st.set_page_config(page_title="1｜用户画像解析", layout="wide")
st.title("📝 AI深度用户观点画像解析")

tab1, tab2 = st.tabs(["解析基准用户","自定义新增社区用户"])

with tab1:
    user_id_input = st.text_input("知乎用户ID", value="user_001")
    if st.button("🚀 开始AI解析"):
        with st.spinner("AI正在深度拆解用户观点、风格、立场..."):
            answers = get_user_sample_answers(user_id_input)
            profile = parse_user_view(answers)
            st.session_state["current_profile"] = profile

        st.success("✅ 画像解析完成")
        col1,col2 = st.columns(2)
        with col1:
            st.markdown("**📌 关注领域**")
            st.info("｜".join(profile["domains"]))
            st.markdown(f"**🧭 核心立场：** {profile['stance']}")
            st.markdown(f"**✍️ 表达风格：** {profile['style']}")
        with col2:
            st.markdown("**⚠️ 高风险冲突话题**")
            for t in profile["risk_topics"]:
                st.warning(t)

        st.subheader("📊 用户8维观点向量")
        st.code(np.array(profile["embedding"]).round(3))

with tab2:
    st.markdown("自定义用户回答，生成全新观点画像，扩充社区样本")
    name = st.text_input("用户昵称", value="新用户")
    content = st.text_area("用户回答文本", height=180)
    if st.button("➕ 加入社区用户池"):
        texts = [i.strip() for i in content.split("\n") if i.strip()]
        new_p = parse_user_view(texts)
        new_p["name"] = name
        st.session_state["candidate_pool"].append(new_p)
        st.success(f"成功添加 {name}！当前社区总人数：{len(st.session_state['candidate_pool'])}")

if "current_profile" in st.session_state:
    st.info("👉 下一步：进入【同频匹配引擎】进行智能社交匹配")
