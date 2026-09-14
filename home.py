import streamlit as st
from pathlib import Path

st.set_page_config(page_title="知乎同频观点匹配系统", layout="wide")

st.markdown("""
<style>
/* ============================================================
   全局按钮体系：统一知乎蓝色调，用三级视觉权重区分用途
     一级 primary        渐变实心 + 亮蓝描边，关键推进动作
     二级 secondary      浅蓝填充 + 蓝描边，辅助操作
     三级 download/link  白底蓝描边，导出与外链
   ============================================================ */

/* 所有按钮的共同基线 */
.stButton > button,
.stDownloadButton > button,
.stLinkButton > a,
[data-testid="stBaseButton-secondary"],
[data-testid="stBaseButton-primary"] {
    min-height: 2.85rem !important;
    border-radius: 12px !important;
    font-weight: 700 !important;
    letter-spacing: .01em;
    transition: transform .15s ease, box-shadow .15s ease, filter .15s ease, background .15s ease !important;
}

/* ---------- 一级：primary 关键动作 ---------- */
.stButton > button[kind="primary"],
[data-testid="stBaseButton-primary"] {
    background-image: linear-gradient(135deg, #0284c7, #075985) !important;
    background-color: #0284c7 !important;
    color: #ffffff !important;
    border: 2px solid #38bdf8 !important;
    box-shadow: 0 6px 18px rgba(2,132,199,.34) !important;
}
.stButton > button[kind="primary"] p,
[data-testid="stBaseButton-primary"] p {
    color: #ffffff !important;
    font-weight: 800 !important;
}
.stButton > button[kind="primary"]:hover:not(:disabled),
[data-testid="stBaseButton-primary"]:hover:not(:disabled) {
    filter: brightness(1.08);
    transform: translateY(-2px);
    box-shadow: 0 10px 24px rgba(2,132,199,.48) !important;
}

/* ---------- 二级：普通按钮 ---------- */
.stButton > button:not([kind="primary"]),
[data-testid="stBaseButton-secondary"] {
    background: #e0f2fe !important;
    color: #0c4a6e !important;
    border: 1.5px solid #7dd3fc !important;
}
.stButton > button:not([kind="primary"]) p,
[data-testid="stBaseButton-secondary"] p {
    color: #0c4a6e !important;
    font-weight: 700 !important;
}
.stButton > button:not([kind="primary"]):hover:not(:disabled),
[data-testid="stBaseButton-secondary"]:hover:not(:disabled) {
    background: #bae6fd !important;
    border-color: #38bdf8 !important;
    transform: translateY(-1px);
    box-shadow: 0 6px 16px rgba(2,132,199,.24) !important;
}

/* ---------- 三级：下载按钮与外链按钮 ---------- */
.stDownloadButton > button,
.stLinkButton > a {
    background: #ffffff !important;
    color: #075985 !important;
    border: 1.5px solid #7dd3fc !important;
}
.stDownloadButton > button p,
.stLinkButton > a p {
    color: #075985 !important;
    font-weight: 700 !important;
}
.stDownloadButton > button:hover:not(:disabled),
.stLinkButton > a:hover {
    background: #f0f9ff !important;
    border-color: #0284c7 !important;
    transform: translateY(-1px);
    box-shadow: 0 6px 16px rgba(2,132,199,.2) !important;
}

/* ---------- 禁用态：保持可读但明显不可点 ---------- */
.stButton > button:disabled,
.stDownloadButton > button:disabled,
[data-testid="stBaseButton-primary"]:disabled,
[data-testid="stBaseButton-secondary"]:disabled {
    opacity: .42 !important;
    filter: grayscale(.35);
    transform: none !important;
    box-shadow: none !important;
    cursor: not-allowed;
}

/* ---------- 返回首页等页内导航链接 ---------- */
[data-testid="stPageLink-NavLink"] {
    border-radius: 10px;
    transition: background .15s ease;
}

/* 尊重系统减少动画偏好 */
@media (prefers-reduced-motion: reduce) {
    .stButton > button:hover,
    .stDownloadButton > button:hover,
    .stLinkButton > a:hover,
    [data-testid="stBaseButton-primary"]:hover,
    [data-testid="stBaseButton-secondary"]:hover { transform: none !important; }
}

/* 首页主行动按钮。
   通过 st.container(key="hero_cta") 生成的 .st-key-hero_cta 定位，
   不能用裸 <div> 包裹——Markdown 与 page_link 是两个独立元素，
   开标签会被立即闭合，无法形成父子关系。 */
.st-key-hero_cta { margin: 1.5rem 0 .6rem; }

.st-key-hero_cta a,
.st-key-hero_cta a:link,
.st-key-hero_cta a:visited,
.st-key-hero_cta [data-testid="stPageLink-NavLink"],
.st-key-hero_cta [data-testid="stPageLink-NavLink"]:link,
.st-key-hero_cta [data-testid="stPageLink-NavLink"]:visited {
    display: inline-flex !important;
    align-items: center;
    justify-content: center;
    min-height: 3.5rem;
    padding: 0 2.6rem !important;
    border-radius: 14px;
    background-image: linear-gradient(135deg, #0284c7, #075985) !important;
    color: #ffffff !important;
    border: 2px solid #38bdf8 !important;
    box-shadow: 0 8px 22px rgba(2,132,199,.38);
    font-size: 1.12rem !important;
    font-weight: 800 !important;
    text-decoration: none !important;
    transition: transform .15s ease, box-shadow .15s ease, filter .15s ease;
    animation: heroPulse 2.6s ease-in-out infinite;
}

/* page_link 内部的文字与图标节点默认继承灰色，需一并覆盖 */
.st-key-hero_cta [data-testid="stPageLink-NavLink"] p,
.st-key-hero_cta [data-testid="stPageLink-NavLink"] span,
.st-key-hero_cta [data-testid="stPageLink-NavLink"] div {
    color: #ffffff !important;
    font-weight: 800 !important;
    font-size: 1.12rem !important;
    margin: 0 !important;
}

.st-key-hero_cta a:hover,
.st-key-hero_cta [data-testid="stPageLink-NavLink"]:hover,
.st-key-hero_cta [data-testid="stPageLink-NavLink"]:focus {
    filter: brightness(1.08);
    transform: translateY(-2px) scale(1.015);
    box-shadow: 0 12px 28px rgba(2,132,199,.55);
    animation: none;
}

/* 呼吸式光圈，引导用户注意主入口 */
@keyframes heroPulse {
    0%, 100% { box-shadow: 0 8px 22px rgba(2,132,199,.38), 0 0 0 0 rgba(56,189,248,.55); }
    50%      { box-shadow: 0 8px 22px rgba(2,132,199,.45), 0 0 0 10px rgba(56,189,248,0); }
}

/* 遵循系统的减少动画偏好 */
@media (prefers-reduced-motion: reduce) {
    .st-key-hero_cta a,
    .st-key-hero_cta [data-testid="stPageLink-NavLink"] { animation: none !important; }
    .st-key-hero_cta a:hover,
    .st-key-hero_cta [data-testid="stPageLink-NavLink"]:hover { transform: none; }
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
    # 用带 key 的容器包裹，使 CSS 能通过 .st-key-hero_cta 命中内部的 page_link。
    with st.container(key="hero_cta"):
        st.page_link(explore_page, label="开始 / 继续话题探索", icon="🚀")
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


