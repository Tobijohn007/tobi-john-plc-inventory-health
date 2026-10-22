# Tobi John PLC: inventory health and executive visibility (demo)

This practice project shows how a group with 7 verticals and 25 business units can get one trusted view of its inventory. A pipeline cleans duplicates, negatives and extra zeros, then reconciles stock records to finance balances. It measures days of stock and sets a seasonal target range for each business unit, so leaders can see what is above, in or below range. It also flags slow-moving, expiring and at-risk items and ranks the actions by naira value. Results appear in a Streamlit dashboard, an HTML executive report and a copilot that answers questions from the model’s numbers. A monthly refresh script checks incoming data before updating everything. The company and its data are fictional.

<img width="1802" height="819" alt="image" src="https://github.com/user-attachments/assets/235f21bc-ecc5-4e9d-9290-51bda8679c57" />


## Run it
    pip install -r requirements.txt
    python run_pipeline.py --regenerate   # builds data and all results in outputs/
    python verify_demo.py                 # checks the pipeline finds the planted problems
    python make_report.py                 # outputs/executive_report.html (open in a browser)
    streamlit run app.py                  # interactive executive view

## What each part does
| File | Job | Type |
|---|---|---|
| generate_data.py | Fake company data with planted problems | data |
| checks.py | Clean duplicates, negative stock, extra zeros; compare with finance | rules |
| metrics.py | Inventory value, days of stock, turnover, holding cost, ABC | calculation |
| adequacy.py | Normal range per business unit from its own history and season | statistics |
| early_warnings.py | Slow-moving, expiry risk, may run short | rules |
| insights.py | Plain-English monthly summary written from the numbers | templates (a language model can polish later; numbers always come from code) |
| views.py, app.py, make_report.py | What the executive sees | display |

## Assumptions to confirm with the business
- Holding cost 25% a year (ask finance).
- ABC cut-offs 80% / 95% of usage value, per business unit.
- Slow-moving = no use for 6 months (12 for spare parts); expiry risk above 80% of shelf life; short below 60% of normal cover.
- Range = normal days of cover learned from the first 24 months, with 15–35% tolerance.

## Honest limits
- The Streamlit app was only smoke-tested with a stand-in, not in real Streamlit (the package could not be installed in the build environment). The HTML report was rendered and checked.
- 2 extra-zero rows and 2 spare-part dead items are missed by design; the model's extra "Excess" units (Pasta, Syrups, etc.) are real idle dead stock.
- With real data, expect messier inputs; rules in checks.py need tuning on actual D365 exports.

https://tobi-john-plc-inventory-health-ntzhezagw6cacu9vdkshqy.streamlit.app/


## Working system (monthly refresh + copilot)
    python refresh.py               # drop the new month's 3 files in incoming/ first; checks, updates, rebuilds everything
    python copilot.py               # ask questions in the terminal (set ANTHROPIC_API_KEY for language-model mode)
    python make_copilot_page.py     # outputs/copilot.html: chat page that opens in any browser
    python make_sample_month.py     # makes a fake next month for testing refresh.py (changes data/: back it up first)
