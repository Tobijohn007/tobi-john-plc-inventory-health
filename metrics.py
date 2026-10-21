"""Part B: inventory health metrics and ABC classification.

This part is calculation, not AI. It turns the clean inventory table into the numbers an
executive reads first, for every business unit, every vertical and the whole company:

  inventory value        total stock in naira, split by type of stock
  share of annual sales  inventory value divided by the last 12 months of sales
  days of inventory      how many days the stock would last at the current pace of sales
  turnover               how many times a year the stock is used up and replaced
  holding cost           the yearly cost of money tied up in stock, shown per month

ABC classification ranks every item by the money value of what is used in a year. A items
are the few that make up the first 80% of usage value, B the next 15%, C the many small rest.
"""
import numpy as np
import pandas as pd

import config as C


def _base(clean, sales, level):
    key = {"business_unit": "business_unit", "vertical": "vertical", "company": "company"}[level]
    c, s = clean.copy(), sales.copy()
    for d in (c, s):
        d["vertical"] = d["business_unit"].map(C.BU_TO_VERTICAL)
        d["company"] = C.COMPANY
    inv = c.pivot_table(index=[key, "month"], columns="stock_type", values="closing_value",
                        aggfunc="sum", fill_value=0.0)
    inv = inv.reindex(columns=C.STOCK_TYPES, fill_value=0.0)
    inv["inventory_value"] = inv.sum(axis=1)
    money = s.groupby([key, "month"])[["cost_of_sales", "sales_value"]].sum()
    base = inv.join(money).reset_index().rename(columns={key: "name"})
    base.insert(0, "level", level)
    return base.sort_values(["name", "month"]).reset_index(drop=True)


def _add_ratios(base, rate):
    g = base.groupby("name")
    base["annual_sales"] = g["sales_value"].transform(lambda x: x.rolling(12).sum())
    base["annual_cost_of_sales"] = g["cost_of_sales"].transform(lambda x: x.rolling(12).sum())
    base["cost_of_sales_3m"] = g["cost_of_sales"].transform(lambda x: x.rolling(3).sum())
    base["avg_inventory_12m"] = g["inventory_value"].transform(lambda x: x.rolling(12).mean())
    base["inventory_pct_of_sales"] = base["inventory_value"] / base["annual_sales"]
    base["days_of_inventory"] = base["inventory_value"] / (base["cost_of_sales_3m"] / 91.3)
    base["turnover"] = base["annual_cost_of_sales"] / base["avg_inventory_12m"]
    base["holding_cost_month"] = base["inventory_value"] * rate / 12
    return base


def build_metrics(clean, sales, rate=C.HOLDING_COST_RATE):
    """One table with a row for every business unit, vertical and the company, for every month."""
    parts = [_add_ratios(_base(clean, sales, level), rate)
             for level in ("business_unit", "vertical", "company")]
    out = pd.concat(parts, ignore_index=True)
    out["vertical"] = np.where(out["level"] == "business_unit",
                               out["name"].map(C.BU_TO_VERTICAL),
                               np.where(out["level"] == "vertical", out["name"], C.COMPANY))
    return out


def abc_classification(clean, items):
    """Rank items by usage value over the last 12 months, inside each business unit."""
    last = clean["month"].max()
    window = clean[clean["month"] > last - pd.DateOffset(months=12)]
    use = window.groupby("item_id")["usage_value"].sum().rename("usage_value_12m")
    now = (clean[clean["month"] == last].set_index("item_id")[["closing_qty", "closing_value"]])
    tbl = items.set_index("item_id").join(use).join(now).reset_index()
    tbl["usage_value_12m"] = tbl["usage_value_12m"].fillna(0.0)
    tbl["closing_value"] = tbl["closing_value"].fillna(0.0)
    tbl = tbl.sort_values(["business_unit", "usage_value_12m"], ascending=[True, False]).reset_index(drop=True)

    total = tbl.groupby("business_unit")["usage_value_12m"].transform("sum")
    share = tbl["usage_value_12m"] / total
    cum_before = share.groupby(tbl["business_unit"]).cumsum() - share
    tbl["abc_class"] = np.where(cum_before < C.ABC_A_CUTOFF, "A",
                                np.where(cum_before < C.ABC_B_CUTOFF, "B", "C"))
    tbl["cover_days"] = np.where(tbl["usage_value_12m"] > 0,
                                 tbl["closing_value"] / (tbl["usage_value_12m"] / 365), np.nan)
    return tbl


def abc_summary(abc, by):
    """Items, usage value and inventory value by class. `by` is 'business_unit' or 'vertical'."""
    g = abc.groupby([by, "abc_class"]).agg(
        items=("item_id", "size"),
        usage_value=("usage_value_12m", "sum"),
        inventory_value=("closing_value", "sum"),
    ).reset_index()
    for col, new in (("items", "items_pct"), ("usage_value", "usage_pct"), ("inventory_value", "inventory_pct")):
        g[new] = g[col] / g.groupby(by)[col].transform("sum")
    return g
