"""Turns chunks into validated structured records.

Token-saving design: only likely-result chunks are sent to the LLM (tables, results/experimental
sections, chunks dense in numbers+units), several chunks are batched per request, and every
paper is processed once (results are stored).
"""
from __future__ import annotations

import re

from . import llm, record_store, schema, units

_NUM_UNIT = re.compile(
    r"\d+(?:\.\d+)?\s*(?:bar|mpa|kpa|psi|atm|%|lmh|l\s*/\s*m|mg\s*/\s*l|g\s*/\s*l|ppm|°\s*c|mm\b|mol)",
    re.IGNORECASE,
)
BATCH_CHARS = 9000


def select_chunks(chunks: list, source: str, max_chunks: int = 30) -> list:
    scored = []
    for c in chunks:
        if c["source"] != source:
            continue
        section = (c.get("section") or "").lower()
        if any(k in section for k in schema.SECTION_SKIP):
            continue
        score = 0
        if c.get("chunk_type") == "table":
            score += 5
        if any(k in section for k in schema.SECTION_GOOD):
            score += 2
        score += min(len(_NUM_UNIT.findall(c["text"])), 6)
        if score > 0:
            scored.append((score, c))
    scored.sort(key=lambda x: -x[0])
    chosen = [c for _, c in scored[:max_chunks]]
    chosen.sort(key=lambda c: (c.get("page") or 0, c["chunk_id"]))
    return chosen


def select_with_retrieval(store, embed_fn, source: str, max_chunks: int = 30) -> list:
    """Preferred selection: your schema-driven retrieval (membrane, fabrication, feed, conditions, set-up,
    performance) for this paper, plus ALL of its table chunks (tables hold most measured values)."""
    ctx = store.retrieve_for_paper(source, embed_fn, k=4)
    ordered, seen = [], set()

    def take(c):
        if c["chunk_id"] not in seen:
            seen.add(c["chunk_id"])
            ordered.append(store.by_id[c["chunk_id"]])

    for c in store.chunks:  # tables first: they are the main data source
        if c["source"] == source and c.get("chunk_type") == "table":
            take(c)
    for hits in ctx.values():
        for h in hits:
            take(h)
    chosen = ordered[:max_chunks]
    chosen.sort(key=lambda c: (c.get("page") or 0, c["chunk_id"]))
    return chosen


def make_batches(chunks: list, budget: int = BATCH_CHARS) -> list:
    batches, current, size = [], [], 0
    for c in chunks:
        n = len(c["text"]) + 60
        if current and size + n > budget:
            batches.append(current)
            current, size = [], 0
        current.append(c)
        size += n
    if current:
        batches.append(current)
    return batches


def _build_prompt(batch: list) -> str:
    parts = [schema.EXTRACTION_INSTRUCTIONS, "\nEXCERPTS:"]
    for c in batch:
        loc = f" | location={c['evidence_location']}" if c.get("evidence_location") else ""
        parts.append(f"\n### chunk_id={c['chunk_id']} | source={c['source']} | page={c.get('page')}{loc}\n{c['text']}")
    return "\n".join(parts)


def _appears(value, text: str) -> bool:
    """True if the number really occurs in the source text (cheap hallucination check)."""
    v = units.num(value)
    if v is None:
        return True
    candidates = {str(value).strip(), f"{v:g}", f"{v:.1f}", f"{v:.2f}"}
    haystack = text.replace(",", "")
    for cand in candidates:
        if cand and re.search(r"(?<![\d.])" + re.escape(cand) + r"(?!\d|\.\d)", haystack):
            return True
    return False


def normalize_record(raw: dict, chunk_lookup: dict, fallback_chunk: dict, store=None):
    """Convert one raw LLM record into a normalised, flagged record. Returns None to drop it."""
    flags = []
    chunk = chunk_lookup.get(str(raw.get("chunk_id")))
    if chunk is None:
        chunk = fallback_chunk
        flags.append("chunk_id_unverified")

    def keep(pair):
        value, flag = pair
        if flag:
            flags.append(flag)
        return value

    rej = keep(units.to_percent(raw.get("rejection_value"), raw.get("rejection_unit")))
    pres = keep(units.to_bar(raw.get("pressure_value"), raw.get("pressure_unit")))
    flux = keep(units.to_lmh(raw.get("flux_value"), raw.get("flux_unit")))
    conc = keep(units.to_mg_per_l(raw.get("feed_conc_value"), raw.get("feed_conc_unit")))
    temp = keep(units.to_celsius(raw.get("temperature_value"), raw.get("temperature_unit")))
    ph = units.num(raw.get("ph"))

    # plausibility ranges - out-of-range values are removed and flagged
    if rej is not None and not (0 <= rej <= 100.0001):
        flags.append("rejection_out_of_range")
        rej = None
    if pres is not None and not (0 < pres <= 300):
        flags.append("pressure_out_of_range")
        pres = None
    if flux is not None and flux < 0:
        flags.append("flux_negative")
        flux = None
    if temp is not None and not (-5 <= temp <= 200):
        flags.append("temperature_out_of_range")
        temp = None
    if ph is not None and not (0 <= ph <= 14):
        flags.append("ph_out_of_range")
        ph = None

    membrane = (str(raw.get("membrane")).strip() if raw.get("membrane") else None) or None
    solute = (str(raw.get("solute")).strip() if raw.get("solute") else None) or None
    if rej is None and flux is None:
        return None
    if not membrane and not solute:
        return None

    # verify the numbers against the actual chunk text
    text = chunk["text"]
    for key in ("rejection_value", "pressure_value", "flux_value"):
        if raw.get(key) is not None and not _appears(raw.get(key), text):
            flags.append(f"not_in_text:{key}")
    evidence = (str(raw.get("evidence") or "")[:300]).strip()
    if evidence:
        if store is not None and getattr(store, "pages", None):
            # strongest check: the quoted text must appear on that exact page of the paper
            if not store.verify_snippet(chunk["source"], chunk.get("page"), evidence):
                flags.append("evidence_not_verbatim")
        elif evidence.lower()[:30] not in re.sub(r"\s+", " ", text.lower()):
            flags.append("evidence_not_verbatim")

    conc_raw = None
    if raw.get("feed_conc_value") is not None:
        conc_raw = f"{raw.get('feed_conc_value')} {raw.get('feed_conc_unit') or ''}".strip()

    return {
        "source": chunk["source"], "page": chunk.get("page"), "location": chunk.get("evidence_location"),
        "chunk_id": chunk["chunk_id"],
        "membrane": membrane, "solute": solute,
        "rejection_pct": rej, "pressure_bar": pres, "flux_lmh": flux,
        "feed_conc_mg_l": conc, "feed_conc_raw": conc_raw, "temperature_c": temp, "ph": ph,
        "operation_mode": raw.get("operation_mode"), "evidence": evidence,
        "flags": ",".join(sorted(set(flags))),
    }


def extract_from_batch(batch: list, store=None):
    result = llm.call_llm(_build_prompt(batch), system=schema.EXTRACTION_SYSTEM,
                          json_mode=True, temperature=0.0, max_tokens=4096)
    obj = llm.extract_json(result.text)
    raw_records = obj.get("records", []) if isinstance(obj, dict) else obj
    lookup = {c["chunk_id"]: c for c in batch}
    out = []
    for raw in raw_records if isinstance(raw_records, list) else []:
        if isinstance(raw, dict):
            rec = normalize_record(raw, lookup, batch[0], store)
            if rec:
                out.append(rec)
    return out, result.provider


def run_extraction(chunks: list, source: str, max_chunks: int = 30, progress=None, store=None, embed_fn=None) -> dict:
    """Extract one paper. Stops cleanly (keeping partial results) if every LLM quota is exhausted."""
    if store is not None and embed_fn is not None:
        selected = select_with_retrieval(store, embed_fn, source, max_chunks)
    else:
        selected = select_chunks(chunks, source, max_chunks)
    batches = make_batches(selected)
    summary = {"source": source, "chunks_selected": len(selected), "batches": len(batches),
               "records_added": 0, "stopped": None, "providers": set(), "complete": False}
    if not selected:
        summary["stopped"] = "No suitable chunks found for this paper (no tables/results/numeric chunks)."
        return summary
    for i, batch in enumerate(batches, start=1):
        if progress:
            progress(i - 1, len(batches), f"Batch {i}/{len(batches)}")
        try:
            records, provider = extract_from_batch(batch, store)
        except llm.LLMError as e:
            summary["stopped"] = str(e)
            break
        summary["providers"].add(provider)
        summary["records_added"] += record_store.add_records(records)
    else:
        summary["complete"] = True
        record_store.mark_processed(source, len(selected), summary["records_added"])
    if progress:
        progress(len(batches), len(batches), "Done")
    summary["providers"] = sorted(summary["providers"])
    return summary
