"""Build outputs/executive_report.html: the executive view as one self-contained page.

    python make_report.py

It needs nothing but a browser to open, so it can be emailed or read on a phone. It shows the
same numbers as the Streamlit app, because both read the tables that views.py prepares.
"""
import html
import json

import numpy as np
import pandas as pd

import config as C
import views as V

esc = html.escape

CSS = """
.report{color-scheme:light;--page:#f9f9f7;--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--muted:#898781;
--grid:#e1e0d9;--axis:#c3c2b7;--ring:rgba(11,11,11,.10);--s1:#2a78d6;--s2:#eb6834;--band:#cde2fb;
--good:#0ca30c;--serious:#ec835a;--critical:#d03b3b;--ca:#184f95;--cb:#3987e5;--cc:#86b6ef;
--on-a:#fff;--on-b:#fff;--on-c:#0b0b0b}
@media (prefers-color-scheme:dark){:root:where(:not([data-theme="light"])) .report{color-scheme:dark;--page:#0d0d0d;
--surface:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--grid:#2c2c2a;--axis:#383835;--ring:rgba(255,255,255,.10);
--s1:#3987e5;--s2:#d95926;--band:#1c3350;--ca:#86b6ef;--cb:#3987e5;--cc:#1c5cab;--on-a:#0b0b0b;--on-b:#fff;--on-c:#fff}}
:root[data-theme="dark"] .report{color-scheme:dark;--page:#0d0d0d;--surface:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;
--grid:#2c2c2a;--axis:#383835;--ring:rgba(255,255,255,.10);--s1:#3987e5;--s2:#d95926;--band:#1c3350;--ca:#86b6ef;
--cb:#3987e5;--cc:#1c5cab;--on-a:#0b0b0b;--on-b:#fff;--on-c:#fff}
*{box-sizing:border-box}body{margin:0;background:var(--page)}
.report{font-family:system-ui,-apple-system,"Segoe UI",sans-serif;color:var(--ink);background:var(--page);
line-height:1.5;padding:24px 16px 56px}
.wrap{max-width:1040px;margin:0 auto}
h1{font-size:26px;margin:0 0 4px;font-weight:650}h2{font-size:19px;margin:36px 0 4px;font-weight:650}
h3{font-size:15px;margin:18px 0 6px;font-weight:650}
.sub{color:var(--ink2);margin:0 0 14px;font-size:14px}.muted{color:var(--muted);font-size:13px}
.card{background:var(--surface);border:1px solid var(--ring);border-radius:12px;padding:16px 18px;margin:10px 0}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px;margin:14px 0}
.tile{background:var(--surface);border:1px solid var(--ring);border-radius:12px;padding:12px 14px}
.tile .l{font-size:13px;color:var(--ink2)}.tile .v{font-size:26px;font-weight:650;margin:2px 0}
.tile .d{font-size:12.5px;color:var(--ink2)}
.todo{margin:6px 0 0;padding-left:20px}.todo li{margin:3px 0}
.scroll{overflow-x:auto;-webkit-overflow-scrolling:touch}
table{border-collapse:collapse;width:100%;font-size:13.5px}
th,td{padding:7px 10px;text-align:left;border-bottom:1px solid var(--grid);white-space:nowrap}
th{font-weight:600;color:var(--ink2);font-size:12.5px;white-space:normal;vertical-align:bottom}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
td.w{white-space:normal;min-width:180px}
.chip{display:inline-flex;gap:6px;align-items:center;font-size:12.5px;white-space:nowrap}
.chip i{font-style:normal;font-size:11px}
.i-excess{color:var(--serious)}.i-short{color:var(--critical)}.i-ok{color:var(--good)}
.legend{display:flex;gap:16px;flex-wrap:wrap;font-size:13px;color:var(--ink2);margin:4px 0 6px}
.legend span{display:inline-flex;align-items:center;gap:6px}
.key{display:inline-block;width:16px;height:2px;border-radius:1px}.sw{display:inline-block;width:10px;height:10px;border-radius:2px}
.chart{position:relative}.chart svg{width:100%;height:auto;display:block;touch-action:pan-y}
.tip{position:absolute;display:none;pointer-events:none;background:var(--surface);border:1px solid var(--axis);
border-radius:8px;padding:6px 9px;font-size:12px;box-shadow:0 2px 8px rgba(0,0,0,.12);white-space:nowrap;z-index:2}
.tip b{display:block;margin-bottom:2px}.tip .sw{margin-right:6px}
svg text{font-family:inherit;fill:var(--muted);font-size:11px}
svg .lab{fill:var(--ink2);font-size:12px}
.bu-head,.bu-row{display:grid;grid-template-columns:160px 125px 1fr 140px;gap:8px 14px;align-items:center}
.bu-head{font-size:12px;color:var(--muted);padding:0 0 4px}
.bu-row{padding:7px 0;border-bottom:1px solid var(--grid)}
.bu-row .nm{font-weight:600;font-size:14px}.bu-row .vt{font-size:12px;color:var(--muted);display:block;font-weight:400}
.bu-row .vl{font-size:13px;font-variant-numeric:tabular-nums}.bu-row .vl small{display:block;color:var(--ink2);font-size:12px}
.bu-row svg{width:100%;height:auto;display:block}
.axis-labels{position:relative;height:14px;font-size:11px;color:var(--muted)}
.axis-labels span{position:absolute;transform:translateX(-50%)}
details{margin:8px 0}summary{cursor:pointer;color:var(--ink2);font-size:13.5px}
details.vert{background:var(--surface);border:1px solid var(--ring);border-radius:10px;padding:10px 14px;margin:8px 0}
details.vert summary{font-weight:600;color:var(--ink);font-size:14.5px}
p{margin:8px 0}
@media (max-width:760px){.bu-head{display:none}
.bu-row{grid-template-columns:1fr auto}.bu-row .ch{grid-column:1/3;grid-row:2}.bu-row .vl{grid-column:2;grid-row:1;text-align:right}
.bu-row .bar{grid-column:1/3;grid-row:3}.bu-row .st{grid-column:1;grid-row:2}
h1{font-size:22px}.tile .v{font-size:22px}}
"""

JS = """
document.querySelectorAll('.chart[data-hover]').forEach(function(el){
  var d=JSON.parse(el.querySelector('script[type="application/json"]').textContent);
  var svg=el.querySelector('svg'),tip=el.querySelector('.tip'),cross=svg.querySelector('.cross'),
      dots=svg.querySelectorAll('.hdot'),vb=svg.viewBox.baseVal;
  function at(e){var r=svg.getBoundingClientRect(),x=(e.clientX-r.left)/r.width*vb.width;
    var i=Math.round((x-d.x0)/(d.x1-d.x0)*(d.n-1));i=Math.max(0,Math.min(d.n-1,i));
    var px=d.x0+(d.x1-d.x0)*i/(d.n-1);
    cross.setAttribute('x1',px);cross.setAttribute('x2',px);cross.style.display='';
    d.series.forEach(function(s,k){dots[k].setAttribute('cx',px);dots[k].setAttribute('cy',s.ys[i]);dots[k].style.display='';});
    tip.innerHTML='<b>'+d.labels[i]+'</b>'+d.series.map(function(s){
      return '<div><span class="sw" style="background:var('+s.color+')"></span>'+s.name+': '+s.vals[i]+'</div>';}).join('');
    tip.style.display='block';var er=el.getBoundingClientRect(),w=tip.offsetWidth,l=e.clientX-er.left+14;
    if(l+w>er.width)l=e.clientX-er.left-w-14;tip.style.left=Math.max(0,l)+'px';tip.style.top='8px';}
  function off(){tip.style.display='none';cross.style.display='none';dots.forEach(function(x){x.style.display='none';});}
  svg.addEventListener('pointermove',at);svg.addEventListener('pointerdown',at);svg.addEventListener('pointerleave',off);
});
"""

STATUS = {
    "Excess": ("▲", "i-excess", "Above range"),
    "Short": ("▼", "i-short", "Below range"),
    "In range": ("●", "i-ok", "In range"),
}


def chip(status):
    icon, cls, label = STATUS[status]
    return f'<span class="chip"><i class="{cls}" aria-hidden="true">{icon}</i>{label}</span>'


def table(df, fmt=None, wide=()):
    fmt = fmt or {}
    head, rows = [], []
    nums = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    for c in df.columns:
        head.append(f'<th class="{"n" if c in nums else ""}">{esc(str(c))}</th>')
    for _, r in df.iterrows():
        cells = []
        for c in df.columns:
            v = r[c]
            if c == "Status":
                cells.append(f"<td>{chip(v)}</td>")
            elif c in nums:
                default = "{:,.0f}" if pd.api.types.is_integer_dtype(df[c]) else "{:,.1f}"
                s = "" if pd.isna(v) else fmt.get(c, default).format(v)
                if s.startswith("-") and not s.strip("-0.,"):
                    s = s[1:]                 # show 0.0, not -0.0
                cells.append(f'<td class="n">{s}</td>')
            else:
                cells.append(f'<td class="{"w" if c in wide else ""}">{esc(str(v))}</td>')
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return f'<div class="scroll"><table><thead><tr>{"".join(head)}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'


def nice_ticks(lo, hi, n=4):
    span = hi - lo if hi > lo else 1
    raw = span / n
    mag = 10 ** np.floor(np.log10(raw))
    step = next(s * mag for s in (1, 2, 2.5, 5, 10) if s * mag >= raw)
    start = np.floor(lo / step) * step
    ticks = np.arange(start, hi + step * 0.999, step)
    return [float(t) for t in ticks]


def line_chart(df, colors, fmt, area=False, label_ends=True, name="chart"):
    W, H, L, R, T, B = 640, 230, 46, 96, 14, 28
    n = len(df)
    dmin, dmax = df.min().min(), df.max().max()
    lo0 = dmin * 0.97 if area else min(dmin, 0)
    ticks = nice_ticks(lo0, dmax)
    if lo0 < 0 and len(ticks) > 1 and ticks[0] < lo0 - (ticks[1] - ticks[0]) * 0.75:
        ticks = ticks[1:]          # do not waste half the chart on a tick far below the data
    lo, hi = min(ticks[0], dmin), ticks[-1]
    x = lambda i: L + (W - L - R) * i / (n - 1)
    y = lambda v: T + (H - T - B) * (1 - (v - lo) / (hi - lo))
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{esc(name)}">']
    for t in ticks:
        out.append(f'<line x1="{L}" x2="{W - R}" y1="{y(t):.1f}" y2="{y(t):.1f}" stroke="var(--grid)" stroke-width="1"/>')
        out.append(f'<text x="{L - 8}" y="{y(t) + 4:.1f}" text-anchor="end">{fmt(t)}</text>')
    base = y(0) if lo <= 0 <= hi else H - B
    out.append(f'<line x1="{L}" x2="{W - R}" y1="{base:.1f}" y2="{base:.1f}" stroke="var(--axis)" stroke-width="1"/>')
    for i, ts in enumerate(df.index):
        if i % 6 == 0:
            out.append(f'<text x="{x(i):.1f}" y="{H - 8}" text-anchor="middle">{ts:%b %y}</text>')
    series = []
    ends = []
    for k, col in enumerate(df.columns):
        pts = [(x(i), y(v)) for i, v in enumerate(df[col])]
        path = "M" + " L".join(f"{px:.1f},{py:.1f}" for px, py in pts)
        if area:
            out.append(f'<path d="{path} L{pts[-1][0]:.1f},{base:.1f} L{pts[0][0]:.1f},{base:.1f} Z" fill="var({colors[k]})" opacity=".10"/>')
        out.append(f'<path d="{path}" fill="none" stroke="var({colors[k]})" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>')
        ends.append((pts[-1][1], col, colors[k]))
        series.append({"name": col, "color": colors[k], "ys": [round(p[1], 1) for p in pts],
                       "vals": [fmt(v) for v in df[col]]})
    ex = x(n - 1)
    for yy, col, c in ends:
        out.append(f'<circle cx="{ex:.1f}" cy="{yy:.1f}" r="4" fill="var({c})" stroke="var(--surface)" stroke-width="2"/>')
    ys_end = sorted(e[0] for e in ends)
    if label_ends and all(b - a >= 15 for a, b in zip(ys_end, ys_end[1:])):
        for yy, col, c in ends:
            out.append(f'<text class="lab" x="{ex + 9:.1f}" y="{yy + 4:.1f}">{esc(col)}</text>')
    out.append(f'<line class="cross" x1="0" x2="0" y1="{T}" y2="{H - B}" stroke="var(--axis)" stroke-width="1" style="display:none"/>')
    for s in series:
        out.append(f'<circle class="hdot" r="4" fill="var({s["color"]})" stroke="var(--surface)" stroke-width="2" style="display:none"/>')
    out.append("</svg>")
    data = {"x0": L, "x1": W - R, "n": n, "labels": [f"{t:%B %Y}" for t in df.index], "series": series}
    legend = ""
    if len(df.columns) > 1:
        legend = '<div class="legend">' + "".join(
            f'<span><i class="key" style="background:var({c})"></i>{esc(col)}</span>' for col, c in zip(df.columns, colors)) + "</div>"
    return (f'{legend}<div class="chart" data-hover="1">{"".join(out)}<div class="tip"></div>'
            f'<script type="application/json">{json.dumps(data)}</script></div>')


def data_table_details(df, fmt, label="Show the data as a table"):
    t = df.copy()
    t.insert(0, "Month", [f"{m:%b %Y}" for m in t.index])
    f = {c: fmt for c in df.columns}
    return f"<details><summary>{label}</summary>{table(t.reset_index(drop=True), f)}</details>"


def range_rows(bu):
    lo_x, hi_x, W = 0.4, 2.0, 400
    px = lambda v: (min(max(v, lo_x), hi_x) - lo_x) / (hi_x - lo_x) * W
    ticks = [0.5, 1.0, 1.5, 2.0]
    axis = "".join(f'<span style="left:{px(t) / W * 100:.1f}%">{t * 100:.0f}%</span>' for t in ticks)
    head = (f'<div class="bu-head"><div>Business unit</div><div>Status</div>'
            f'<div><div class="axis-labels">{axis}</div>Stock as a share of its target (shaded band = range)</div>'
            f'<div>Stock held</div></div>')
    rows = []
    color = {"Excess": "--serious", "Short": "--critical", "In range": "--good"}
    for _, r in bu.iterrows():
        lowx, highx, v = r["Range low (x target)"], r["Range high (x target)"], r["Stock vs target (x)"]
        tip = (f'{r["Business unit"]}: stock is {v:.2f} times its target; range is {lowx:.2f} to {highx:.2f} times target.')
        svg = (f'<svg viewBox="0 0 {W} 24" role="img" aria-label="{esc(tip)}"><title>{esc(tip)}</title>'
               f'<line x1="0" x2="{W}" y1="12" y2="12" stroke="var(--grid)"/>'
               f'<rect x="{px(lowx):.1f}" y="5" width="{px(highx) - px(lowx):.1f}" height="14" rx="4" fill="var(--band)"/>'
               f'<line x1="{px(1.0):.1f}" x2="{px(1.0):.1f}" y1="3" y2="21" stroke="var(--axis)" stroke-width="1.5"/>'
               f'<circle cx="{px(v):.1f}" cy="12" r="5.5" fill="var({color[r["Status"]]})" stroke="var(--surface)" stroke-width="2"/></svg>')
        if r["Status"] == "Excess":
            note = f'<small>₦{r["Above range (₦bn)"]:.1f}bn above range</small>'
        elif r["Status"] == "Short":
            note = f'<small>₦{r["Below range (₦bn)"]:.1f}bn below range</small>'
        else:
            note = "<small>within range</small>"
        rows.append(
            f'<div class="bu-row"><div class="nm">{esc(r["Business unit"])}<span class="vt">{esc(r["Vertical"])}</span></div>'
            f'<div class="st">{chip(r["Status"])}</div><div class="bar">{svg}</div>'
            f'<div class="vl">₦{r["Inventory (₦bn)"]:.1f}bn{note}</div></div>')
    return head + "".join(rows)


def abc_chart(abc):
    W, left, bar_w, bh, gap = 640, 120, 500, 26, 2
    out = [f'<svg viewBox="0 0 {W} 128" role="img" aria-label="Share of items, usage value and inventory value held by A, B and C items">']
    for r, (label, row) in enumerate(abc.iterrows()):
        y = 8 + r * 38
        out.append(f'<text class="lab" x="{left - 10}" y="{y + 17}" text-anchor="end">{esc(label)}</text>')
        x = left
        for cls, var, on in (("A", "--ca", "--on-a"), ("B", "--cb", "--on-b"), ("C", "--cc", "--on-c")):
            w = bar_w * row[cls] / 100
            seg = max(w - gap, 0)
            out.append(f'<rect x="{x:.1f}" y="{y}" width="{seg:.1f}" height="{bh}" rx="3" fill="var({var})">'
                       f'<title>{esc(label)}: class {cls} is {row[cls]:.1f}%</title></rect>')
            if seg >= 38:
                out.append(f'<text x="{x + seg / 2:.1f}" y="{y + 17}" text-anchor="middle" style="fill:var({on});font-weight:600">{row[cls]:.0f}%</text>')
            x += w
    out.append("</svg>")
    legend = '<div class="legend">' + "".join(
        f'<span><i class="sw" style="background:var({v})"></i>{t}</span>'
        for t, v in (("A items (the first 80% of usage value)", "--ca"), ("B items (next 15%)", "--cb"), ("C items (the rest)", "--cc"))) + "</div>"
    t = abc.round(1).reset_index().rename(columns={"index": "Share of"})
    t.columns = ["Share of", "A (%)", "B (%)", "C (%)"]
    return legend + "".join(out) + f"<details><summary>Show the data as a table</summary>{table(t)}</details>"


def build():
    d = V.load()
    last = d["last"]
    k = V.company_kpis(d)
    text, actions = V.summary_for(d, C.COMPANY)
    mom = k.inventory_value / k.inventory_prev - 1

    tiles = [
        ("Inventory value", f"₦{k.inventory_value / V.BN:,.1f}bn", f"{'up' if mom >= 0 else 'down'} {abs(mom):.1%} on last month"),
        ("Share of annual sales", f"{k.pct_of_sales:.1%}", f"turnover {k.turnover:.1f} times a year"),
        ("Days of stock", f"{k.days_of_inventory:.0f}", f"{k.days_of_inventory_yoy:.0f} a year ago"),
        ("Above range", f"₦{k.excess_value / V.BN:,.1f}bn", f"about ₦{k.excess_cost_month / V.MN:,.0f}m a month to hold"),
        ("Gap to finance", f"{k.gap_clean_pct:+.1%}", f"{k.gap_reported_pct:+.1%} before cleaning"),
    ]
    tiles_html = '<div class="tiles">' + "".join(
        f'<div class="tile"><div class="l">{a}</div><div class="v">{b}</div><div class="d">{c}</div></div>' for a, b, c in tiles) + "</div>"

    paras = "".join(f"<p>{esc(p)}</p>" for p in text.split("\n\n"))
    todo = '<ul class="todo">' + "".join(f"<li>{esc(a)}</li>" for a in actions) + "</ul>"

    bu = V.bu_table(d)
    vt = V.vertical_table(d)
    gap = V.gap_trend(d)
    trend = V.company_trend(d)[["Cleaned"]]
    gap_chart = line_chart(gap, ["--s2", "--s1"], lambda v: f"{v:.1f}%", name="Gap between inventory and finance balance, as reported and after cleaning")
    trend_chart = line_chart(trend, ["--s1"], lambda v: f"₦{v:,.0f}bn", area=True, name="Company inventory value after cleaning")

    warn_sections = []
    for kind, blurb in (
        ("Slow-moving", "No use for 6 months (12 for spare parts) while stock remains."),
        ("Expiry risk", "Stock would take longer than 80% of shelf life to use up."),
        ("May run short", "Stock covers less than 60% of normal days of cover."),
    ):
        v = V.warnings_view(d, kind, None, 8)
        body = "<p class='muted'>None.</p>" if v.empty else table(v, wide=("Why", "Item"))
        warn_sections.append(f"<h3>{kind}</h3><p class='sub'>{blurb}</p>{body}")

    verts = "".join(
        f'<details class="vert"><summary>{esc(n)}</summary>'
        + "".join(f"<p>{esc(p)}</p>" for p in V.summary_for(d, n)[0].split("\n\n"))
        + '<ul class="todo">' + "".join(f"<li>{esc(a)}</li>" for a in V.summary_for(d, n)[1]) + "</ul></details>"
        for n in C.VERTICALS)

    accuracy = d["accuracy"].copy()
    for c in accuracy.columns[1:]:
        accuracy[c] = accuracy[c] * 100
    accuracy.columns = ["Stock", "Seasonal model (%)", "3-month average (%)", "Fixed level (%)", "Seasonal model bias (%)"]
    flags = d["flags"].copy()
    for c in ("excess_share", "short_share", "flagged_share"):
        flags[c] = flags[c] * 100
    flags.columns = ["Range type", "Above range (%)", "Below range (%)", "Flagged in total (%)"]

    body = f"""
<div class="wrap">
<h1>{esc(C.COMPANY)}: inventory health</h1>
<p class="sub">{last:%B %Y}. Demo data: the company, its numbers and its problems are made up.</p>
{tiles_html}
<div class="card"><h3 style="margin-top:0">Summary and what to do</h3>{paras}<b>What to do</b>{todo}</div>

<h2>By vertical</h2>
<p class="sub">Days of stock is how long the stock would last at the current pace of sales.</p>
{table(vt)}

<h2>Is each business unit in range?</h2>
<p class="sub">The range is the stock the business normally needs for next month's expected sales, plus or minus what is normal. It moves with the seasons. Units above their range come first.</p>
<div class="card">{range_rows(bu)}</div>

<h2>One trusted number</h2>
<p class="sub">Gap between inventory and the finance balance. The reports disagree because of duplicate rows, sign errors and extra zeros. After cleaning, what is left is mostly timing.</p>
<div class="card">{gap_chart}{data_table_details(gap, "{:.2f}")}</div>
{table(V.issues_summary(d), {"Net effect, latest month (₦bn)": "{:,.2f}", "Size of errors, latest month (₦bn)": "{:,.2f}"})}
<h3>Biggest gaps to finance, latest month</h3>
{table(V.recon_view(d, 8))}

<h2>Inventory value over time</h2>
<div class="card">{trend_chart}{data_table_details(trend, "{:,.1f}")}</div>

<h2>Where the value is (ABC)</h2>
<p class="sub">About a quarter of items make up four-fifths of the usage value. Plan those first.</p>
<div class="card">{abc_chart(V.abc_company(d))}</div>

<h2>Early warnings</h2>
{"".join(warn_sections)}

<h2>Summary by vertical</h2>
{verts}

<h2>How well does the model work?</h2>
<p class="sub">Forecast error (WAPE) for next month's usage. Lower is better. The seasonal model beats both simple rivals except for spare parts, which are too lumpy for any of them.</p>
{table(accuracy)}
<p class="sub" style="margin-top:14px">Share of store-months flagged. A fixed range raises more alarms because it ignores the seasons.</p>
{table(flags)}
<p class="muted">Money is in naira billions (bn) or millions (m). Target days of cover are learned from the business's own history and must be agreed with the supply chain team before use.</p>
</div>"""
    page = (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{esc(C.COMPANY)} inventory health</title><style>{CSS}</style></head>'
            f'<body><div class="report">{body}</div><script>{JS}</script></body></html>')
    path = C.OUT_DIR / "executive_report.html"
    path.write_text(page, encoding="utf-8")
    return path


if __name__ == "__main__":
    p = build()
    print(f"wrote {p} ({p.stat().st_size / 1024:.0f} KB)")
