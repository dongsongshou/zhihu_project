import streamlit as st
import numpy as np

st.set_page_config(page_title="同频群体分析", layout="wide")

st.title("同频群体分析")
st.caption("基于同频匹配结果进行群体统计与观点分析")

if "match_result" not in st.session_state or len(st.session_state["match_result"]) == 0:
    st.error("需要先完成同频匹配计算，请前往匹配页面执行操作")
    st.stop()

match_result = st.session_state["match_result"]
st.success(f"已读取匹配结果，匹配用户数量：{len(match_result)}")

st.divider()
st.subheader("同频用户列表")
for idx, item in enumerate(match_result):
    st.markdown(f"**{idx + 1}. 用户：{item['input']}** | 相似度：{item['similarity']}")
    with st.expander("查看该用户 8 维观点得分"):
        for name, score in item["profile"]["viewpoint_scores"]:
            st.markdown(f"- {name}：{score} 分")

emb_list = []
sim_list = []
score_list = []
for item in match_result:
    emb_list.append(np.array(item["profile"]["embedding"]))
    sim_list.append(item["similarity"])
    score_list.append(item["profile"]["viewpoint_scores"])

st.divider()
st.subheader("基础统计信息")
st.write(f"参与分析同频用户数：{len(emb_list)}")
st.write(f"相似度区间：{min(sim_list)} ~ {max(sim_list)}")

if st.button("执行群体分析，输出分析结果"):
    group_analysis_result = {
        "user_count": len(emb_list),
        "sim_min": float(min(sim_list)),
        "sim_max": float(max(sim_list)),
        "match_users": match_result,
        "embeddings": [e.tolist() for e in emb_list],
        "all_scores": score_list,
    }
    st.session_state["group_analysis_result"] = group_analysis_result
    st.success("群体分析完成，可前往报告输出页面继续处理")

# ===== 修复处：使用 .get() 并在赋值后判断是否为 None =====
gr = st.session_state.get("group_analysis_result")
if gr is not None:
    st.info(f"当前已生成群体分析结果，有效用户数：{gr['user_count']}")
else:
    st.info("点击按钮生成群体分析结果")