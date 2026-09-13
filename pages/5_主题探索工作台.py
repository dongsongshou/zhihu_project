"""可解释的主题探索与多样化推荐，不依赖外部模型请求。"""
import json

import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(page_title="主题探索工作台", layout="wide")
st.title("主题探索工作台")
st.caption("EXPLORE · COMPARE · CONNECT | 从单次匹配，走向可解释的候选探索与讨论组构建")
st.info("当前特征来自关键词主题分布。相似度不是匹配成功概率，主题差异不代表立场冲突；搜索条目也不等同于已验证的用户身份。")

pool = st.session_state.get("user_candidate_pool") or []
if len(pool) < 2:
    st.warning("请先在画像页面加入至少两个候选对象，然后进入工作台。")
    st.stop()

try:
    vectors = np.asarray([p["embedding"] for p in pool], dtype=float)
    if vectors.ndim != 2 or vectors.shape[1] == 0 or not np.isfinite(vectors).all():
        raise ValueError("向量必须同维度，且不能包含空值或无穷值")
except (KeyError, TypeError, ValueError) as exc:
    st.error(f"候选特征不可用：{exc}。请重新生成画像。")
    st.stop()

norms = np.linalg.norm(vectors, axis=1, keepdims=True)
normalized = np.divide(vectors, norms, out=np.zeros_like(vectors), where=norms != 0)
valid = norms[:, 0] > 0
similarities = np.clip(normalized @ normalized.T, -1.0, 1.0)
labels = [f"{i + 1}. {p.get('input_text', '未命名')}" for i, p in enumerate(pool)]
names = pool[0].get("viewpoint_names", [])
if len(names) != vectors.shape[1]:
    names = [f"维度 {i + 1}" for i in range(vectors.shape[1])]

cols = st.columns(4)
cols[0].metric("候选对象", len(pool))
cols[1].metric("有效特征", int(valid.sum()))
cols[2].metric("真实搜索标记", sum(bool(p.get("is_real_search")) for p in pool))
cols[3].metric("主题维度", vectors.shape[1])
if not valid.all():
    st.warning("零向量对象缺少有效主题信息，将排除在推荐和组队之外。")

atlas, compare, recommend = st.tabs(["全局关系矩阵", "双对象对比", "多样化推荐与组队"])

with atlas:
    st.subheader("候选对象之间的主题相似关系")
    if len(pool) > 100:
        st.caption("为保证交互性能，矩阵仅展示前 100 个对象；推荐仍使用完整候选池。")
    size = min(len(pool), 100)
    matrix = pd.DataFrame(similarities[:size, :size], index=labels[:size], columns=labels[:size])
    st.dataframe(matrix.style.background_gradient(cmap="Blues", vmin=-1, vmax=1).format("{:.3f}"), use_container_width=True)
    st.download_button("导出当前关系矩阵 CSV", matrix.to_csv().encode("utf-8-sig"), "topic_similarity.csv", "text/csv")
    st.caption("有效向量的对角线为 1；零向量相似度按 0 处理，不代表已有反对证据。")

with compare:
    left, right = st.columns(2)
    a = left.selectbox("基准对象", range(len(pool)), format_func=lambda i: labels[i], key="explore_a")
    b = right.selectbox("对比对象", [i for i in range(len(pool)) if i != a], format_func=lambda i: labels[i], key="explore_b")
    if not (valid[a] and valid[b]):
        st.warning("至少一个对象缺少有效特征，暂不解释相似性。")
    else:
        st.metric("主题余弦相似度", f"{similarities[a, b]:.3f}")
        frame = pd.DataFrame({"基准对象": normalized[a], "对比对象": normalized[b]}, index=names)
        st.bar_chart(frame)
        difference = normalized[b] - normalized[a]
        detail = frame.copy()
        detail["对比对象 − 基准对象"] = difference
        st.dataframe(detail, use_container_width=True)
        strongest = int(np.argmax(np.abs(difference)))
        if abs(difference[strongest]) > 1e-8:
            st.write(f"最大主题差异：{names[strongest]}，归一化分量差 {difference[strongest]:+.3f}。这反映主题覆盖差异，而非立场分歧。")
        else:
            st.write("两个对象的主题分布一致；仅凭当前特征无法进一步区分。")
    with st.expander("查看分析依据与来源"):
        for i in (a, b):
            st.write(labels[i])
            st.caption("来源：" + ("真实搜索标记" if pool[i].get("is_real_search") else "输入文本兜底或未标记"))
            st.text(str(pool[i].get("search_content", "未保存来源文本")))

with recommend:
    st.subheader("保留共同话题，同时减少推荐结果重复")
    st.caption("采用 MMR 贪心重排：评分 = λ × 与基准的相似度 − (1−λ) × 与已选对象的最大相似度。它是可解释的启发式排序，不是经过训练的成功率预测。")
    base = st.selectbox("组队发起对象", range(len(pool)), format_func=lambda i: labels[i], key="explore_base")
    controls = st.columns(3)
    weight = controls[1].slider("相关性权重 λ", 0.0, 1.0, 0.7, 0.05)
    threshold = controls[2].slider("最低主题相似度", -1.0, 1.0, 0.1, 0.05)
    real_only = st.checkbox("仅推荐带真实搜索标记的对象")
    candidates = [
        i for i in range(len(pool))
        if i != base and valid[i] and valid[base]
        and similarities[base, i] >= threshold
        and (not real_only or pool[i].get("is_real_search"))
    ]
    st.caption(f"当前筛选命中 {len(candidates)} 个有效候选对象")
    max_count = min(20, len(candidates))
    if max_count <= 1:
        count = max_count
        controls[0].metric("推荐人数（不含发起对象）", count)
    else:
        count = controls[0].slider(
            "推荐人数（不含发起对象）",
            min_value=1,
            max_value=max_count,
            value=min(3, max_count),
        )
    selected, rows = [], []
    if valid[base]:
        # 候选不足时自动返回全部候选，不制造虚假的推荐数量。
        target_count = min(count, len(candidates))
        while candidates and len(selected) < target_count:
            def score(i):
                redundancy = max(0.0, max((float(similarities[i, j]) for j in selected), default=0.0))
                return weight * float(similarities[base, i]) - (1 - weight) * redundancy

            chosen = max(candidates, key=lambda i: (score(i), -i))
            rows.append({"推荐顺序": len(selected) + 1, "对象": labels[chosen], "主题相似度": float(similarities[base, chosen]), "选择时 MMR 分": score(chosen)})
            selected.append(chosen)
            candidates.remove(chosen)
    if not valid[base]:
        st.warning("发起对象缺少有效主题特征，请更换对象或重新生成画像。")
    elif not selected:
        st.info("没有候选对象满足当前条件。请降低相似度阈值或取消真实搜索筛选。")
    else:
        recommendation_frame = pd.DataFrame(rows)
        st.dataframe(recommendation_frame, use_container_width=True, hide_index=True)
        st.download_button(
            "下载推荐结果 CSV",
            recommendation_frame.to_csv(index=False).encode("utf-8-sig"),
            "mmr_recommendations.csv",
            "text/csv",
        )
        st.caption("MMR 分记录每次贪心选择时的评分，不是全局最优解；分数可能为负数。")
        members = [base] + selected
        mean = normalized[members].mean(axis=0)
        topics = [str(names[i]) for i in np.argsort(-mean, kind="stable") if mean[i] > 0][:3]
        st.subheader("讨论小组草案")
        st.write("参与对象：" + "、".join(labels[i] for i in members))
        st.write("主要覆盖主题：" + ("、".join(topics) or "暂无法提取"))
        agenda = [f"围绕“{topic}”：各自提供一条来源材料，再讨论证据、适用条件与局限。" for topic in topics]
        for step, prompt in enumerate(agenda, 1):
            st.write(f"{step}. {prompt}")
        st.caption("议程为规则生成的讨论建议，未模拟真人发言，未发送邀请，也未创建真实群组。")
        draft = {"method": "MMR", "lambda": weight, "min_similarity": threshold, "base": labels[base], "recommendations": rows, "agenda": agenda, "limitations": "基于主题特征的启发式草案，不代表身份验证、真实立场或组队成功率。"}
        st.download_button("下载讨论小组草案 JSON", json.dumps(draft, ensure_ascii=False, indent=2), "discussion_group.json", "application/json")
