import streamlit as st
from pathlib import Path

st.set_page_config(page_title="知乎同频观点匹配系统", layout="wide")

st.markdown("""
<style>
/* 统一强化操作按钮，主按钮与普通按钮有明显层级。 */
.stButton > button, .stDownloadButton > button, .stPageLink > a {
    min-height: 2.7rem;
    border-radius: 10px;
    font-weight: 700;
    border: 1px solid #155e75;
    transition: transform .15s ease, box-shadow .15s ease, background .15s ease;
}
.stButton > button[kind="primary"] {
    background: #075985;
    color: #fff;
    border-color: #05445e;
    box-shadow: 0 4px 12px rgba(7,89,133,.28);
}
.stButton > button[kind="primary"]:hover {
    background: #064e70;
    transform: translateY(-1px);
    box-shadow: 0 6px 16px rgba(7,89,133,.36);
}
.stButton > button:not([kind="primary"]), .stDownloadButton > button {
    background: #e0f2fe;
    color: #0c4a6e;
}
.stButton > button:not([kind="primary"]):hover, .stDownloadButton > button:hover {
    background: #bae6fd;
}
.stButton > button:disabled { opacity: .45; }
.hero-cta { margin: 1.4rem 0; }
.hero-cta a, .hero-cta a:link, .hero-cta a:visited,
.hero-cta [data-testid="stPageLink-NavLink"],
.hero-cta [data-testid="stPageLink-NavLink"]:link,
.hero-cta [data-testid="stPageLink-NavLink"]:visited {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-height: 3.4rem;
    padding: 0 2rem;
    border-radius: 14px;
        background: #7c2d12 !important;
        color: #ffffff !important;
        background-image: linear-gradient(135deg, #9a3412, #7c2d12) !important;
    border: 2px solid #fbbf24 !important;
    box-shadow: 0 8px 20px rgba(245,158,11,.35);
    font-size: 1.08rem;
    font-weight: 800;
    text-decoration: none !important;
    transition: transform .15s ease, box-shadow .15s ease, background .15s ease;
}
.hero-cta a:hover, .hero-cta a:focus,
.hero-cta [data-testid="stPageLink-NavLink"]:hover,
.hero-cta [data-testid="stPageLink-NavLink"]:focus {
    background: #92400e !important;
    transform: translateY(-2px) scale(1.01);
    box-shadow: 0 11px 26px rgba(124,45,18,.55);
}
</style>
""", unsafe_allow_html=True)


from utils.exploration_ui import render


def landing():
    st.title("一个热点，不止一种声音")
    st.markdown("### 让看山带你读懂讨论")
    st.write("选择一个话题，从多角度搜集真实内容，核对原文，发现内容之间的关联，并带走一份可追溯的探索报告。")
    hero_image = Path(__file__).parent / "assets" / "zhihu.png"
    if hero_image.is_file():
        st.image(str(hero_image), use_container_width=True)
    st.markdown("**选择话题 → 收集内容 → 快速阅读 → 探索关系 → 发现作者 → 筹备讨论 → 导出报告**")
    st.markdown('<div class="hero-cta">', unsafe_allow_html=True)
    st.page_link(explore_page, label="开始 / 继续话题探索")
    st.markdown('</div>', unsafe_allow_html=True)
    st.caption("支持知乎热榜和自定义话题。返回上一步保留数据，不重复调用接口。")
    with st.expander("算法与使用边界"):
        st.markdown("""
系统从一条你喜欢的知乎内容出发，在同一话题候选池中进行双层匹配：先使用 **TF-IDF 与余弦相似度** 识别词法关联，再可选调用 **知乎直答大模型** 对内容的核心议题、共同兴趣和主要差异进行语义判断。最终结果可按“大模型语义判断 + TF-IDF 证据”的综合分排序；关闭大模型时使用 TF-IDF 排序。

匹配结果会进一步生成“内容作者候选卡”，包含作者昵称、原文入口、内容相关分、推荐理由和建议开场问题，帮助用户从“发现内容”走向“发现值得交流的作者”。

**重要边界：**
- TF-IDF 反映共同文本特征；大模型反映内容语义相关性，二者都不等于用户立场一致或人与人的匹配成功率；
- 作者昵称来自搜索结果，不等于身份认证，也不代表取得该作者的全部创作；
- 作者候选卡对应公开内容，不按昵称自动合并用户；
- 邀请、关注、私信和建群均需用户自行核对并完成，系统不会代发；
- 大模型语义判断为可选能力，会消耗知乎直答额度；接口不可用或返回格式异常时，失败对象会被跳过，不伪造语义分；
- 当前主流程暂未接入热点内容自动聚类，聚类不作为已完成能力宣传。
        """)


home_page = st.Page(landing, title="首页", default=True)
explore_page = st.Page(render, title="话题探索", url_path="explore")
st.session_state["home_page_object"] = home_page
navigation = st.navigation(
    [home_page, explore_page],
    position="hidden",
)
navigation.run()


