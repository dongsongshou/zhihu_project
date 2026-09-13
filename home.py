import streamlit as st
import numpy as np

from utils.match_engine import cluster_users

st.set_page_config(page_title="知乎同频观点匹配系统", layout="wide")

for key, default in {
    "current_profile": None,
    "user_candidate_pool": [],
    "match_result": [],
    "group_analysis_result": None,
    "final_report": None,
}.items():
    st.session_state.setdefault(key, default)

st.title("知乎同频观点匹配系统")
st.caption("基于 8 维观点向量的用户画像、同频匹配、群体分析与报告输出演示")

st.markdown(
    """
该项目围绕知乎内容场景构建完整的观点分析链路：

1. 用户画像构建：输入关键词，生成 8 维观点画像。
2. 同频匹配：在候选池中计算余弦相似度，筛选高相关用户。
3. 群体分析：汇总匹配结果，形成群体层面的统计视图。
4. 报告输出：生成结构化结果，便于展示与扩展。
"""
)

st.divider()

candidate_pool = st.session_state["user_candidate_pool"]
match_result = st.session_state["match_result"]
group_analysis_result = st.session_state["group_analysis_result"]
final_report = st.session_state["final_report"]

metric_cols = st.columns(4)
metric_cols[0].metric("候选用户", len(candidate_pool))
metric_cols[1].metric("匹配结果", len(match_result))
metric_cols[2].metric("群体分析", "已生成" if group_analysis_result else "未生成")
metric_cols[3].metric("最终报告", "已生成" if final_report else "未生成")

st.subheader("候选池概览")
if len(candidate_pool) >= 2:
    try:
        user_clustered, centers = cluster_users(candidate_pool)
        st.success(f"已完成聚类分析，共 {len(centers)} 个簇")
    except Exception as exc:
        st.error(f"聚类分析失败：{exc}")
        user_clustered = candidate_pool
        centers = None
else:
    st.info("候选用户不足 2 个，暂不执行聚类分析")
    user_clustered = candidate_pool
    centers = None

if user_clustered:
    with st.expander("查看候选池明细"):
        for item in user_clustered:
            name = item.get("input_text", item.get("name", "未知用户"))
            cluster_label = item.get("cluster", -1)
            embedding = np.round(np.array(item.get("embedding", [])), 4)
            st.write(f"{name} | 聚类标签：{cluster_label} | 向量：{embedding}")

if centers is not None:
    with st.expander("查看聚类中心"):
        for idx, center in enumerate(centers):
            st.write(f"簇 {idx}：{np.round(center, 4)}")

st.divider()

st.subheader("流程状态")
if st.session_state.get("current_profile"):
    st.info(f"当前已生成画像：{st.session_state['current_profile'].get('input_text', '未命名输入')}")
else:
    st.info("尚未生成用户画像")

if match_result:
    st.success("同频匹配结果已就绪")
else:
    st.warning("同频匹配结果尚未生成，请前往匹配页面完成计算")

if group_analysis_result:
    st.success("群体分析结果已就绪")
else:
    st.warning("群体分析结果尚未生成")

if final_report:
    st.success("最终报告已就绪")
else:
    st.warning("最终报告尚未生成")

st.divider()
st.caption("建议按顺序完成：用户画像构建 -> 同频匹配 -> 群体分析 -> 报告输出")

