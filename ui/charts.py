"""Dependency-free SVG charts that follow the light/dark theme through CSS variables."""
from __future__ import annotations

import math

from . import components as C

W = 760


def _esc(x):
    return C.esc(x)


def _wrap(title, subtitle, svg) -> str:
    sub = f'<div class="cs">{_esc(subtitle)}</div>' if subtitle else ""
    return C.one_line(f'<div class="rg-chart"><div class="ct">{_esc(title)}</div>{sub}{svg}</div>')


def nice_ticks(lo, hi, n=5):
    if hi <= lo:
        hi = lo + 1
    raw = (hi - lo) / n
    mag = 10 ** math.floor(math.log10(raw))
    step = next(m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw)
    start = math.floor(lo / step) * step
    ticks, v = [], start
    while v <= hi + step * 0.5:
        ticks.append(round(v, 10))
        v += step
    return ticks


def _tick_label(v):
    return f"{v:g}"


def bar_chart_h(items, title, subtitle="", unit="", vmax=None) -> str:
    """items: dict(label, value, color, tip). Horizontal ranked bars."""
    if not items:
        return ""
    row_h, left, right, top = 30, 235, 70, 6
    h = top + row_h * len(items) + 8
    vmax = vmax or max(i["value"] for i in items) or 1
    parts = [f'<svg viewBox="0 0 {W} {h}" role="img">']
    for k, it in enumerate(items):
        y = top + k * row_h
        bw = max(3, (W - left - right) * it["value"] / vmax)
        label = it["label"] if len(it["label"]) <= 36 else it["label"][:35] + "…"
        stroke = ' stroke="#f59e0b" stroke-width="2"' if it.get("best") else ""
        parts.append(
            f'<g><title>{_esc(it.get("tip") or it["label"])}</title>'
            f'<text x="{left - 10}" y="{y + 18}" text-anchor="end" style="fill:var(--text);font-size:12.5px">{_esc(label)}</text>'
            f'<rect x="{left}" y="{y + 4}" width="{W - left - right}" height="20" rx="6" style="fill:var(--surface2)"/>'
            f'<rect x="{left}" y="{y + 4}" width="{bw:.1f}" height="20" rx="6" fill="{it["color"]}" opacity=".9"{stroke}/>'
            f'<text x="{left + bw + 8:.1f}" y="{y + 19}" style="fill:var(--text);font-size:12.5px;font-weight:700">'
            f'{it["value"]:g}{_esc(unit)}</text></g>')
    parts.append("</svg>")
    return _wrap(title, subtitle, "".join(parts))


def scatter(points, title, subtitle="", xlabel="", ylabel="", vline=None, legend=(), ymin=None, ymax=None) -> str:
    """points: dict(x, y, color, r, tip). vline: (x, label) draws a dashed limit and shades the region beyond."""
    if len(points) < 2:
        return ""
    H, l, r, t, b = 340, 58, 18, 14, 52
    xs, ys = [p["x"] for p in points], [p["y"] for p in points]
    if vline:
        xs.append(vline[0])
    x0, x1 = min(xs), max(xs)
    pad = (x1 - x0) * 0.08 or 1
    x0, x1 = max(0, x0 - pad) if min(xs) >= 0 else x0 - pad, x1 + pad
    y0 = ymin if ymin is not None else min(ys) - (max(ys) - min(ys)) * 0.1 - 1
    y1 = ymax if ymax is not None else max(ys) + (max(ys) - min(ys)) * 0.1 + 1
    if ymax is None:
        y1 = min(y1, 102) if max(ys) <= 100 else y1

    def X(v):
        return l + (v - x0) / (x1 - x0) * (W - l - r)

    def Y(v):
        return t + (1 - (v - y0) / (y1 - y0)) * (H - t - b)

    s = [f'<svg viewBox="0 0 {W} {H}" role="img">']
    for tv in nice_ticks(y0, y1):
        if y0 <= tv <= y1:
            s.append(f'<line x1="{l}" x2="{W - r}" y1="{Y(tv):.1f}" y2="{Y(tv):.1f}" style="stroke:var(--grid)"/>'
                     f'<text x="{l - 8}" y="{Y(tv) + 4:.1f}" text-anchor="end" style="fill:var(--muted);font-size:11.5px">{_tick_label(tv)}</text>')
    for tv in nice_ticks(x0, x1):
        if x0 <= tv <= x1:
            s.append(f'<line y1="{t}" y2="{H - b}" x1="{X(tv):.1f}" x2="{X(tv):.1f}" style="stroke:var(--grid)"/>'
                     f'<text x="{X(tv):.1f}" y="{H - b + 17}" text-anchor="middle" style="fill:var(--muted);font-size:11.5px">{_tick_label(tv)}</text>')
    if vline:
        vx = X(vline[0])
        s.append(f'<rect x="{vx:.1f}" y="{t}" width="{max(0, W - r - vx):.1f}" height="{H - t - b}" fill="#dc2626" opacity=".07"/>'
                 f'<line x1="{vx:.1f}" x2="{vx:.1f}" y1="{t}" y2="{H - b}" stroke="#dc2626" stroke-width="1.6" stroke-dasharray="6 4"/>'
                 f'<text x="{vx + 6:.1f}" y="{t + 13}" style="fill:#dc2626;font-size:11.5px;font-weight:700">{_esc(vline[1])}</text>')
    s.append(f'<line x1="{l}" x2="{W - r}" y1="{H - b}" y2="{H - b}" style="stroke:var(--muted)"/>'
             f'<line x1="{l}" x2="{l}" y1="{t}" y2="{H - b}" style="stroke:var(--muted)"/>')
    for p in points:
        s.append(f'<circle cx="{X(p["x"]):.1f}" cy="{Y(p["y"]):.1f}" r="{p.get("r", 7)}" fill="{p["color"]}" fill-opacity=".78" '
                 f'stroke="#fff" stroke-width="1.3"><title>{_esc(p.get("tip", ""))}</title></circle>')
    s.append(f'<text x="{(l + W - r) / 2:.0f}" y="{H - 10}" text-anchor="middle" style="fill:var(--muted);font-size:12px;font-weight:600">{_esc(xlabel)}</text>'
             f'<text transform="translate(15 {(t + H - b) / 2:.0f}) rotate(-90)" text-anchor="middle" style="fill:var(--muted);font-size:12px;font-weight:600">{_esc(ylabel)}</text></svg>')
    leg = "".join(f'<span style="margin-right:.9rem;font-size:.78rem;color:var(--text)"><span style="display:inline-block;width:10px;height:10px;'
                  f'border-radius:50%;background:{c};margin-right:.3rem"></span>{_esc(n)}</span>' for n, c in legend)
    return _wrap(title, subtitle, "".join(s) + (f'<div style="margin-top:.3rem">{leg}</div>' if leg else ""))


def column_chart(labels, series, title, subtitle="", colors=("#0d9488", "#f59e0b"), names=()) -> str:
    """series: list of value-lists (stacked). Vertical columns with value labels."""
    if not labels:
        return ""
    H, l, r, t, b = 250, 40, 12, 20, 42
    totals = [sum(s[i] for s in series) for i in range(len(labels))]
    ymax = max(totals) or 1
    ticks = nice_ticks(0, ymax, 4)
    if all(float(v).is_integer() for ser in series for v in ser):
        ticks = [t_ for t_ in ticks if float(t_).is_integer()] or [0, 1]
    ymax = max(ticks)
    slot = (W - l - r) / len(labels)
    bw = min(56, slot * 0.62)
    s = [f'<svg viewBox="0 0 {W} {H}" role="img">']
    for tv in ticks:
        y = t + (1 - tv / ymax) * (H - t - b)
        s.append(f'<line x1="{l}" x2="{W - r}" y1="{y:.1f}" y2="{y:.1f}" style="stroke:var(--grid)"/>'
                 f'<text x="{l - 6}" y="{y + 4:.1f}" text-anchor="end" style="fill:var(--muted);font-size:11px">{_tick_label(tv)}</text>')
    for i, lab in enumerate(labels):
        cx = l + slot * (i + 0.5)
        base = H - b
        for k, ser in enumerate(series):
            v = ser[i]
            if v <= 0:
                continue
            hh = v / ymax * (H - t - b)
            base -= hh
            s.append(f'<rect x="{cx - bw / 2:.1f}" y="{base:.1f}" width="{bw:.1f}" height="{hh:.1f}" rx="5" fill="{colors[k % len(colors)]}" opacity=".9">'
                     f'<title>{_esc(lab)}: {v:g}{(" " + names[k]) if names else ""}</title></rect>')
        s.append(f'<text x="{cx:.1f}" y="{base - 5:.1f}" text-anchor="middle" style="fill:var(--text);font-size:11.5px;font-weight:700">{totals[i]:g}</text>')
        short = lab if len(str(lab)) <= 9 else str(lab)[:8] + "…"
        s.append(f'<text x="{cx:.1f}" y="{H - b + 16}" text-anchor="middle" style="fill:var(--muted);font-size:11.5px">{_esc(short)}</text>')
    s.append(f'<line x1="{l}" x2="{W - r}" y1="{H - b}" y2="{H - b}" style="stroke:var(--muted)"/></svg>')
    leg = ""
    if names:
        leg = "".join(f'<span style="margin-right:.9rem;font-size:.78rem;color:var(--text)"><span style="display:inline-block;width:10px;height:10px;'
                      f'border-radius:3px;background:{colors[k % len(colors)]};margin-right:.3rem"></span>{_esc(n)}</span>' for k, n in enumerate(names))
    return _wrap(title, subtitle, "".join(s) + (f'<div style="margin-top:.2rem">{leg}</div>' if leg else ""))


# ----------------------------------------------------------------------------- chart builders from data
def _label(r):
    return f"{r.get('membrane') or r.get('solute') or 'record'} · {r.get('source')}"


def ranking_chart(records, metric="rejection_pct", papers=None):
    rows = [r for r in records if r.get(metric) is not None]
    if len(rows) < 2:
        return ""
    names = {"rejection_pct": ("Rejection ranking", " %", 100.0), "flux_lmh": ("Flux ranking", " LMH", None),
             "pressure_bar": ("Operating pressure", " bar", None)}
    title, unit, vmax = names.get(metric, (metric, "", None))
    top = max(r[metric] for r in rows)
    flux_max = max([r[metric] for r in rows] or [1])
    items = []
    for r in rows[:12]:
        color = C.heat(r[metric], 0, 100) if metric == "rejection_pct" else "#0891b2" if metric == "flux_lmh" else "#2563eb"
        tip = (f"{_label(r)} (p.{r.get('page')})\nrejection: {C.fmt(r.get('rejection_pct'))} % · pressure: {C.fmt(r.get('pressure_bar'), 2)} bar"
               f" · flux: {C.fmt(r.get('flux_lmh'))} LMH\nsolute: {r.get('solute') or '–'}")
        items.append({"label": _label(r), "value": round(r[metric], 2), "color": color, "tip": tip, "best": r[metric] == top})
    return bar_chart_h(items, title, "Ranked records that matched your question (gold outline = best)", unit, vmax)


def tradeoff_chart(records, pressure_limit=None):
    pts_src = [r for r in records if r.get("pressure_bar") is not None and r.get("rejection_pct") is not None]
    if len(pts_src) < 2:
        return ""
    flux_max = max([r["flux_lmh"] for r in pts_src if r.get("flux_lmh") is not None] or [1])
    groups = {}
    pts = []
    for r in pts_src:
        key = r.get("solute") or "unknown solute"
        col = groups.setdefault(key, C.PALETTE[len(groups) % len(C.PALETTE)])
        rad = 6 + (8 * r["flux_lmh"] / flux_max if r.get("flux_lmh") is not None else 0)
        pts.append({"x": r["pressure_bar"], "y": r["rejection_pct"], "color": col, "r": round(rad, 1),
                    "tip": f"{_label(r)}\nrejection {C.fmt(r['rejection_pct'])} % @ {C.fmt(r['pressure_bar'], 2)} bar\nflux {C.fmt(r.get('flux_lmh'))} LMH · {key}"})
    vl = (pressure_limit, f"limit {pressure_limit:g} bar") if pressure_limit is not None else None
    return scatter(pts, "Rejection vs operating pressure", "Bubble size = flux · colour = solute", "Pressure (bar)", "Rejection (%)",
                   vline=vl, legend=list(groups.items()), ymin=None, ymax=None)


def flux_rejection_chart(records):
    pts_src = [r for r in records if r.get("flux_lmh") is not None and r.get("rejection_pct") is not None]
    if len(pts_src) < 2:
        return ""
    groups, pts = {}, []
    for r in pts_src:
        key = r.get("membrane") or "unknown membrane"
        col = groups.setdefault(key, C.PALETTE[len(groups) % len(C.PALETTE)])
        pts.append({"x": r["flux_lmh"], "y": r["rejection_pct"], "color": col, "r": 7,
                    "tip": f"{_label(r)}\nflux {C.fmt(r['flux_lmh'])} LMH · rejection {C.fmt(r['rejection_pct'])} %"})
    legend = list(groups.items())[:8]
    return scatter(pts, "Flux vs rejection trade-off", "Top-right = permeable AND selective", "Flux (LMH)", "Rejection (%)", legend=legend)


def records_per_paper_chart(records):
    if not records:
        return ""
    ok, flagged = {}, {}
    for r in records:
        d = flagged if r.get("flags") else ok
        d[r["source"]] = d.get(r["source"], 0) + 1
    labels = sorted(set(ok) | set(flagged))
    return column_chart(labels, [[ok.get(s, 0) for s in labels], [flagged.get(s, 0) for s in labels]],
                        "Records per paper", "Green = all numbers verified · amber = has extraction flags",
                        colors=("#16a34a", "#f59e0b"), names=("verified", "flagged"))


def year_chart(results):
    years = [r["year"] for r in results if r.get("year")]
    if not years:
        return ""
    lo, hi = min(years), max(years)
    labels = list(range(lo, hi + 1))
    return column_chart([str(y) for y in labels], [[years.count(y) for y in labels]], "Results by publication year",
                        "How recent is the evidence?", colors=("#2563eb",))


def citations_chart(results):
    rows = [r for r in results if r.get("cited_by")]
    if len(rows) < 2:
        return ""
    rows = sorted(rows, key=lambda r: -r["cited_by"])[:8]
    items = [{"label": (r["title"] or "")[:60], "value": r["cited_by"], "color": "#2563eb",
              "tip": f"{r['title']} ({r.get('year')})"} for r in rows]
    return bar_chart_h(items, "Most cited results", "Citation counts from OpenAlex", " cites")
