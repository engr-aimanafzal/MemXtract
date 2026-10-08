"""Central configuration: file locations and secrets access.

All API keys are read from Streamlit secrets (Streamlit Cloud -> App settings -> Secrets).
Nothing secret is stored in the repository.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

try:
    import streamlit as st
except Exception:  # lets the logic modules be tested without streamlit installed
    st = None

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
IMPORTED_DIR = DATA_DIR / "imported"

# ---- Files YOU add (exact names!) -------------------------------------------
CHUNKS_FILE = IMPORTED_DIR / "chunks.jsonl"
EMBEDDINGS_FILE = IMPORTED_DIR / "embeddings.npy"
EMBED_INFO_FILE = IMPORTED_DIR / "embedding_info.json"
METADATA_FILE = IMPORTED_DIR / "metadata.jsonl"  # optional, merged by chunk_id
PAGES_FILE = IMPORTED_DIR / "pages.json"          # optional: page text for verification {paper: {page: text}}

# ---- Files the app uses -------------------------------------------------------
RECORDS_SEED_FILE = DATA_DIR / "records_seed.json"
RECORDS_DB_FILE = DATA_DIR / "records.db"


def secret(name: str, default: str = "") -> str:
    """Read a value from Streamlit secrets, falling back to environment variables."""
    value = None
    if st is not None:
        try:
            value = st.secrets.get(name)
        except Exception:
            value = None
    if not value:
        value = os.environ.get(name)
    return str(value) if value else default


def embed_info() -> dict:
    if EMBED_INFO_FILE.exists():
        try:
            return json.loads(EMBED_INFO_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def embedding_model_name() -> str:
    return embed_info().get("model") or secret("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")


def embedding_backend() -> str:
    return secret("EMBEDDING_BACKEND", "fastembed")


def query_prefix() -> str:
    info = embed_info()
    if "query_prefix" in info:
        return info["query_prefix"] or ""
    return secret("QUERY_PREFIX", "")
