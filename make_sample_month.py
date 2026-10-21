"""Makes a sample 'next month' extract in incoming/, to test the monthly refresh.
In real life these three files come from the ERP and finance each month.

    python make_sample_month.py
"""
import numpy as np
import pandas as pd

import config as C

rng = np.random.default_rng(7)
raw = pd.read_csv(C.DATA_DIR / "inventory_raw.csv", parse_dates=["month"])
sales = pd.read_csv(C.DATA_DIR / "sales.csv", parse_dates=["month"])
fin = pd.read_csv(C.DATA_DIR / "finance_balances.csv", parse_dates=["month"])

last = raw["month"].max()
new = last + pd.DateOffset(months=1)
base = raw[(raw["month"] == last - pd.DateOffset(months=11)) & (raw["source"] == "ERP")].copy()  # same month last year
base = base.drop_duplicates(["item_id"])
n = len(base)
base["month"] = new
base["closing_qty"] *= rng.normal(1.06, 0.05, n).clip(0.8)
base["usage_qty"] *= rng.normal(1.06, 0.05, n).clip(0.8)
base["unit_cost"] *= 1.01
base["closing_value"] = base["closing_qty"] * base["unit_cost"]
base["source"] = "ERP"
clean_value = base.groupby("business_unit")["closing_value"].sum()

# a few realistic errors, so the checks have something to catch
bad = base.sample(3, random_state=1).index
base.loc[bad[0], ["closing_qty", "closing_value"]] *= -1                     # negative stock
base.loc[bad[1], ["closing_qty", "closing_value"]] *= 10                     # extra zero
dup = base.sample(4, random_state=2).copy()
dup["source"] = "Report B"                                                   # duplicate from a second report
inv = pd.concat([base, dup], ignore_index=True)

s = sales[sales["month"] == last - pd.DateOffset(months=11)].copy()
s["month"] = new
s[["cost_of_sales", "sales_value"]] *= 1.07
f = pd.DataFrame({"business_unit": clean_value.index, "month": new,
                  "finance_balance": clean_value.values * rng.normal(1.0, 0.012, len(clean_value))})

d = C.ROOT / "incoming"
d.mkdir(exist_ok=True)
inv.to_csv(d / "inventory_raw.csv", index=False)
s.to_csv(d / "sales.csv", index=False)
f.to_csv(d / "finance_balances.csv", index=False)
print(f"Sample extract for {new:%B %Y} written to {d}: {len(inv)} stock rows, {len(s)} sales rows, {len(f)} finance rows")
