import sys
import time
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))
import api_client as api  # noqa: E402
from helpers import MODE_LABELS, MODES, safe_markdown, source_label, status_text  # noqa: E402

st.set_page_config(page_title="DocMind", layout="wide")

MAX_UPLOAD_MB = 20


def init_state() -> None:
    st.session_state.setdefault("token", None)
    st.session_state.setdefault("email", None)
    st.session_state.setdefault("messages", [])
    st.session_state.setdefault("notice", None)
    st.session_state.setdefault("uploader_n", 0)


def logout(message: str | None = None) -> None:
    st.session_state["token"] = None
    st.session_state["email"] = None
    st.session_state["messages"] = []
    st.session_state["notice"] = message
    st.rerun()

def auth_view() -> None:
    st.title("DocMind")
    st.caption("Ask questions about your own PDF and DOCX files. Every answer comes with page citations.")
    if st.session_state.get("notice"):
        st.warning(st.session_state["notice"])
        st.session_state["notice"] = None

    login_tab, register_tab = st.tabs(["Log in", "Create account"])
    with login_tab:
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Log in")
        if submitted:
            try:
                token = api.login(email.strip(), password)
            except api.ApiError as e:
                st.error(str(e))
            else:
                st.session_state["token"] = token
                st.session_state["email"] = email.strip()
                st.rerun()

    with register_tab:
        with st.form("register_form"):
            email = st.text_input("Email", key="reg_email")
            password = st.text_input("Password (8 to 72 characters)", type="password", key="reg_password")
            submitted = st.form_submit_button("Create account")
        if submitted:
            try:
                api.register(email.strip(), password)
                token = api.login(email.strip(), password)
            except api.ApiError as e:
                st.error(str(e))
            else:
                st.session_state["token"] = token
                st.session_state["email"] = email.strip()
                st.rerun()

def wait_until_ready(token: str, doc_id: int, timeout: int = 180) -> None:
    with st.status("Reading, chunking and embedding your document...", expanded=True) as status:
        started = time.time()
        while time.time() - started < timeout:
            try:
                doc = api.get_document(token, doc_id)
            except api.ApiError as e:
                status.update(label="Could not check status", state="error")
                st.error(str(e))
                return
            if doc["status"] == "ready":
                status.update(label=f"Ready: {doc['filename']} ({doc['chunks']} chunks)", state="complete")
                return
            if doc["status"] == "failed":
                status.update(label="Processing failed", state="error")
                st.error(doc.get("error") or "Unknown error")
                return
            time.sleep(2)
        status.update(label="Still processing. Refresh the page in a minute.", state="running")


def documents_view(token: str, docs: list[dict]) -> None:
    st.subheader("Your documents")
    upload = st.file_uploader(
        f"Upload a PDF or DOCX (max {MAX_UPLOAD_MB} MB)",
        type=["pdf", "docx"],
        key=f"uploader_{st.session_state['uploader_n']}",
    )
    if upload is not None and st.button("Process document", type="primary"):
        data = upload.getvalue()
        if len(data) > MAX_UPLOAD_MB * 1024 * 1024:
            st.error(f"File is larger than {MAX_UPLOAD_MB} MB.")
        else:
            try:
                created = api.upload_document(token, upload.name, data)
            except api.ApiError as e:
                st.error(str(e))
            else:
                wait_until_ready(token, created["id"])
                st.session_state["uploader_n"] += 1
                time.sleep(1)
                st.rerun()

    if not docs:
        st.info("No documents yet. Upload one to get started.")
        return
    if st.button("Refresh list"):
        st.rerun()
    for d in docs:
        c1, c2, c3, c4 = st.columns([5, 2, 2, 1])
        c1.write(d["filename"])
        c2.write(status_text(d))
        c3.write(f"{d['chunks']} chunks")
        if c4.button("Delete", key=f"delete_{d['id']}"):
            try:
                api.delete_document(token, d["id"])
            except api.ApiError as e:
                st.error(str(e))
            else:
                st.rerun()
        if d["status"] == "failed" and d.get("error"):
            st.caption(f"Error: {d['error']}")

def render_sources(msg: dict) -> None:
    sources = msg.get("sources") or []
    meta = msg.get("meta", "")
    if sources:
        with st.expander(f"Sources ({len(sources)})"):
            for s in sources:
                st.markdown(f"**{source_label(s)}**")
                st.caption(safe_markdown(s["snippet"]))
        if not msg.get("cited"):
            st.warning("The model did not cite specific chunks. These are the excerpts it was given.")
    if meta:
        st.caption(meta)


def render_message(msg: dict) -> None:
    with st.chat_message(msg["role"]):
        st.markdown(safe_markdown(msg["content"]))
        if msg["role"] == "assistant":
            render_sources(msg)


def chat_view(token: str, docs: list[dict]) -> None:
    ready = [d for d in docs if d["status"] == "ready"]
    if not ready:
        st.info("Upload a document in the Documents tab, then ask questions here.")
        return
    names = {d["id"]: d["filename"] for d in ready}

    with st.expander("Search settings"):
        mode = st.selectbox(
            "Retrieval mode", MODES, index=MODES.index("hybrid_rerank"), format_func=MODE_LABELS.get
        )
        top_k = st.slider("Excerpts sent to the model", 3, 8, 5)
        selected = st.multiselect(
            "Limit to documents (empty means all)", list(names), format_func=names.get
        )

    for msg in st.session_state["messages"]:
        render_message(msg)

    question = st.chat_input("Ask about your documents")
    if not question:
        return

    user_msg = {"role": "user", "content": question}
    st.session_state["messages"].append(user_msg)
    render_message(user_msg)
    with st.chat_message("assistant"):
        with st.spinner("Searching your documents..."):
            try:
                result = api.ask(token, question, mode, top_k, selected or None)
            except api.ApiError as e:
                if e.status == 401:
                    logout("Your session expired. Please log in again.")
                st.error(f"Could not get an answer: {e}")
                st.session_state["messages"].pop()
                return
    reply = {
        "role": "assistant",
        "content": result["answer"],
        "sources": result.get("sources", []),
        "cited": result.get("cited", False),
        "meta": f"{MODE_LABELS[mode].split(' (')[0]} | {result.get('latency_ms', 0) / 1000:.1f}s",
    }
    st.session_state["messages"].append(reply)
    st.rerun()

def main() -> None:
    init_state()
    if not st.session_state["token"]:
        auth_view()
        return

    token = st.session_state["token"]
    with st.sidebar:
        st.write(st.session_state["email"])
        if st.button("Log out"):
            logout()
        if st.button("Clear chat"):
            st.session_state["messages"] = []
            st.rerun()

    try:
        docs = api.list_documents(token)
    except api.ApiError as e:
        if e.status == 401:
            logout("Your session expired. Please log in again.")
        st.error(str(e))
        return

    st.title("DocMind")
    chat_tab, docs_tab = st.tabs(["Chat", "Documents"])
    with docs_tab:
        documents_view(token, docs)
    with chat_tab:
        chat_view(token, docs)


main()

