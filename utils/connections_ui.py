"""从内容发现作者：会话内收藏、讨论筹备与人工分享，不调用社交写接口。"""
import hashlib
import html
import json
from datetime import datetime, timezone
from urllib.parse import urlsplit

import streamlit as st


def safe_source(url):
    try:
        parsed = urlsplit(str(url or ""))
        host = (parsed.hostname or "").lower()
        if parsed.scheme == "https" and (host == "zhihu.com" or host.endswith(".zhihu.com")):
            return str(url)
    except ValueError:
        pass
    return ""


def render_connections(state):
    st.subheader("从喜欢的内容，发现值得交流的作者")
    st.info("候选卡按内容生成，不按昵称合并身份。相似度衡量内容，不衡量人与人的契合度。收藏仅保留在当前应用会话；邀请、关注和讨论需你在知乎核对后自行操作。")
    saved = st.session_state.setdefault("connection_bookmarks", {})
    topic = state["anchor"]["title"]
    base = state["pool"][state["base"]]
    eligible = [r for r in state["results"] if r["similarity"] > 0]
    if not eligible:
        st.warning("当前没有正相关内容，不生成作者推荐。可换一条兴趣内容再探索。")
    for result in eligible[:5]:
        profile = result["profile"]
        source = safe_source(profile.get("source_url"))
        author = profile.get("author_name") or "未提供作者昵称"
        title = profile["input_text"]
        # 无可靠作者 ID：以话题与内容为键，绝不按昵称推断同一用户。
        token = hashlib.sha256((topic + "\n" + (source or profile["search_content"])).encode("utf-8")).hexdigest()[:24]
        current_angles = set(profile.get("angles", []))
        additional = sorted(current_angles - set(base.get("angles", [])))
        question = f"关于“{topic}”，你认为这篇内容的结论适用于哪些场景？有没有例外或不同的实践经验？"
        invitation = f"你好，我在探索“{topic}”时读到了《{title}》，希望进一步了解你的思考。{question} 如果你愿意，期待在原文下交流；不方便也没关系。"
        card = {"key": token, "topic": topic, "author_display_name": author,
                "content_title": title, "source_url": source, "base_title": base["input_text"],
                "content_similarity": float(result["similarity"]), "retrieval_angles": sorted(current_angles),
                "opening_question": question, "invitation_draft": invitation,
                "identity_status": "未核验；此卡对应一条内容，不代表唯一用户", "delivery_status": "未发送"}
        with st.container(border=True):
            st.markdown(f"#### 内容作者候选 · 对象 {result['index'] + 1}")
            st.text(author)
            st.write(title)
            st.caption(f"内容相关分 {result['similarity']:.3f} · 依据你选择的《{base['input_text']}》")
            st.write("为什么推荐：这条摘要在当前话题池中，与所选内容有较高的词法相关性。尚不能推断你与作者的共同兴趣或观点一致。")
            st.write("可补充的检索视角：" + ("、".join(additional) if additional else "尚无额外检索角度证据"))
            st.caption("检索视角是召回渠道，不是作者的真实立场或经过分类的观点。")
            if source:
                st.link_button("前往知乎原文 · 核对作者并自行交流", source)
            else:
                st.warning("缺少可核对的知乎原文链接，暂不支持加入待联系名单。")
            edited = st.text_area(
                "邀请文案（可编辑后收藏或下载）",
                saved.get(token, {}).get("invitation_draft", invitation),
                key=f"invite_{token}",
            )
            card["invitation_draft"] = edited
            if st.button("更新本地收藏" if token in saved else "加入本地待联系名单", key=f"save_{token}", disabled=not source, type="primary"):
                previous = saved.get(token, {})
                saved[token] = {**card, "note": previous.get("note", ""), "status": previous.get("status", "待核对")}
                st.success("已保存在当前会话。未执行知乎关注或发送通知。")
            with st.expander("开场问题与邀请草稿"):
                st.write(question)
                st.caption("下载使用上方当前编辑内容；修改后请点击更新本地收藏以保存。")
                st.download_button("下载邀请草稿", edited, f"invitation_{token}.txt", "text/plain", key=f"invite_download_{token}")
            st.download_button("下载话题候选卡 JSON", json.dumps(card, ensure_ascii=False, indent=2), f"candidate_{token}.json", "application/json", key=f"card_{token}")

    st.divider()
    st.subheader("我的待联系名单与讨论筹备")
    st.caption("不同话题的收藏保留在本浏览器会话中；刷新或重启可能丢失。请下载备份，不保存他人的私人联系方式。状态是你手动记录的，不是知乎接口核验结果。")
    keys = list(saved)
    if not keys:
        st.info("先从候选卡收藏一条带原文链接的内容。")
        return
    chosen = st.selectbox("查看已收藏内容", keys, format_func=lambda key: f"{saved[key]['author_display_name']} · {saved[key]['content_title']}")
    item = saved[chosen]
    statuses = ["待核对", "准备交流", "已自行留言", "已自行收到回复", "暂不联系"]
    item["status"] = st.selectbox("手动进展记录", statuses, index=statuses.index(item.get("status", "待核对")), key=f"contact_status_{chosen}")
    item["note"] = st.text_area("我的交流笔记（不会发送给作者）", item.get("note", ""), key=f"contact_note_{chosen}")
    if st.button("移出待联系名单", key=f"remove_{chosen}"):
        del saved[chosen]
        st.rerun()
    st.download_button("备份全部收藏及交流笔记", json.dumps(list(saved.values()), ensure_ascii=False, indent=2), "connection_bookmarks.json", "application/json")

    topic_keys = [key for key in keys if saved[key]["topic"] == topic]
    selected = st.multiselect("选择本话题的讨论候选（按内容选择，不代表已入群）", topic_keys, format_func=lambda key: saved[key]["content_title"], key=f"group_selection_{state['revision']}")
    group_title = st.text_input("讨论主题", value=topic, key=f"group_title_{state['revision']}")
    agenda = st.text_area("讨论议程（规则草案，可编辑）", "1. 各自分享一条可核对的材料。\n2. 讨论结论成立的条件和反例。\n3. 总结共识、分歧和仍需验证的问题。", key=f"group_agenda_{state['revision']}")
    # 分享只白名单导出公开内容信息，不包含待联系名单中的私人笔记和进展。
    public_candidates = [
        {field: saved[key].get(field, "") for field in
         ("author_display_name", "content_title", "source_url", "identity_status")}
        for key in selected
    ]
    draft = {"title": group_title, "anchor": state["anchor"], "agenda": agenda,
             "candidate_contents": public_candidates, "created_at": datetime.now(timezone.utc).isoformat(),
             "status": "筹备草案，未邀请、未创建群聊、未验证参与意愿"}
    st.download_button("下载讨论筹备与分享卡", json.dumps(draft, ensure_ascii=False, indent=2), "discussion_draft.json", "application/json", disabled=not selected or not group_title.strip())
    st.caption("分享卡仅包含讨论主题、议程和公开来源，不包含你的交流笔记、手动状态或私人邀请草稿。")
    links = []
    for candidate in public_candidates:
        url = safe_source(candidate["source_url"])
        title_text = html.escape(str(candidate["content_title"]))
        label = html.escape(str(candidate["author_display_name"]))
        source_link = f'<a href="{html.escape(url, quote=True)}" target="_blank" rel="noopener noreferrer">阅读知乎原文</a>' if url else "暂无有效来源"
        links.append(f"<article><h3>{title_text}</h3><p>来源作者：{label}（身份未核验）</p>{source_link}</article>")
    share_html = (
        '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>看山 · 讨论邀请卡</title><style>'
        'body{font-family:system-ui,sans-serif;background:#edf3f7;color:#16324a;margin:0;padding:24px}'
        'main{max-width:820px;margin:auto}header,article,section{background:white;padding:24px;border-radius:18px;margin:16px 0}'
        'header{background:#123b59;color:white}h1{overflow-wrap:anywhere}pre{white-space:pre-wrap;font:inherit}'
        'a{color:#0868b2}footer{font-size:14px;line-height:1.8}</style></head><body><main>'
        f'<header><p>看山 · 一起讨论一个问题</p><h1>{html.escape(group_title)}</h1></header>'
        f'<section><h2>讨论议程</h2><pre>{html.escape(agenda)}</pre></section>'
        '<h2>建议阅读的公开材料</h2>' + "".join(links) +
        '<footer>这是讨论筹备草案，所列作者并未确认参与。请先征得参与同意；本卡不代表已发送邀请或已创建群聊。'
        '文本相关性不代表立场一致。请回到原文核对背景并尊重作者。</footer></main></body></html>'
    )
    st.download_button("下载可分享的 HTML 话题卡", share_html, "discussion_share.html", "text/html", disabled=not selected or not group_title.strip())
    if st.button("保存本次讨论草案到会话", disabled=not selected or not group_title.strip(), type="primary"):
        state["discussion_draft"] = draft
        st.success("已保存公开版草案，未发送邀请。")
    st.caption("真实群聊、多用户对话、OAuth 身份绑定和持久化关系管理尚未接入。请先获得对方参与同意，再在合适的平台组织讨论。")
