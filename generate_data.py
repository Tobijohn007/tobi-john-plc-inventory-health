"""Create fictional but realistic data for Tobi John PLC.

This stands in for the Dynamics 365 exports, finance records and sales data that a real
project would request in week 1. The data is made up, but it is built to behave like a real
business: demand has seasons, stock follows demand, prices rise, and some things go wrong on
purpose so the model has something to find:

  * duplicate rows from a second report, sign errors and extra zeros in quantities
  * finance balances that lag behind inventory in four business units
  * three business units that slowly build up too much stock
  * two business units that run short of stock for a few months
  * about 5% of items that stop moving while their stock stays on the shelf

The answers are saved in data/planted_problems.json and data/planted_rows.csv so that
verify_demo.py can check how well the model finds them.
"""
import json

import numpy as np
import pandas as pd

import config as C

TYPE_CODE = {
    "Finished goods": "FG",
    "Raw materials": "RM",
    "Packaging materials": "PK",
    "Work in progress": "WP",
    "Spare parts": "SP",
}
TYPE_MIX = {  # share of a business unit's items
    "Finished goods": 0.20,
    "Raw materials": 0.33,
    "Packaging materials": 0.20,
    "Work in progress": 0.07,
    "Spare parts": 0.20,
}
TYPE_USAGE_SHARE = {  # yearly usage value as a share of the unit's cost of sales
    "Finished goods": 1.00,
    "Raw materials": 0.70,
    "Packaging materials": 0.12,
    "Work in progress": 1.00,
    "Spare parts": 0.03,
}
TYPE_COVER_DAYS = {  # normal days of stock held
    "Finished goods": 18,
    "Raw materials": 30,
    "Packaging materials": 28,
    "Work in progress": 2,
    "Spare parts": 150,
}
TYPE_COST_MEDIAN = {  # median unit cost in naira
    "Finished goods": 900,
    "Raw materials": 550,
    "Packaging materials": 120,
    "Work in progress": 700,
    "Spare parts": 25000,
}
TYPE_UOM = {
    "Finished goods": "kg",
    "Raw materials": "kg",
    "Packaging materials": "pcs",
    "Work in progress": "kg",
    "Spare parts": "pcs",
}
STOCKED_TYPES = {"Finished goods", "Raw materials", "Packaging materials"}

# Planted behaviours (month index 0 = Oct 2023, 35 = Sep 2026)
EXCESS_BUILD = {"Biscuits": 1.70, "Fertilizer": 1.50, "Vegetable Oil": 1.40}
EXCESS_START = 24  # stock starts building up in Oct 2025
SHORT_SPELLS = {"Energy Drinks": (32, 35, 0.55), "Bottled Water": (28, 30, 0.60)}
TIMING_GAP_BUS = ["Pasta", "Soft Drinks", "Refined Sugar", "Animal Feeds"]
TIMING_GAP_FROM = 30  # finance lags from Apr 2026
TIMING_GAP = 0.03

PRICE_INFLATION = 1.14   # unit costs per year
VOLUME_GROWTH = 1.13     # cost of sales per year (nominal)


def shelf_life(vertical, stype, rng):
    if stype == "Finished goods" and vertical != "Packaging":
        base = {
            "Foods": 270, "Flour & Milling": 180, "Agro": 150, "Beverages": 270,
            "Sugar & Sweeteners": 540, "Edible Oils & Fats": 365,
        }[vertical]
        return float(round(base * rng.choice([0.7, 1.0, 1.3])))
    if stype == "Raw materials" and rng.random() < 0.30:
        return 365.0
    return np.nan


def build_clean_world(rng):
    """The true, correct data, before any reporting errors are added."""
    n = C.N_MONTHS
    months = pd.date_range(C.START_MONTH, periods=n + 1, freq="MS")  # one extra month for next-month need
    t = np.arange(n + 1)
    growth = VOLUME_GROWTH ** (t / 12)
    inflation = PRICE_INFLATION ** (t / 12)

    item_rows, frames, dead_items = [], [], []
    bu_no = 0
    for vertical, spec in C.VERTICALS.items():
        s = np.array(spec["season"], dtype=float)
        s = s / s.mean()
        season = s[months.month.values - 1]
        for bu, cos_bn in spec["units"].items():
            bu_no += 1
            bu_code = f"BU{bu_no:02d}"
            cos_month = cos_bn * 1e9 / 12 * growth * season  # expected monthly cost of sales
            n_items = int(rng.integers(36, 45))
            counts = {k: max(2, int(round(n_items * p))) for k, p in TYPE_MIX.items()}
            counts["Raw materials"] += n_items - sum(counts.values())
            bu_factor = rng.uniform(0.85, 1.20)

            mult = np.ones(n)
            if bu in EXCESS_BUILD:
                tt = np.arange(n)
                ramp = np.clip((tt - (EXCESS_START - 1)) / 12, 0, 1)
                mult = 1 + (EXCESS_BUILD[bu] - 1) * ramp
            if bu in SHORT_SPELLS:
                a, b, f = SHORT_SPELLS[bu]
                mult = mult.copy()
                mult[a:b + 1] = f

            for stype, cnt in counts.items():
                w = rng.lognormal(0, 1.1, cnt)
                share = w / w.sum()
                for k in range(cnt):
                    item_id = f"{bu_code}-{TYPE_CODE[stype]}-{k + 1:03d}"
                    base_cost = rng.lognormal(np.log(TYPE_COST_MEDIAN[stype]), 0.7)
                    unit_cost = base_cost * inflation[:n]

                    expected = cos_month * TYPE_USAGE_SHARE[stype] * share[k]  # length n+1
                    usage_val = expected[:n] * rng.lognormal(0, 0.10, n)
                    if stype == "Spare parts":
                        active = rng.random(n) < 0.45
                        usage_val = np.where(active, usage_val / 0.45, 0.0)

                    target_val = expected[1:] * TYPE_COVER_DAYS[stype] * bu_factor / C.DAYS_PER_MONTH
                    m = mult if stype in STOCKED_TYPES else np.ones(n)
                    stock_val = target_val * m * rng.lognormal(0, 0.10, n)

                    closing_qty = stock_val / unit_cost
                    usage_qty = usage_val / unit_cost

                    dead_from = None
                    if stype != "Work in progress" and rng.random() < 0.05:
                        dead_from = int(rng.integers(14, 29))
                        usage_qty = usage_qty.copy()
                        usage_qty[dead_from:] = 0.0
                        closing_qty = closing_qty.copy()
                        closing_qty[dead_from:] = closing_qty[dead_from - 1]
                        dead_items.append({
                            "item_id": item_id,
                            "business_unit": bu,
                            "dead_from": str(months[dead_from].date()),
                        })

                    item_rows.append({
                        "item_id": item_id,
                        "item_name": f"{bu} - {stype.lower()} {k + 1:03d}",
                        "business_unit": bu,
                        "vertical": vertical,
                        "stock_type": stype,
                        "uom": TYPE_UOM[stype],
                        "shelf_life_days": shelf_life(vertical, stype, rng),
                    })
                    frames.append(pd.DataFrame({
                        "month": months[:n],
                        "item_id": item_id,
                        "business_unit": bu,
                        "stock_type": stype,
                        "closing_qty": closing_qty,
                        "usage_qty": usage_qty,
                        "unit_cost": unit_cost,
                    }))

    truth = pd.concat(frames, ignore_index=True)
    items = pd.DataFrame(item_rows)
    return truth, items, dead_items


def add_reporting_errors(truth, rng):
    """Turn the true data into what the reports actually show."""
    raw = truth.copy()
    raw["source"] = "ERP"
    n = len(raw)
    planted = []

    def note(idx, issue):
        for i in idx:
            planted.append({
                "month": str(raw.at[i, "month"].date()),
                "item_id": raw.at[i, "item_id"],
                "issue_type": issue,
            })

    # 1. sign errors: stock typed in as a negative number
    sign_idx = rng.choice(n, size=int(n * 0.0025), replace=False)
    raw.loc[sign_idx, "closing_qty"] = -raw.loc[sign_idx, "closing_qty"]
    note(sign_idx, "Negative stock")

    # 2. extra zeros: a quantity ten or one hundred times too big
    remaining = np.setdiff1d(np.arange(n), sign_idx)
    ez_idx = rng.choice(remaining, size=int(n * 0.003), replace=False)
    value = (raw["closing_qty"] * raw["unit_cost"]).abs()
    low = (value < value.quantile(0.25)).to_numpy()
    factors = np.where(low[ez_idx] & (rng.random(len(ez_idx)) < 0.4), 100.0, 10.0)
    raw.loc[ez_idx, "closing_qty"] = raw.loc[ez_idx, "closing_qty"].to_numpy() * factors
    note(ez_idx, "Extra zeros")

    # 3. duplicate rows from a second report that is slightly different
    pool = np.setdiff1d(remaining, ez_idx)
    dup_idx = rng.choice(pool, size=int(n * 0.005), replace=False)
    dups = raw.loc[dup_idx].copy()
    dups["source"] = "Report B"
    dups["closing_qty"] = dups["closing_qty"] * (1 + rng.normal(0, 0.02, len(dups)))
    note(dup_idx, "Duplicate row")

    raw = pd.concat([raw, dups], ignore_index=True)
    raw["closing_value"] = raw["closing_qty"] * raw["unit_cost"]
    raw = raw.sort_values(["month", "item_id", "source"]).reset_index(drop=True)
    return raw, pd.DataFrame(planted)


def build_finance_and_sales(truth, rng):
    truth = truth.copy()
    truth["closing_value"] = truth["closing_qty"] * truth["unit_cost"]
    truth["usage_value"] = truth["usage_qty"] * truth["unit_cost"]

    true_bu = (truth.groupby(["business_unit", "month"])["closing_value"].sum()
               .rename("true_value").reset_index())
    fin = true_bu.copy()
    fin["finance_balance"] = fin["true_value"] * (1 + rng.normal(0, 0.003, len(fin)))
    late = fin["business_unit"].isin(TIMING_GAP_BUS) & (fin["month"] >= pd.Timestamp(C.START_MONTH) + pd.DateOffset(months=TIMING_GAP_FROM))
    fin.loc[late, "finance_balance"] *= (1 - TIMING_GAP)

    fg = truth[truth["stock_type"] == "Finished goods"]
    sales = (fg.groupby(["business_unit", "month"])["usage_value"].sum()
             .rename("cost_of_sales").reset_index())
    margin = sales["business_unit"].map(C.BU_TO_VERTICAL).map(lambda v: C.VERTICALS[v]["margin"])
    sales["sales_value"] = sales["cost_of_sales"] / (1 - margin) * rng.lognormal(0, 0.01, len(sales))
    return fin, sales, true_bu


def main():
    C.DATA_DIR.mkdir(exist_ok=True)
    rng = np.random.default_rng(C.SEED)

    truth, items, dead_items = build_clean_world(rng)
    raw, planted_rows = add_reporting_errors(truth, rng)
    fin, sales, true_bu = build_finance_and_sales(truth, rng)

    raw_out = raw[["month", "item_id", "business_unit", "stock_type", "closing_qty",
                   "usage_qty", "unit_cost", "closing_value", "source"]]
    raw_out.to_csv(C.DATA_DIR / "inventory_raw.csv", index=False)
    items.to_csv(C.DATA_DIR / "items.csv", index=False)
    fin[["business_unit", "month", "finance_balance"]].to_csv(C.DATA_DIR / "finance_balances.csv", index=False)
    sales.to_csv(C.DATA_DIR / "sales.csv", index=False)
    true_bu.to_csv(C.DATA_DIR / "truth_value_by_bu_month.csv", index=False)
    planted_rows.to_csv(C.DATA_DIR / "planted_rows.csv", index=False)

    planted = {
        "company": C.COMPANY,
        "excess_business_units": EXCESS_BUILD,
        "excess_starts": str(pd.Timestamp(C.START_MONTH) + pd.DateOffset(months=EXCESS_START))[:10],
        "short_spells": {
            bu: {"from": str((pd.Timestamp(C.START_MONTH) + pd.DateOffset(months=a)).date()),
                 "to": str((pd.Timestamp(C.START_MONTH) + pd.DateOffset(months=b)).date()),
                 "stock_factor": f}
            for bu, (a, b, f) in SHORT_SPELLS.items()
        },
        "finance_lag_business_units": TIMING_GAP_BUS,
        "finance_lag_from": str((pd.Timestamp(C.START_MONTH) + pd.DateOffset(months=TIMING_GAP_FROM)).date()),
        "finance_lag_share": TIMING_GAP,
        "reporting_errors": planted_rows["issue_type"].value_counts().to_dict(),
        "dead_items": dead_items,
    }
    (C.DATA_DIR / "planted_problems.json").write_text(json.dumps(planted, indent=2))

    print(f"{C.COMPANY}: {len(C.VERTICALS)} verticals, {items['business_unit'].nunique()} business units, "
          f"{len(items):,} items, {raw['month'].nunique()} months")
    print(f"  inventory_raw.csv rows: {len(raw_out):,}  (true rows: {len(truth):,})")
    print(f"  planted reporting errors: {planted['reporting_errors']}")
    print(f"  planted dead items: {len(dead_items)}")


if __name__ == "__main__":
    main()
