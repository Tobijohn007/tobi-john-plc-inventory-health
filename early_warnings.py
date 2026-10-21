"""Part C (continued): early warnings at item level.

Three warnings, each with a plain rule and a money amount:

  Slow-moving     no use for 6 months (12 for spare parts, which move rarely) while stock
                  is still on the shelf. The whole stock value is at risk of becoming obsolete.
  Expiry risk     the item has a shelf life, and the stock would take longer than 80% of that
                  shelf life to use up at the recent pace. The amount at risk is the stock
                  beyond what could be used within the shelf life.
  May run short   the item is used regularly, but stock covers less than 60% of the normal
                  days of cover for its store. The amount is what it would cost to restock
                  back to normal cover.

Batch and expiry dates are not in the demo data, so expiry risk uses cover days against shelf
life. If the real system records batches, use the real expiry dates instead.
"""
import numpy as np
import pandas as pd

import config as C

SLOW_MONTHS = {"Spare parts": 12}
DEFAULT_SLOW_MONTHS = 6
SHORT_STOCK_SHARE = 0.60
EXPIRY_SHARE = 0.80
STOCKED_TYPES = {"Finished goods", "Raw materials", "Packaging materials"}


def build_warnings(clean, items, abc, targets):
    last = clean["month"].max()
    recent = clean[clean["month"] > last - pd.DateOffset(months=6)]
    use6 = recent.groupby("item_id").agg(usage_qty_6m=("usage_qty", "sum"))
    last_use = (clean[clean["usage_qty"] > 0].groupby("item_id")["month"].max().rename("last_use_month"))
    now = clean[clean["month"] == last].set_index("item_id")[["closing_qty", "closing_value", "unit_cost"]]

    t = (items.set_index("item_id").join(now).join(use6).join(last_use)
         .join(abc.set_index("item_id")[["abc_class"]]).reset_index())
    t = t.merge(targets[["business_unit", "stock_type", "target_days"]],
                on=["business_unit", "stock_type"], how="left")
    t["usage_qty_6m"] = t["usage_qty_6m"].fillna(0.0)

    gap = (last.year - t["last_use_month"].dt.year) * 12 + (last.month - t["last_use_month"].dt.month)
    t["months_since_use"] = gap.fillna(C.N_MONTHS).astype(int)
    daily = t["usage_qty_6m"] / 182.5
    t["cover_days"] = np.where(daily > 0, t["closing_qty"] / daily, np.nan)

    out = []

    def add(mask, kind, amount, meaning, detail):
        sub = t.loc[mask]
        out.append(pd.DataFrame({
            "warning_type": kind,
            "vertical": sub["vertical"].to_numpy(),
            "business_unit": sub["business_unit"].to_numpy(),
            "item_id": sub["item_id"].to_numpy(),
            "item_name": sub["item_name"].to_numpy(),
            "stock_type": sub["stock_type"].to_numpy(),
            "abc_class": sub["abc_class"].to_numpy(),
            "closing_value": sub["closing_value"].to_numpy(),
            "cover_days": sub["cover_days"].to_numpy(),
            "shelf_life_days": sub["shelf_life_days"].to_numpy(),
            "amount": np.asarray(amount)[mask.to_numpy()] if hasattr(mask, "to_numpy") else np.asarray(amount),
            "amount_meaning": meaning,
            "detail": detail[mask.to_numpy()] if isinstance(detail, pd.Series) else detail,
        }))

    # 1. slow-moving
    threshold = t["stock_type"].map(SLOW_MONTHS).fillna(DEFAULT_SLOW_MONTHS)
    slow = (t["closing_value"] > 0) & (t["stock_type"] != "Work in progress") & (t["months_since_use"] >= threshold)
    add(slow, "Slow-moving", t["closing_value"].to_numpy(), "Stock value at risk of going obsolete",
        ("No use for " + t["months_since_use"].astype(str) + " months"))

    # 2. expiry risk
    has_shelf = t["shelf_life_days"].notna() & (t["closing_qty"] > 0)
    not_used = t["usage_qty_6m"] == 0
    slow_cover = t["cover_days"] > EXPIRY_SHARE * t["shelf_life_days"]
    expiry = has_shelf & (not_used | slow_cover)
    qty_beyond = (t["closing_qty"] - daily * t["shelf_life_days"]).clip(lower=0)
    at_risk = np.where(not_used, t["closing_value"], qty_beyond * t["unit_cost"])
    detail = np.where(not_used, "Not used in 6 months; shelf life " + t["shelf_life_days"].round(0).astype(str) + " days",
                      "Stock covers " + t["cover_days"].round(0).astype(str) + " days; shelf life "
                      + t["shelf_life_days"].round(0).astype(str) + " days")
    add(expiry, "Expiry risk", at_risk, "Stock value that may expire before use", pd.Series(detail, index=t.index))

    # 3. may run short
    short = ((t["usage_qty_6m"] > 0) & t["stock_type"].isin(STOCKED_TYPES) & t["target_days"].notna()
             & (t["cover_days"] < SHORT_STOCK_SHARE * t["target_days"]))
    need = (t["target_days"] * daily * t["unit_cost"] - t["closing_value"]).clip(lower=0)
    detail = "Stock covers " + t["cover_days"].round(0).astype(str) + " days; normal is " + t["target_days"].round(0).astype(str)
    add(short, "May run short", need.to_numpy(), "Value needed to restock to normal cover", pd.Series(detail, index=t.index))

    w = pd.concat(out, ignore_index=True)
    order = {"A": 0, "B": 1, "C": 2}
    w["_c"] = w["abc_class"].map(order)
    w = w.sort_values(["warning_type", "_c", "amount"], ascending=[True, True, False]).drop(columns="_c")
    return w.reset_index(drop=True)
