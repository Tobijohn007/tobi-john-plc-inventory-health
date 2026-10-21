"""Settings for the Tobi John PLC inventory health demo.

Everything about the fictional company lives here: the 7 verticals, the 25 business
units, how seasonal each vertical is, and the few numbers that a real project would
agree with finance and the supply chain team (marked "to confirm").
"""
from pathlib import Path

COMPANY = "Tobi John PLC"
SEED = 42

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
OUT_DIR = ROOT / "outputs"

# 36 monthly snapshots: Oct 2023 to Sep 2026
START_MONTH = "2023-10-01"
N_MONTHS = 36

# ---- numbers a real project must agree with the business (to confirm) -------------
HOLDING_COST_RATE = 0.25   # yearly cost of money tied up in stock (finance to confirm)
ABC_A_CUTOFF = 0.80        # A items: the top items that make up the first 80% of usage value
ABC_B_CUTOFF = 0.95        # B items: the next 15%; C items are the rest
BASELINE_MONTHS = 24       # months used to learn each store's normal days of cover
MIN_TOLERANCE = 0.15       # a range is never narrower than +/-15% around the target
MAX_TOLERANCE = 0.35       # and never wider than +/-35%
DAYS_PER_MONTH = 30.4

STOCK_TYPES = [
    "Finished goods",
    "Raw materials",
    "Packaging materials",
    "Work in progress",
    "Spare parts",
]

# Monthly demand pattern per vertical, January to December (1.0 = average month).
# Annual cost of sales per business unit is in naira billions.
VERTICALS = {
    "Foods": {
        "margin": 0.26,
        "season": [0.92, 0.88, 0.95, 1.10, 0.98, 0.95, 1.00, 1.15, 1.00, 0.95, 1.02, 1.25],
        "units": {"Pasta": 85, "Noodles": 70, "Biscuits": 40, "Snacks": 25, "Breakfast Cereals": 18},
    },
    "Flour & Milling": {
        "margin": 0.18,
        "season": [0.95, 0.93, 0.97, 1.08, 1.00, 0.97, 0.98, 1.05, 1.00, 0.98, 1.02, 1.15],
        "units": {"Premium Flour": 150, "Bakery Flour": 110, "Semolina": 45, "Bran & Co-products": 20},
    },
    "Agro": {
        "margin": 0.22,
        "season": [0.85, 0.85, 0.95, 1.15, 1.25, 1.20, 1.05, 0.95, 0.95, 0.90, 0.90, 1.00],
        "units": {"Animal Feeds": 95, "Fertilizer": 60},
    },
    "Beverages": {
        "margin": 0.30,
        "season": [1.12, 1.20, 1.22, 1.12, 0.98, 0.88, 0.84, 0.84, 0.88, 0.95, 1.02, 1.30],
        "units": {"Soft Drinks": 80, "Juice": 35, "Bottled Water": 30, "Energy Drinks": 22},
    },
    "Packaging": {
        "margin": 0.20,
        "season": [0.95, 0.95, 1.00, 1.05, 1.00, 0.97, 0.98, 1.05, 1.00, 1.00, 1.03, 1.15],
        "units": {"Cartons": 28, "Flexible Films": 38, "Labels": 12},
    },
    "Sugar & Sweeteners": {
        "margin": 0.19,
        "season": [0.95, 0.95, 1.00, 1.05, 1.00, 0.95, 0.97, 1.03, 1.00, 1.00, 1.05, 1.20],
        "units": {"Refined Sugar": 130, "Confectionery": 33, "Syrups": 15},
    },
    "Edible Oils & Fats": {
        "margin": 0.21,
        "season": [0.95, 0.93, 0.98, 1.08, 1.00, 0.97, 0.97, 1.02, 1.00, 1.00, 1.05, 1.20],
        "units": {"Vegetable Oil": 100, "Margarine": 36, "Cooking Fats": 24, "Soap": 30},
    },
}

BU_TO_VERTICAL = {bu: v for v, spec in VERTICALS.items() for bu in spec["units"]}
