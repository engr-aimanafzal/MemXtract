"""Light / dark theme for the whole app.

The app does not depend on Streamlit's own theme: every colour is set here, so the 🌙 toggle works the same
on every Streamlit version. Components (tables, charts, cards) use the same palette via CSS variables.
"""
from __future__ import annotations

LIGHT = dict(
    bg="#f3f6fb", surface="#ffffff", surface2="#eef2f8", border="#dbe3ef", text="#0f172a", muted="#5b6b82",
    primary="#0d9488", primary2="#2563eb", accent="#f59e0b", good="#16a34a", warn="#d97706", bad="#dc2626",
    shadow="0 1px 2px rgba(15,23,42,.06), 0 6px 18px rgba(15,23,42,.06)", grid="#e3e9f3",
    hero="linear-gradient(135deg,#0d9488 0%,#2563eb 100%)",
)
DARK = dict(
    bg="#0a101d", surface="#121a2c", surface2="#19243b", border="#27344f", text="#e8eef8", muted="#9db0cb",
    primary="#2dd4bf", primary2="#60a5fa", accent="#fbbf24", good="#4ade80", warn="#fbbf24", bad="#f87171",
    shadow="0 1px 2px rgba(0,0,0,.5), 0 8px 24px rgba(0,0,0,.35)", grid="#243149",
    hero="linear-gradient(135deg,#0f766e 0%,#1d4ed8 100%)",
)


def palette(dark: bool) -> dict:
    return DARK if dark else LIGHT


def css(dark: bool) -> str:
    p = palette(dark)
    root = ";".join(f"--{k}:{v}" for k, v in p.items())
    return f"""<style>
:root{{{root}}}
.stApp,[data-testid="stAppViewContainer"],[data-testid="stMain"]{{background:var(--bg)!important;color:var(--text)}}
[data-testid="stHeader"]{{background:transparent!important}}
[data-testid="stBottom"],[data-testid="stBottom"]>div,[data-testid="stBottomBlockContainer"]{{background:var(--bg)!important}}
.block-container{{padding-top:1.4rem;max-width:1250px}}
[data-testid="stSidebar"]{{background:var(--surface)!important;border-right:1px solid var(--border)}}
h1,h2,h3,h4,h5,h6,p,li,label,.stMarkdown,[data-testid="stMarkdownContainer"],[data-testid="stWidgetLabel"] p,
[data-testid="stCaptionContainer"]{{color:var(--text)}}
[data-testid="stCaptionContainer"],small{{color:var(--muted)!important}}
a{{color:var(--primary2)}}
hr{{border-color:var(--border)}}
/* inputs */
[data-baseweb="input"],[data-baseweb="textarea"],[data-baseweb="select"]>div,[data-baseweb="base-input"]{{
 background:var(--surface2)!important;border-color:var(--border)!important;color:var(--text)!important}}
input,textarea,[data-baseweb="select"] *{{color:var(--text)!important}}
[data-testid="stChatInput"]{{background:var(--surface)!important;border:1px solid var(--border);border-radius:16px;box-shadow:var(--shadow)}}
[data-testid="stChatInput"] textarea{{color:var(--text)!important;background:transparent!important}}
[data-baseweb="popover"],[data-baseweb="popover"]>div,[data-baseweb="menu"],ul[role="listbox"]{{background:var(--surface)!important;color:var(--text)!important}}
li[role="option"]{{color:var(--text)!important}}
li[role="option"]:hover{{background:var(--surface2)!important}}
/* buttons */
.stButton>button,.stDownloadButton>button{{background:var(--surface);color:var(--text);border:1px solid var(--border);
 border-radius:12px;font-weight:550;transition:all .15s}}
.stButton>button:hover,.stDownloadButton>button:hover{{border-color:var(--primary);color:var(--primary);transform:translateY(-1px)}}
.stButton>button[kind="primary"]{{background:linear-gradient(135deg,var(--primary),var(--primary2));color:#fff;border:0}}
.stButton>button[kind="primary"]:hover{{color:#fff;filter:brightness(1.08)}}
/* expanders, alerts, tabs */
[data-testid="stExpander"]{{background:var(--surface);border:1px solid var(--border)!important;border-radius:14px}}
[data-testid="stExpander"] summary,[data-testid="stExpander"] summary *{{color:var(--text)!important}}
[data-testid="stAlert"]{{background:var(--surface2)!important;border:1px solid var(--border);border-radius:12px;color:var(--text)}}
[data-testid="stAlert"] *{{color:var(--text)!important}}
button[role="tab"]{{color:var(--muted)!important;font-weight:600}}
button[role="tab"][aria-selected="true"]{{color:var(--primary)!important}}
[data-baseweb="tab-highlight"]{{background:var(--primary)!important}}
[data-baseweb="tab-border"]{{background:var(--border)!important}}
[data-testid="stStatusWidget"],[data-testid="stStatus"]{{background:var(--surface)!important;border-color:var(--border)!important}}
code,pre{{background:var(--surface2)!important;color:var(--text)!important;border-radius:8px}}
[data-testid="stProgress"] div[role="progressbar"] > div{{background:linear-gradient(90deg,var(--primary),var(--primary2))!important}}
/* keyed containers = cards */
[class*="st-key-card"]{{background:var(--surface);border:1px solid var(--border);border-radius:18px;padding:1.1rem 1.3rem;
 box-shadow:var(--shadow);margin-bottom:.8rem}}
[class*="st-key-card_answer"]{{border-left:5px solid var(--primary)}}
/* radio used as a segmented control */
[data-testid="stRadio"] [role="radiogroup"]{{gap:.35rem}}
/* ---------- components ---------- */
.rg-hero{{background:var(--hero);color:#fff;border-radius:22px;padding:1.5rem 1.8rem;margin-bottom:1rem;box-shadow:var(--shadow)}}
.rg-hero h1{{color:#fff!important;margin:0;font-size:1.85rem;letter-spacing:-.02em}}
.rg-hero p{{color:rgba(255,255,255,.88)!important;margin:.35rem 0 .7rem}}
.rg-chip{{display:inline-block;padding:.18rem .65rem;border-radius:999px;font-size:.78rem;font-weight:600;margin:0 .35rem .3rem 0;
 background:rgba(255,255,255,.18);color:#fff;border:1px solid rgba(255,255,255,.28)}}
.rg-brand{{display:flex;align-items:center;gap:.6rem;font-weight:800;font-size:1.1rem;color:var(--text);margin-bottom:.4rem}}
.rg-brand span.logo{{background:var(--hero);border-radius:12px;width:38px;height:38px;display:flex;align-items:center;justify-content:center;font-size:1.3rem}}
.rg-badge{{display:inline-block;padding:.12rem .55rem;border-radius:999px;font-size:.74rem;font-weight:650;white-space:nowrap;margin:1px 3px 1px 0}}
.rg-stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:.75rem;margin:.2rem 0 1rem}}
.rg-stat{{background:var(--surface);border:1px solid var(--border);border-radius:16px;padding:.8rem 1rem;box-shadow:var(--shadow);border-top:4px solid var(--c,var(--primary))}}
.rg-stat .l{{font-size:.74rem;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);font-weight:700}}
.rg-stat .v{{font-size:1.55rem;font-weight:800;color:var(--text);line-height:1.2;margin-top:.15rem}}
.rg-stat .s{{font-size:.8rem;color:var(--muted);margin-top:.1rem}}
.rg-table-wrap{{margin-bottom:.9rem;overflow:auto;max-height:520px;border:1px solid var(--border);border-radius:14px;background:var(--surface);box-shadow:var(--shadow)}}
table.rg-table{{border-collapse:separate;border-spacing:0;width:100%;font-size:.86rem;color:var(--text)}}
table.rg-table th{{position:sticky;top:0;z-index:1;background:var(--surface2);color:var(--muted);text-align:left;font-size:.72rem;
 text-transform:uppercase;letter-spacing:.05em;padding:.6rem .7rem;border-bottom:1px solid var(--border);white-space:nowrap}}
table.rg-table td{{padding:.5rem .7rem;border-bottom:1px solid var(--border);vertical-align:middle;color:var(--text)}}
table.rg-table tr:last-child td{{border-bottom:0}}
table.rg-table tr:hover td{{background:var(--surface2)}}
table.rg-table tr.best td{{box-shadow:inset 0 0 0 9999px rgba(245,158,11,.10)}}
table.rg-table td.num{{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}}
.rg-bar{{position:relative;min-width:92px;height:22px;border-radius:7px;background:var(--surface2);overflow:hidden}}
.rg-bar i{{position:absolute;left:0;top:0;bottom:0;border-radius:7px;opacity:.85}}
.rg-bar b{{position:relative;display:block;text-align:right;padding:0 .45rem;line-height:22px;font-size:.8rem;color:var(--text)}}
.rg-ev{{background:var(--surface);border:1px solid var(--border);border-left:5px solid var(--c,var(--primary));border-radius:14px;
 padding:.7rem .9rem;margin-bottom:.6rem}}
.rg-ev .h{{display:flex;flex-wrap:wrap;gap:.35rem;align-items:center;margin-bottom:.35rem}}
.rg-ev .t{{font-size:.84rem;color:var(--text);line-height:1.5}}
.rg-score{{display:inline-block;width:70px;height:7px;border-radius:5px;background:var(--surface2);vertical-align:middle;overflow:hidden}}
.rg-score i{{display:block;height:100%;background:linear-gradient(90deg,var(--primary),var(--primary2))}}
.rg-note{{border-radius:12px;padding:.65rem .9rem;margin:.5rem 0;font-size:.88rem;border:1px solid var(--border);background:var(--surface2);color:var(--text)}}
.rg-note.warn{{border-left:5px solid var(--warn)}} .rg-note.bad{{border-left:5px solid var(--bad)}} .rg-note.good{{border-left:5px solid var(--good)}}
.rg-note.info{{border-left:5px solid var(--primary2)}}
.rg-src{{background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:.75rem 1rem;margin-bottom:.6rem;box-shadow:var(--shadow)}}
.rg-src a.title{{font-weight:700;color:var(--text);text-decoration:none;font-size:.95rem}}
.rg-src a.title:hover{{color:var(--primary)}}
.rg-src .meta{{color:var(--muted);font-size:.8rem;margin:.2rem 0}}
.rg-src .abs{{color:var(--text);font-size:.84rem;line-height:1.45;opacity:.9}}
.rg-step{{display:flex;gap:.7rem;align-items:flex-start;background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:.7rem .9rem;margin-bottom:.5rem}}
.rg-step .n{{width:28px;height:28px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:800;color:#fff;flex:none}}
.rg-chart{{background:var(--surface);border:1px solid var(--border);border-radius:16px;padding:.7rem .9rem;box-shadow:var(--shadow);margin-bottom:.8rem}}
.rg-chart .ct{{font-weight:700;color:var(--text);font-size:.92rem;margin-bottom:.1rem}}
.rg-chart .cs{{color:var(--muted);font-size:.78rem;margin-bottom:.3rem}}
.rg-chart svg{{width:100%;height:auto;display:block}}
.rg-mini{{border-collapse:collapse;font-size:.78rem;width:100%}}
.rg-mini th{{background:#0f766e;color:#fff;padding:.25rem .5rem;text-align:left}}
.rg-mini td{{padding:.2rem .5rem;border-bottom:1px solid var(--border);color:var(--text)}}
</style>"""
