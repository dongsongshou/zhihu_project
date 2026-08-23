import streamlit as st
import pandas as pd
from utils.match_engine import match_candidates
from utils.visual_helper import plot_radar

st.set_page_config(page_title="2｜同频匹配引擎", layout="wide")
st.title("🔍 AI多策略智能匹配引擎")

if "current_profile" not in st.session_state:
    st.warning("请先解析用户画像")
    st.stop()

base = st.session_state["current_profile"]
pool = st.session_state["candidate_pool"]

mode_map = {
    "✨灵魂同频（高共识）":"syntropy",
    "🔍互补视角（最适合学习）":"complement",
    "⚡观点碰撞（打破信息茧房）":"collision"
}

sel_mode = st.selectbox("选择匹配策略", list(mode_map.keys()))
if st.button("🚀 开始智能匹配"):
    with st.spinner("向量计算、共识度分析、冲突度分析中..."):
        res = match_candidates(base, pool, mode_map[sel_mode])
        st.session_state["matched_list"] = res

if "matched_list" in st.session_state:
    df = pd.DataFrame(res)[["name","similarity","consensus","conflict","weight_score","reason"]]
    st.subheader("📋 智能匹配结果榜单")
    st.dataframe(df, use_container_width=True)

    sel_name = st.selectbox("选择用户进行观点对比", [i["name"] for i in res])
    target = next(i for i in res if i["name"]==sel_name)

    st.divider()
    col1,col2 = st.columns([1,1])
    with col1:
        st.success(f"匹配得分：{target['weight_score']}")
        st.info(f"双方共识度：{target['consensus']}%")
        st.warning(f"双方冲突度：{target['conflict']}%")
        st.markdown("匹配解读："+target["reason"])
    with col2:
        plot_radar(base["embedding"], target["embedding"], "基准用户", sel_name)

    st.info("👉 下一步：AI自动生成社交话术")
