"""The orchestrator. A fixed, cheap pipeline (max 2 LLM calls per question) instead of a free-roaming agent:

Library mode : plan (LLM or regex) -> query records DB -> comparability check -> retrieve chunks -> answer
Global mode  : make search query -> OpenAlex + Tavily -> answer from abstracts/snippets
"""
from __future__ import annotations

import re

from . import comparability, global_search, llm, record_store, units

ANSWER_SYSTEM = (
    "You are a careful research assistant for scientific papers. Answer ONLY from the CONTEXT provided. "
    "If the context does not contain the answer, say so plainly and suggest what to do next. "
    "Never invent numbers. When you give a number, state the conditions it was measured under "
    "(solute, pressure, concentration, temperature) if they are in the context, and cite the source."
)

_FILTER_KEYS = ["solute", "membrane", "pressure_max", "pressure_min", "rejection_min", "temperature_min",
                "temperature_max", "ph_min", "ph_max", "flux_min"]
_BELOW = re.compile(r"(?:below|under|less than|lower than|<=?|≤|up to|at most|not exceeding)\s*"
                    r"(\d+(?:\.\d+)?)\s*(bar|mpa|kpa|psi|atm)\b", re.I)
_ABOVE = re.compile(r"(?:above|over|more than|greater than|higher than|>=?|≥|at least|exceeding)\s*"
                    r"(\d+(?:\.\d+)?)\s*(bar|mpa|kpa|psi|atm)\b", re.I)
_NUMERIC_WORDS = ("highest", "lowest", "best", "worst", "maximum", "minimum", "compare", "rank", "above",
                  "below", "under", "over", "greater", "less than", "average", "how much", "what rejection",
                  "what flux")


def heuristic_plan(question: str) -> dict:
    q = question.lower()
    filters = {}
    m = _BELOW.search(question)
    if m:
        filters["pressure_max"] = units.to_bar(m.group(1), m.group(2))[0]
    m = _ABOVE.search(question)
    if m:
        filters["pressure_min"] = units.to_bar(m.group(1), m.group(2))[0]
    sort_by = None
    if "rejection" in q or "removal" in q:
        sort_by = "rejection_pct"
    elif "flux" in q or "permeab" in q:
        sort_by = "flux_lmh"
    intent = "both" if any(w in q for w in _NUMERIC_WORDS) else "evidence"
    return {"intent": intent, "filters": filters, "sort_by": sort_by,
            "descending": not any(w in q for w in ("lowest", "minimum", "worst")),
            "search_query": question}


def plan_question(question: str, use_llm: bool = True):
    base = heuristic_plan(question)
    if not use_llm:
        return base, None
    prompt = (
        "Turn the user's question into a retrieval plan. Return ONLY JSON with keys:\n"
        '"intent": "numeric" | "evidence" | "both"  (numeric = needs comparing/ranking measured values),\n'
        '"filters": object with any of ' + str(_FILTER_KEYS) + " (numbers in bar / % / C; null if not asked),\n"
        '"sort_by": "rejection_pct" | "flux_lmh" | "pressure_bar" | null,\n'
        '"descending": true/false,\n'
        '"search_query": 5-12 keywords for searching the paper text.\n\n'
        f"Question: {question}"
    )
    try:
        res = llm.call_llm(prompt, json_mode=True, temperature=0.0, max_tokens=600)
        obj = llm.extract_json(res.text)
        if not isinstance(obj, dict):
            return base, None
        filters = {k: v for k, v in (obj.get("filters") or {}).items() if k in _FILTER_KEYS and v not in (None, "")}
        for k in list(filters):
            if k not in ("solute", "membrane"):
                n = units.num(filters[k])
                if n is None:
                    del filters[k]
                else:
                    filters[k] = n
        filters.update({k: v for k, v in base["filters"].items() if k.startswith("pressure")})  # regex is exact
        plan = {
            "intent": obj.get("intent") if obj.get("intent") in ("numeric", "evidence", "both") else base["intent"],
            "filters": filters,
            "sort_by": obj.get("sort_by") if obj.get("sort_by") in ("rejection_pct", "flux_lmh", "pressure_bar")
            else base["sort_by"],
            "descending": bool(obj.get("descending", base["descending"])),
            "search_query": str(obj.get("search_query") or question),
        }
        return plan, res.provider
    except llm.LLMError:
        return base, None


def _fmt(v):
    if v is None:
        return "-"
    return f"{v:g}" if isinstance(v, (int, float)) else str(v)


def records_table(records: list, limit: int = 12) -> str:
    cols = ["source", "page", "membrane", "solute", "rejection_pct", "pressure_bar", "flux_lmh",
            "feed_conc_mg_l", "feed_conc_raw", "temperature_c", "ph", "flags"]
    lines = [" | ".join(cols)]
    for r in records[:limit]:
        lines.append(" | ".join(_fmt(r.get(c)) for c in cols))
    return "\n".join(lines)


def _cite_label(c: dict) -> str:
    loc = c.get("evidence_location")
    return f"{c['source']}, p.{c.get('page')}" + (f", {loc}" if loc else "")


def answer_library(question, store, embedder, k=6, use_planner=True, source=None, papers=None) -> dict:
    plan, plan_provider = plan_question(question, use_llm=use_planner)

    records, warnings = [], []
    if plan["intent"] in ("numeric", "both"):
        filters = dict(plan["filters"])
        if source:
            filters["source"] = source
        records = record_store.query(filters, plan["sort_by"], plan["descending"], limit=15)
        warnings = comparability.check(records)
        hidden = len(record_store.query(filters, plan["sort_by"], plan["descending"], limit=500,
                                        verified_only=False)) - len(record_store.query(
                                            filters, plan["sort_by"], plan["descending"], limit=500))
        if hidden > 0:
            warnings.append(f"{hidden} matching record(s) were hidden because a number could not be verified "
                            "in the source text (see the Records page, flag 'not_in_text').")
        if record_store.count() == 0:
            warnings.append("No structured records exist yet - open the 'Extract records' page to build them. "
                            "This answer uses text excerpts only.")

    qvec = embedder.embed(plan["search_query"])
    chunks = store.search(qvec, k=k, source=source, max_per_source=4, query_text=plan["search_query"])  # hybrid BM25 + dense

    context = []
    if records:
        context.append("EXTRACTED RECORDS (structured data; 'flags' mark less reliable values):\n" + records_table(records))
    if warnings:
        context.append("COMPARABILITY WARNINGS:\n- " + "\n- ".join(warnings))
    excerpts = []
    for c in chunks:
        excerpts.append(f"[{_cite_label(c)}] ({c.get('chunk_type')})\n{c['text'][:800]}")
    if excerpts:
        context.append("TEXT EXCERPTS:\n" + "\n\n".join(excerpts))
    if papers:
        used = sorted({c["source"] for c in chunks} | {r["source"] for r in records if r.get("source")})
        legend = [f"{p}: {papers[p]['title']}" + (f" ({papers[p]['year']})" if papers[p].get("year") else "")
                  for p in used if p in papers and papers[p].get("title")]
        if legend:
            context.append("PAPERS:\n" + "\n".join(legend))

    prompt = (f"QUESTION: {question}\n\nCONTEXT:\n" + "\n\n".join(context) +
              "\n\nWrite a concise answer. Cite as [source, p.N] (add the table/figure label when shown, e.g. [P03, p.5, Table 2]). If you compared numbers, state the conditions "
              "and mention any comparability warnings that matter.")
    res = llm.call_llm(prompt, system=ANSWER_SYSTEM, temperature=0.1, max_tokens=1500)
    return {"answer": res.text.strip(), "provider": res.provider, "plan": plan, "records": records,
            "chunks": chunks, "warnings": warnings}


def make_search_query(question: str) -> str:
    try:
        res = llm.call_llm(
            "Write a search query (4-8 keywords, no quotes, no operators) for finding scientific papers "
            f"that answer this question. Reply with the query only.\n\nQuestion: {question}",
            temperature=0.0, max_tokens=60)
        q = res.text.strip().strip('"').splitlines()[0]
        if 3 <= len(q) <= 200:
            return q
    except llm.LLMError:
        pass
    return global_search.keyword_query(question)


def answer_global(question, use_papers=True, use_web=True, n_papers=8, n_web=5) -> dict:
    query = make_search_query(question)
    results, problems = [], []
    if use_papers:
        try:
            results += global_search.openalex_search(query, n_papers)
        except global_search.SearchError as e:
            problems.append(str(e))
    if use_web:
        try:
            results += global_search.tavily_search(query, n_web)
        except global_search.SearchError as e:
            problems.append(str(e))
    if not results:
        return {"answer": "No results were found. " + " ".join(problems), "provider": None, "query": query,
                "results": [], "problems": problems}

    blocks = []
    for i, r in enumerate(results, start=1):
        meta = r["title"] + (f" ({r.get('year')})" if r.get("year") else "")
        blocks.append(f"[{i}] {meta}\n{(r.get('abstract') or '')[:700]}")
    prompt = (f"QUESTION: {question}\n\nSEARCH RESULTS:\n" + "\n\n".join(blocks) +
              "\n\nAnswer concisely using only these results. Cite results as [1], [2]. "
              "State clearly when results disagree or when the abstracts do not give the exact value asked for.")
    res = llm.call_llm(prompt, system=ANSWER_SYSTEM, temperature=0.1, max_tokens=1500)
    return {"answer": res.text.strip(), "provider": res.provider, "query": query,
            "results": results, "problems": problems}
