"""统一话题会话的五步探索界面。网络请求只由按钮触发。"""
import json
from datetime import datetime, timezone
from urllib.parse import urlsplit

import pandas as pd
import requests
import streamlit as st

from zhihu_client import ZhihuClient, ZhihuAPIError
from utils.content_match import match_content
from utils.connections_ui import render_connections, safe_source
from utils.llm_judge import judge_pair, SemanticJudgeError

STEPS = ["选择话题", "收集内容", "快速阅读", "探索关系", "发现作者与讨论", "导出报告"]
ANGLES = ["背景与事实", "质疑与风险", "实践经验", "行业影响", "普通人体验"]


def new_exploration():
    return {"step": 0, "anchor": None, "pool": [], "results": [], "errors": [], "queries": [], "revision": 0}


def render():
    state = st.session_state.setdefault("exploration", new_exploration())
    st.markdown("""
<style>
@keyframes exploration-page-in {
    from { opacity: 0; transform: perspective(1400px) rotateY(-5deg) translateX(22px); }
    to { opacity: 1; transform: perspective(1400px) rotateY(0) translateX(0); }
}
[class*="st-key-exploration_sheet_"] {
    animation: exploration-page-in .4s ease-out;
    transform-origin: left center;
    border: 1px solid rgba(128,128,128,.25);
    border-radius: 20px;
    box-shadow: 0 12px 32px rgba(0,0,0,.08);
    padding: clamp(12px, 3vw, 32px);
}
@media (prefers-reduced-motion: reduce) {
    [class*="st-key-exploration_sheet_"] { animation: none; }
}
</style>
""", unsafe_allow_html=True)
    with st.container(key=f"exploration_sheet_{state['step']}"):
        _render_page()


def _turn_page(offset):
    state = st.session_state["exploration"]
    state["step"] = max(0, min(len(STEPS) - 1, state["step"] + offset))


def _page_controls(step, ready, location):
    previous, number, following = st.columns([2, 1, 2])
    previous.button(
        "← 上一页", disabled=step == 0, use_container_width=True,
        key=f"{location}_previous", on_click=_turn_page, args=(-1,),
    )
    number.markdown(f"**{step + 1} / {len(STEPS)}**")
    following.button(
        "下一页 →" if step < len(STEPS) - 1 else "已到最后一页",
        disabled=not ready or step == len(STEPS) - 1, use_container_width=True,
        type="primary", key=f"{location}_next", on_click=_turn_page, args=(1,),
    )


def _render_page():
    state = st.session_state.setdefault("exploration", new_exploration())
    step = state["step"]
    home_page = st.session_state.get("home_page_object")
    if home_page is not None:
        st.page_link(home_page, label="← 返回首页")
    st.title(f"{step + 1:02d} / {STEPS[step]}")
    top_controls = st.container()
    st.caption("所有步骤共用本次话题会话；旧版页面的候选池不参与本流程。")
    st.progress((step + 1) / len(STEPS), text=f"第 {step + 1} 步 / {len(STEPS)} · {STEPS[step]}")
    st.write(" → ".join(f"【{name}】" if i == step else name for i, name in enumerate(STEPS)))
    if state["anchor"]:
        st.caption("当前话题：" + state["anchor"]["title"])
    ready = False

    if step == 0:
        mode = st.radio("话题来源", ["知乎热榜", "自定义话题"], horizontal=True)
        title, url = "", ""
        if mode == "知乎热榜":
            if st.button("获取 / 刷新热榜"):
                client = None
                try:
                    client = ZhihuClient()
                    st.session_state["exploration_hot"] = client.hot_list(limit=20)
                except (ValueError, requests.RequestException, ZhihuAPIError):
                    st.error("获取失败，请检查 Access Secret、网络和接口额度。不会使用模拟榜单。")
                finally:
                    if client is not None:
                        client.session.close()
            hot = st.session_state.get("exploration_hot", [])
            if hot:
                chosen = st.selectbox("选择热点", range(len(hot)), format_func=lambda i: hot[i].get("Title", "未命名"))
                title, url = hot[chosen].get("Title", ""), hot[chosen].get("Url", "")
                st.write(hot[chosen].get("Summary") or "暂无摘要")
        else:
            title = st.text_input("话题关键词", max_chars=100).strip()
        if st.button("确认话题", disabled=not bool(title)):
            anchor = {"title": title, "url": url}
            if state["anchor"] != anchor:
                revision = state["revision"] + 1
                state.update(new_exploration())
                state["revision"] = revision
                state["anchor"] = anchor
            st.success("话题已确认。更换话题会清除旧内容、匹配和报告数据。")
        ready = state["anchor"] == {"title": title, "url": url} and bool(title)

    elif step == 1:
        angles = st.multiselect("检索角度", ANGLES, default=ANGLES[:3])
        count = st.slider("每角度返回条数", 1, 10, 5)
        queries = [f"{state['anchor']['title']} {angle}" for angle in angles]
        st.caption(f"将发起 {len(queries)} 次搜索；角度只代表检索意图，不是内容立场。翻页不会调用接口。")
        st.write(queries)
        if st.button("检索 / 重新构建候选池", disabled=not angles, type="primary"):
            state.update(pool=[], results=[], errors=[], queries=queries)
            state["revision"] += 1
            objects = {}
            client = None
            try:
                client = ZhihuClient()
                with st.spinner("正在按角度检索…"):
                    for angle, query in zip(angles, queries):
                        try:
                            items = client.search_zhihu(query, count=count)
                            for item in items:
                                body = str(item.get("ContentText") or "").strip()
                                if not body:
                                    continue
                                text = f"{item.get('Title', '')}\n{body}"
                                source = str(item.get("Url") or "")
                                # 优先使用内容标识，避免不同检索链接的溯源参数影响去重。
                                key = (item.get("ContentType"), str(item["ContentID"])) if item.get("ContentID") else (source or text)
                                if key in objects:
                                    if angle not in objects[key]["angles"]:
                                        objects[key]["angles"].append(angle)
                                    continue
                                objects[key] = {"input_text": item.get("Title") or "未命名", "search_content": text,
                                                "source_url": source, "author_name": item.get("AuthorName", ""),
                                                "is_real_search": True, "angles": [angle]}
                        except (ValueError, requests.RequestException, ZhihuAPIError):
                            state["errors"].append(f"{angle}：请求失败；为避免额度或频率限制，已停止后续检索。")
                            break
            except ValueError:
                state["errors"].append("缺少有效配置，请设置 Access Secret。")
            finally:
                if client is not None:
                    client.session.close()
            state["pool"] = list(objects.values())
            state["collected_at"] = datetime.now(timezone.utc).isoformat()
        for error in state["errors"]:
            st.warning(error)
        st.metric("已保存候选内容", len(state["pool"]))
        ready = bool(state["pool"])
        if state["pool"] and queries != state["queries"]:
            st.info("检索角度已修改但尚未重新检索；当前仍展示上次的内容快照。")

    elif step == 2:
        st.subheader("候选内容速览")
        st.caption("编号在本次候选池中固定；重新检索后重新编号。此处为内容审阅，尚未实现热点内容自动聚类。")
        st.dataframe(pd.DataFrame([{"对象": f"对象 {i+1}", "作者昵称": p.get("author_name") or "未提供", "标题": p["input_text"], "检索角度": "、".join(p["angles"]), "原文": p.get("source_url", "")} for i, p in enumerate(state["pool"])]), hide_index=True, use_container_width=True)
        for i, item in enumerate(state["pool"]):
            with st.expander(f"对象 {i+1} · {item.get('author_name') or '未提供作者'} · {item['input_text']}"):
                st.markdown(f"**作者昵称：** {item.get('author_name') or '未提供'}")
                st.text(item["search_content"])
                if urlsplit(item["source_url"]).scheme in ("http", "https"):
                    st.link_button("核对原文", item["source_url"])
        ready = len(state["pool"]) >= 2
        if not ready:
            st.info("至少需要两条内容才能匹配，请返回上一步补充检索。")

    elif step == 3:
        pool = state["pool"]
        base = st.selectbox("基准内容", range(len(pool)), format_func=lambda i: f"对象 {i+1}", key=f"wizard_base_{state['revision']}")
        st.write(pool[base]["input_text"])
        st.caption("本流程按搜索摘要做 TF-IDF 正文匹配，不显示不存在的主题向量贡献。相似度不代表立场一致。")
        semantic_mode = st.checkbox("使用知乎直答进行语义判断（会调用接口）", value=False, key=f"semantic_mode_{state['revision']}")
        cache_key = (state["revision"], base, semantic_mode)
        cached = state.get("match_cache")
        should_compute = cached is None or cached.get("key") != cache_key
        if should_compute:
            st.info("当前基准对象或语义模式已变化；点击“计算并固定排序”后才会重新匹配。")
        if st.button("计算并固定排序", type="primary", disabled=not should_compute, key=f"compute_match_{state['revision']}_{base}_{semantic_mode}"):
            st.session_state[f"run_match_{state['revision']}_{base}_{semantic_mode}"] = True
            st.rerun()
        should_run = st.session_state.pop(f"run_match_{state['revision']}_{base}_{semantic_mode}", False)
        try:
            if cached is not None and cached.get("key") == cache_key and not should_run:
                results, info = cached["results"], cached["info"]
            else:
                results, info = match_content(pool, base, text_weight=1.0, real_only=True, top_k=len(pool)-1)
            if semantic_mode and (cached is None or cached.get("key") != cache_key or should_run):
                progress = st.progress(0, text="正在进行语义判断…")
                for position, result in enumerate(results, 1):
                    try:
                        judgment = judge_pair(pool[base]["search_content"], result["profile"]["search_content"], state["anchor"]["title"])
                    except SemanticJudgeError:
                        # 单个对象请求失败时直接跳过，不影响其他成功结果。
                        continue
                    result["llm_score"] = judgment["score"]
                    result["semantic_reason"] = judgment.get("reason", "")
                    result["common_interest"] = judgment.get("common_interest", "")
                    result["difference"] = judgment.get("difference", "")
                    result["similarity"] = round(0.7 * judgment["score"] + 0.3 * result["similarity"], 4)
                    progress.progress(position / len(results))
                # 只保留成功完成语义判断的结果，失败对象不参与本次语义排序。
                results = [item for item in results if "llm_score" in item]
                results.sort(key=lambda item: (-item["similarity"], item["index"]))
                state["method"] = "知乎直答语义判断 70% + TF-IDF 词法证据 30%"

            state["results"], state["base"] = results, base
            state["match_cache"] = {"key": cache_key, "results": results, "info": info}
            state.setdefault("method", "TF-IDF 中文 2～4 字片段 / 英文单词，L2 归一化余弦")
            frame = pd.DataFrame([{"对象": f"对象 {r['index']+1}", "作者昵称": r['profile'].get('author_name') or '未提供', "相似度": r["similarity"], "标题": r["input"]} for r in results])
            if results:
                st.bar_chart(frame.set_index("对象")[["相似度"]])
                st.dataframe(frame, hide_index=True, use_container_width=True)
                detail = st.selectbox("查看得分依据", range(len(results)), format_func=lambda i: f"对象 {results[i]['index']+1}", key=f"wizard_detail_{state['revision']}_{base}")
                selected_result = results[detail]
                if semantic_mode and selected_result.get("semantic_reason"):
                    st.markdown("**大模型语义判断**")
                    st.write(selected_result.get("semantic_reason"))
                    st.write("共同兴趣：" + (selected_result.get("common_interest") or "未提取"))
                    st.write("主要差异：" + (selected_result.get("difference") or "未提取"))
                    st.metric("大模型语义相关度", f"{selected_result.get('llm_score', 0):.3f}")
                    with st.expander("查看 TF-IDF 技术证据"):
                        st.dataframe(pd.DataFrame(selected_result["evidence"]), hide_index=True)
                        st.caption("这些词片段仅用于技术审计，不是大模型生成的语义依据，也不代表独立观点证据。")
                else:
                    st.dataframe(pd.DataFrame(selected_result["evidence"]), hide_index=True)
                    st.caption("展示最高贡献的共同片段；片段可重叠，不是独立的观点证据。")
            st.caption(f"参与文本 {info['documents']} 条 · TF-IDF 特征 {info['features']} 个")
            if semantic_mode:
                st.caption("当前推荐排序以大模型语义判断为主；下方关键词仅作为可选的 TF-IDF 技术审计证据。")
                st.markdown("### 大模型语义推荐列表")
                st.caption("系统已自动完成候选批量判断，并按综合分排序；无需逐个点击。")
                semantic_rows = []
                for item in results:
                    semantic_rows.append({
                        "推荐顺序": len(semantic_rows) + 1,
                        "对象": f"对象 {item['index'] + 1}",
                        "作者昵称": item["profile"].get("author_name") or "未提供",
                        "语义相关度": round(item.get("llm_score", 0), 4),
                        "综合分": round(item["similarity"], 4),
                        "共同兴趣": item.get("common_interest", ""),
                        "主要差异": item.get("difference", ""),
                        "标题": item["input"],
                    })
                if semantic_rows:
                    st.dataframe(pd.DataFrame(semantic_rows), hide_index=True, use_container_width=True)
                    st.markdown("### 优先推荐阅读")
                    for item in results[:5]:
                        with st.container(border=True):
                            st.markdown(f"**对象 {item['index'] + 1} · {item['profile'].get('author_name') or '未提供作者'}**")
                            st.write(item["input"])
                            st.caption(f"语义相关度 {item.get('llm_score', 0):.3f} · 综合分 {item['similarity']:.3f}")
                            st.write(item.get("semantic_reason") or "模型未返回详细理由。")
                            if item.get("common_interest"):
                                st.write("共同兴趣：" + item["common_interest"])
                            if item.get("difference"):
                                st.write("互补角度：" + item["difference"])
                            source_url = item["profile"].get("source_url", "")
                            if source_url:
                                st.link_button("阅读原文并核对作者", source_url)

            if semantic_mode:
                st.info("语义判断结果来自知乎直答模型；失败或未勾选时仍使用 TF-IDF。")
            ready = bool(results)
        except ValueError as exc:
            state["results"] = []
            st.warning(str(exc))

    elif step == 4:
        render_connections(state)
        ready = bool(state["results"])

    else:
        st.subheader("本次探索报告")
        pool = state["pool"]
        results = state["results"]
        angle_counts = {}
        for item in pool:
            for angle in item.get("angles", []):
                angle_counts[angle] = angle_counts.get(angle, 0) + 1
        source_count = sum(bool(item.get("source_url")) for item in pool)
        top_results = results[:5]
        base_title = pool[state["base"]]["input_text"]
        author_candidates = []
        for result in (r for r in results if r["similarity"] > 0):
            profile = result["profile"]
            name = str(profile.get("author_name") or "").strip()
            source = safe_source(profile.get("source_url"))
            if not name or name in {"知乎用户", "匿名用户", "匿名"} or not source:
                continue
            author_candidates.append({
                "object": result["index"] + 1, "author_name": name,
                "title": result["input"], "source_url": source,
                "content_similarity": round(result["similarity"], 4),
                "reason": f"该摘要与所选《{base_title}》存在词法相关性，可先阅读原文，再判断是否值得交流。",
                "opening_question": f"读到《{result['input']}》后，我想请教：其中哪些结论最依赖具体条件？有没有值得补充的经验或反例？",
            })
            if len(author_candidates) == 5:
                break
        conclusion = (
            f"围绕“{state['anchor']['title']}”，本次收集 {len(pool)} 条候选内容；"
            f"依据你选择的《{base_title}》，整理出 {len(author_candidates)} 条带作者昵称和原文链接的交流线索。"
            if author_candidates else
            f"本次收集 {len(pool)} 条候选内容，但暂未找到同时具备正相关分、可识别昵称和有效原文链接的作者线索，建议补充检索后再尝试。"
        )
        conclusion += "这些是内容关联的作者线索，不代表已匹配到相同数量的独立用户或确认双方兴趣相同。"
        if state["errors"]:
            conclusion += "部分检索失败，当前结果仅覆盖已成功取得的内容。"
        report = {
            "summary": {
                "conclusion": conclusion,
                "base_title": base_title,
                "author_candidates": author_candidates,
                "anchor": state["anchor"],
                "content_count": len(pool),
                "source_coverage": round(source_count / len(pool), 3) if pool else 0,
                "angle_distribution": angle_counts,
                "top_matches": [{"object": r["index"] + 1, "title": r["input"], "similarity": round(r["similarity"], 4)} for r in top_results],
            },
            "method": state.get("method", "TF-IDF 内容相似度"),
            "collected_at": state.get("collected_at"),
            "request_errors": state["errors"],
            "base_object": state.get("base", 0) + 1,
            "limitations": "内容相关性不等于真实立场；检索角度不等于观点标签；作者昵称不等于身份验证。",
            "technical_detail": {"queries": state["queries"], "contents": [{"object": i + 1, **p} for i, p in enumerate(pool)], "matches": [{k: v for k, v in r.items() if k != "profile"} for r in results]},
        }
        st.success(f"报告已生成：{state['anchor']['title']}")
        summary = report["summary"]
        metric_cols = st.columns(4)
        metric_cols[0].metric("候选内容", summary["content_count"])
        metric_cols[1].metric("来源覆盖", f"{summary['source_coverage']:.0%}")
        metric_cols[2].metric("检索角度", len(summary["angle_distribution"]))
        metric_cols[3].metric("推荐结果", len(results))
        st.markdown("### 一句话结论")
        st.write(summary["conclusion"])
        st.markdown("### 值得进一步了解的作者")
        st.caption("按对应内容的相似度排序，最多展示 5 条。不按昵称合并身份，不把分数称为人与人的匹配率。")
        if not author_candidates:
            st.info("暂无可核对的作者推荐；仍可查看下方内容结果。")
        for candidate in author_candidates:
            with st.container(border=True):
                st.text(f"对象 {candidate['object']} · {candidate['author_name']}")
                st.write(candidate["title"])
                st.caption(f"内容相关分：{candidate['content_similarity']:.4f}")
                st.write(candidate["reason"])
                st.write("建议开场：" + candidate["opening_question"])
                st.link_button("核对原文与作者", candidate["source_url"])
        st.caption("建议先核对内容归属，再自行留言或征得讨论意愿；本报告未发送邀请，也不包含私人交流笔记。")
        st.markdown("### 检索渠道覆盖")
        st.caption("同一条内容可能由多个检索角度召回，数量之和可超过候选总数；这不是观点阵营或社区讨论占比。")
        st.dataframe(pd.DataFrame([{"检索角度": k, "内容数量": v} for k, v in sorted(angle_counts.items(), key=lambda x: -x[1])]), hide_index=True, use_container_width=True)
        st.markdown("### 最值得优先阅读的内容")
        st.dataframe(pd.DataFrame([{"对象": f"对象 {r['index'] + 1}", "标题": r["input"], "相似度": round(r["similarity"], 4)} for r in top_results]), hide_index=True, use_container_width=True)
        with st.expander("查看技术依据和完整明细"):
            st.json(report["technical_detail"])
            st.caption(report["limitations"])
        st.download_button("下载 JSON 报告", json.dumps(report, ensure_ascii=False, indent=2), "topic_exploration.json", "application/json")
        markdown = f"# 话题探索报告\n\n## 热点\n{state['anchor']['title']}\n\n## 一句话结论\n{summary['conclusion']}\n\n## 检索渠道覆盖\n"
        markdown += "\n".join(f"- {k}：{v} 条" for k, v in sorted(angle_counts.items(), key=lambda x: -x[1]))
        markdown += "\n\n## 优先阅读\n" + "\n".join(f"- 对象 {r['index'] + 1}：{r['input']}（相似度 {r['similarity']:.4f}）" for r in top_results)
        markdown += "\n\n## 值得进一步了解的作者\n\n"
        for candidate in author_candidates:
            markdown += (
                f"### 对象 {candidate['object']} · {candidate['author_name']}\n\n"
                f"内容：{candidate['title']}\n\n内容相关分：{candidate['content_similarity']:.4f}\n\n"
                f"推荐依据：{candidate['reason']}\n\n原文：{candidate['source_url']}\n\n"
                f"建议开场：{candidate['opening_question']}\n\n"
            )
        if not author_candidates:
            markdown += "暂无可核对的作者推荐。\n"
        markdown += "\n作者线索不等于独立用户，未核验身份或参与意愿；开场问题为规则草案，未发送邀请。检索角度仅为召回渠道，可重复计数。\n"
        markdown += "\n\n## 分析边界\n" + report["limitations"]
        st.download_button("下载 Markdown 报告", markdown, "topic_exploration.md", "text/markdown")

    with top_controls:
        _page_controls(step, ready, "top")
        if not ready and step < len(STEPS) - 1:
            st.caption("完成本页操作后可翻到下一页；返回上一页不会重复请求接口。")
    st.divider()
    _page_controls(step, ready, "bottom")
