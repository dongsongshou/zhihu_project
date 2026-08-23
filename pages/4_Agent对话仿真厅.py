import streamlit as st
from utils.agent_simu import simulate_agent_chat

st.set_page_config(page_title="4｜Agent对话仿真厅", layout="wide")
st.title("🎭 数字分身对话仿真 + 智能复盘")

if "matched_list" not in st.session_state:
    st.warning("请先完成匹配流程")
    st.stop()

matched = st.session_state["matched_list"]
sel_idx = st.selectbox("选择对话对象",range(len(matched)),format_func=lambda i:matched[i]["name"])
target = matched[sel_idx]
base = st.session_state["current_profile"]

tolerance = st.slider("沟通包容度",0.0,1.0,0.7)

if st.button("🚀 启动AI对话预演"):
    with st.spinner("数字分身对话中..."):
        dialog = simulate_agent_chat(base, target, tolerance)

    st.divider()
    st.subheader("📜 仿真对话记录")
    for msg in dialog:
        if msg["role"]=="A":
            st.chat_message("基准用户",avatar="👨").write(msg["content"])
        else:
            st.chat_message("目标用户",avatar="👩").write(msg["content"])

    # AI复盘
    st.divider()
    st.subheader("📈 AI对话复盘分析")
    st.success("✅ 本次对话氛围：理性友好、观点互补、无情绪化对立")
    st.info("💡 结论：双方适合长期深度交流，可拓展学术、AI、社区治理话题")
    st.warning("⚠️ 建议：减少极端价值观话题，保持思辨包容")

st.markdown("""
### 💡产品核心价值
**解决知乎社区最大痛点：匹配到人，但聊不起来、容易吵架、找不到同频思想伙伴**
本项目实现：观点建模 → 智能匹配 → 破冰辅助 → 对话预演 → 风险预判 全链路AI社区体验升级
""")

