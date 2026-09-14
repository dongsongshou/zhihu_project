"""热点锚点工作流：热点 → 多角度检索 → 候选池 → 池内匹配。"""
import os
import streamlit as st
import re
import pandas as pd
import numpy as np
from sklearn.cluster import KMeans

from zhihu_client import ZhihuClient, ZhihuAPIError
from utils.content_match import match_content
from utils.zhihu_openapi import build_semantic_embedding, VIEWPOINT_NAMES

ANGLE_RULES = {
    "背景与事实": ["背景", "原因", "事实", "数据", "历史", "现状"],
    "支持观点": ["支持", "认可", "看好", "优势", "价值", "有效"],
    "质疑与风险": ["风险", "问题", "质疑", "争议", "缺点", "局限", "担忧"],
    "实践经验": ["体验", "经验", "使用", "实践", "案例", "落地"],
    "行业影响": ["行业", "职业", "就业", "商业", "市场", "产业"],
    "普通人体验": ["个人", "生活", "普通人", "日常", "感受", "怎么办"],
}


def classify_content(title, text, requested_angle):
    """对检索结果做轻量可解释二次分类；这是内容标签，不是立场判断。"""
    corpus = f"{title} {text}".lower()
    scores = {angle: sum(1 for word in words if word.lower() in corpus) for angle, words in ANGLE_RULES.items()}
    best = max(scores, key=scores.get)
    if scores[best] == 0:
        best = "未识别"
    return best, scores

st.set_page_config(page_title="热点锚点工作流", layout="wide")
st.title("热点锚点工作流")
st.caption("HOTSPOT → ANGLES → POOL → MATCH | 在同一话题空间内发现不同视角")
st.info("先选择一个热榜话题作为锚点，再围绕它生成多角度检索结果，最后只在同一话题候选池内进行匹配。")

secret = os.getenv("ZHIHU_ACCESS_SECRET", "")
try:
    client = ZhihuClient(access_secret=secret or None)
except ValueError as exc:
    st.error(str(exc))
    st.stop()

if "hot_anchor_items" not in st.session_state:
    st.session_state.hot_anchor_items = []
if "anchor_pool" not in st.session_state:
    st.session_state.anchor_pool = []

with st.sidebar:
    st.header("工作流设置")
    limit = st.slider("热榜条数", 1, 30, 10)
    angle_count = st.slider("每个角度检索条数", 1, 10, 5)

if st.button("刷新知乎热榜", type="primary"):
    try:
        st.session_state.hot_anchor_items = client.hot_list(limit=limit)
    except (ZhihuAPIError, Exception) as exc:
        st.error(f"热榜获取失败：{exc}")

items = st.session_state.hot_anchor_items
if not items:
    st.warning("请先点击“刷新知乎热榜”。")
    st.stop()

st.subheader("Step 1 · 选择热点作为话题锚点")
options = list(range(len(items)))
selected = st.selectbox("当前热榜", options, format_func=lambda i: f"Top {i + 1} · {items[i].get('Title', '未命名')}")
anchor = items[selected]
st.markdown(f"### {anchor.get('Title', '未命名')}")
st.write(anchor.get("Summary") or "该热点暂无摘要。")
st.link_button("打开知乎原文", anchor.get("Url", "#"))

st.divider()
st.subheader("Step 2 · 围绕热点进行多角度检索")
st.caption("角度词用于扩大同一议题的观察面，而不是改变话题锚点。")
angles = st.multiselect("选择检索角度", ["背景与事实", "支持观点", "质疑与风险", "实践经验", "行业影响", "普通人体验"], default=["背景与事实", "质疑与风险", "实践经验"])
if st.button("构建同话题候选池"):
    pool = []
    base = anchor.get("Title", "")
    for angle in angles:
        query = f"{base} {angle}"
        try:
            results = client.search_zhihu(query, count=angle_count)
        except Exception as exc:
            st.warning(f"角度“{angle}”检索失败：{exc}")
            continue
        for result in results:
            text = f"{result.get('Title', '')}\n{result.get('ContentText', '')}".strip()
            if not text:
                continue
            detected_angle, angle_scores = classify_content(result.get("Title", ""), result.get("ContentText", ""), angle)
            pool.append({
                "input_text": f"{angle}｜{result.get('Title', '未命名')}",
                "search_content": text,
                "is_real_search": True,
                "source_url": result.get("Url", ""),
                "author_name": result.get("AuthorName", ""),
                "angle": angle,
                "detected_angle": detected_angle,
                "angle_scores": angle_scores,
                "anchor_title": base,
            })
    # 按链接去重，保留原始来源和角度
    unique, seen = [], set()
    for obj in pool:
        key = obj["source_url"] or obj["search_content"]
        if key not in seen:
            seen.add(key)
            unique.append(obj)
    st.session_state.anchor_pool = unique
    st.success(f"已构建候选池：{len(unique)} 条内容，来自 {len(angles)} 个角度。")

pool = st.session_state.anchor_pool
if not pool:
    st.info("请选择角度并构建候选池。")
    st.stop()

st.subheader("Step 3 · 候选池审阅")
st.caption("检索角度表示搜索意图；识别角度是基于关键词的二次内容标签，两者不等同于支持或反对立场。")
st.dataframe(pd.DataFrame([{"对象序号": f"对象 {i + 1}", "检索角度": p["angle"], "识别角度": p.get("detected_angle", "未识别"), "标题": p["input_text"], "作者": p["author_name"], "来源": p["source_url"]} for i, p in enumerate(pool)]), use_container_width=True, hide_index=True)

st.divider()
st.subheader("Step 3.5 · 观点聚类与阅读摘要")
st.caption("将同一热点下的内容按主题向量聚成若干观点簇，先看每簇代表内容，再决定是否展开全文。聚类表示主题相近，不代表立场完全一致。")
cluster_max = min(6, len(pool))
if cluster_max >= 2:
    cluster_count = st.slider("观点簇数量", 2, cluster_max, min(3, cluster_max))
    cluster_vectors = np.asarray([build_semantic_embedding(p["search_content"]) for p in pool], dtype=float)
    if np.any(np.linalg.norm(cluster_vectors, axis=1) > 0):
        labels_cluster = KMeans(n_clusters=cluster_count, random_state=42, n_init=10).fit_predict(cluster_vectors)
        for cluster_id in range(cluster_count):
            members = [i for i, label in enumerate(labels_cluster) if label == cluster_id]
            if not members:
                continue
            center = cluster_vectors[members].mean(axis=0)
            top_dims = np.argsort(-center)[:3]
            topic_text = "、".join(VIEWPOINT_NAMES[i] for i in top_dims if i < len(VIEWPOINT_NAMES))
            with st.expander(f"观点簇 {cluster_id + 1}｜{len(members)} 条内容｜主要主题：{topic_text}", expanded=True):
                for i in members[:5]:
                    st.markdown(f"**对象 {i + 1}** · {pool[i]['input_text']} · {pool[i].get('detected_angle', '未识别')}")
                    st.caption(f"作者：{pool[i].get('author_name') or '未提供'}｜来源：{pool[i].get('source_url') or '未提供'}")
                    st.write(pool[i]["search_content"][:280] + ("..." if len(pool[i]["search_content"]) > 280 else ""))
                if len(members) > 5:
                    st.caption(f"其余 {len(members) - 5} 条内容已折叠，可在候选池表格中查看。")
    else:
        st.info("当前内容未命中主题词，暂时无法进行观点聚类。")

st.divider()
st.subheader("Step 4 · 同一话题空间内匹配")
base_index = st.selectbox("选择基准内容", range(len(pool)), format_func=lambda i: f"对象 {i + 1}")
st.caption(f"当前基准：对象 {base_index + 1}｜{pool[base_index]['input_text']}")
weight = st.slider("正文相似度权重", 0.0, 1.0, 0.85, 0.05)
try:
    results, analysis = match_content(pool, base_index, text_weight=weight, real_only=False, top_k=20)
except ValueError as exc:
    st.warning(f"暂时无法匹配：{exc}")
    st.stop()

st.write(f"候选对象：{analysis['documents']}｜文本特征：{analysis['features']}｜匹配方法：{analysis['method']}")
rows = [{"排名": i + 1, "对象序号": r["index"] + 1, "候选标题": r["input"], "检索角度": r["profile"].get("angle", ""), "识别角度": r["profile"].get("detected_angle", "未识别"), "综合分": round(r["similarity"], 4), "正文相似度": round(r["text_similarity"], 4), "主题相似度": round(r["topic_similarity"], 4)} for i, r in enumerate(results)]
if rows:
    frame = pd.DataFrame(rows).set_index("排名")
    # 柱状图横轴使用候选内容标题，而不是 1、2、3 等结果排名，
    # 这样切换基准内容后，图表能明确反映剩余候选对象的真实身份。
    chart_frame = frame[["对象序号", "正文相似度", "主题相似度"]].copy()
    chart_frame["对象序号"] = chart_frame["对象序号"].map(lambda value: f"对象 {value}")
    chart_frame = chart_frame.set_index("对象序号")
    st.bar_chart(chart_frame)
    st.dataframe(frame, use_container_width=True)
    st.download_button("导出锚点匹配结果", frame.to_csv().encode("utf-8-sig"), "hotspot_anchor_matches.csv", "text/csv")
    detail = st.selectbox("查看匹配证据", range(len(results)), format_func=lambda i: f"对象 {results[i]['index'] + 1}")
    st.caption(f"当前查看：对象 {results[detail]['index'] + 1}｜{results[detail]['input']}")
    evidence = results[detail]
    st.write(f"综合分 = {evidence['text_similarity']:.3f} × {evidence['text_weight']:.2f} + {evidence['topic_similarity']:.3f} × {1 - evidence['text_weight']:.2f}")
    st.write("共同文本特征：" + ("、".join(x["feature"] for x in evidence["evidence"]) or "无"))
else:
    st.info("候选池中没有其他可比较对象。")
