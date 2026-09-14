import streamlit as st
from pathlib import Path

from utils.exploration_ui import render


st.set_page_config(page_title="知乎同频观点匹配系统", layout="wide")

def landing():
    st.title("一个热点，不止一种声音")
    st.markdown("### 让看山带你读懂讨论")
    st.write("选择一个话题，从多角度搜集真实内容，核对原文，发现内容之间的关联，并带走一份可追溯的探索报告。")
    hero_image = Path(__file__).parent / "assets" / "zhihu.png"
    if hero_image.is_file():
        st.image(str(hero_image), use_container_width=True)
    st.markdown("**选择话题 → 收集内容 → 快速阅读 → 探索关系 → 导出报告**")
    st.page_link(explore_page, label="开始 / 继续话题探索")
    st.caption("支持知乎热榜和自定义话题。返回上一步保留数据，不重复调用接口。")
    with st.expander("算法与使用边界"):
        st.write("正文采用 TF-IDF 与余弦相似度，展示共同文本片段及得分贡献。相似度不等于立场一致，作者昵称不等于身份验证。热点内容自动聚类尚未接入本流程。")


explore_page = st.Page(render, title="话题探索", url_path="explore")
navigation = st.navigation([st.Page(landing, title="首页", default=True), explore_page])
navigation.run()


