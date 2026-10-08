"""Hybrid retrieval for the Streamlit app: BM25 + dense (cosine) fused with reciprocal-rank fusion,
evidence-quality priors, per-paper context retrieval and page-level snippet verification.

The text-normalisation / tokenisation / synonym / prior / schema-query blocks below are copied VERBATIM
from your membrane_index.py (so the app tokenises exactly like your Colab notebook). Only the storage layer is
different: the app keeps vectors in a numpy matrix (equivalent to FAISS IndexFlatIP) and has its own tiny
BM25Okapi implementation (same formula as rank_bm25), so no faiss / rank_bm25 install is needed on Streamlit.
"""
from __future__ import annotations

import math
import re
from collections import Counter

import numpy as np

# ===================================================================================== verbatim from membrane_index.py
_LIG = {"\ufb01": "fi", "\ufb02": "fl", "\ufb00": "ff", "\ufb03": "ffi", "\ufb04": "ffl",
        "\u00ad": "", "\u00a0": " ", "\u2009": " ", "\u202f": " ", "\u200b": ""}

def fix_chars(t):
    for a, b in _LIG.items():
        t = t.replace(a, b)
    return t

def norm_match(t):
    """Aggressive normalisation used ONLY for matching/verification (never stored)."""
    t = fix_chars(t)
    t = t.translate(str.maketrans({"\u2212": "-", "\u2013": "-", "\u2014": "-", "\u2018": "'", "\u2019": "'",
                                   "\u201c": '"', "\u201d": '"', "\u207b": "-", "\u00b2": "2", "\u00b9": "1"}))
    t = re.sub(r"([A-Za-z]{2,})-\s+([a-z])", r"\1\2", t)          # leftover broken hyphenation
    return re.sub(r"\s+", " ", t).strip().lower()

_SEP = r"[\s\u00b7.*()]*"

_UNIT_SUBS = [
 (r"l\s*per\s*\(?\s*m\s*\^?2\s*per\s*h(?:our)?\s*per\s*bar\s*\)?", " lmh_per_bar "),     # RSC style: L per (m2 per h per bar)
 (r"l\s*per\s*\(?\s*m\s*\^?2\s*per\s*h(?:our)?\s*\)?", " lmh "),
 (rf"l{_SEP}m{_SEP}\^?{_SEP}-?2{_SEP}h{_SEP}\^?{_SEP}-?1{_SEP}bar{_SEP}\^?{_SEP}-?1", " lmh_per_bar "),
 (rf"l\s*/\s*\(?\s*m\s*\^?2{_SEP}h{_SEP}bar\s*\)?", " lmh_per_bar "),
 (r"\blmh\s*/\s*bar\b|\blmh\s*bar\s*-?1\b", " lmh_per_bar "),
 (rf"l{_SEP}m{_SEP}\^?{_SEP}-?2{_SEP}h{_SEP}\^?{_SEP}-?1", " lmh "),
 (rf"l\s*/\s*\(?\s*m\s*\^?2{_SEP}h\s*\)?", " lmh "),
 (r"l\s*/\s*m2\s*/\s*h", " lmh "),
 (r"mg\s*/\s*l\b|mg\s*l\s*-1", " mg_l "), (r"wt\s*\.?\s*%", " wtpct "), (r"\bvol\s*\.?\s*%", " volpct "),
 (r"\bg\s*/\s*mol", " g_mol "),
]

SYNONYMS = {  # glossary: literature phrase -> canonical term appended to the text/query
 "rejection": r"remov\w*\s+(?:of\s+)?(?:up to\s+|about\s+|more than\s+|over\s+)?\d+(?:\.\d+)?\s*%|\d\s*%\s*(?:of\s+the\s+\w+\s+)?(?:was\s+|were\s+)?remov|\d\s*%\s*(?:dye\s+)?removal|retention|removal efficiency|dye removal|removal rate|separation efficiency|rejection rate|dye rejection|removal of dyes?|decolou?ri[sz]ation",
 "flux": r"permeate flux|water flux|pure water flux|permeation flux|\bpwf\b|\blmh\b",
 "permeance": r"pressure-normali[sz]ed flux|lmh_per_bar|\bgpu\b",
 "selectivity": r"separation factor",
 "deadend": r"dead-?end|unstirred|stirred cell|stirred-cell",
 "crossflow": r"cross-?flow|tangential",
 "pressure": r"\bbar\b|\bkpa\b|\bmpa\b|\bpsi\b|transmembrane pressure|applied pressure|\btmp\b",
 "concentration": r"mg_l|\bppm\b|mol/l|initial concentration",
 "psf": r"polysulfone|\budel\b", "pes": r"polyethersulfone", "pvdf": r"polyvinylidene|kynar", "pan": r"polyacrylonitrile",
 "ag": r"silver", "tio2": r"titania|titanium dioxide", "cnt": r"carbon nanotubes?|mwcnt|swcnt", "mof": r"metal-organic framework|metal organic framework",
 "zif": r"zeolitic imidazolate", "go": r"graphene oxide", "nf": r"nanofiltration", "uf": r"ultrafiltration", "ro": r"reverse osmosis",
 "mmm": r"mixed-matrix|mixed matrix", "tfc": r"thin-film composite", "tfn": r"thin-film nanocomposite",
}

_STOP = set("the of and a an in on for to with by at as is are was were be this that these those from or it its we our can which than then their".split())

def lex_text(t):
    t = norm_match(t)
    t = re.sub(r"(?<=\w)\s*-\s*(?=\d)", "-", t)
    for rx, rep in _UNIT_SUBS: t = re.sub(rx, rep, t)
    extra = [canon for canon, rx in SYNONYMS.items() if re.search(rx, t)]
    return t + " " + " ".join(extra)

def tokenize(t):
    toks = re.findall(r"\d+(?:\.\d+)?|[a-z][a-z0-9_@\-]*", lex_text(t))
    out = []
    for w in toks:
        if w in _STOP: continue
        if len(w) > 3 and w.endswith("s") and not w.endswith("ss"): w = w[:-1]
        out.append(w)
    return out

PRIOR = {"table": 0.0006, "results": 0.0003, "methods": 0.0002, "abstract": 0.0, "conclusion": -0.0002, "introduction": -0.0006, "front_matter": -0.0006, "other": -0.0002}

_QSEC = [("abstract", r"\babstract\b"), ("methods", r"\b(experimental|methods?|materials and methods)\b"),
         ("results", r"\bresults?\b"), ("conclusion", r"\bconclusions?\b"), ("introduction", r"\bintroduction\b")]

SCHEMA_QUERIES = {
  "membrane": "membrane composition base polymer polysulfone PSf PES PVDF filler MOF CNT graphene oxide loading wt% membrane thickness",
  "membrane_class": "nanofiltration ultrafiltration reverse osmosis mixed-matrix membrane thin-film composite pore size MWCO",
  "fabrication": "membrane preparation fabrication phase inversion casting interfacial polymerization solvent crosslinking post-treatment",
  "application_feed": "feed solution target dye contaminant reactive black methylene blue anionic cationic textile effluent initial concentration mg/L ppm",
  "operating_conditions": "operating pressure bar kPa transmembrane pressure applied pressure temperature pH test duration filtration time",
  "test_setup": "dead-end cross-flow stirred cell filtration setup flat sheet hollow fiber spiral wound lab-scale pilot membrane area",
  "performance": "pure water flux LMH L/m2h dye rejection removal efficiency retention % permeability permeance selectivity recovery results",
}

# ===================================================================================== app-side retrieval
class BM25Okapi:
    """Same scoring as rank_bm25.BM25Okapi (k1=1.5, b=0.75, epsilon=0.25), with an inverted index for speed."""

    def __init__(self, corpus, k1=1.5, b=0.75, epsilon=0.25):
        self.k1, self.b = k1, b
        self.n = len(corpus)
        self.doc_len = np.array([len(d) for d in corpus], dtype=float)
        self.avgdl = float(self.doc_len.mean()) if self.n else 0.0
        df, self.postings = Counter(), {}
        for i, doc in enumerate(corpus):
            for w, f in Counter(doc).items():
                df[w] += 1
                self.postings.setdefault(w, []).append((i, f))
        self.idf, negative, idf_sum = {}, [], 0.0
        for w, n_w in df.items():
            v = math.log(self.n - n_w + 0.5) - math.log(n_w + 0.5)
            self.idf[w] = v
            idf_sum += v
            if v < 0:
                negative.append(w)
        avg_idf = idf_sum / len(self.idf) if self.idf else 0.0
        for w in negative:
            self.idf[w] = epsilon * avg_idf

    def get_scores(self, query):
        score = np.zeros(self.n)
        if not self.n:
            return score
        for q in query:
            idf = self.idf.get(q)
            if idf is None:
                continue
            for i, f in self.postings[q]:
                score[i] += idf * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * self.doc_len[i] / self.avgdl))
        return score


class HybridStore:
    EXCLUDE = {"references", "acknowledgements"}
    MIN_SNIPPET_CHARS = 12

    def __init__(self, chunks: list, embeddings: np.ndarray, pages: dict | None = None):
        self.chunks, self.emb, self.pages = chunks, embeddings, pages or {}
        self._sources = np.array([c["source"] for c in chunks])
        self._types = np.array([c.get("chunk_type", "text") for c in chunks])
        self._sections = np.array([c.get("section", "") for c in chunks])
        self._allowed = np.array([c.get("section", "") not in self.EXCLUDE for c in chunks])
        self.sources = sorted(set(self._sources.tolist()))
        self.by_id = {c["chunk_id"]: c for c in chunks}
        self.bm25 = BM25Okapi([
            tokenize(c["text"] + " " + str(c.get("evidence_location") or "") + " " + " ".join(c.get("tags") or []))
            for c in chunks
        ])

    # ------------------------------------------------------------------ search
    def search(self, qvec=None, k=6, source=None, chunk_type=None, section=None, max_per_source=None,
               query_text="", prior=True):
        """Hybrid search. qvec = normalised query embedding (dense), query_text = words (BM25). Either may be omitted."""
        mask = self._allowed.copy()
        if source:
            mask &= self._sources == source
        if chunk_type:
            mask &= self._types == chunk_type
        if section:
            mask &= self._sections == section
        if not mask.any() or (qvec is None and not query_text):
            return []

        fused = {}

        def add(order):
            for r, i in enumerate(order[:100]):
                fused[i] = fused.get(i, 0.0) + 1.0 / (60 + r)

        if query_text:
            s = np.where(mask, self.bm25.get_scores(tokenize(query_text)), -1e9)
            add([int(i) for i in np.argsort(-s) if mask[i] and s[i] > 0])
        if qvec is not None:
            d = np.where(mask, self.emb @ np.asarray(qvec, dtype=np.float32), -1e9)
            add([int(i) for i in np.argsort(-d) if mask[i]])
        if not fused:
            return []
        if prior:  # evidence-quality prior: own results (tables/results/methods) beat intro/conclusion/front matter
            for i in fused:
                c = self.chunks[i]
                fused[i] += PRIOR.get("table" if c.get("chunk_type") == "table" else c.get("section", ""), 0.0)
        if query_text:
            want = [g for g, rx in _QSEC if re.search(rx, query_text, re.I)]
            for i in fused:
                if self.chunks[i].get("section") in want:
                    fused[i] += 0.012

        results, per_source = [], {}
        for i in sorted(fused, key=lambda j: -fused[j]):
            src = self.chunks[i]["source"]
            if max_per_source and per_source.get(src, 0) >= max_per_source:
                continue
            per_source[src] = per_source.get(src, 0) + 1
            hit = dict(self.chunks[i])
            hit["score"] = round(fused[i], 4)
            results.append(hit)
            if len(results) >= k:
                break
        return results

    def retrieve_for_paper(self, pid, embed_fn, k=4):
        """Schema-driven context for ONE paper (membrane, fabrication, feed, conditions, set-up, performance)."""
        ctx = {}
        for sec, q in SCHEMA_QUERIES.items():
            qv = embed_fn(q)
            hits = self.search(qv, k, source=pid, query_text=q)
            hits += self.search(qv, 6 if sec == "performance" else 2, source=pid, chunk_type="table", query_text=q)
            if sec in ("performance", "operating_conditions"):
                hits += self.search(qv, 1, source=pid, section="abstract", query_text=q)
            seen, merged = set(), []
            for h in hits:
                if h["chunk_id"] not in seen:
                    seen.add(h["chunk_id"])
                    merged.append(h)
            ctx[sec] = merged
        return ctx

    # ------------------------------------------------------------------ verification (hallucination guards)
    def page_text(self, pid, page):
        pg = self.pages.get(pid, {})
        return pg.get(page, pg.get(str(page), "")) if isinstance(pg, dict) else ""

    def verify_snippet(self, pid, page, snippet) -> bool:
        """True only if the snippet appears (whitespace/dash/quote-insensitive) on that exact page.
        Fragments split by an ellipsis are checked in order. Very short snippets are rejected."""
        text = self.page_text(pid, page)
        if not text or not isinstance(snippet, str):
            return False
        frags = [norm_match(f) for f in re.split(r"\[\s*\.\.\.\s*\]|\.{3,}|\u2026", snippet)]
        frags = [f for f in frags if f]
        if not frags or any(len(f) < self.MIN_SNIPPET_CHARS for f in frags):
            return False
        pos = 0
        for f in frags:
            k = text.find(f, pos)
            if k < 0:
                return False
            pos = k + len(f)
        return True

    def number_on_page(self, pid, page, value) -> bool:
        text = self.page_text(pid, page)
        if not text:
            return True  # nothing to check against
        s = str(value).strip().replace(",", "")
        return bool(s) and re.search(r"(?<![\d.])" + re.escape(s) + r"(?!\d|\.\d)", text.replace(",", "")) is not None
