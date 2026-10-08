"""Loads and validates the files you imported (chunks + embeddings)."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from . import config


@dataclass
class Library:
    chunks: list = field(default_factory=list)
    embeddings: Optional[np.ndarray] = None
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    stats: dict = field(default_factory=dict)
    pages: dict = field(default_factory=dict)
    papers: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.errors and self.embeddings is not None and len(self.chunks) > 0


def _read_jsonl(path):
    rows, errors = [], []
    with open(path, "r", encoding="utf-8-sig") as f:
        for n, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as e:
                errors.append(f"{path.name} line {n}: invalid JSON ({e.msg})")
                continue
            if not isinstance(obj, dict):
                errors.append(f"{path.name} line {n}: each line must be a JSON object")
                continue
            rows.append(obj)
    return rows, errors


def _is_lfs_pointer(path) -> bool:
    try:
        with open(path, "rb") as f:
            return f.read(40).startswith(b"version https://git-lfs")
    except Exception:
        return False


def _to_int(value):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def load_library() -> Library:
    lib = Library()

    if not config.CHUNKS_FILE.exists():
        lib.errors.append("Missing file: data/imported/chunks.jsonl")
    if not config.EMBEDDINGS_FILE.exists():
        lib.errors.append("Missing file: data/imported/embeddings.npy")
    if lib.errors:
        return lib

    for p in (config.CHUNKS_FILE, config.EMBEDDINGS_FILE):
        if _is_lfs_pointer(p):
            lib.errors.append(
                f"{p.name} is a Git LFS pointer, not the real file. Streamlit Cloud does not fetch "
                "LFS files: keep the file under 100 MB and commit it normally (no LFS)."
            )
    if lib.errors:
        return lib

    # ---- chunks
    chunks, errs = _read_jsonl(config.CHUNKS_FILE)
    lib.errors.extend(errs[:10])
    if not chunks:
        lib.errors.append("chunks.jsonl contains no usable rows")
        return lib

    # optional separate metadata file, merged by chunk_id
    if config.METADATA_FILE.exists():
        meta_rows, merrs = _read_jsonl(config.METADATA_FILE)
        lib.errors.extend(merrs[:10])
        meta = {str(m.get("chunk_id")): m for m in meta_rows if m.get("chunk_id") is not None}
        merged = 0
        for c in chunks:
            m = meta.get(str(c.get("chunk_id")))
            if m:
                for k, v in m.items():
                    c.setdefault(k, v)
                merged += 1
        if merged < len(chunks):
            lib.warnings.append(f"metadata.jsonl matched {merged} of {len(chunks)} chunks by chunk_id")

    seen, missing_text, missing_source, missing_page, dupes = set(), 0, 0, 0, 0
    for i, c in enumerate(chunks):
        c["chunk_id"] = str(c.get("chunk_id", f"chunk_{i}"))
        if c["chunk_id"] in seen:
            dupes += 1
        seen.add(c["chunk_id"])
        c["text"] = str(c.get("text") or "").strip()
        if not c["text"]:
            missing_text += 1
        c["source"] = str(c.get("source") or "").strip()
        if not c["source"]:
            missing_source += 1
            c["source"] = "unknown_source"
        c["page"] = _to_int(c.get("page"))
        if c["page"] is None:
            missing_page += 1
        c["section"] = str(c.get("section") or "")
        c["chunk_type"] = str(c.get("chunk_type") or "text").lower()
    if dupes:
        lib.errors.append(f"{dupes} duplicate chunk_id values (chunk_id must be unique)")
    if missing_text:
        lib.errors.append(f"{missing_text} chunks have empty text")
    if missing_source:
        lib.warnings.append(f"{missing_source} chunks have no 'source' (labelled unknown_source)")
    if missing_page:
        lib.warnings.append(f"{missing_page} chunks have no 'page' (citations will lack page numbers)")

    # ---- embeddings
    try:
        emb = np.load(config.EMBEDDINGS_FILE, allow_pickle=False)
    except Exception as e:
        lib.errors.append(
            f"Could not read embeddings.npy ({e}). Save it with "
            "np.save('embeddings.npy', np.asarray(vectors, dtype='float32'))."
        )
        return lib
    if emb.ndim != 2:
        lib.errors.append(f"embeddings.npy must be 2-D (n_chunks x dimension); found shape {emb.shape}")
        return lib
    if emb.shape[0] != len(chunks):
        lib.errors.append(
            f"Row mismatch: embeddings.npy has {emb.shape[0]} rows but chunks.jsonl has {len(chunks)} chunks. "
            "Row i of the embeddings must belong to line i of chunks.jsonl."
        )
        return lib
    emb = emb.astype(np.float32)
    if not np.isfinite(emb).all():
        lib.errors.append("embeddings.npy contains NaN/inf values")
        return lib
    norms = np.linalg.norm(emb, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    emb = emb / norms

    lib.chunks = chunks
    lib.embeddings = emb

    # optional page text (used to verify quoted evidence and numbers against the real page)
    if config.PAGES_FILE.exists():
        try:
            pages = json.loads(config.PAGES_FILE.read_text(encoding="utf-8"))
            if isinstance(pages, dict):
                lib.pages = pages
            else:
                lib.warnings.append("pages.json must be a JSON object {paper: {page: text}}; ignored")
        except Exception as e:
            lib.warnings.append(f"pages.json could not be read ({e}); evidence is verified against chunks only")

    # per-paper info (title/year/doi) taken from the chunk fields when the builder notebook provided them
    for c in chunks:
        info = lib.papers.setdefault(c["source"], {})
        for src_key, dst_key in (("title", "title"), ("publication_year", "year"), ("doi", "doi")):
            if c.get(src_key) and not info.get(dst_key):
                info[dst_key] = c[src_key]
    lib.stats = {
        "chunks": len(chunks),
        "papers": len({c["source"] for c in chunks}),
        "dimension": int(emb.shape[1]),
        "table_chunks": sum(1 for c in chunks if c["chunk_type"] == "table"),
        "pages_file": bool(lib.pages),
        "papers_with_titles": sum(1 for v in lib.papers.values() if v.get("title")),
        "model_in_embedding_info": config.embed_info().get("model", "(embedding_info.json not found)"),
    }
    return lib
