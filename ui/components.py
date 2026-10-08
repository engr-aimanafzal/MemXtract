"""HTML building blocks: colored tables, stat cards, evidence cards, source cards, notes."""
from __future__ import annotations

import html
import re
import zlib

GOOD, WARN, BAD, BLUE, PURPLE, GRAY = "#16a34a", "#d97706", "#dc2626", "#2563eb", "#9333ea", "#64748b"
PALETTE = ["#0d9488", "#2563eb", "#9333ea", "#db2777", "#ea580c", "#65a30d", "#0891b2", "#ca8a04", "#7c3aed", "#dc2626"]


class Html(str):
    """Marks a string as already-safe HTML produced by this module."""


def esc(x) -> str:
    return html.escape("" if x is None else str(x), quote=True)


def one_line(s: str) -> str:
    """Streamlit renders markdown first; HTML without blank lines/indentation is passed through untouched."""
    return re.sub(r"\s*\n\s*", "", s)


def color_for(key) -> str:
    return PALETTE[zlib.crc32(str(key).encode()) % len(PALETTE)]


def badge(text, color=GRAY, solid=False) -> Html:
    style = f"background:{color};color:#fff" if solid else f"background:{color}26;color:{color};border:1px solid {color}59"
    return Html(f'<span class="rg-badge" style="{style}">{esc(text)}</span>')


def heat(v, lo=0.0, hi=100.0, reverse=False) -> str:
    """Red -> green colour for a value inside [lo, hi]."""
    if v is None or hi == lo:
        t = 0.5
    else:
        t = max(0.0, min(1.0, (v - lo) / (hi - lo)))
    if reverse:
        t = 1 - t
    return f"hsl({8 + t * 122:.0f},70%,46%)"


def fmt(v, nd=1, suffix="") -> str:
    if v is None or v == "":
        return "–"
    if isinstance(v, (int, float)):
        s = f"{v:.{nd}f}".rstrip("0").rstrip(".") if nd else f"{v:.0f}"
        return s + suffix
    return esc(v) + suffix


def note(text, kind="info") -> str:
    return one_line(f'<div class="rg-note {kind}">{text}</div>')


def hero(title, subtitle, chips=()) -> str:
    chips_html = "".join(f'<span class="rg-chip">{esc(c)}</span>' for c in chips)
    return one_line(f'<div class="rg-hero"><h1>{esc(title)}</h1><p>{esc(subtitle)}</p>{chips_html}</div>')


def stat_cards(items) -> str:
    cards = []
    for it in items:
        c = it.get("color", "#0d9488")
        sub = f'<div class="s">{esc(it["sub"])}</div>' if it.get("sub") else ""
        cards.append(f'<div class="rg-stat" style="--c:{c}"><div class="l">{esc(it["label"])}</div>'
                     f'<div class="v">{esc(it["value"])}</div>{sub}</div>')
    return one_line('<div class="rg-stats">' + "".join(cards) + "</div>")


def steps(items) -> str:
    """items: (title, description, ok)"""
    out = []
    for i, (title, desc, ok) in enumerate(items, start=1):
        color = GOOD if ok else WARN
        mark = "✓" if ok else str(i)
        out.append(f'<div class="rg-step"><div class="n" style="background:{color}">{mark}</div>'
                   f'<div><b>{esc(title)}</b><br><span style="color:var(--muted);font-size:.85rem">{desc}</span></div></div>')
    return one_line("".join(out))


# ----------------------------------------------------------------------------- generic table
def table(rows, columns, numeric=(), row_classes=None) -> str:
    """rows: list of dict. Cells that are `Html` are inserted as-is, everything else is escaped."""
    head = "".join(f"<th>{esc(c)}</th>" for c in columns)
    body = []
    for ri, r in enumerate(rows):
        tds = []
        for c in columns:
            v = r.get(c)
            cell = v if isinstance(v, Html) else esc("–" if v in (None, "") else v)
            tds.append(f'<td class="{"num" if c in numeric else ""}">{cell}</td>')
        cls = (row_classes or {}).get(ri)
        body.append(f'<tr class="{cls}">' if cls else "<tr>")
        body[-1] += "".join(tds) + "</tr>"
    return one_line(f'<div class="rg-table-wrap"><table class="rg-table"><thead><tr>{head}</tr></thead>'
                    f'<tbody>{"".join(body)}</tbody></table></div>')


# ----------------------------------------------------------------------------- records table
def flag_badges(flags: str) -> Html:
    if not flags:
        return badge("✓ verified", GOOD)
    out, seen = [], set()
    for f in str(flags).split(","):
        label = ("number" if f.startswith("not_in_text") else "assumed" if "assumed" in f else f)
        if label in seen:
            continue
        seen.add(label)
        if f.startswith("not_in_text"):
            out.append(badge("number not in text", BAD))
        elif f == "evidence_not_verbatim":
            out.append(badge("quote not found", WARN))
        elif f == "chunk_id_unverified":
            out.append(badge("location uncertain", WARN))
        elif "assumed" in f:
            out.append(badge("unit assumed", WARN))
        elif "out_of_range" in f:
            out.append(badge("out of range", BAD))
        elif f:
            out.append(badge(f.replace("_", " ")[:28], WARN))
    return Html("".join(out))


def _bar(value, lo, hi, text, reverse=False, color=None) -> Html:
    if value is None:
        return Html('<span style="color:var(--muted)">–</span>')
    w = 0 if hi == lo else max(3.0, min(100.0, (value - lo) / (hi - lo) * 100))
    return Html(f'<div class="rg-bar"><i style="width:{w:.0f}%;background:{color or heat(value, lo, hi, reverse)}"></i><b>{text}</b></div>')


def records_table(records, papers=None, pressure_limit=None, highlight_best_by=None) -> str:
    papers = papers or {}
    if not records:
        return ""
    flux_max = max([r["flux_lmh"] for r in records if r.get("flux_lmh") is not None] or [1])
    best_idx = None
    if highlight_best_by:
        vals = [(r.get(highlight_best_by), i) for i, r in enumerate(records) if r.get(highlight_best_by) is not None]
        best_idx = max(vals)[1] if vals else None
    cols = ["#", "Paper", "Where", "Membrane", "Solute", "Rejection %", "Pressure (bar)", "Flux (LMH)",
            "Conditions", "Status"]
    rows = []
    for i, r in enumerate(records):
        src = r.get("source")
        title = (papers.get(src) or {}).get("title") or ""
        paper_cell = Html(f'{badge(src, color_for(src), solid=True)}<div style="color:var(--muted);font-size:.72rem;max-width:210px;'
                          f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="{esc(title)}">{esc(title[:48])}</div>')
        where = f"p.{r['page']}" if r.get("page") is not None else ""
        if r.get("location"):
            where += f" · {r['location']}"
        p = r.get("pressure_bar")
        if p is None:
            p_cell = Html('<span style="color:var(--muted)">–</span>')
        else:
            ok = pressure_limit is not None and p <= pressure_limit + 1e-9
            p_cell = badge(f"{fmt(p, 2)}" + (" ✓" if ok else ""), GOOD if ok else BLUE)
        conc = r.get("feed_conc_raw") or (f"{fmt(r.get('feed_conc_mg_l'), 1)} mg/L" if r.get("feed_conc_mg_l") is not None else None)
        mark = "🏆 " if i == best_idx else ""
        cond = [x for x in (conc, f"{fmt(r.get('temperature_c'), 0)} °C" if r.get("temperature_c") is not None else None,
                            f"pH {fmt(r.get('ph'), 1)}" if r.get("ph") is not None else None) if x]
        rows.append({
            "#": i + 1, "Paper": paper_cell, "Where": where or "–",
            "Membrane": Html(f"<b>{mark}{esc(r.get('membrane') or '–')}</b>"), "Solute": r.get("solute"),
            "Rejection %": _bar(r.get("rejection_pct"), 0, 100, fmt(r.get("rejection_pct"), 1)),
            "Pressure (bar)": p_cell,
            "Flux (LMH)": _bar(r.get("flux_lmh"), 0, flux_max, fmt(r.get("flux_lmh"), 1), color="#0891b2"),
            "Conditions": Html("<br>".join(f'<span style="font-size:.8rem">{esc(x)}</span>' for x in cond) or "–"),
            "Status": flag_badges(r.get("flags") or ""),
        })
    return table(rows, cols, numeric=("#",), row_classes={best_idx: "best"} if best_idx is not None else None)


# ----------------------------------------------------------------------------- evidence cards
def _mini_table(t) -> str:
    header = t.get("header") or []
    rows = (t.get("rows") or [])[:8]
    head = "".join(f"<th>{esc(h)}</th>" for h in header)
    body = "".join("<tr>" + "".join(f"<td>{esc(c)}</td>" for c in r) + "</tr>" for r in rows)
    more = ""
    if len(t.get("rows") or []) > 8:
        more = f'<div style="color:var(--muted);font-size:.75rem;margin-top:.2rem">… {len(t["rows"]) - 8} more rows</div>'
    return f'<div style="overflow:auto"><table class="rg-mini"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>{more}'


def evidence_cards(chunks, papers=None) -> str:
    papers = papers or {}
    top = max([c.get("score", 0) for c in chunks] or [1]) or 1
    out = []
    for c in chunks:
        src = c.get("source")
        kind = c.get("chunk_type", "text")
        kcolor = {"table": PURPLE, "caption": GRAY}.get(kind, BLUE)
        head = badge(src, color_for(src), solid=True)
        title = (papers.get(src) or {}).get("title")
        if title:
            head += Html(f'<span style="color:var(--muted);font-size:.78rem">{esc(title[:70])}</span>')
        head += badge(f"p.{c.get('page')}", GRAY) + (badge(c["evidence_location"], PURPLE) if c.get("evidence_location") else "")
        head += badge(kind.upper(), kcolor)
        if c.get("section"):
            head += badge(str(c["section"]), GRAY)
        pct = max(4, min(100, c.get("score", 0) / top * 100))
        head += Html(f'<span class="rg-score" title="relevance"><i style="width:{pct:.0f}%"></i></span>')
        if kind == "table" and isinstance(c.get("table"), dict):
            body = _mini_table(c["table"])
        else:
            text = " ".join(str(c.get("text", "")).split())
            body = esc(text[:650] + ("…" if len(text) > 650 else ""))
        out.append(f'<div class="rg-ev" style="--c:{color_for(src)}"><div class="h">{head}</div><div class="t">{body}</div></div>')
    return one_line("".join(out))


# ----------------------------------------------------------------------------- global results
def source_cards(results) -> str:
    out = []
    for i, r in enumerate(results, start=1):
        kind = r.get("kind", "paper")
        tag = badge("PAPER", BLUE, solid=True) if kind == "paper" else badge("WEB", GOOD, solid=True)
        meta = []
        if r.get("year"):
            meta.append(str(r["year"]))
        if r.get("journal"):
            meta.append(esc(r["journal"]))
        if r.get("cited_by"):
            meta.append(f"cited {r['cited_by']}×")
        oa = f' <a href="{esc(r["oa_url"])}" target="_blank">open-access ↗</a>' if r.get("oa_url") else ""
        abstract = " ".join((r.get("abstract") or "").split())
        out.append(f'<div class="rg-src">{tag}{badge(f"[{i}]", GRAY)}<a class="title" href="{esc(r.get("url"))}" target="_blank">{esc(r.get("title"))}</a>'
                   f'<div class="meta">{" · ".join(meta)}{oa}</div><div class="abs">{esc(abstract[:420])}{"…" if len(abstract) > 420 else ""}</div></div>')
    return one_line("".join(out))


def papers_table(results) -> str:
    rows = []
    for i, r in enumerate(results, start=1):
        link = Html(f'<a href="{esc(r.get("url"))}" target="_blank">{esc((r.get("title") or "")[:90])}</a>')
        cited = r.get("cited_by")
        rows.append({
            "#": i, "Type": badge("PAPER", BLUE) if r.get("kind") == "paper" else badge("WEB", GOOD),
            "Title": link, "Year": r.get("year"), "Journal": r.get("journal"),
            "Cited by": Html(f'<div class="rg-bar"><i style="width:{min(100, (cited or 0) / 2):.0f}%;background:#2563eb"></i><b>{cited}</b></div>') if cited is not None else "–",
            "Open access": badge("yes", GOOD) if r.get("oa_url") else badge("no", GRAY),
        })
    return table(rows, ["#", "Type", "Title", "Year", "Journal", "Cited by", "Open access"], numeric=("#", "Year"))
