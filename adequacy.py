"""Part C: is the inventory adequate?

For every business unit and type of stock (a "store"), the model answers one question each
month: is the stock excess, in range, or short?

How it works, step by step:

  1. Learn the normal cover. Over the first 24 months, work out how many days of next month's
     usage each store normally holds (the middle value), and how much that varies.
  2. Forecast next month's usage. Take the same month last year and scale it by how much
     usage has grown over the past year. This keeps the seasons. (Spare parts are lumpy, so
     they use a smoothed yearly average instead.)
  3. Set the range. Target stock = normal cover days x forecast daily usage. The range is the
     target plus or minus a tolerance learned from how much cover normally varies.
  4. Label the store: above the range is Excess, below is Short, otherwise In range.

Because the forecast follows the seasons, the range rises before a busy month and falls
after it. A fixed range cannot do that, so the model also scores a fixed-range version to
show how many false alarms the seasonal one avoids.

The "normal cover" is learned from the business's own history. In a real project it must be
agreed with the supply chain team (week 8 of the plan), because history can contain habits
the business does not want to keep.
"""
import numpy as np
import pandas as pd

import config as C

KEYS = ["business_unit", "stock_type"]


def build_series(clean):
    s = (clean.groupby(KEYS + ["month"])
         .agg(usage_value=("usage_value", "sum"), closing_value=("closing_value", "sum"))
         .reset_index().sort_values(KEYS + ["month"]).reset_index(drop=True))
    s["month_idx"] = s.groupby(KEYS).cumcount()
    return s


def add_forecasts(s):
    """Forecast of next month's usage, made at the end of each month, plus two simple rivals."""
    g = s.groupby(KEYS)["usage_value"]
    s["usage_12m"] = g.transform(lambda x: x.rolling(12).sum())
    s["growth"] = s.groupby(KEYS)["usage_12m"].transform(lambda x: x / x.shift(12))
    seasonal = g.shift(11) * s["growth"]                  # same month last year, scaled by growth
    smoothed = s["usage_12m"] / 12 * s["growth"] ** 0.5   # yearly average, nudged for growth
    s["forecast_next"] = np.where(s["stock_type"] == "Spare parts", smoothed, seasonal)
    s["flat_next"] = s["usage_12m"] / 12                   # rival 1: a fixed, non-seasonal level
    s["ma3_next"] = g.transform(lambda x: x.rolling(3).mean())  # rival 2: 3-month moving average
    s["actual_next"] = g.shift(-1)
    return s


def learn_targets(s):
    """Normal days of cover for each store, and how much it normally varies."""
    base = s[s["month_idx"] < C.BASELINE_MONTHS].copy()
    base["cover_days"] = base["closing_value"] / (base["actual_next"] / C.DAYS_PER_MONTH)
    base = base.replace([np.inf, -np.inf], np.nan).dropna(subset=["cover_days"])
    g = base.groupby(KEYS)["cover_days"]
    out = g.median().rename("target_days").to_frame()
    out["spread"] = g.agg(lambda x: (x - x.median()).abs().median())
    out["tolerance"] = (1.4826 * out["spread"] / out["target_days"] * 1.5).clip(
        C.MIN_TOLERANCE, C.MAX_TOLERANCE)
    return out.reset_index()


def _label(closing, low, high, available):
    label = np.select([closing > high, closing < low], ["Excess", "Short"], default="In range")
    return pd.Series(label, index=closing.index).where(available)


def add_ranges(s, targets):
    s = s.merge(targets, on=KEYS, how="left")
    avail = s["forecast_next"].notna() & s["target_days"].notna()
    s["target_value"] = s["target_days"] * s["forecast_next"] / C.DAYS_PER_MONTH
    s["range_low"] = s["target_value"] * (1 - s["tolerance"])
    s["range_high"] = s["target_value"] * (1 + s["tolerance"])
    s["status"] = _label(s["closing_value"], s["range_low"], s["range_high"], avail)
    s["excess_value"] = (s["closing_value"] - s["range_high"]).clip(lower=0).where(avail)
    s["shortfall_value"] = (s["range_low"] - s["closing_value"]).clip(lower=0).where(avail)
    s["cover_days_now"] = s["closing_value"] / (s["forecast_next"] / C.DAYS_PER_MONTH)

    # the fixed-range rival, for comparison only
    flat_target = s["target_days"] * s["flat_next"] / C.DAYS_PER_MONTH
    s["status_fixed_range"] = _label(
        s["closing_value"], flat_target * (1 - s["tolerance"]), flat_target * (1 + s["tolerance"]), avail)
    s["vertical"] = s["business_unit"].map(C.BU_TO_VERTICAL)
    return s


def backtest(s):
    """How good was the forecast, and how many false alarms does the seasonal range avoid?"""
    d = s.dropna(subset=["forecast_next", "ma3_next", "flat_next", "actual_next"]).copy()
    rows = []
    groups = [("All stock", d)] + [(t, d[d["stock_type"] == t]) for t in C.STOCK_TYPES]
    for name, x in groups:
        a = x["actual_next"].sum()
        rows.append({
            "stock_type": name,
            "wape_seasonal_model": (x["forecast_next"] - x["actual_next"]).abs().sum() / a,
            "wape_moving_average": (x["ma3_next"] - x["actual_next"]).abs().sum() / a,
            "wape_fixed_level": (x["flat_next"] - x["actual_next"]).abs().sum() / a,
            "bias_seasonal_model": (x["forecast_next"] - x["actual_next"]).sum() / a,
        })
    accuracy = pd.DataFrame(rows)

    a = s[s["status"].notna()]
    flags = pd.DataFrame({
        "method": ["Seasonal range (model)", "Fixed range"],
        "excess_share": [(a["status"] == "Excess").mean(), (a["status_fixed_range"] == "Excess").mean()],
        "short_share": [(a["status"] == "Short").mean(), (a["status_fixed_range"] == "Short").mean()],
    })
    flags["flagged_share"] = flags["excess_share"] + flags["short_share"]
    return accuracy, flags


def roll_up(s, by):
    """Add up store ranges to business unit or vertical level."""
    a = s[s["status"].notna()]
    g = a.groupby([by, "month"]).agg(
        closing_value=("closing_value", "sum"),
        target_value=("target_value", "sum"),
        range_low=("range_low", "sum"),
        range_high=("range_high", "sum"),
        excess_value=("excess_value", "sum"),
        shortfall_value=("shortfall_value", "sum"),
        forecast_next=("forecast_next", "sum"),
    ).reset_index()
    g["status"] = np.select([g["closing_value"] > g["range_high"], g["closing_value"] < g["range_low"]],
                            ["Excess", "Short"], default="In range")
    g["cover_days_now"] = g["closing_value"] / (g["forecast_next"] / C.DAYS_PER_MONTH)
    g["excess_holding_cost_month"] = g["excess_value"] * C.HOLDING_COST_RATE / 12
    return g


def run_adequacy(clean):
    s = add_forecasts(build_series(clean))
    targets = learn_targets(s)
    s = add_ranges(s, targets)
    accuracy, flags = backtest(s)
    s_out = s[s["status"].notna()].copy()
    bu = roll_up(s_out, "business_unit")
    bu["vertical"] = bu["business_unit"].map(C.BU_TO_VERTICAL)
    vertical = roll_up(s_out, "vertical")
    return {"series": s_out, "business_unit": bu, "vertical": vertical,
            "accuracy": accuracy, "flag_rates": flags, "targets": targets}
