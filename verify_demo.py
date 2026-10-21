"""Known-answer check. The demo data has planted problems, so we can test whether the
pipeline finds them. Run after run_pipeline.py:  python verify_demo.py"""
import json
import pandas as pd
import config as C

D, O = C.DATA_DIR if hasattr(C, "DATA_DIR") else C.OUT_DIR.parent / "data", C.OUT_DIR
plant = json.loads((D / "planted_problems.json").read_text())
rows = pd.read_csv(D / "planted_rows.csv", parse_dates=["month"])
iss = pd.read_csv(O / "data_issues.csv", parse_dates=["month"])
rec = pd.read_csv(O / "reconciliation.csv", parse_dates=["month"])
truth = pd.read_csv(D / "truth_value_by_bu_month.csv", parse_dates=["month"])
adq = pd.read_csv(O / "adequacy_business_units.csv", parse_dates=["month"])
warn = pd.read_csv(O / "warnings.csv")
last = pd.Timestamp(json.loads((O / "run_info.json").read_text())["latest_month"])
results = []

def check(name, ok, detail):
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}  {name}: {detail}")

# 1. data errors found
for kind, need in (("Duplicate row", 0.99), ("Negative stock", 0.95), ("Extra zeros", 0.90)):
    p = rows[rows["issue_type"] == kind][["month", "item_id"]].drop_duplicates()
    f = iss[iss["issue_type"].str.startswith(kind)][["month", "item_id"]].drop_duplicates()
    hit = len(p.merge(f))
    r = hit / max(len(p), 1)
    check(f"{kind} found", r >= need, f"{hit}/{len(p)} planted rows caught ({r:.0%}); {len(f) - hit} extra flagged")

# 2. cleaning brings us back to the truth
m = rec.merge(truth, on=["business_unit", "month"])
err_rep = ((m["reported_value"] - m["true_value"]).abs().sum() / m["true_value"].sum())
err_cln = ((m["clean_value"] - m["true_value"]).abs().sum() / m["true_value"].sum())
check("Cleaning moves values toward the truth", err_cln < err_rep * 0.1,
      f"error vs truth {err_rep:.2%} as reported -> {err_cln:.3%} after cleaning")

# 3. range model flags the planted excess and short business units, latest month
now = adq[adq["month"] == last].set_index("business_unit")["status"]
ex = set(now[now == "Excess"].index)
want_ex = set(plant["excess_business_units"])
check("Planted excess units flagged", want_ex <= ex, f"missed: {sorted(want_ex - ex) or 'none'}; extra flagged: {sorted(ex - want_ex) or 'none'}")
for bu, s in plant["short_spells"].items():
    a = adq[(adq["business_unit"] == bu) & (adq["month"] >= pd.Timestamp(s["from"])) & (adq["month"] <= pd.Timestamp(s["to"]))]
    share = (a["status"] == "Short").mean()
    check(f"{bu} short spell seen", share >= 0.5, f"flagged Short in {share:.0%} of {len(a)} planted months")

# 4. dead items show up as warnings
dead = pd.DataFrame(plant["dead_items"])
flagged = set(warn.loc[warn["warning_type"].isin(["Slow-moving", "Expiry risk"]), "item_id"])
got = dead["item_id"].isin(flagged)
check("Dead items warned", got.mean() >= 0.8, f"{got.sum()}/{len(dead)} caught; missed: {dead.loc[~got, 'item_id'].tolist()[:5]}")

# 5. extra Excess flags beyond the planted three: explain them
extra = sorted(ex - want_ex)
if extra:
    d = dead.groupby("business_unit").size()
    print("NOTE  extra Excess units:", {b: f"{d.get(b, 0)} dead items planted" for b in extra})

print(f"\n{sum(results)}/{len(results)} checks passed")
raise SystemExit(0 if all(results) else 1)
