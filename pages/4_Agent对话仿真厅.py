import json
import streamlit as st
import numpy as np
import pandas as pd




st.set_page_config(page_title="群体观点报告输出", layout="wide")

st.title("群体观点报告输出")
st.caption("基于群体分析结果生成结构化报告")

group_analysis_result = st.session_state.get("group_analysis_result")
if not group_analysis_result:
    st.warning("需要先完成群体分析，请前往分析页面继续操作")
    st.stop()



st.success(f"已读取群体分析结果，群体用户数量：{group_analysis_result['user_count']}")
st.info("本报告反映的是基于公开内容的主题倾向与相似关系，不等同于对用户真实立场的确定性判断。")


user_count = group_analysis_result["user_count"]
sim_min = group_analysis_result["sim_min"]
sim_max = group_analysis_result["sim_max"]
match_users = group_analysis_result["match_users"]
all_scores = group_analysis_result["all_scores"]
viewpoint_names = [
    "科技发展乐观", "关注社会公平", "文化包容倾向", "风险审慎态度",
    "个人主义-集体主义", "现实务实", "创新接纳度", "公共事务参与意愿",
]

st.divider()
metric_cols = st.columns(4)
metric_cols[0].metric("群体成员", user_count)
metric_cols[1].metric("最高相似度", f"{sim_max:.3f}")
metric_cols[2].metric("最低相似度", f"{sim_min:.3f}")
metric_cols[3].metric("平均相似度", f"{np.mean([u.get('similarity', 0) for u in match_users]):.3f}" if match_users else "--")

st.subheader("群体主题结构")
if all_scores:
    chart_data = pd.DataFrame([
        {str(name).replace("‑", "-"): float(score) for name, score in scores}
        for scores in all_scores
    ]).reindex(columns=viewpoint_names)
    st.bar_chart(chart_data.mean().sort_values(ascending=False))

st.subheader("数据质量与来源")
real_count = sum(1 for user in match_users if user.get("profile", {}).get("is_real_search", False))
col_a, col_b, col_c = st.columns(3)
col_a.metric("真实搜索成员", f"{real_count}/{len(match_users)}")
col_b.metric("模拟/兜底成员", max(0, len(match_users) - real_count))
col_c.metric("维度数量", len(viewpoint_names))
st.caption("搜索结果不保证属于输入指定的用户。未使用真实搜索的条目可能来自输入文本兜底；来源标记不代表内容质量或用户身份已验证。")

st.subheader("参与群体的用户列表")

for idx, user in enumerate(match_users):
    st.markdown(f"**{idx + 1}. 用户关键词：{user['input']}** | 相似度：{user['similarity']}")
    with st.expander("查看该用户 8 维观点得分"):
        for name, score in user["profile"]["viewpoint_scores"]:
            st.markdown(f"- {name}：{score} 分")

st.divider()
st.subheader("成员对比明细")
member_rows = []
for user in match_users:
    row = {"成员": user.get("input", "未知"), "相似度": user.get("similarity", 0)}
    profile_scores = user.get("profile", {}).get("viewpoint_scores", [])
    row.update({name: float(score) for name, score in profile_scores})
    member_rows.append(row)
if member_rows:
    st.dataframe(pd.DataFrame(member_rows), use_container_width=True, hide_index=True)

st.subheader("群体基础统计")
st.write(f"群体用户总数：{user_count}")
st.write(f"成员与基准用户相似度区间：{sim_min} ~ {sim_max}")





group_avg_scores = []


for dim_idx in range(len(viewpoint_names)):
    values = [
        float(score) for scores in all_scores for name, score in scores
        if str(name).replace("‑", "-") == viewpoint_names[dim_idx]
        and np.isfinite(float(score))
    ]
    avg = round(float(np.mean(values)), 2) if values else 0.0

    group_avg_scores.append((viewpoint_names[dim_idx], avg))

st.subheader("群体 8 维观点平均得分")
for name, avg_score in group_avg_scores:
    col1, col2 = st.columns([3, 7])
    with col1:
        st.markdown(f"**{name}**")
    with col2:
        st.progress(min(100, max(0, int(avg_score))), text=f"{avg_score} 分")

if st.button("生成最终群体观点报告"):
    final_report = {
        "user_count": user_count,
        "sim_min": sim_min,
        "sim_max": sim_max,
        "real_search_count": real_count,
        "limitations": "关键词主题分布不等同于真实立场；搜索结果不保证属于输入指定的用户；相似度不是匹配成功概率。",
        "group_avg_scores": group_avg_scores,
        "member_list": [{"input": u["input"], "similarity": u["similarity"]} for u in match_users],
    }
    st.session_state["final_report"] = final_report
    st.success("最终群体观点报告已生成")

if st.session_state.get("final_report"):
    report = st.session_state["final_report"]
    st.divider()
    st.subheader("报告快照与下载")
    st.caption("以下导出均使用点击生成报告时的数据快照；分析数据变更后请重新生成。")
    st.json(report)
    markdown_report = "# 群体主题分析报告\n\n"
    markdown_report += f"- 群体成员：{report['user_count']}\n- 相似度区间：{report['sim_min']} ~ {report['sim_max']}\n\n"
    markdown_report += "## 群体主题均值\n\n"
    markdown_report += "\n".join(f"- {name}：{score} 分" for name, score in report["group_avg_scores"])
    markdown_report += "\n\n## 分析边界\n\n" + report.get("limitations", "主题分布不等同于真实立场。")
    st.download_button("下载 Markdown 报告", markdown_report, "zhihu_viewpoint_report.md", "text/markdown")
    st.download_button(
        "下载 JSON 报告",
        data=json.dumps(report, ensure_ascii=False, indent=2, default=str),
        file_name="zhihu_viewpoint_report.json",
        mime="application/json",
    )


