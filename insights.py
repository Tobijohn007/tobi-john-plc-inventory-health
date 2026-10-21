"""Part D: the monthly insight summary.

The code calculates every number, then writes a short plain-language summary for each vertical
and for the whole company: what changed, what it means and what to do.

In this demo the sentences come from fixed templates, so the summary works offline and every
number in it can be traced to a table. In the real project an AI language model can replace
`write_summary` to make the wording more natural. The model is only given the facts below, and
the numbers still come from this code, so the figures stay accurate.
"""
import numpy as np
import pandas as pd

import config as C


def money(x):
    x = float(x)
    return f"₦{x / 1e9:,.1f}bn" if abs(x) >= 1e9 else f"₦{x / 1e6:,.0f}m"


def _count(n, one, many):
    """'1 item has' or '5 items have'."""
    return f"{n} {one if n == 1 else many}"


def change_text(now, before):
    if not before:
        return "unchanged"
    c = now / before - 1
    return f"{'up' if c >= 0 else 'down'} {abs(c):.1%}"


def _scope(df, name):
    return df if name == C.COMPANY else df[df["vertical"] == name]


def collect_facts(name, ctx):
    last, prev, yoy = ctx["last"], ctx["prev"], ctx["yoy"]
    level = "company" if name == C.COMPANY else "vertical"
    m = ctx["metrics"]
    m = m[(m["level"] == level) & (m["name"] == name)].set_index("month")
    now, before, ago = m.loc[last], m.loc[prev], m.loc[yoy]

    bu = _scope(ctx["bu_adequacy"], name)
    bu = bu[bu["month"] == last]
    excess = bu[bu["status"] == "Excess"].sort_values("excess_value", ascending=False)
    short = bu[bu["status"] == "Short"].sort_values("shortfall_value", ascending=False)

    abc = _scope(ctx["abc"], name)
    a = abc[abc["abc_class"] == "A"]

    w = _scope(ctx["warnings"], name)
    slow = w[w["warning_type"] == "Slow-moving"]
    expiry = w[w["warning_type"] == "Expiry risk"]
    runshort = w[w["warning_type"] == "May run short"]

    rec = _scope(ctx["recon"], name)
    finance = rec["finance_balance"].sum()
    iss = _scope(ctx["issues"], name)
    iss = iss[(iss["month"] == last) & (~iss["issue_type"].str.contains("flagged only"))]

    return {
        "name": name, "level": level,
        "inventory_value": now["inventory_value"], "inventory_prev": before["inventory_value"],
        "inventory_yoy": ago["inventory_value"],
        "pct_of_sales": now["inventory_pct_of_sales"],
        "days_of_inventory": now["days_of_inventory"], "days_of_inventory_yoy": ago["days_of_inventory"],
        "turnover": now["turnover"],
        "n_units": len(bu), "n_excess": len(excess), "n_short": len(short),
        "n_in_range": int((bu["status"] == "In range").sum()),
        "excess_value": float(bu["excess_value"].sum()),
        "excess_cost_month": float(bu["excess_holding_cost_month"].sum()),
        "excess_units": excess[["business_unit", "excess_value"]].values.tolist(),
        "short_units": short[["business_unit", "shortfall_value"]].values.tolist(),
        "a_items": len(a), "a_items_pct": len(a) / max(len(abc), 1),
        "a_usage_pct": a["usage_value_12m"].sum() / max(abc["usage_value_12m"].sum(), 1),
        "a_inventory_pct": a["closing_value"].sum() / max(abc["closing_value"].sum(), 1),
        "n_slow": len(slow), "slow_value": float(slow["amount"].sum()),
        "n_expiry": len(expiry), "expiry_value": float(expiry["amount"].sum()),
        "n_runshort": len(runshort),
        "reported_value": rec["reported_value"].sum(), "clean_value": rec["clean_value"].sum(),
        "finance_value": finance,
        "gap_reported_pct": rec["gap_reported"].sum() / finance,
        "gap_clean_pct": rec["gap_clean"].sum() / finance,
        "n_fixed": len(iss), "fixed_value": float(iss["impact_value"].abs().sum()),
    }


def write_summary(f):
    """Turn the facts into plain sentences. Replace this with a language model if wanted."""
    name = f["name"]
    p1 = (f"{name} holds {money(f['inventory_value'])} of inventory, "
          f"{change_text(f['inventory_value'], f['inventory_prev'])} on last month and "
          f"{change_text(f['inventory_value'], f['inventory_yoy'])} on a year ago. "
          f"That is {f['pct_of_sales']:.1%} of annual sales, or {f['days_of_inventory']:.0f} days of stock "
          f"({f['days_of_inventory_yoy']:.0f} a year ago).")

    p2 = f"Of {f['n_units']} business units, {f['n_excess']} are above their range, {f['n_short']} below it and {f['n_in_range']} in range."
    if f["n_excess"]:
        top, topv = f["excess_units"][0]
        p2 += (f" In total {money(f['excess_value'])} sits above range, costing about "
               f"{money(f['excess_cost_month'])} a month to hold. The largest is {top}, at {money(topv)} above the top of its range.")
    if f["n_short"]:
        s, sv = f["short_units"][0]
        p2 += f" {s} is {money(sv)} below the bottom of its range, so supply needs checking before it runs out."

    p3 = (f"{f['a_items']} A items ({f['a_items_pct']:.0%} of items) make up {f['a_usage_pct']:.0%} of usage value "
          f"and hold {f['a_inventory_pct']:.0%} of inventory value, so planning effort should start there.")

    p4 = []
    if f["n_slow"]:
        p4.append(f"{_count(f['n_slow'], 'item has', 'items have')} not moved for months and "
                  f"{'holds' if f['n_slow'] == 1 else 'hold'} {money(f['slow_value'])}.")
    if f["n_expiry"]:
        p4.append(f"{_count(f['n_expiry'], 'item may', 'items may')} expire before use, "
                  f"with {money(f['expiry_value'])} at risk.")
    if f["n_runshort"]:
        p4.append(f"{_count(f['n_runshort'], 'item holds', 'items hold')} less than 60% of normal cover.")
    p4 = " ".join(p4)

    p5 = (f"As reported, inventory differs from the finance balance by {f['gap_reported_pct']:+.1%}. "
          f"After cleaning, the gap is {f['gap_clean_pct']:+.1%}. "
          f"{_count(f['n_fixed'], 'data error', 'data errors')} worth {money(f['fixed_value'])} "
          f"{'was' if f['n_fixed'] == 1 else 'were'} corrected this month.")
    if abs(f["gap_clean_pct"]) > abs(f["gap_reported_pct"]):
        p5 += " The reported figure looked closer to finance only because errors partly cancelled each other out."
    if abs(f["gap_clean_pct"]) > 0.005:
        p5 += " The remaining gap looks like timing, such as receipts not yet posted, and should be checked with finance."

    todo = []
    if f["n_excess"]:
        names = ", ".join(u for u, _ in f["excess_units"][:3])
        todo.append(f"Hold back purchasing in {names} until stock falls back into range.")
    if f["n_slow"]:
        todo.append("Review the slow-moving items, starting with A items, and decide whether to sell, return or write them down.")
    if f["n_expiry"]:
        todo.append("Use at-risk items first, and agree a promotion or transfer for stock that cannot be used in time.")
    if f["n_short"] or f["n_runshort"]:
        todo.append("Raise orders for the items and units running short, starting with A items.")
    if abs(f["gap_clean_pct"]) > 0.005:
        todo.append("Agree with finance how to close the remaining gap, and use one inventory number in S&OP.")
    if not todo:
        todo.append("No action needed beyond the usual monthly review.")

    parts = [p1, p2, p3] + ([p4] if p4 else []) + [p5]
    return "\n\n".join(parts), todo


def build_summaries(metrics, bu_adequacy, abc, warnings, recon, issues):
    last = metrics["month"].max()
    ctx = {
        "last": last, "prev": last - pd.DateOffset(months=1), "yoy": last - pd.DateOffset(months=12),
        "metrics": metrics, "bu_adequacy": bu_adequacy, "abc": abc, "warnings": warnings,
        "recon": recon[recon["month"] == last], "issues": issues,
    }
    names = [C.COMPANY] + list(C.VERTICALS)
    facts = [collect_facts(n, ctx) for n in names]
    rows = []
    for f in facts:
        body, todo = write_summary(f)
        rows.append({"level": f["level"], "name": f["name"], "summary": body,
                     "actions": "\n".join(todo)})
    kpis = pd.DataFrame(facts).drop(columns=["excess_units", "short_units"])
    return pd.DataFrame(rows), kpis, last


def as_markdown(summaries, last):
    lines = [f"# {C.COMPANY}: inventory health summary for {last:%B %Y}", ""]
    for _, r in summaries.iterrows():
        lines += [f"## {r['name']}", "", r["summary"], "", "**What to do**", ""]
        lines += [f"- {a}" for a in r["actions"].split("\n")]
        lines.append("")
    return "\n".join(lines)
