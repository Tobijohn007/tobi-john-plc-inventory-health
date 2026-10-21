"""Part A: one trusted inventory dataset.

Takes the inventory as the reports show it, finds the common data problems, fixes the ones
that can be fixed safely, writes down every change with its money value, and then compares
the result with the finance balances.

Every rule here is simple on purpose, so it can be explained to the people who own the data:

  1. Duplicate rows       two reports give the same item for the same month: keep the ERP row.
  2. Negative stock       if the number is a normal size for that item once the sign is
                          flipped, it was a sign error. Otherwise set it to zero and flag it.
  3. Extra zeros          a quantity 10 or 100 times the item's usual level is divided back
                          down, but only if the result then looks normal for that item.
"""
import numpy as np
import pandas as pd

import config as C


def _log(df, mask, issue_type, corrected_value):
    sub = df.loc[mask]
    return pd.DataFrame({
        "issue_type": issue_type,
        "month": sub["month"].to_numpy(),
        "item_id": sub["item_id"].to_numpy(),
        "business_unit": sub["business_unit"].to_numpy(),
        "reported_value": sub["closing_value"].to_numpy(),
        "corrected_value": np.asarray(corrected_value),
    })


def clean_inventory(raw):
    """Return (clean table, log of every issue found)."""
    df = raw.copy()
    df["month"] = pd.to_datetime(df["month"])
    logs = []

    # 1. duplicates: keep the ERP row, drop the others
    df["_rank"] = (df["source"] != "ERP").astype(int)
    df = df.sort_values(["month", "item_id", "_rank"]).reset_index(drop=True)
    dup = df.duplicated(["month", "item_id"], keep="first")
    logs.append(_log(df, dup, "Duplicate row", np.zeros(int(dup.sum()))))
    df = df.loc[~dup].drop(columns="_rank").reset_index(drop=True)

    # each item's usual stock level: the middle value over its own history
    usual = (df.loc[df["closing_qty"] > 0].groupby("item_id")["closing_qty"].median()
             .rename("usual_qty"))
    df = df.merge(usual, on="item_id", how="left")
    df["fixed_qty"] = df["closing_qty"]

    # 2. negative stock
    neg = df["closing_qty"] < 0
    flipped_ratio = df["closing_qty"].abs() / df["usual_qty"]
    sign_error = neg & flipped_ratio.between(0.3, 3.0)
    df.loc[sign_error, "fixed_qty"] = df.loc[sign_error, "closing_qty"].abs()
    logs.append(_log(df, sign_error, "Negative stock (sign flipped)",
                     df.loc[sign_error, "fixed_qty"] * df.loc[sign_error, "unit_cost"]))
    unclear = neg & ~sign_error
    df.loc[unclear, "fixed_qty"] = 0.0
    logs.append(_log(df, unclear, "Negative stock (set to zero)", np.zeros(int(unclear.sum()))))

    # 3. extra zeros
    ratio = df["fixed_qty"] / df["usual_qty"]
    big = ratio >= 5
    power = np.round(np.log10(ratio.where(big, 10))).clip(lower=1)
    divisor = 10.0 ** power
    candidate = df["fixed_qty"] / divisor
    ok = big & (candidate / df["usual_qty"]).between(0.35, 3.0)
    df.loc[ok, "fixed_qty"] = candidate[ok]
    logs.append(_log(df, ok, "Extra zeros (divided back)",
                     df.loc[ok, "fixed_qty"] * df.loc[ok, "unit_cost"]))
    flag_only = big & ~ok
    logs.append(_log(df, flag_only, "Unusual jump (flagged only)", df.loc[flag_only, "closing_value"]))

    df["closing_qty"] = df["fixed_qty"]
    df["closing_value"] = df["closing_qty"] * df["unit_cost"]
    df["usage_value"] = df["usage_qty"] * df["unit_cost"]
    clean = df[["month", "item_id", "business_unit", "stock_type", "closing_qty",
                "usage_qty", "unit_cost", "closing_value", "usage_value"]].copy()

    issues = pd.concat(logs, ignore_index=True)
    issues["impact_value"] = issues["reported_value"] - issues["corrected_value"]
    issues["vertical"] = issues["business_unit"].map(C.BU_TO_VERTICAL)
    return clean, issues


def reconcile(raw, clean, finance):
    """Compare reported inventory, cleaned inventory and the finance balance for each unit and month."""
    rep = raw.groupby(["business_unit", "month"])["closing_value"].sum().rename("reported_value")
    cln = clean.groupby(["business_unit", "month"])["closing_value"].sum().rename("clean_value")
    fin = finance.set_index(["business_unit", "month"])["finance_balance"]
    out = pd.concat([rep, cln, fin], axis=1).reset_index()
    out["vertical"] = out["business_unit"].map(C.BU_TO_VERTICAL)
    out["gap_reported"] = out["reported_value"] - out["finance_balance"]
    out["gap_clean"] = out["clean_value"] - out["finance_balance"]
    out["gap_reported_pct"] = out["gap_reported"] / out["finance_balance"]
    out["gap_clean_pct"] = out["gap_clean"] / out["finance_balance"]
    return out


def reconciliation_summary(recon, month):
    """Latest-month view: how much of the gap to finance the cleaning explains."""
    r = recon[recon["month"] == month].copy()
    r["abs_gap_reported"] = r["gap_reported"].abs()
    r["abs_gap_clean"] = r["gap_clean"].abs()
    r["explained_by_cleaning"] = (r["abs_gap_reported"] - r["abs_gap_clean"]).clip(lower=0)
    r["explained_share"] = np.where(
        r["abs_gap_reported"] > 0, r["explained_by_cleaning"] / r["abs_gap_reported"], 0.0)
    return r.sort_values("abs_gap_reported", ascending=False).reset_index(drop=True)
