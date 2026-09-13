import streamlit as st

import pandas as pd
from utils.content_match import match_content

st.set_page_config(page_title="同频匹配引擎", layout="wide")

st.title("同频匹配引擎")
st.caption("依据关键词搜索摘要匹配内容，并展示文本特征与得分贡献")

if "user_candidate_pool" not in st.session_state:
    st.session_state["user_candidate_pool"] = []

pool = st.session_state["user_candidate_pool"]

if len(pool) == 0:
    st.error("候选池为空，请先前往用户画像构建页面生成并加入候选用户")
    if "match_result" in st.session_state:
        del st.session_state["match_result"]
    st.stop()

st.success(f"候选池用户总数：{len(pool)}")

user_options = [f"{idx + 1}. {p['input_text']}" for idx, p in enumerate(pool)]
selected_idx = st.selectbox("请选择基准用户", range(len(pool)), format_func=lambda x: user_options[x])

base_user = pool[selected_idx]
st.subheader("基准用户信息")
st.write(f"输入关键词：{base_user['input_text']}")
for name, score in base_user["viewpoint_scores"]:
    st.markdown(f"- **{name}**：{score} 分")

st.divider()

st.subheader("内容匹配参数")
real_only = st.checkbox("仅使用真实搜索内容", value=True)
text_weight = st.slider("正文相似度权重", 0.0, 1.0, 0.8, 0.05)
st.caption("综合分 = 正文 TF-IDF 余弦 × 权重 + 原有主题余弦 × (1−权重)。主题特征不可用时仅使用正文。分数衡量文本相关性，不代表立场一致或匹配成功率。")

if len(pool) < 2:
    st.info("请至少加入两个候选对象后进行内容匹配。")
    st.stop()

# 每次根据当前来源、基准和权重计算，避免展示过期推荐。
try:
    res, analysis = match_content(pool, selected_idx, text_weight=text_weight, real_only=real_only)
except ValueError as exc:
    st.warning(str(exc))
    st.stop()

st.subheader("匹配过程")
st.graphviz_chart('digraph { rankdir=LR; node [shape=box]; "搜索摘要" -> "清理HTML与重复行" -> "中文片段 / 英文单词" -> "TF-IDF权重" -> "正文余弦" -> "融合主题得分" -> "候选排序"; }')
cols = st.columns(3)
cols[0].metric("参与建模的内容对象", analysis["documents"])
cols[1].metric("文本特征数", analysis["features"])
cols[2].metric("返回候选数", len(res))
st.caption("TF-IDF 降低候选池中常见片段的权重，并用对数词频限制重复词的影响。摘要按行去重、每对象最多处理 30,000 字符。相同搜索结果仍可能产生高分，不能据此认定为同一用户。")

if not res:
    st.info("没有可用于比较的候选文本特征，请补充搜索内容。")
    st.stop()

ranking = pd.DataFrame([
    {"候选": f"{item['index'] + 1}. {item['input']}",
     "正文贡献": item["text_weight"] * item["text_similarity"],
     "主题贡献": (1 - item["text_weight"]) * item["topic_similarity"],
     "综合分": item["similarity"]}
    for item in res
]).set_index("候选")
st.subheader("推荐排序与分数组成")
st.bar_chart(ranking[["正文贡献", "主题贡献"]])
st.dataframe(ranking, use_container_width=True)

choice = st.selectbox("查看一条匹配的计算依据", range(len(res)), format_func=lambda i: res[i]["input"])
item = res[choice]
st.write(f"正文余弦 {item['text_similarity']:.4f} × {item['text_weight']:.2f} + 主题余弦 {item['topic_similarity']:.4f} × {1-item['text_weight']:.2f} = {item['similarity']:.4f}")
st.subheader("共同文本特征的贡献")
if item["evidence"]:
    evidence_frame = pd.DataFrame(item["evidence"]).rename(columns={"feature": "共同片段", "contribution": "正文余弦贡献"})
    st.bar_chart(evidence_frame.set_index("共同片段"))
    st.caption(f"共 {item['shared_features']} 个共同特征，展示贡献最高的 12 个。全部共同特征的 TF-IDF 权重乘积之和等于正文余弦；中文片段可能重叠，不是独立观点证据。")
else:
    st.info("没有共同文本特征，正文余弦为 0。")
with st.expander("核对实际参与计算的摘要", expanded=False):
    left, right = st.columns(2)
    left.write(base_user["input_text"])
    left.text(analysis["texts"][selected_idx])
    right.write(item["input"])
    right.text(analysis["texts"][item["index"]])

st.download_button("下载匹配得分 CSV", ranking.to_csv().encode("utf-8-sig"), "content_matches.csv", "text/csv")
if st.button("将本次匹配用于群体分析", type="primary"):
    st.session_state["match_result"] = res
    st.session_state["group_analysis_result"] = None
    st.session_state["final_report"] = None
    st.success("匹配已保存，旧群体报告已清除，请前往群体分析页面重新生成。")


