"""Monthly refresh: the working system.

Each month:  1) drop the new extracts in incoming/   2) run   python refresh.py

What it does, in order:
  1. Gate: checks the new files are complete and are really the next month. If not, it STOPS,
     changes nothing and writes an alert (outputs/ALERT.txt).
  2. Saves a backup of the data, then adds the new month to data/.
  3. Runs the full pipeline (clean, reconcile, days of stock, ranges, warnings, ABC).
  4. Writes the dashboard (executive_report.html) and the colour-coded action list (Excel).
  5. Compares with last month (what changed status) and saves a dated copy in outputs/history/.
  6. Adds one line to run_log.csv so there is a record of every run.
"""
import shutil
import sys
from datetime import datetime

import pandas as pd

import config as C
import export_action_list
import make_copilot_page
import make_report
import run_pipeline

INCOMING = C.ROOT / "incoming"
ARCHIVE = C.ROOT / "incoming_archive"
HISTORY = C.OUT_DIR / "history"
LOG = C.ROOT / "run_log.csv"

NEED = {
    "inventory_raw.csv": ["month", "item_id", "business_unit", "stock_type", "closing_qty", "usage_qty", "unit_cost", "closing_value", "source"],
    "sales.csv": ["business_unit", "month", "cost_of_sales", "sales_value"],
    "finance_balances.csv": ["business_unit", "month", "finance_balance"],
}


def gate(new, old_raw, items):
    """Returns (problems that stop the run, warnings that are only logged)."""
    stop, warn = [], []
    for name, cols in NEED.items():
        if name not in new:
            stop.append(f"{name} is missing from incoming/")
            continue
        miss = [c for c in cols if c not in new[name].columns]
        if miss:
            stop.append(f"{name} is missing columns: {miss}")
    if stop:
        return stop, warn

    last = old_raw["month"].max()
    expected = last + pd.DateOffset(months=1)
    for name, df in new.items():
        months = set(df["month"].unique())
        if months != {expected}:
            stop.append(f"{name}: expected only {expected:%B %Y}, found {sorted(str(m)[:10] for m in months)}")
    if stop:
        return stop, warn

    inv = new["inventory_raw.csv"]
    erp = inv[inv["source"] == "ERP"]
    n_prev = (old_raw["month"] == last).sum()
    if abs(len(inv) - n_prev) / n_prev > 0.10:
        stop.append(f"stock rows changed by more than 10% ({n_prev:,} last month, {len(inv):,} now)")
    missing = set(items["item_id"]) - set(inv["item_id"])
    if len(missing) / len(items) > 0.05:
        stop.append(f"{len(missing)} of {len(items)} items have no stock row ({len(missing) / len(items):.0%})")
    elif missing:
        warn.append(f"{len(missing)} items have no stock row this month")
    units = set(items["business_unit"])
    for name in ("sales.csv", "finance_balances.csv"):
        gone = units - set(new[name]["business_unit"])
        if gone:
            stop.append(f"{name} has no rows for: {sorted(gone)}")
    unknown = set(inv["item_id"]) - set(items["item_id"])
    if unknown:
        warn.append(f"{len(unknown)} items are not in the item master (new items?)")
    if erp["closing_value"].isna().any():
        stop.append("blank closing values in the ERP rows")
    return stop, warn


def status_changes(before, after):
    m = before.merge(after, on="business_unit", suffixes=("_before", "_now"))
    m = m[m["status_before"] != m["status_now"]]
    return m[["business_unit", "status_before", "status_now"]]


def main():
    C.OUT_DIR.mkdir(exist_ok=True)
    alert = C.OUT_DIR / "ALERT.txt"
    files = {n: INCOMING / n for n in NEED}
    if not any(p.exists() for p in files.values()):
        print("Nothing in incoming/. Put the new month's three files there and run again.")
        return 1

    old_raw = pd.read_csv(C.DATA_DIR / "inventory_raw.csv", parse_dates=["month"])
    items = pd.read_csv(C.DATA_DIR / "items.csv")
    new = {n: pd.read_csv(p, parse_dates=["month"]) for n, p in files.items() if p.exists()}

    stop, warn = gate(new, old_raw, items)
    if stop:
        alert.write_text("REFRESH STOPPED. Nothing was changed.\n" + "\n".join("- " + s for s in stop) + "\n")
        print("REFRESH STOPPED. Nothing was changed:")
        for s in stop:
            print("  -", s)
        return 2
    if alert.exists():
        alert.unlink()

    month = new["inventory_raw.csv"]["month"].iloc[0]
    tag = f"{month:%Y-%m}"
    prev_adq = None
    p = C.OUT_DIR / "adequacy_business_units.csv"
    if p.exists():
        a = pd.read_csv(p, parse_dates=["month"])
        prev_adq = a[a["month"] == a["month"].max()][["business_unit", "status"]]

    # backup, then add the new month
    bk = C.ROOT / "data_backup" / datetime.now().strftime("%Y%m%d_%H%M%S")
    bk.mkdir(parents=True, exist_ok=True)
    for n in NEED:
        shutil.copy(C.DATA_DIR / n, bk / n)
        old = pd.read_csv(C.DATA_DIR / n, parse_dates=["month"])
        pd.concat([old, new[n]], ignore_index=True).to_csv(C.DATA_DIR / n, index=False)

    # run everything
    run_pipeline.main()
    report = make_report.build()
    xlsx, ranked = export_action_list.export()
    make_copilot_page.build()

    # history and change since last month
    h = HISTORY / tag
    h.mkdir(parents=True, exist_ok=True)
    for f in ("kpis.csv", "adequacy_business_units.csv", "warnings.csv", "monthly_summary.md", "ranked_action_list.xlsx", "executive_report.html", "copilot.html"):
        shutil.copy(C.OUT_DIR / f, h / f)
    changes = None
    if prev_adq is not None:
        a = pd.read_csv(p, parse_dates=["month"])
        now = a[a["month"] == a["month"].max()][["business_unit", "status"]]
        changes = status_changes(prev_adq, now)
        changes.to_csv(h / "status_changes.csv", index=False)

    # archive what came in, and log the run
    ARCHIVE.mkdir(exist_ok=True)
    for n, f in files.items():
        shutil.move(str(f), ARCHIVE / f"{tag}_{n}")
    k = pd.read_csv(C.OUT_DIR / "kpis.csv")
    c = k[k["level"] == "company"].iloc[0]
    iss = pd.read_csv(C.OUT_DIR / "data_issues.csv", parse_dates=["month"])
    row = {"run_at": datetime.now().strftime("%Y-%m-%d %H:%M"), "month": tag,
           "stock_rows_in": len(new["inventory_raw.csv"]), "issues_found_this_month": int((iss["month"] == month).sum()),
           "inventory_bn": round(c.inventory_value / 1e9, 1), "n_excess": int(c.n_excess), "n_short": int(c.n_short),
           "gap_vs_finance_after_cleaning": round(c.gap_clean_pct, 4), "warnings_logged": "; ".join(warn)}
    pd.DataFrame([row]).to_csv(LOG, mode="a", header=not LOG.exists(), index=False)

    print(f"\nRefresh for {month:%B %Y} finished.")
    print(f"  data issues found and fixed this month: {row['issues_found_this_month']}")
    if warn:
        print("  warnings:", "; ".join(warn))
    if changes is not None:
        print("  status changes since last month:", "none" if changes.empty else "")
        for r in changes.itertuples():
            print(f"    {r.business_unit}: {r.status_before} -> {r.status_now}")
    print(f"  dashboard: {report}\n  action list: {xlsx}\n  saved to: {h}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
