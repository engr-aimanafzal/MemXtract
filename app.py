from __future__ import annotations
import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
"""Paper Research Agent - Streamlit app (light / dark, colored tables, charts).
Pages: Ask (library / global) · Extract records · Records · Data check
All API keys come from Streamlit secrets. Nothing secret is stored in the code.
"""
from __future__ import annotations

import re

import pandas as pd
import streamlit as st

from core import agent, config, data_loader, extractor, global_search, llm, record_store, schema
from core.embedder import QueryEmbedder
from core.hybrid_index import HybridStore
from ui import charts as G
from ui import components as C
from ui import theme

st.set_page_config(page_title="MemXtract", page_icon="🧪", layout="wide")
record_store.init_db()

MODE_LIB = "📚 Search my library"
MODE_GLO = "🌍 Search globally"
PAGES = ["💬 Ask", "🧪 Extract records", "📊 Records", "🩺 Data check"]


# ----------------------------------------------------------------------------- cached resources
@st.cache_resource(show_spinner="Loading your library...")
def load_library():
    lib = data_loader.load_library()
    store = HybridStore(lib.chunks, lib.embeddings, lib.pages) if lib.ok else None
    return lib, store


@st.cache_resource(show_spinner="Loading the embedding model (the first start downloads it)...")
def load_embedder():
    return QueryEmbedder(config.embedding_model_name(), config.embedding_backend(), config.query_prefix())


def md_inline(text: str) -> str:
    """Tiny markdown -> HTML for the hint texts (bold / italic only)."""
    text = C.esc(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    return re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)


def show(html: str):
    if html:
        st.markdown(html, unsafe_allow_html=True)


def records_csv(records: list) -> str:
    df = pd.DataFrame(records)
    cols = [c for c in schema.DISPLAY_COLUMNS if c in df.columns]
    return df[cols].to_csv(index=False)


# ----------------------------------------------------------------------------- sidebar + theme
def sidebar():
    if "dark" not in st.session_state:
        try:
            st.session_state["dark"] = st.query_params.get("theme") == "dark"
        except Exception:
            st.session_state["dark"] = False
    lib, _ = load_library()
    with st.sidebar:
        show('<div class="rg-brand"><span class="logo">🧪</span>MemXtract</div>')
        dark = st.toggle("🌙 Dark mode", key="dark")
        page = st.radio("Navigate", PAGES, label_visibility="collapsed", key="page")
        st.divider()
        providers = llm.configured_providers()
        chips = []
        chips.append(C.badge(f"{lib.stats['chunks']} chunks · {lib.stats['papers']} papers", C.GOOD) if lib.ok else C.badge("library not loaded", C.WARN))
        chips.append(C.badge(f"{record_store.count()} records", C.BLUE))
        chips.append(C.badge("LLM: " + ", ".join(providers), C.GOOD) if providers else C.badge("no LLM key", C.BAD))
        show("<div>" + "".join(chips) + "</div>")
        if page == PAGES[0] and any(st.session_state.get("messages", {}).values()):
            if st.button("🗑 Clear conversation", key="clear_chat"):
                st.session_state["messages"] = {MODE_LIB: [], MODE_GLO: []}
                st.rerun()
    show(theme.css(dark))
    return dark, page


def library_problems(lib):
    show(C.note("<b>Your library files are not ready yet.</b><br>" + "<br>".join("• " + C.esc(e) for e in lib.errors), "bad"))
    show(C.steps([
        ("Build the files in Google Colab", "Run <b>pdf_to_embeddings.ipynb</b> (last cell exports the app files).", False),
        ("Add them to your repo", "Put <code>chunks.jsonl</code>, <code>embeddings.npy</code>, <code>embedding_info.json</code> "
                                  "(and <code>pages.json</code>) in <code>data/imported/</code>.", False),
        ("Reboot the app", "Then open <b>Data check</b> to confirm everything loads.", False),
    ]))


# ----------------------------------------------------------------------------- rendering of answers
def render_library(out: dict, key: str, dark: bool, papers: dict):
    recs, plan, chunks = out["records"], out["plan"], out["chunks"]
    metric = plan.get("sort_by") or "rejection_pct"
    limit = (plan.get("filters") or {}).get("pressure_max")
    names = {"rejection_pct": ("Best rejection", "%"), "flux_lmh": ("Top flux", "LMH"), "pressure_bar": ("Pressure", "bar")}

    if recs:
        ranked = [r for r in recs if r.get(metric) is not None]
        best = ranked[0] if plan.get("sort_by") and ranked else (max(ranked, key=lambda r: r[metric]) if ranked else None)
        pres = [r["pressure_bar"] for r in recs if r.get("pressure_bar") is not None]
        ok_n = sum(1 for r in recs if not r.get("flags"))
        lab, unit = names.get(metric, ("Best value", ""))
        cards = [
            dict(label=lab, value=f"{C.fmt(best[metric], 1)} {unit}" if best else "–",
                 sub=f"{best['source']} · {best.get('membrane') or best.get('solute') or ''}" if best else "", color="#16a34a"),
            dict(label="Records matched", value=len(recs), sub=f"{len({r['source'] for r in recs})} papers", color="#2563eb"),
            dict(label="Pressure range", value=(f"{min(pres):g} – {max(pres):g} bar" if pres else "–"),
                 sub=(f"limit {limit:g} bar" if limit is not None else ""), color="#9333ea"),
            dict(label="Verified", value=f"{ok_n} / {len(recs)}", sub=f"{len(recs) - ok_n} flagged", color="#f59e0b"),
        ]
    else:
        cards = [
            dict(label="Excerpts used", value=len(chunks), sub=f"{len({c['source'] for c in chunks})} papers", color="#2563eb"),
            dict(label="Structured records", value="none matched", sub="answer is based on text excerpts", color="#f59e0b"),
        ]
    show(C.stat_cards(cards))

    with st.container(key=f"card_answer_{key}"):
        st.markdown(out["answer"])
    if out.get("warnings"):
        show(C.note("<b>Check before comparing</b><br>" + "<br>".join("• " + C.esc(w) for w in out["warnings"]), "warn"))

    t_table, t_chart, t_ev, t_how = st.tabs(["📊 Results table", "📈 Charts", "📄 Evidence", "🧭 How I searched"])
    with t_table:
        if recs:
            show(C.records_table(recs, papers, pressure_limit=limit, highlight_best_by=metric if plan.get("sort_by") else None))
            st.download_button("⬇ Download table (CSV)", records_csv(recs), file_name="results.csv", mime="text/csv", key=f"dl_{key}")
        else:
            msg = "No structured records matched this question, so the answer uses text excerpts only."
            if record_store.count() == 0:
                msg += " Open <b>Extract records</b> to build the structured database - numeric questions work best after that."
            show(C.note(msg, "info"))
    with t_chart:
        figs = [G.ranking_chart(recs, metric, papers), G.tradeoff_chart(recs, limit), G.flux_rejection_chart(recs)]
        figs = [f for f in figs if f]
        if figs:
            for f in figs:
                show(f)
        else:
            show(C.note("Charts appear when at least two records with numeric values match the question.", "info"))
    with t_ev:
        show(C.evidence_cards(chunks, papers) or C.note("No excerpts were retrieved.", "info"))
    with t_how:
        f = plan.get("filters") or {}
        chips = [C.badge(f"intent: {plan['intent']}", C.BLUE)]
        chips += [C.badge(f"{k} = {v:g}" if isinstance(v, (int, float)) else f"{k} = {v}", C.PURPLE) for k, v in f.items()]
        if plan.get("sort_by"):
            chips.append(C.badge(f"sorted by {plan['sort_by']} {'↓' if plan.get('descending') else '↑'}", C.GOOD))
        chips.append(C.badge(f"answered by {out['provider']}", C.GRAY))
        show("<div>" + "".join(chips) + "</div>")
        show(C.note(f"Search words used for retrieval (hybrid BM25 + embeddings): <b>{C.esc(plan.get('search_query'))}</b>", "info"))


def render_global(out: dict, key: str, dark: bool):
    results = out.get("results", [])
    papers_n = sum(1 for r in results if r.get("kind") == "paper")
    years = [r["year"] for r in results if r.get("year")]
    top = max([r for r in results if r.get("cited_by")], key=lambda r: r["cited_by"], default=None)
    show(C.stat_cards([
        dict(label="Results", value=len(results), sub=f"{papers_n} papers · {len(results) - papers_n} web", color="#2563eb"),
        dict(label="Years covered", value=(f"{min(years)} – {max(years)}" if years else "–"), sub="", color="#9333ea"),
        dict(label="Most cited", value=(f"{top['cited_by']}×" if top else "–"), sub=((top["title"] or "")[:34] if top else ""), color="#16a34a"),
    ]))
    for p in out.get("problems", []):
        show(C.note(C.esc(p), "warn"))
    with st.container(key=f"card_answer_{key}"):
        st.markdown(out["answer"])
    if results:
        t_src, t_tab, t_chart = st.tabs(["🔗 Sources", "📊 Table", "📈 Charts"])
        with t_src:
            show(C.source_cards(results))
        with t_tab:
            show(C.papers_table(results))
        with t_chart:
            figs = [f for f in (G.year_chart(results), G.citations_chart(results)) if f]
            for f in figs:
                show(f)
            if not figs:
                show(C.note("Not enough dated or cited results to chart.", "info"))
    st.caption(f"Search query used: “{out.get('query')}” · answered by {out.get('provider')}")


# ----------------------------------------------------------------------------- page: ask
def page_ask(dark: bool):
    lib, store = load_library()
    providers = llm.configured_providers()
    show(C.hero("MemXtract", "Simple and Transparent Membrane literature Comparsion. "
                "Instantly compare membrane performence across research papers with 100% Verified source citations",
                ["📚 " + (f"{lib.stats['papers']} papers" if lib.ok else "library not loaded"), f"🧪 {record_store.count()} records",
                 "🤖 " + (", ".join(providers) if providers else "no LLM key")]))

    if not providers:
        show(C.note("<b>One thing is missing: an LLM key.</b>", "bad"))
        show(C.steps([("Get a free Gemini key", "Create one at aistudio.google.com/apikey", False),
                      ("Add it to Streamlit secrets", "App → Settings → Secrets → <code>GEMINI_API_KEY = \"...\"</code>", False),
                      ("Reboot the app", "The sidebar will then show the active LLM.", False)]))
        return

    mode = st.radio("Where should I search?", [MODE_LIB, MODE_GLO], horizontal=True, key="mode", label_visibility="collapsed")
    if mode == MODE_LIB:
        hint, examples, placeholder = schema.LIBRARY_HINT, schema.LIBRARY_EXAMPLES, schema.LIBRARY_PLACEHOLDER
        if not lib.ok:
            library_problems(lib)
            return
    else:
        hint, examples, placeholder = schema.GLOBAL_HINT, schema.GLOBAL_EXAMPLES, schema.GLOBAL_PLACEHOLDER
    show(C.note("💡 " + md_inline(hint), "info"))

    source, k, use_planner, use_papers, use_web = None, 6, True, True, True
    with st.expander("⚙️ Search settings"):
        if mode == MODE_LIB:
            c1, c2 = st.columns([2, 1])
            choice = c1.selectbox("Limit to one paper (optional)", ["All papers"] + store.sources,
                                  format_func=lambda s: s if s == "All papers" else f"{s} · {(lib.papers.get(s) or {}).get('title', '')[:60]}")
            source = None if choice == "All papers" else choice
            k = c2.slider("Excerpts to retrieve", 3, 12, 6)
            use_planner = st.checkbox("Use AI to plan the search (1 extra free-tier request, better filters)", value=True)
        else:
            c1, c2 = st.columns(2)
            use_papers = c1.checkbox("OpenAlex (scientific papers)", value=True)
            use_web = c2.checkbox("Tavily (general web)", value=True)

    state = st.session_state.setdefault("messages", {MODE_LIB: [], MODE_GLO: []})
    history = state[mode]

    for i, m in enumerate(history):
        with st.chat_message(m["role"], avatar="🧑‍🔬" if m["role"] == "user" else "🧪"):
            if m["role"] == "user":
                st.markdown(m["content"])
            elif "error" in m:
                show(C.note(C.esc(m["error"]), "bad"))
            elif mode == MODE_LIB:
                render_library(m["out"], f"{i}", dark, lib.papers)
            else:
                render_global(m["out"], f"g{i}", dark)

    if not history:
        st.markdown("##### Try one of these")
        cols = st.columns(2)
        for i, q in enumerate(examples):
            if cols[i % 2].button(q, key=f"ex_{mode}_{i}"):
                st.session_state["pending"] = q
                st.rerun()
    else:
        with st.expander("💡 Suggested questions"):
            for i, q in enumerate(examples):
                if st.button(q, key=f"ex2_{mode}_{i}"):
                    st.session_state["pending"] = q
                    st.rerun()

    question = st.chat_input(placeholder)
    if not question and st.session_state.get("pending"):
        question = st.session_state.pop("pending")
    if not question:
        return

    history.append({"role": "user", "content": question})
    with st.chat_message("user", avatar="🧑‍🔬"):
        st.markdown(question)
    with st.chat_message("assistant", avatar="🧪"):
        try:
            with st.spinner("Searching your library..." if mode == MODE_LIB else "Searching papers and the web..."):
                if mode == MODE_LIB:
                    embedder = load_embedder()
                    if embedder.embed("dimension check").shape[0] != lib.stats["dimension"]:
                        raise RuntimeError(
                            f"Embedding mismatch: your stored vectors have {lib.stats['dimension']} dimensions but the model "
                            f"'{embedder.model_name}' produces a different size. Fix the model name in data/imported/embedding_info.json.")
                    out = agent.answer_library(question, store, embedder, k=k, use_planner=use_planner, source=source, papers=lib.papers)
                else:
                    out = agent.answer_global(question, use_papers=use_papers, use_web=use_web)
        except (llm.LLMError, RuntimeError, global_search.SearchError) as e:
            show(C.note(C.esc(str(e)), "bad"))
            history.append({"role": "assistant", "error": str(e)})
            return
        idx = len(history)
        if mode == MODE_LIB:
            render_library(out, f"{idx}", dark, lib.papers)
        else:
            render_global(out, f"g{idx}", dark)
        history.append({"role": "assistant", "out": out})


# ----------------------------------------------------------------------------- page: extract
def page_extract(dark: bool):
    show(C.hero("Simple and Transparent Membrane Literature Comparsion & Reasearch",
                ["Isnstantly compare membrane performence accross research papers with 100% verified source Citations"]))
    lib, store = load_library()
    if not lib.ok:
        library_problems(lib)
        return
    if not llm.configured_providers():
        show(C.note("No LLM key found in Streamlit secrets.", "bad"))
        return

    processed = record_store.processed_sources()
    rows = record_store.all_records()
    flagged = sum(1 for r in rows if r.get("flags"))
    show(C.stat_cards([
        dict(label="Papers in library", value=len(store.sources), color="#2563eb"),
        dict(label="Papers processed", value=f"{len(processed)} / {len(store.sources)}", color="#16a34a"),
        dict(label="Records", value=len(rows), color="#9333ea"),
        dict(label="Flagged", value=flagged, sub="need a human look", color="#f59e0b"),
    ]))
    show(C.note("The LLM only <b>proposes</b> values. Code converts units, checks plausible ranges, and verifies that each number "
                "(and the quoted sentence) really appears on that page of the paper. Unverified values are hidden from rankings.", "info"))

    chosen = st.multiselect("Papers to process", store.sources,
                            format_func=lambda s: f"{'✅ ' if s in processed else ''}{s} · {(lib.papers.get(s) or {}).get('title', '')[:60]}",
                            help="✅ = already processed. Free tiers have daily limits - do a few papers at a time.")
    max_chunks = st.slider("Max chunks per paper", 10, 80, 30, help="Fewer chunks = fewer tokens. 30 is enough for most papers.")
    if st.button("▶ Run extraction", type="primary", disabled=not chosen):
        embedder = load_embedder()
        bar = st.progress(0.0, text="Starting...")
        for pi, src in enumerate(chosen):
            def cb(done, total, msg, pi=pi, src=src):
                bar.progress(min((pi + done / max(total, 1)) / len(chosen), 1.0), text=f"{src} - {msg}")

            summary = extractor.run_extraction(lib.chunks, src, max_chunks, cb, store=store, embed_fn=embedder.embed)
            line = (f"<b>{C.esc(src)}</b> - {summary['chunks_selected']} chunks → {summary['records_added']} new records"
                    + (f" (via {', '.join(summary['providers'])})" if summary["providers"] else ""))
            if summary["stopped"]:
                show(C.note(line + f"<br>Stopped: {C.esc(summary['stopped'])}", "warn"))
                break
            show(C.note(line, "good"))
        bar.empty()

    show(G.records_per_paper_chart(rows))

    st.markdown("##### Keep your records permanently")
    show(C.note(f"Records stored now: <b>{record_store.count()}</b>. Streamlit Cloud forgets files when the app restarts - download the "
                "records and commit them to your repo as <code>data/records_seed.json</code>; the app loads that file automatically.", "warn"))
    c1, c2 = st.columns(2)
    c1.download_button("⬇ Download records (records_seed.json)", record_store.export_json(), file_name="records_seed.json",
                       mime="application/json", disabled=record_store.count() == 0)
    up = c2.file_uploader("Restore records from a JSON file", type="json")
    if up is not None and c2.button("Import this file"):
        try:
            show(C.note(f"Imported {record_store.import_json(up.getvalue().decode('utf-8'))} new records.", "good"))
        except Exception as e:
            show(C.note(f"Could not import: {C.esc(e)}", "bad"))


# ----------------------------------------------------------------------------- page: records
def page_records(dark: bool):
    show(C.hero("Records", "Everything extracted from your papers, color-coded by value and verification status."))
    lib, _ = load_library()
    rows = record_store.all_records()
    if not rows:
        show(C.note("No records yet. Use the <b>Extract records</b> page first.", "info"))
        return
    c1, c2, c3 = st.columns([2, 1, 1])
    src = c1.selectbox("Paper", ["All"] + sorted({r["source"] for r in rows}))
    rej_min = c2.number_input("Min rejection %", 0, 100, 0)
    flagged_only = c3.checkbox("Only flagged")
    view = [r for r in rows if (src == "All" or r["source"] == src) and (r.get("rejection_pct") or 0) >= rej_min
            and (not flagged_only or r.get("flags"))]
    view.sort(key=lambda r: -(r.get("rejection_pct") or -1))
    show(C.stat_cards([dict(label="Shown", value=len(view), sub=f"of {len(rows)}", color="#2563eb"),
                       dict(label="Verified", value=sum(1 for r in view if not r.get("flags")), color="#16a34a"),
                       dict(label="Flagged", value=sum(1 for r in view if r.get("flags")), color="#f59e0b")]))
    show(C.records_table(view[:300], lib.papers, highlight_best_by="rejection_pct"))
    if len(view) > 300:
        st.caption(f"Showing the first 300 of {len(view)} records - use the filters to narrow down.")
    t1, t2 = st.tabs(["📈 Charts", "⬇ Downloads"])
    with t1:
        for f in (G.records_per_paper_chart(view), G.tradeoff_chart(view), G.flux_rejection_chart(view)):
            show(f)
    with t2:
        st.download_button("Download CSV", records_csv(view), file_name="records.csv", mime="text/csv")
        st.download_button("Download JSON", record_store.export_json(), file_name="records_seed.json", mime="application/json")
    with st.expander("Danger zone"):
        if st.checkbox("I understand this deletes all records") and st.button("Delete all records"):
            record_store.clear()
            st.rerun()


# ----------------------------------------------------------------------------- page: data check
def page_check(dark: bool):
    show(C.hero("Data check", "Confirm that your files, embedding model and API keys are wired correctly."))
    lib, _ = load_library()

    files = [("data/imported/chunks.jsonl", config.CHUNKS_FILE, "required"),
             ("data/imported/embeddings.npy", config.EMBEDDINGS_FILE, "required"),
             ("data/imported/embedding_info.json", config.EMBED_INFO_FILE, "strongly recommended"),
             ("data/imported/pages.json", config.PAGES_FILE, "recommended (verifies quotes/numbers)"),
             ("data/imported/metadata.jsonl", config.METADATA_FILE, "optional"),
             ("data/records_seed.json", config.RECORDS_SEED_FILE, "optional")]
    st.markdown("##### 1. Your files")
    show(C.table([{"File": n, "Status": C.badge("found", C.GOOD) if p.exists() else C.badge("missing", C.BAD), "Need": need}
                  for n, p, need in files], ["File", "Status", "Need"]))
    if lib.ok:
        show(C.stat_cards([dict(label="Chunks", value=lib.stats["chunks"], color="#2563eb"),
                           dict(label="Papers", value=lib.stats["papers"], sub=f"{lib.stats['papers_with_titles']} with titles", color="#16a34a"),
                           dict(label="Table chunks", value=lib.stats["table_chunks"], color="#9333ea"),
                           dict(label="Dimension", value=lib.stats["dimension"], sub=lib.stats["model_in_embedding_info"], color="#f59e0b"),
                           dict(label="Page text", value="loaded" if lib.stats["pages_file"] else "missing", color="#0891b2")]))
        for w in lib.warnings:
            show(C.note(C.esc(w), "warn"))
    else:
        library_problems(lib)

    st.markdown("##### 2. Embedding model")
    show(C.note(f"Model used for questions: <b>{C.esc(config.embedding_model_name())}</b> (backend {C.esc(config.embedding_backend())}) · "
                f"query prefix: <b>{C.esc(config.query_prefix()[:40] or 'none')}</b>", "info"))
    if st.button("Test embedding model"):
        try:
            dim = load_embedder().embed("membrane rejection test").shape[0]
            if lib.ok and dim != lib.stats["dimension"]:
                show(C.note(f"Dimension {dim} ≠ stored vectors {lib.stats['dimension']}. The model name is wrong for your embeddings.", "bad"))
            else:
                show(C.note(f"Model works - {dim} dimensions" + (" and matches your stored vectors." if lib.ok else "."), "good"))
        except Exception as e:
            show(C.note(f"Could not load the embedding model: {C.esc(e)}", "bad"))

    st.markdown("##### 3. Secrets and connections")
    keys = ["GEMINI_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY", "OPENALEX_API_KEY", "TAVILY_API_KEY"]
    show(C.table([{"Secret": k, "Status": C.badge("set", C.GOOD) if config.secret(k) else C.badge("not set", C.GRAY)} for k in keys],
                 ["Secret", "Status"]))
    c1, c2, c3 = st.columns(3)
    if c1.button("Test LLM"):
        try:
            r = llm.call_llm("Reply with the single word: OK", max_tokens=50)
            show(C.note(f"{C.esc(r.provider)} ({C.esc(r.model)}) replied: {C.esc(r.text.strip()[:40])}", "good"))
        except llm.LLMError as e:
            show(C.note(C.esc(str(e)), "bad"))
    if c2.button("Test OpenAlex"):
        try:
            show(C.note(f"OpenAlex works - {len(global_search.openalex_search('membrane filtration', 2))} results", "good"))
        except global_search.SearchError as e:
            show(C.note(C.esc(str(e)), "bad"))
    if c3.button("Test Tavily"):
        try:
            show(C.note(f"Tavily works - {len(global_search.tavily_search('membrane filtration', 2))} results", "good"))
        except global_search.SearchError as e:
            show(C.note(C.esc(str(e)), "bad"))


# ----------------------------------------------------------------------------- main
_dark, _page = sidebar()
{PAGES[0]: page_ask, PAGES[1]: page_extract, PAGES[2]: page_records, PAGES[3]: page_check}[_page](_dark)
