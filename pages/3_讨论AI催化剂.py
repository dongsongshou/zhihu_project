import streamlit as st
from utils.config import DEMO_MODE
from openai import OpenAI

st.set_page_config(page_title="3｜AI社交催化剂", layout="wide")
st.title("💬 AI社交破冰 & 讨论策略生成器")

if "matched_list" not in st.session_state:
    st.warning("请先完成匹配！")
    st.stop()

matched = st.session_state["matched_list"]
names = [x["name"] for x in matched]
idx = st.selectbox("选择交流对象", range(len(names)), format_func=lambda x:names[x])
target = matched[idx]
base = st.session_state["current_profile"]

style = st.radio("破冰文案风格", ["学术严谨","轻松友好","极简高效","深度思辨"])

MOCK = {
    "topics":["AI与学习效率","社区理性讨论建设","青年独立思考能力"],
    "lines":["我很认同你的观点，想听听你更多的看法。","这个角度很新颖，能否展开聊聊？"],
    "risk":["避免极端对立话题","避免情绪化评判"]
}

if st.button("✨ 一键生成社交策略"):
    if DEMO_MODE:
        res = MOCK
    else:
        client = OpenAI()
        prompt = f"""
你是知乎社区AI社交助手，根据两个用户的画像，生成{style}风格的破冰话术、推荐话题、避雷提示。
用户A：{base}
用户B：{target}
输出JSON：{{topics:[],lines:[],risk:[]}}
        """
        out = client.chat.completions.create(model="gpt-3.5-turbo",messages=[{"role":"user","content":prompt}],temperature=0.6)
        import json
        res = json.loads(out.choices[0].message.content)

    col1,col2,col3 = st.columns(3)
    with col1:
        st.subheader("✅适配话题")
        for t in res["topics"]: st.success(t)
    with col2:
        st.subheader("🗨️破冰话术")
        for s in res["lines"]: st.code(s)
    with col3:
        st.subheader("⚠️避雷提醒")
        for r in res["risk"]: st.error(r)

st.info("👉 下一步：进入Agent对话仿真，预演真实交流")
