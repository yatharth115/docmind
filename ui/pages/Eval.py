import json
from pathlib import Path

import pandas as pd
import streamlit as st

RESULTS_DIR = Path("eval/results")
LABELS = {
    "vector": "Vector only",
    "keyword": "Keyword only",
    "hybrid": "Hybrid (RRF)",
    "hybrid_rerank": "Hybrid + rerank",
}

st.set_page_config(page_title="DocMind Eval", layout="wide")
st.title("DocMind: retrieval evaluation")

files = sorted(RESULTS_DIR.glob("*.json"), reverse=True)
if not files:
    st.warning("No results yet. Run: python -m eval.run_eval")
    st.stop()

choice = st.sidebar.selectbox("Results file", files, format_func=lambda p: p.name)
data = json.loads(choice.read_text(encoding="utf-8"))
meta, modes = data["meta"], data["modes"]
mode_names = meta["modes"]

st.caption(
    f"{meta['n_questions']} questions {meta['types']} | {meta['n_chunks']} chunks "
    f"(size {meta['chunk_size']} words, overlap {meta['overlap']}) | "
    f"{len(meta['files'])} documents | top_k {meta['top_k']} | {meta['created_at']}"
)
st.info(
    "Small test set: a gap of a few questions can be noise. "
    "Read the confidence interval before claiming one mode is better."
)

# 1. Summary
rows = []
for m in mode_names:
    s = modes[m]["summary"]
    lo, hi = modes[m]["hit5_ci"]
    rows.append({
        "Mode": LABELS[m],
        "Hit@1": s["hit@1"],
        "Hit@3": s["hit@3"],
        "Hit@5": s["hit@5"],
        "Hit@5 95% CI": f"{lo:.2f} to {hi:.2f}",
        "Recall@5": s["recall@5"],
        "MRR": s["mrr"],
        "Latency p50 (ms)": s["latency_p50_ms"],
        "Latency p95 (ms)": s["latency_p95_ms"],
    })
df = pd.DataFrame(rows).set_index("Mode")
st.subheader("Summary")
st.dataframe(df.round(3), width="stretch")
st.bar_chart(df[["Hit@1", "Hit@3", "Hit@5"]])

# 2. By question type
st.subheader("Hit@5 by question type")
types = sorted({r["type"] for r in modes[mode_names[0]]["records"]})
by_type = {}
for m in mode_names:
    recs = modes[m]["records"]
    by_type[LABELS[m]] = {
        t: sum(r["hit@5"] for r in recs if r["type"] == t) / max(1, sum(1 for r in recs if r["type"] == t))
        for t in types
    }
st.dataframe(pd.DataFrame(by_type).T.round(3), width="stretch")

# 3. Head to head
st.subheader("Head to head (Hit@5)")
c1, c2 = st.columns(2)
a = c1.selectbox("Mode A", mode_names, index=0, format_func=LABELS.get)
b = c2.selectbox("Mode B", mode_names, index=len(mode_names) - 1, format_func=LABELS.get)
rec_a = {r["id"]: r for r in modes[a]["records"]}
rec_b = {r["id"]: r for r in modes[b]["records"]}
only_a = [i for i in rec_a if rec_a[i]["hit@5"] and not rec_b[i]["hit@5"]]
only_b = [i for i in rec_a if rec_b[i]["hit@5"] and not rec_a[i]["hit@5"]]
m1, m2, m3 = st.columns(3)
m1.metric(f"Only {LABELS[a]} found", len(only_a))
m2.metric(f"Only {LABELS[b]} found", len(only_b))
m3.metric("Both found or both missed", len(rec_a) - len(only_a) - len(only_b))
with st.expander("Which questions?"):
    st.write(f"Only {LABELS[a]}:", only_a or "none")
    st.write(f"Only {LABELS[b]}:", only_b or "none")

# 4. Failures
st.subheader("Failures (gold page not in top 5)")
mode = st.selectbox("Mode", mode_names, index=len(mode_names) - 1, format_func=LABELS.get, key="fail_mode")
failed = [r for r in modes[mode]["records"] if not r["hit@5"]]
st.write(f"{len(failed)} of {len(modes[mode]['records'])} questions missed.")
for r in failed:
    with st.expander(f"{r['id']} [{r['type']}] {r['question']}"):
        st.write(f"Gold: {r['file']} pages {r['pages']}")
        st.dataframe(
            pd.DataFrame(r["top"])[["rank", "file", "page", "hit", "text"]],
            width="stretch",
        )
