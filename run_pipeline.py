"""Run the whole pipeline: data -> checks -> metrics -> adequacy -> warnings -> summaries.

    python run_pipeline.py              uses the data in data/ (creates it if missing)
    python run_pipeline.py --regenerate makes fresh sample data first

Everything it produces goes to outputs/ as plain CSV files that the app and the HTML report read.
"""
import argparse
import json

import pandas as pd

import adequacy
import checks
import config as C
import early_warnings
import generate_data
import insights
import metrics


def load_inputs():
    d = C.DATA_DIR
    raw = pd.read_csv(d / "inventory_raw.csv", parse_dates=["month"])
    items = pd.read_csv(d / "items.csv")
    finance = pd.read_csv(d / "finance_balances.csv", parse_dates=["month"])
    sales = pd.read_csv(d / "sales.csv", parse_dates=["month"])
    return raw, items, finance, sales


def main(regenerate=False):
    if regenerate or not (C.DATA_DIR / "inventory_raw.csv").exists():
        generate_data.main()
    C.OUT_DIR.mkdir(exist_ok=True)
    raw, items, finance, sales = load_inputs()

    # Part A: one trusted dataset
    clean, issues = checks.clean_inventory(raw)
    recon = checks.reconcile(raw, clean, finance)
    last = clean["month"].max()
    recon_latest = checks.reconciliation_summary(recon, last)

    # Part B: health metrics and ABC
    met = metrics.build_metrics(clean, sales)
    abc = metrics.abc_classification(clean, items)

    # Part C: adequacy ranges and early warnings
    adq = adequacy.run_adequacy(clean)
    warn = early_warnings.build_warnings(clean, items, abc, adq["targets"])

    # Part D: monthly insight summary
    summaries, kpis, last = insights.build_summaries(met, adq["business_unit"], abc, warn, recon, issues)

    out = C.OUT_DIR
    clean.to_csv(out / "clean_inventory.csv", index=False)
    issues.to_csv(out / "data_issues.csv", index=False)
    recon.to_csv(out / "reconciliation.csv", index=False)
    recon_latest.to_csv(out / "reconciliation_latest.csv", index=False)
    met.to_csv(out / "metrics.csv", index=False)
    abc.to_csv(out / "abc_items.csv", index=False)
    metrics.abc_summary(abc, "business_unit").to_csv(out / "abc_summary_business_unit.csv", index=False)
    metrics.abc_summary(abc, "vertical").to_csv(out / "abc_summary_vertical.csv", index=False)
    adq["series"].to_csv(out / "adequacy_series.csv", index=False)
    adq["business_unit"].to_csv(out / "adequacy_business_units.csv", index=False)
    adq["vertical"].to_csv(out / "adequacy_verticals.csv", index=False)
    adq["targets"].to_csv(out / "adequacy_targets.csv", index=False)
    adq["accuracy"].to_csv(out / "forecast_accuracy.csv", index=False)
    adq["flag_rates"].to_csv(out / "flag_rates.csv", index=False)
    warn.to_csv(out / "warnings.csv", index=False)
    kpis.to_csv(out / "kpis.csv", index=False)
    summaries.to_csv(out / "summaries.csv", index=False)
    (out / "monthly_summary.md").write_text(insights.as_markdown(summaries, last))
    (out / "run_info.json").write_text(json.dumps({"latest_month": str(last.date()), "company": C.COMPANY}))

    c = kpis[kpis["level"] == "company"].iloc[0]
    print(f"{C.COMPANY}, {last:%B %Y}")
    print(f"  inventory (clean) {insights.money(c.inventory_value)}, {c.pct_of_sales:.1%} of annual sales, "
          f"{c.days_of_inventory:.0f} days")
    print(f"  business units: {c.n_excess} excess, {c.n_short} short, {c.n_in_range} in range")
    print(f"  excess {insights.money(c.excess_value)}, holding cost {insights.money(c.excess_cost_month)} a month")
    print(f"  reported vs finance {c.gap_reported_pct:+.1%}, after cleaning {c.gap_clean_pct:+.1%}")
    print(f"  warnings: {len(warn)} ({warn['warning_type'].value_counts().to_dict()})")
    print(f"  wrote {len(list(out.glob('*')))} files to {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--regenerate", action="store_true")
    main(ap.parse_args().regenerate)
