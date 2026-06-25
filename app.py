import json
import os
import tempfile
import uuid
import base64
from datetime import datetime
from pathlib import Path

def get_image_base64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

import streamlit as st
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from backend.btw_handler import handle_btw
from backend.paper_loader import load_arxiv, load_document, load_webpage
from backend.rag_graph import build_graph
from backend.vector_store import add_paper, list_papers, delete_paper

st.set_page_config(page_title="Papeer", page_icon="📚", layout="centered")

# Premium CSS UI/UX overrides from external stylesheet
if os.path.exists("static/style.css"):
    with open("static/style.css", "r", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


@st.cache_resource
def get_graph():
    return build_graph()


SESSIONS_FILE = Path("sessions.json")
_rename_llm = ChatOpenAI(
    model="llama-3.1-8b-instant",
    openai_api_key=os.environ["GROQ_API_KEY"],
    openai_api_base="https://api.groq.com/openai/v1",
    temperature=0.1,
)


def load_sessions() -> dict:
    try:
        return json.loads(SESSIONS_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_sessions(sessions_meta: dict) -> None:
    SESSIONS_FILE.write_text(json.dumps(sessions_meta, indent=2), encoding="utf-8")


def _serialize_state(values: dict) -> dict:
    out = {}
    for k, v in values.items():
        if k == "messages":
            out[k] = [
                {
                    "type": type(m).__name__,
                    "content": (
                        m.content[:300]
                        if isinstance(m.content, str)
                        else repr(m.content)[:300]
                    ),
                }
                for m in (v or [])
            ]
        elif k == "retrieved_docs":
            out[k] = [
                {"content": d.page_content[:300], "metadata": d.metadata}
                for d in (v or [])
            ]
        else:
            out[k] = v
    return out


def generate_session_name(first_message: str) -> str:
    try:
        response = _rename_llm.invoke(
            [
                {
                    "role": "system",
                    "content": (
                        "Generate a concise 3-5 word title for a research chat session "
                        "based on the user's first message. Return only the title, "
                        "no punctuation at the end, no quotes."
                    ),
                },
                {"role": "user", "content": first_message[:500]},
            ]
        )
        return response.content.strip()
    except Exception:
        return "New Session"


def maybe_rename_session(session_id: str, first_message: str) -> None:
    if st.session_state.sessions_meta.get(session_id, {}).get("is_named"):
        return
    name = generate_session_name(first_message)
    st.session_state.sessions_meta[session_id]["name"] = name
    st.session_state.sessions_meta[session_id]["is_named"] = True
    save_sessions(st.session_state.sessions_meta)


def create_session() -> str:
    sid = str(uuid.uuid4())
    st.session_state.sessions_meta[sid] = {
        "id": sid,
        "name": "New Session",
        "created_at": datetime.now().isoformat(),
        "is_named": False,
    }
    save_sessions(st.session_state.sessions_meta)
    st.session_state.chats[sid] = []
    st.session_state.turns[sid] = 0
    return sid


def delete_session(session_id: str) -> None:
    if session_id in st.session_state.sessions_meta:
        del st.session_state.sessions_meta[session_id]
        save_sessions(st.session_state.sessions_meta)
    if session_id in st.session_state.chats:
        del st.session_state.chats[session_id]
    if session_id in st.session_state.turns:
        del st.session_state.turns[session_id]

    try:
        from backend.vector_store import delete_session_collection
        delete_session_collection(session_id)
    except Exception as e:
        st.sidebar.error(f"Failed to clear vector store: {e}")

    import sqlite3
    try:
        conn = sqlite3.connect("checkpoints.db")
        cursor = conn.cursor()
        for table in ["checkpoints", "checkpoint_writes", "checkpoint_blobs"]:
            try:
                cursor.execute(f"DELETE FROM {table} WHERE thread_id = ?", (session_id,))
            except sqlite3.OperationalError:
                pass
        conn.commit()
        conn.close()
    except Exception as e:
        st.sidebar.error(f"Failed to clear checkpoints: {e}")


def load_session_chats(session_id: str) -> list[dict]:
    config = {
        "configurable": {"thread_id": session_id},
        "metadata": {"session_id": session_id}
    }
    try:
        state = graph.get_state(config)
        if not state or not state.values:
            return []
        chats = []
        turn = 0
        for msg in state.values.get("messages", []):
            type_name = type(msg).__name__
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            if type_name == "HumanMessage":
                chats.append({"role": "user", "content": content})
            elif type_name in ("AIMessage", "AIMessageChunk"):
                turn += 1
                chats.append({"role": "assistant", "content": content, "turn": turn, "graph_state": {}})
        return chats
    except Exception:
        return []


def switch_session(session_id: str) -> None:
    st.session_state.active_session_id = session_id
    if session_id not in st.session_state.chats:
        st.session_state.chats[session_id] = load_session_chats(session_id)
    if session_id not in st.session_state.turns:
        turn_count = sum(1 for m in st.session_state.chats[session_id] if m["role"] == "assistant")
        st.session_state.turns[session_id] = turn_count


graph = get_graph()

# ── Bootstrap ──────────────────────────────────────────────────────────────────
if "sessions_meta" not in st.session_state:
    st.session_state.sessions_meta = load_sessions()
if "chats" not in st.session_state:
    st.session_state.chats = {}
if "turns" not in st.session_state:
    st.session_state.turns = {}
if "active_session_id" not in st.session_state:
    if st.session_state.sessions_meta:
        latest = max(
            st.session_state.sessions_meta.values(),
            key=lambda s: s["created_at"],
        )
        switch_session(latest["id"])
    else:
        sid = create_session()
        st.session_state.active_session_id = sid

active_sid = st.session_state.active_session_id

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    # Logo container
    if os.path.exists("papeer_logo.jpg"):
        img_b64 = get_image_base64("papeer_logo.jpg")
        st.markdown(
            f'''
            <div class="logo-container">
                <img class="logo-image" src="data:image/jpeg;base64,{img_b64}" alt="Papeer Logo">
                <div style="font-family:\'Outfit\'; font-weight:800; font-size:1.4rem; margin-top:10px; color:#f3f4f6;">Papeer</div>
                <div style="font-size:0.7rem; color:#a78bfa; font-weight: 600; letter-spacing:1.5px; margin-top:2px;">AI RESEARCH CO-PILOT</div>
            </div>
            ''',
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            '''
            <div class="logo-container">
                <div style="width:90px;height:90px;border-radius:50%;background:#8b5cf6;display:flex;align-items:center;justify-content:center;color:#fff;font-weight:bold;font-size:1.5rem;box-shadow:0 0 20px rgba(139,92,246,0.4)">📚</div>
                <div style="font-family:\'Outfit\'; font-weight:800; font-size:1.4rem; margin-top:10px; color:#f3f4f6;">Papeer</div>
                <div style="font-size:0.7rem; color:#a78bfa; font-weight: 600; letter-spacing:1.5px; margin-top:2px;">AI RESEARCH CO-PILOT</div>
            </div>
            ''',
            unsafe_allow_html=True
        )

    if st.button("+ New Chat", use_container_width=True):
        new_sid = create_session()
        st.session_state.active_session_id = new_sid
        active_sid = new_sid
        st.rerun()
    st.divider()
    st.markdown("## 💬 Sessions")

    sorted_sessions = sorted(
        st.session_state.sessions_meta.values(),
        key=lambda s: s["created_at"],
        reverse=True,
    )
    for session in sorted_sessions:
        sid = session["id"]
        is_active = sid == st.session_state.active_session_id
        btn_type = "primary" if is_active else "secondary"
        cols = st.columns([0.8, 0.2])
        with cols[0]:
            if st.button(
                session["name"],
                key=f"sess_{sid}",
                use_container_width=True,
                type=btn_type,
            ):
                if not is_active:
                    switch_session(sid)
                    st.rerun()
        with cols[1]:
            if st.button("🗑️", key=f"del_sess_{sid}", use_container_width=True):
                delete_session(sid)
                if is_active:
                    if st.session_state.sessions_meta:
                        latest = max(
                            st.session_state.sessions_meta.values(),
                            key=lambda s: s["created_at"],
                        )
                        switch_session(latest["id"])
                    else:
                        new_sid = create_session()
                        switch_session(new_sid)
                st.rerun()


    st.divider()
    st.markdown("## 📄 Documents")

    # ── Section 1: File upload ─────────────────────────────────────────────────
    st.markdown("**Upload Files**")
    uploaded_files = st.file_uploader(
        "PDF, TXT, or Markdown",
        type=["pdf", "txt", "md", "markdown"],
        accept_multiple_files=True,
        key=f"uploader_{active_sid}",
        label_visibility="collapsed",
    )
    if st.button("Add Files", use_container_width=True, key="btn_add_files"):
        if uploaded_files:
            processed_key = f"processed_files_{active_sid}"
            if processed_key not in st.session_state:
                st.session_state[processed_key] = set()
            with st.spinner("Processing files…"):
                for f in uploaded_files:
                    if f.name in st.session_state[processed_key]:
                        st.info(f"Already loaded: {f.name}")
                        continue
                    suffix = Path(f.name).suffix
                    tmp_path = None
                    try:
                        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                            tmp.write(f.read())
                            tmp_path = tmp.name
                        docs = load_document(tmp_path)
                        for doc in docs:
                            doc.metadata["title"] = Path(f.name).stem
                        add_paper(docs, active_sid)
                        st.session_state[processed_key].add(f.name)
                        st.success(f"Added: {f.name}")
                    except Exception as e:
                        st.error(f"Failed: {f.name} — {e}")
                    finally:
                        if tmp_path:
                            Path(tmp_path).unlink(missing_ok=True)
            st.rerun()
        else:
            st.warning("No files selected.")

    # ── Section 2: Web URL loader ──────────────────────────────────────────────
    st.markdown("**Web Pages**")
    url_input = st.text_area(
        "URLs (one per line)",
        key=f"url_area_{active_sid}",
        height=80,
        label_visibility="collapsed",
        placeholder="https://example.com/paper",
    )
    if st.button("Load URLs", use_container_width=True, key="btn_load_urls"):
        urls = [u.strip() for u in url_input.splitlines() if u.strip()]
        if urls:
            with st.spinner("Loading web pages…"):
                for url in urls:
                    try:
                        docs = load_webpage(url)
                        add_paper(docs, active_sid)
                        st.success(f"Loaded: {url[:60]}")
                    except Exception as e:
                        st.error(f"Failed: {url[:60]} — {e}")
            st.rerun()
        else:
            st.warning("Enter at least one URL.")

    # ── Section 3: ArXiv loader ────────────────────────────────────────────────
    st.markdown("**ArXiv Papers**")
    arxiv_title = st.text_input(
        "Paper title or ArXiv ID",
        key=f"arxiv_input_{active_sid}",
        label_visibility="collapsed",
        placeholder="1706.03762  or  Attention Is All You Need",
    )
    if st.button("Load ArXiv Paper", use_container_width=True, key="btn_load_arxiv"):
        if arxiv_title.strip():
            with st.spinner("Loading from ArXiv…"):
                try:
                    docs = load_arxiv(arxiv_title.strip())
                    add_paper(docs, active_sid)
                    loaded_title = docs[0].metadata.get("title") if docs else arxiv_title.strip()
                    st.success(f"Loaded: {loaded_title}")
                except Exception as e:
                    st.error(f"Failed: {e}")
            st.rerun()
        else:
            st.warning("Enter a paper title or ArXiv ID.")

    # ── Loaded Documents list ──────────────────────────────────────────────────
    st.divider()
    st.markdown("### Loaded Documents")
    try:
        doc_titles = list_papers(active_sid)
    except Exception:
        doc_titles = None
    if doc_titles is None:
        st.caption("Could not load document list — try refreshing.")
    elif doc_titles:
        for title in doc_titles:
            cols = st.columns([0.8, 0.2])
            with cols[0]:
                disp_title = f"{title[:22]}..." if len(title) > 25 else title
                st.markdown(f"<div class='doc-pill' title='{title}'>📄 {disp_title}</div>", unsafe_allow_html=True)
            with cols[1]:
                if st.button("🗑️", key=f"del_doc_{active_sid}_{title}", use_container_width=True):
                    try:
                        delete_paper(title, active_sid)
                        processed_key = f"processed_files_{active_sid}"
                        if processed_key in st.session_state and title in st.session_state[processed_key]:
                            st.session_state[processed_key].remove(title)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to delete: {e}")
    else:
        st.caption("No documents loaded yet.")

    # ── Quick Help Guide ─────────────────────────────────────────────────────────
    st.divider()
    with st.expander("ℹ️ Features & Commands Guide", expanded=False):
        st.markdown(
            """
            <div style="font-size:0.85rem; line-height:1.5; color:#cbd5e1;">
            <b>💬 Paper Q&A:</b> Ask questions normally to search your uploaded PDF/Text/ArXiv papers. Uses Hybrid Retrieval (Dense Vector + BM25).<br><br>
            <b>🔍 Cohere Reranking:</b> Automatically re-scores retrieved snippets using <code>rerank-english-v3.0</code> to filter irrelevant details.<br><br>
            <b>⚡ /btw Command:</b> Start a prompt with <code>/btw</code> (e.g., <i>/btw what is softplus?</i>) to chat directly with the AI, bypassing documents.<br><br>
            <b>🛡️ Double Guardrails:</b> Automatically validates input queries (anti-injection check) and output answers (hallucination check).
            </div>
            """,
            unsafe_allow_html=True
        )


# ── Page header ────────────────────────────────────────────────────────────────
if os.path.exists("papeer_logo.jpg"):
    img_b64 = get_image_base64("papeer_logo.jpg")
    logo_html = f'<img class="hero-logo" src="data:image/jpeg;base64,{img_b64}" alt="Papeer Logo">'
else:
    logo_html = '<div style="width:64px;height:64px;border-radius:14px;background:#8b5cf6;display:flex;align-items:center;justify-content:center;color:#fff;font-weight:bold;font-size:1.5rem;box-shadow:0 0 15px rgba(139,92,246,0.4);">📚</div>'

st.markdown(
    f'''
    <div class="hero-container" style="margin-bottom: 15px;">
        <div class="hero-header-row" style="margin-bottom: 0;">
            {logo_html}
            <div class="hero-title-group">
                <h1 class="main-title" style="margin:0; font-size: 2.1rem; line-height: 1;">Papeer</h1>
                <p class="hero-slogan">Your Intelligent AI Research Co-pilot</p>
                <div style="display:flex; gap:8px; margin-top:8px; flex-wrap:wrap;">
                    <span style="font-size:0.72rem; background:rgba(139,92,246,0.1); border:1px solid rgba(139,92,246,0.25); color:#c084fc; padding:2px 8px; border-radius:4px; font-weight:600; font-family:\'Inter\';">⚡ Cohere Rerank v3</span>
                    <span style="font-size:0.72rem; background:rgba(139,92,246,0.1); border:1px solid rgba(139,92,246,0.25); color:#c084fc; padding:2px 8px; border-radius:4px; font-weight:600; font-family:\'Inter\';">📦 Qdrant Hybrid</span>
                    <span style="font-size:0.72rem; background:rgba(139,92,246,0.1); border:1px solid rgba(139,92,246,0.25); color:#c084fc; padding:2px 8px; border-radius:4px; font-weight:600; font-family:\'Inter\';">📊 LangSmith Traced</span>
                    <span style="font-size:0.72rem; background:rgba(139,92,246,0.1); border:1px solid rgba(139,92,246,0.25); color:#c084fc; padding:2px 8px; border-radius:4px; font-weight:600; font-family:\'Inter\';">🧪 DeepEval Measured</span>
                    <span style="font-size:0.72rem; background:rgba(139,92,246,0.1); border:1px solid rgba(139,92,246,0.25); color:#c084fc; padding:2px 8px; border-radius:4px; font-weight:600; font-family:\'Inter\';">🌐 Tavily Search</span>
                    <span style="font-size:0.72rem; background:rgba(139,92,246,0.1); border:1px solid rgba(139,92,246,0.25); color:#c084fc; padding:2px 8px; border-radius:4px; font-weight:600; font-family:\'Inter\';">🛡️ Dual Guardrails</span>
                </div>
            </div>
        </div>
    </div>
    ''',
    unsafe_allow_html=True
)

st.markdown(
    '''
    <div class="features-container" style="background: rgba(30, 27, 75, 0.2); border: 1px solid rgba(139, 92, 246, 0.15); border-radius: 16px; padding: 20px; margin-bottom: 25px; backdrop-filter: blur(8px); box-shadow: 0 8px 24px rgba(0,0,0,0.2);">
        <div class="features-grid" style="margin-top: 0;">
            <div class="feature-card">
                <span class="feature-icon">🔍</span>
                <div class="feature-text">
                    <strong>Ask Papers</strong>
                    <p>Performs semantic retrieval across Qdrant vector databases and BM25 local keyword indices using an EnsembleRetriever (0.7 dense / 0.3 sparse). Documents are dynamically re-ranked via Cohere, validated by Guardrails, and traced in LangSmith.</p>
                </div>
            </div>
            <div class="feature-card">
                <span class="feature-icon">✅</span>
                <div class="feature-text">
                    <strong>Verify Claims</strong>
                    <p>Extracts claims, expands them into target queries, and executes concurrent web queries on general engines and site-specific databases (arxiv.org) using Tavily to check for supporting/contradicting preprints, reviews, or literature.</p>
                </div>
            </div>
            <div class="feature-card">
                <span class="feature-icon">🌐</span>
                <div class="feature-text">
                    <strong>Web Search</strong>
                    <p>Integrates the Tavily search engine directly into the chat flow. Prefix any prompt with <code>/btw</code> to initiate a fast web query or chat session that bypasses the uploaded document stores and context memory limits.</p>
                </div>
            </div>
        </div>
    </div>
    ''',
    unsafe_allow_html=True
)

# ── Chat display ───────────────────────────────────────────────────────────────
chat_history = st.session_state.chats.get(active_sid, [])
for msg in chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant":
            with st.expander(f"📊 Graph state · turn {msg['turn']}", expanded=False):
                st.json(msg["graph_state"])

# Premium Quick Actions welcoming screen
action_prompt = None
if not chat_history:
    st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)
    st.markdown("### ⚡ Quick Start Prompts")
    cols_actions = st.columns(3)
    with cols_actions[0]:
        if st.button("🛡️ Verify Claim\n\nLSTMs vs Transformers", use_container_width=True, key="qa_btn_1"):
            action_prompt = "Verify claim: LSTMs outperform Transformers for long-context recall."
    with cols_actions[1]:
        if st.button("🌐 Search the Web\n\nLatest AI releases", use_container_width=True, key="qa_btn_2"):
            action_prompt = "/btw What are the latest releases in generative AI?"
    with cols_actions[2]:
        if st.button("📊 Ask Papers\n\nCore methodology", use_container_width=True, key="qa_btn_3"):
            action_prompt = "Summarize the core methodology and findings of the loaded documents."

# ── Chat input ─────────────────────────────────────────────────────────────────
prompt_input = st.chat_input("Ask about your papers, verify a claim, or search the web…")
prompt = prompt_input or action_prompt

if prompt:
    is_btw = prompt.strip().lower().startswith("/btw")

    if is_btw:
        query = prompt.strip()[4:].strip()

        with st.chat_message("user"):
            st.markdown(prompt)
            st.caption("Side channel — not saved to session history.")

        with st.chat_message("assistant"):
            if not query:
                st.markdown("Please add a question after `/btw`, e.g. `/btw What is attention?`")
            else:
                placeholder = st.empty()
                response_text = ""
                for chunk in handle_btw(query):
                    response_text += chunk
                    placeholder.markdown(response_text + "▌")
                placeholder.markdown(response_text)
            st.caption("Side channel — not saved to session history.")

    else:
        if active_sid not in st.session_state.chats:
            st.session_state.chats[active_sid] = []
        if active_sid not in st.session_state.turns:
            st.session_state.turns[active_sid] = 0

        is_first_message = len(st.session_state.chats[active_sid]) == 0

        with st.chat_message("user"):
            st.markdown(prompt)
        st.session_state.chats[active_sid].append({"role": "user", "content": prompt})
        st.session_state.turns[active_sid] += 1
        current_turn = st.session_state.turns[active_sid]

        if is_first_message:
            maybe_rename_session(active_sid, prompt)

        input_state = {
            "messages": [HumanMessage(content=prompt)],
            "session_id": active_sid,
            "query": prompt,
            "route": None,
            "retrieved_docs": [],
            "retrieval_attempts": 0,
            "claim_verdict": None,
            "claim_source": None,
            "superseding_papers": [],
            "answer": None,
            "is_relevant": None,
            "rewrite_count": 0,
            "cohere_log": None,
        }
        config = {
            "configurable": {"thread_id": active_sid},
            "metadata": {"session_id": active_sid}
        }

        with st.chat_message("assistant"):
            placeholder = st.empty()
            response_text = ""

            for chunk, metadata in graph.stream(input_state, config, stream_mode="messages"):
                if (
                    metadata.get("langgraph_node") == "generate_answer"
                    and hasattr(chunk, "content")
                    and chunk.content
                ):
                    response_text += chunk.content
                    placeholder.markdown(response_text + "▌")

            if not response_text:
                final_values = graph.get_state(config).values
                response_text = final_values.get("answer") or "No response generated."

            placeholder.markdown(response_text)

            final_values = graph.get_state(config).values
            
            if final_values.get("cohere_log"):
                st.caption(f"🔍 **Cohere Rerank Log:** {final_values.get('cohere_log')}")

            state_snapshot = _serialize_state(final_values)

            with st.expander(f"📊 Graph state · turn {current_turn}", expanded=False):
                st.json(state_snapshot)

        st.session_state.chats[active_sid].append(
            {
                "role": "assistant",
                "content": response_text,
                "graph_state": state_snapshot,
                "turn": current_turn,
            }
        )

        if is_first_message:
            st.rerun()
