"""Data preparation for the executive view.

Everything the app and the HTML report show is built here, from the CSV files in outputs/.
Keeping this separate from the screen code means it can be tested without a browser.
Money columns are in naira billions (bn) unless the name says millions (m).
"""
import json

import numpy as np
import pandas as pd

import config as C

BN = 1e9
MN = 1e6


def load(out_dir=C.OUT_DIR):
    def rd(name, **kw):
        return pd.read_csv(out_dir / name, **kw)

    d = {
        "metrics": rd("metrics.csv", parse_dates=["month"]),
        "kpis": rd("kpis.csv"),
        "summaries": rd("summaries.csv"),
        "bu_adq": rd("adequacy_business_units.csv", parse_dates=["month"]),
        "v_adq": rd("adequacy_verticals.csv", parse_dates=["month"]),
        "series": rd("adequacy_series.csv", parse_dates=["month"]),
        "targets": rd("adequacy_targets.csv"),
        "accuracy": rd("forecast_accuracy.csv"),
        "flags": rd("flag_rates.csv"),
        "abc_items": rd("abc_items.csv"),
        "abc_bu": rd("abc_summary_business_unit.csv"),
        "abc_v": rd("abc_summary_vertical.csv"),
        "warnings": rd("warnings.csv"),
        "issues": rd("data_issues.csv", parse_dates=["month"]),
        "recon": rd("reconciliation.csv", parse_dates=["month"]),
        "recon_latest": rd("reconciliation_latest.csv", parse_dates=["month"]),
    }
    d["last"] = pd.Timestamp(json.loads((out_dir / "run_info.json").read_text())["latest_month"])
    return d


def vertical_table(d):
    k = d["kpis"]
    k = k[k["level"] == "vertical"].copy()
    out = pd.DataFrame({
        "Vertical": k["name"],
        "Inventory (₦bn)": k["inventory_value"] / BN,
        "% of annual sales": k["pct_of_sales"] * 100,
        "Days of stock": k["days_of_inventory"],
        "Turnover (times a year)": k["turnover"],
        "Units above range": k["n_excess"],
        "Units below range": k["n_short"],
        "Above range (₦bn)": k["excess_value"] / BN,
        "Holding cost of excess (₦m a month)": k["excess_cost_month"] / MN,
    })
    return out.sort_values("Inventory (₦bn)", ascending=False).reset_index(drop=True)


def company_kpis(d):
    return d["kpis"][d["kpis"]["level"] == "company"].iloc[0]


def bu_table(d, vertical=None):
    last = d["last"]
    m = d["metrics"]
    m = m[(m["level"] == "business_unit") & (m["month"] == last)]
    a = d["bu_adq"]
    a = a[a["month"] == last]
    t = m.merge(a[["business_unit", "status", "range_low", "range_high", "target_value",
                   "excess_value", "shortfall_value", "cover_days_now"]],
                left_on="name", right_on="business_unit", how="left")
    if vertical and vertical != "All":
        t = t[t["vertical"] == vertical]
    out = pd.DataFrame({
        "Business unit": t["name"],
        "Vertical": t["vertical"],
        "Status": t["status"],
        "Inventory (₦bn)": t["inventory_value"] / BN,
        "Bottom of range (₦bn)": t["range_low"] / BN,
        "Top of range (₦bn)": t["range_high"] / BN,
        "Above range (₦bn)": t["excess_value"] / BN,
        "Below range (₦bn)": t["shortfall_value"] / BN,
        "% of annual sales": t["inventory_pct_of_sales"] * 100,
        "Days of stock": t["days_of_inventory"],
        "Turnover (times a year)": t["turnover"],
        "Stock vs target (x)": t["inventory_value"] / t["target_value"],
        "Range low (x target)": t["range_low"] / t["target_value"],
        "Range high (x target)": t["range_high"] / t["target_value"],
    })
    order = {"Excess": 0, "Short": 1, "In range": 2}
    out["_o"] = out["Status"].map(order)
    out = out.sort_values(["_o", "Above range (₦bn)", "Inventory (₦bn)"], ascending=[True, False, False])
    return out.drop(columns="_o").reset_index(drop=True)


def bu_range_history(d, bu):
    a = d["bu_adq"][d["bu_adq"]["business_unit"] == bu].sort_values("month")
    return pd.DataFrame({
        "Stock held": a["closing_value"].to_numpy() / BN,
        "Bottom of range": a["range_low"].to_numpy() / BN,
        "Top of range": a["range_high"].to_numpy() / BN,
    }, index=a["month"].to_numpy())


def store_table(d, bu):
    """Latest month by type of stock for one business unit."""
    s = d["series"]
    s = s[(s["business_unit"] == bu) & (s["month"] == d["last"])]
    return pd.DataFrame({
        "Type of stock": s["stock_type"],
        "Status": s["status"],
        "Stock held (₦bn)": s["closing_value"] / BN,
        "Bottom of range (₦bn)": s["range_low"] / BN,
        "Top of range (₦bn)": s["range_high"] / BN,
        "Normal days of cover": s["target_days"],
        "Days of cover now": s["cover_days_now"],
    }).reset_index(drop=True)


def company_trend(d):
    r = d["recon"].groupby("month")[["reported_value", "clean_value", "finance_balance"]].sum()
    return pd.DataFrame({
        "Reported": r["reported_value"] / BN,
        "Cleaned": r["clean_value"] / BN,
        "Finance": r["finance_balance"] / BN,
    })


def gap_trend(d):
    r = d["recon"].groupby("month")[["reported_value", "clean_value", "finance_balance"]].sum()
    return pd.DataFrame({
        "As reported": (r["reported_value"] / r["finance_balance"] - 1) * 100,
        "After cleaning": (r["clean_value"] / r["finance_balance"] - 1) * 100,
    })


def abc_company(d):
    """Share of items, usage value and inventory value held by each class, whole company."""
    a = d["abc_items"]
    rows = {}
    for label, col in (("Items", None), ("Usage value", "usage_value_12m"), ("Inventory value", "closing_value")):
        if col is None:
            s = a.groupby("abc_class").size()
        else:
            s = a.groupby("abc_class")[col].sum()
        rows[label] = (s / s.sum() * 100).reindex(["A", "B", "C"]).fillna(0.0)
    return pd.DataFrame(rows).T


def abc_bu_table(d, bu):
    s = d["abc_bu"]
    s = s[s["business_unit"] == bu]
    return pd.DataFrame({
        "Class": s["abc_class"],
        "Items": s["items"],
        "% of items": s["items_pct"] * 100,
        "% of usage value": s["usage_pct"] * 100,
        "Inventory (₦bn)": s["inventory_value"] / BN,
        "% of inventory value": s["inventory_pct"] * 100,
    }).reset_index(drop=True)


def abc_top_items(d, bu, n=12):
    a = d["abc_items"]
    a = a[(a["business_unit"] == bu) & (a["abc_class"] == "A")].sort_values("usage_value_12m", ascending=False).head(n)
    return pd.DataFrame({
        "Item": a["item_name"],
        "Type of stock": a["stock_type"],
        "Usage, last 12 months (₦bn)": a["usage_value_12m"] / BN,
        "Stock held (₦bn)": a["closing_value"] / BN,
        "Days of cover": a["cover_days"],
    }).reset_index(drop=True)


def warnings_view(d, kind, vertical=None, n=15):
    w = d["warnings"]
    w = w[w["warning_type"] == kind]
    if vertical and vertical != "All":
        w = w[w["vertical"] == vertical]
    w = w.sort_values("amount", ascending=False).head(n)
    return pd.DataFrame({
        "Item": w["item_name"],
        "Class": w["abc_class"],
        "Why": w["detail"],
        w["amount_meaning"].iloc[0] + " (₦m)" if len(w) else "Amount (₦m)": w["amount"] / MN,
    }).reset_index(drop=True)


def warnings_totals(d, vertical=None):
    w = d["warnings"]
    if vertical and vertical != "All":
        w = w[w["vertical"] == vertical]
    g = w.groupby("warning_type").agg(items=("item_id", "size"), amount=("amount", "sum")).reset_index()
    g["amount_bn"] = g["amount"] / BN
    return g


def issues_summary(d):
    """Counts over all months, and the money effect for the latest month only.

    Inventory is a month-end balance, so adding errors across months would not mean anything.
    """
    i = d["issues"]
    now = i[i["month"] == d["last"]]
    g = i.groupby("issue_type").size().rename("rows_all").to_frame()
    g["rows_now"] = now.groupby("issue_type").size()
    g["net_now"] = now.groupby("issue_type")["impact_value"].sum()
    g["abs_now"] = now.assign(a=now["impact_value"].abs()).groupby("issue_type")["a"].sum()
    g = g.fillna(0).reset_index()
    return pd.DataFrame({
        "What was found": g["issue_type"],
        "Rows found (all months)": g["rows_all"].astype(int),
        "Rows in latest month": g["rows_now"].astype(int),
        "Net effect, latest month (₦bn)": g["net_now"] / BN,
        "Size of errors, latest month (₦bn)": g["abs_now"] / BN,
    }).sort_values("Size of errors, latest month (₦bn)", ascending=False).reset_index(drop=True)


def recon_view(d, n=10):
    r = d["recon_latest"].head(n)
    return pd.DataFrame({
        "Business unit": r["business_unit"],
        "As reported (₦bn)": r["reported_value"] / BN,
        "After cleaning (₦bn)": r["clean_value"] / BN,
        "Finance (₦bn)": r["finance_balance"] / BN,
        "Gap as reported (%)": r["gap_reported_pct"] * 100,
        "Gap after cleaning (%)": r["gap_clean_pct"] * 100,
        "Gap explained by cleaning (%)": r["explained_share"] * 100,
    }).reset_index(drop=True)


def summary_for(d, name):
    r = d["summaries"][d["summaries"]["name"] == name].iloc[0]
    return r["summary"], [a for a in r["actions"].split("\n") if a]
