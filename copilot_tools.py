"""The copilot's 'tools': plain functions that read the model's results and return facts.
Every number the copilot says comes from here, never from a language model's memory."""
import pandas as pd

import config as C

O = C.OUT_DIR
_cache = {}


def _t(name):
    if name not in _cache:
        df = pd.read_csv(O / f"{name}.csv")
        if "month" in df.columns:
            df["month"] = pd.to_datetime(df["month"])
        _cache[name] = df
    return _cache[name]


def bn(x):
    return f"₦{x / 1e9:,.1f}bn"


def mn(x):
    return f"₦{x / 1e6:,.0f}m"


def units():
    return sorted(_t("adequacy_business_units")["business_unit"].unique())


def verticals():
    return sorted(_t("adequacy_business_units")["vertical"].unique())


def _latest():
    a = _t("adequacy_business_units")
    return a[a["month"] == a["month"].max()]


def company_overview():
    k = _t("kpis")
    c = k[k["level"] == "company"].iloc[0]
    return {"month": f"{_latest()['month'].iloc[0]:%B %Y}", "inventory": bn(c.inventory_value),
            "days_of_stock": round(c.days_of_inventory), "units_above_range": int(c.n_excess),
            "units_below_range": int(c.n_short), "units_in_range": int(c.n_in_range),
            "excess_value": bn(c.excess_value), "holding_cost_of_excess_per_month": mn(c.excess_cost_month),
            "gap_to_finance_before_cleaning": f"{c.gap_reported_pct:+.1%}", "gap_to_finance_after_cleaning": f"{c.gap_clean_pct:+.1%}",
            "class_A_items": int(c.a_items), "slow_moving_items": int(c.n_slow), "slow_moving_value": bn(c.slow_value),
            "expiry_risk_items": int(c.n_expiry), "expiry_risk_value": bn(c.expiry_value), "may_run_short_items": int(c.n_runshort)}


def unit_status(name):
    l = _latest()
    r = l[l["business_unit"].str.lower() == name.lower()]
    if r.empty:
        return {"error": f"No business unit called {name}. Units: {', '.join(units())}"}
    r = r.iloc[0]
    m = _t("metrics")
    m = m[(m["level"] == "business_unit") & (m["name"].str.lower() == name.lower())].sort_values("month")
    days = m["days_of_inventory"].dropna()
    w = _t("warnings")
    w = w[w["business_unit"].str.lower() == name.lower()]
    ab = abc(name)
    rec = _t("reconciliation_latest")
    rec = rec[rec["business_unit"].str.lower() == name.lower()]
    out = {"business_unit": r.business_unit, "vertical": r.vertical, "status": r.status,
           "stock_now": bn(r.closing_value), "range": f"{bn(r.range_low)} to {bn(r.range_high)}",
           "above_range_by": bn(r.excess_value), "below_range_by": bn(r.shortfall_value),
           "holding_cost_of_excess_per_month": mn(r.excess_holding_cost_month),
           "slow_moving_items": int((w["warning_type"] == "Slow-moving").sum()),
           "expiry_risk_items": int((w["warning_type"] == "Expiry risk").sum()),
           "may_run_short_items": int((w["warning_type"] == "May run short").sum()),
           "class_A_items": ab.get("A", {}).get("items", 0)}
    if len(days):
        out["days_of_stock"] = round(days.iloc[-1])
    if not rec.empty:
        out["gap_to_finance_after_cleaning"] = f"{rec.iloc[0].gap_clean_pct:+.1%}"
    if r.status == "Excess":
        out["summary"] = f"{r.business_unit} holds {bn(r.closing_value)}, which is {bn(r.excess_value)} above its range of {out['range']}. Holding that excess costs about {out['holding_cost_of_excess_per_month']} a month."
        out["suggested_actions"] = "Review purchasing and slow-moving items first, and hold new orders until stock is back in range."
    elif r.status == "Short":
        out["summary"] = f"{r.business_unit} holds {bn(r.closing_value)}, which is {bn(r.shortfall_value)} below its range of {out['range']}."
        out["suggested_actions"] = "Check open purchase orders and the items flagged as may run short."
    else:
        out["summary"] = f"{r.business_unit} holds {bn(r.closing_value)}, inside its range of {out['range']}."
        out["suggested_actions"] = "No action needed on the total. Check the warning list for individual items."
    return out


def vertical_summary(name):
    s = _t("summaries")
    s = s[(s["level"] == "vertical") & (s["name"].str.lower() == name.lower())]
    return {"error": f"No vertical called {name}"} if s.empty else {"summary": s.iloc[0]["summary"], "actions": s.iloc[0]["actions"]}


def rank_units(kind="excess", n=5):
    l = _latest()
    col, flag = ("excess_value", "Excess") if kind == "excess" else ("shortfall_value", "Short")
    d = l[l["status"] == flag].sort_values(col, ascending=False).head(n)
    return [{"business_unit": r.business_unit, "amount": bn(getattr(r, col)), "stock_now": bn(r.closing_value),
             "range": f"{bn(r.range_low)} to {bn(r.range_high)}"} for r in d.itertuples()]


def warnings_for(unit=None, kind=None, n=5):
    w = _t("warnings")
    if unit:
        w = w[w["business_unit"].str.lower() == unit.lower()]
    if kind:
        w = w[w["warning_type"].str.lower().str.contains(kind.lower())]
    w = w.sort_values("amount", ascending=False)
    return {"count": len(w), "total_value": bn(w["amount"].sum()),
            "top": [{"item": r.item_name, "unit": r.business_unit, "type": r.warning_type, "value": bn(r.amount), "why": r.detail}
                    for r in w.head(n).itertuples()]}


def abc(unit=None):
    a = _t("abc_summary_business_unit")
    if unit:
        a = a[a["business_unit"].str.lower() == unit.lower()]
    g = a.groupby("abc_class")[["items", "usage_value", "inventory_value"]].sum()
    g["usage_pct"] = g["usage_value"] / g["usage_value"].sum()
    g["inventory_pct"] = g["inventory_value"] / g["inventory_value"].sum()
    return {c: {"items": int(r["items"]), "share_of_usage": f"{r.usage_pct:.0%}", "share_of_inventory": f"{r.inventory_pct:.0%}"}
            for c, r in g.iterrows()}


def finance_check(unit=None):
    r = _t("reconciliation_latest")
    if unit:
        r = r[r["business_unit"].str.lower() == unit.lower()]
    r = r.sort_values("abs_gap_clean", ascending=False)
    k = _t("kpis")
    c = k[k["level"] == "company"].iloc[0]
    return {"company_gap_before_cleaning": f"{c.gap_reported_pct:+.1%}", "company_gap_after_cleaning": f"{c.gap_clean_pct:+.1%}",
            "errors_fixed": int(c.n_fixed), "value_fixed": bn(c.fixed_value),
            "largest_remaining_gaps": [{"unit": x.business_unit, "gap": f"{x.gap_clean_pct:+.1%}", "amount": mn(x.gap_clean)} for x in r.head(3).itertuples()]}
