import streamlit as st
from utils.config import DEMO_MODE
from utils.visual_helper import build_network_html, render_pyvis_html, plot_cluster_dist, plot_heatmap
from utils.match_engine import cluster_users

st.set_page_config(page_title="知同频｜AI灵魂匹配", layout="wide")

# 初始化会话
if "candidate_pool" not in st.session_state:
    from utils.ai_parser import MOCK_PARSE_RESULT
    st.session_state["candidate_pool"] = [
        {**MOCK_PARSE_RESULT,"name":"用户A","embedding":[0.11,0.23,-0.04,0.31,0.44,-0.20,0.17,0.10]},
        {**MOCK_PARSE_RESULT,"name":"用户B","embedding":[0.60,-0.30,0.55,-0.22,0.10,0.11,-0.40,0.20]},
        {**MOCK_PARSE_RESULT,"name":"用户C","embedding":[0.20,0.10,0.15,0.05,-0.10,0.30,0.22,-0.31]},
        {**MOCK_PARSE_RESULT,"name":"用户D","embedding":[0.33,0.41,0.22,0.10,-0.20,0.17,0.05,0.31]},
        {**MOCK_PARSE_RESULT,"name":"用户E","embedding":[-0.11,-0.23,0.44,0.30,0.20,0.10,-0.17,0.22]}
    ]

# 侧边栏
with st.sidebar:
    st.header("⚙️ 系统状态")
    st.success("🎮 演示模式运行中" if DEMO_MODE else "🔑 真实API模式")
    if st.button("🔄 重置所有数据"):
        st.session_state.clear()
        st.rerun()
    st.divider()
    st.metric("社区用户总数", len(st.session_state["candidate_pool"]))

# 首页标题
st.title("🧠 知同频｜AI观点社区匹配系统")
st.subheader("知乎黑客松 2026｜灵魂匹配局 高阶创新版")
st.markdown("""
### 🔥 项目高阶创新点（比赛高分核心）
1. **8维用户观点向量建模**（不止标签，深度人格建模）
2. **KMeans社区用户聚类**，自动划分社交圈层
3. **共识度/冲突度双维度计算**
4. **三策略智能匹配**：同频共鸣 / 互补学习 / 破茧碰撞
5. **AI社交破冰多风格文案**
6. **Agent数字分身对话仿真 + 情绪复盘**
7. **完整社区社交网络图谱+热力图分析**
""")
st.divider()

# 社区大盘分析
st.subheader("🌐 社区全局智能分析大盘")
user_clustered, centers = cluster_users(st.session_state["candidate_pool"])
st.session_state["candidate_pool"] = user_clustered

col1, col2 = st.columns(2)
with col1:
    plot_cluster_dist(user_clustered)
with col2:
    plot_heatmap(user_clustered)

st.subheader("🕸️ 社区用户动态关系网络图")
net_html = build_network_html(user_clustered)
render_pyvis_html(net_html)

st.info("👈 左侧页面依次体验：画像解析 → 智能匹配 → AI破冰 → 对话仿真")
