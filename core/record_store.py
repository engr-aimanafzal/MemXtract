"""Structured experimental records (SQLite).

Streamlit Cloud's disk is temporary: records survive reruns but NOT app restarts.
To keep them permanently: download records.json in the Extract page and commit it to the
repo as data/records_seed.json - the app loads it automatically when the database is empty.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from . import config

COLUMNS = ["source", "page", "location", "chunk_id", "membrane", "solute", "rejection_pct", "pressure_bar", "flux_lmh",
           "feed_conc_mg_l", "feed_conc_raw", "temperature_c", "ph", "operation_mode", "evidence", "flags"]

_DDL = """
CREATE TABLE IF NOT EXISTS records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT, page INTEGER, location TEXT, chunk_id TEXT, membrane TEXT, solute TEXT,
    rejection_pct REAL, pressure_bar REAL, flux_lmh REAL, feed_conc_mg_l REAL, feed_conc_raw TEXT,
    temperature_c REAL, ph REAL, operation_mode TEXT, evidence TEXT, flags TEXT,
    dedup_key TEXT UNIQUE
);
CREATE TABLE IF NOT EXISTS extraction_log (
    source TEXT PRIMARY KEY, n_chunks INTEGER, n_records INTEGER, ts TEXT
);
"""

_NUMERIC_FILTERS = {
    "pressure_max": ("pressure_bar", "<="), "pressure_min": ("pressure_bar", ">="),
    "rejection_min": ("rejection_pct", ">="), "rejection_max": ("rejection_pct", "<="),
    "temperature_min": ("temperature_c", ">="), "temperature_max": ("temperature_c", "<="),
    "ph_min": ("ph", ">="), "ph_max": ("ph", "<="), "flux_min": ("flux_lmh", ">="),
}
_TEXT_FILTERS = {"solute": "solute", "membrane": "membrane", "source": "source"}
_SORTABLE = {"rejection_pct", "pressure_bar", "flux_lmh", "feed_conc_mg_l", "temperature_c", "ph"}

_db_path = None


def _resolve_path() -> str:
    global _db_path
    if _db_path:
        return _db_path
    for candidate in (config.RECORDS_DB_FILE, Path(tempfile.gettempdir()) / "records.db"):
        try:
            conn = sqlite3.connect(str(candidate))
            conn.executescript(_DDL)
            cols = {r[1] for r in conn.execute("PRAGMA table_info(records)")}
            if "location" not in cols:  # database created by an older version of the app
                conn.execute("ALTER TABLE records ADD COLUMN location TEXT")
            conn.commit()
            conn.close()
            _db_path = str(candidate)
            return _db_path
        except (sqlite3.Error, OSError):
            continue
    raise RuntimeError("Could not create a writable SQLite database")


def _conn():
    conn = sqlite3.connect(_resolve_path())
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables and load data/records_seed.json when the database is empty."""
    with _conn() as c:
        empty = c.execute("SELECT COUNT(*) FROM records").fetchone()[0] == 0
    if empty and config.RECORDS_SEED_FILE.exists():
        try:
            import_json(config.RECORDS_SEED_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass


def _dedup_key(rec: dict) -> str:
    parts = [rec.get(k) for k in ("source", "page", "membrane", "solute", "rejection_pct",
                                  "pressure_bar", "flux_lmh", "feed_conc_raw", "temperature_c")]
    return hashlib.md5(json.dumps(parts, default=str).encode()).hexdigest()


def add_records(records: list) -> int:
    inserted = 0
    with _conn() as c:
        for r in records:
            values = [r.get(col) for col in COLUMNS]
            try:
                cur = c.execute(
                    f"INSERT OR IGNORE INTO records ({','.join(COLUMNS)}, dedup_key) "
                    f"VALUES ({','.join('?' * len(COLUMNS))}, ?)",
                    values + [_dedup_key(r)],
                )
                inserted += cur.rowcount
            except sqlite3.Error:
                continue
    return inserted


def mark_processed(source: str, n_chunks: int, n_records: int) -> None:
    with _conn() as c:
        c.execute("INSERT OR REPLACE INTO extraction_log VALUES (?,?,?,?)",
                  (source, n_chunks, n_records, datetime.now(timezone.utc).isoformat(timespec="seconds")))


def processed_sources() -> dict:
    with _conn() as c:
        return {r["source"]: dict(r) for r in c.execute("SELECT * FROM extraction_log")}


def count() -> int:
    with _conn() as c:
        return c.execute("SELECT COUNT(*) FROM records").fetchone()[0]


def query(filters: dict | None = None, sort_by: str | None = None, descending: bool = True, limit: int = 50,
          verified_only: bool = True) -> list:
    """Filter and rank records. Rows with a missing value for a filtered column are excluded.

    verified_only=True hides records whose numbers could not be found in the source text
    (flag "not_in_text"), so a hallucinated value can never win a ranking.
    """
    filters = filters or {}
    where, params = [], []
    if verified_only:
        where.append("(flags IS NULL OR flags NOT LIKE '%not_in_text%')")
    for key, (col, op) in _NUMERIC_FILTERS.items():
        v = filters.get(key)
        if v is not None:
            where.append(f"{col} {op} ?")
            params.append(float(v))
    for key, col in _TEXT_FILTERS.items():
        v = filters.get(key)
        if v:
            where.append(f"{col} LIKE ?")
            params.append(f"%{v}%")
    order = ""
    if sort_by in _SORTABLE:
        where.append(f"{sort_by} IS NOT NULL")
        order = f" ORDER BY {sort_by} {'DESC' if descending else 'ASC'}"
    sql = "SELECT * FROM records" + (" WHERE " + " AND ".join(where) if where else "") + order + " LIMIT ?"
    params.append(int(limit))
    with _conn() as c:
        return [dict(r) for r in c.execute(sql, params)]


def all_records() -> list:
    with _conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM records ORDER BY source, page")]


def export_json() -> str:
    rows = [{k: v for k, v in r.items() if k not in ("id", "dedup_key")} for r in all_records()]
    return json.dumps(rows, ensure_ascii=False, indent=1)


def import_json(text: str) -> int:
    data = json.loads(text)
    if not isinstance(data, list):
        raise ValueError("records file must contain a JSON list")
    n = add_records([r for r in data if isinstance(r, dict)])
    for source in {r.get("source") for r in data if isinstance(r, dict) and r.get("source")}:
        n_src = sum(1 for r in data if isinstance(r, dict) and r.get("source") == source)
        mark_processed(source, 0, n_src)
    return n


def clear() -> None:
    with _conn() as c:
        c.execute("DELETE FROM records")
        c.execute("DELETE FROM extraction_log")
