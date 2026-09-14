import pandas as pd
import streamlit as st

from utils.zhida_rank import rank_search_results, rank_by_query

st.set_page_config(page_title="语义打分排序", layout="wide")

st.title("语义打分排序")
st.caption("以知乎直答大模型对搜索结果与基准内容做语义评分，区分议题相关性与立场一致性")

# ---------------- 基准内容 ----------------
st.subheader("1. 基准内容")

pool = st.session_state.get("user_candidate_pool", [])
base_source = st.radio(
    "基准来源",
    ["手动输入", "从候选池选择"],
    horizontal=True,
    disabled=not pool,
)

if base_source == "从候选池选择" and pool:
    options = [f"{i + 1}. {p.get('input_text', '未命名')}" for i, p in enumerate(pool)]
    picked = st.selectbox("选择基准对象", range(len(pool)), format_func=lambda i: options[i])
    base_content = st.text_area(
        "基准内容（可编辑）",
        value=str(pool[picked].get("search_content", "")),
        height=160,
    )
else:
    base_content = st.text_area(
        "输入基准内容",
        placeholder="粘贴一段代表你立场的内容，系统将据此对搜索结果打分排序。",
        height=160,
    )

# ---------------- 候选来源 ----------------
st.subheader("2. 候选内容来源")

mode = st.radio("来源方式", ["实时搜索知乎", "使用已有搜索结果"], horizontal=True)

query = ""
count = 10
if mode == "实时搜索知乎":
    col_q, col_c = st.columns([3, 1])
    query = col_q.text_input("检索关键词", placeholder="例如：第一学历 学历歧视 招聘")
    count = col_c.number_input("检索条数", 1, 10, 10)
else:
    cached = st.session_state.get("last_search_items", [])
    if cached:
        st.success(f"已缓存 {len(cached)} 条搜索结果")
    else:
        st.info("暂无缓存结果，请先在其他页面执行搜索，或改用实时搜索。")

# ---------------- 评分参数 ----------------
st.subheader("3. 评分参数")

col_a, col_b, col_c = st.columns(3)
relevance_weight = col_a.slider("议题相关性权重", 0.0, 1.0, 0.6, 0.05)
model = col_b.selectbox(
    "直答模型",
    ["zhida-fast-1p5", "zhida-thinking-1p5", "zhida-agent"],
    help="批量打分推荐 fast，需要更强推理时用 thinking。",
)
batch_size = col_c.slider("每次请求评分条数", 1, 10, 5, help="越大越省额度，过大可能降低稳定性。")

st.caption(
    f"综合分 = 议题相关性 × {relevance_weight:.2f} + 立场一致性 × {1 - relevance_weight:.2f}。"
    " 议题相关性衡量是否讨论同一件事，立场一致性衡量观点方向是否相同；两者独立评估。"
)

st.divider()

# ---------------- 执行 ----------------
if st.button("开始打分排序", type="primary"):
    if not base_content.strip():
        st.error("请先填写基准内容")
        st.stop()

    progress = st.progress(0.0, text="正在调用知乎直答…")

    def on_progress(done, total):
        progress.progress(done / total, text=f"已完成 {done}/{total} 批")

    try:
        with st.spinner("模型评分中…"):
            if mode == "实时搜索知乎":
                if not query.strip():
                    st.error("请填写检索关键词")
                    st.stop()
                result = rank_by_query(
                    base_content, query, count=int(count),
                    relevance_weight=relevance_weight, model=model,
                    batch_size=int(batch_size), progress_callback=on_progress,
                )
                st.session_state["last_search_items"] = [r["raw"] for r in result["ranked"]]
            else:
                items = st.session_state.get("last_search_items", [])
                if not items:
                    st.error("没有可用的缓存搜索结果")
                    st.stop()
                result = rank_search_results(
                    base_content, items,
                    relevance_weight=relevance_weight, model=model,
                    batch_size=int(batch_size), progress_callback=on_progress,
                )
        progress.empty()
        st.session_state["rank_result"] = result
    except ValueError as exc:
        progress.empty()
        st.warning(str(exc))
        st.stop()
    except Exception as exc:
        progress.empty()
        st.error(f"调用失败：{type(exc).__name__}: {exc}")
        st.stop()

# ---------------- 结果展示 ----------------
result = st.session_state.get("rank_result")
if not result:
    st.stop()

stats = result["stats"]
ranked = result["ranked"]

cols = st.columns(4)
cols[0].metric("候选总数", stats["total_items"])
cols[1].metric("成功评分", stats["scored"])
cols[2].metric("直答调用", f"{stats['api_calls']} 次")
cols[3].metric("耗时", f"{stats['elapsed']}s")
st.caption(
    f"评分方式：{stats['method']}。分批打分可显著节省额度——"
    f"{stats['total_items']} 条内容仅消耗 {stats['api_calls']} 次调用。"
)

if not ranked:
    st.warning("没有任何候选获得有效评分")
    st.stop()

st.subheader("排序结果")

frame = pd.DataFrame([
    {
        "排名": r["rank"],
        "标题": r["title"][:40],
        "议题贡献": round(r["relevance"] * relevance_weight, 4),
        "立场贡献": round(r["stance"] * (1 - relevance_weight), 4),
        "综合分": r["score"],
    }
    for r in ranked
]).set_index("标题")

st.bar_chart(frame[["议题贡献", "立场贡献"]])
st.dataframe(frame, use_container_width=True)

st.subheader("议题 × 立场分布")
scatter = pd.DataFrame([
    {"议题相关性": r["relevance"], "立场一致性": r["stance"], "标题": r["title"][:24]}
    for r in ranked
])
st.scatter_chart(scatter, x="议题相关性", y="立场一致性")
st.caption(
    "右上角为同议题同立场（真正的同频），右下角为同议题但立场对立（适合做观点碰撞），"
    "左侧为议题无关。TF-IDF 无法区分右上与右下，这正是语义评分的价值。"
)

st.subheader("逐条评分依据")
for r in ranked:
    with st.expander(
        f"#{r['rank']}　综合 {r['score']:.3f}　|　议题 {r['relevance']:.2f}　立场 {r['stance']:.2f}　|　{r['title'][:44]}"
    ):
        if r["url"]:
            st.markdown(f"[查看原文]({r['url']})")
        if r["author"]:
            st.caption(f"作者：{r['author']}")
        st.write(f"**判断依据**：{r['reason']}")
        left, right = st.columns(2)
        left.write("**共同论点**")
        left.write("\n".join(f"- {s}" for s in r["shared"]) if r["shared"] else "_无_")
        right.write("**分歧点**")
        right.write("\n".join(f"- {d}" for d in r["diff"]) if r["diff"] else "_无_")

if result["failed"]:
    with st.expander(f"未能评分的 {len(result['failed'])} 条"):
        for f in result["failed"]:
            st.write(f"- {f['title'][:50]} — {f['error']}")

export = pd.DataFrame([
    {
        "排名": r["rank"], "标题": r["title"], "作者": r["author"], "链接": r["url"],
        "综合分": r["score"], "议题相关性": r["relevance"], "立场一致性": r["stance"],
        "共同论点": "；".join(r["shared"]), "分歧点": "；".join(r["diff"]), "依据": r["reason"],
    }
    for r in ranked
])
st.download_button(
    "下载评分结果 CSV",
    export.to_csv(index=False).encode("utf-8-sig"),
    "semantic_ranking.csv",
    "text/csv",
)
