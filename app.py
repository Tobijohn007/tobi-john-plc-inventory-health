"""Executive view for Tobi John PLC.

    streamlit run app.py

Shows what an MD or CFO needs to see first: how much inventory the business holds, how that
compares with the size of the business, whether each business unit is in range, and what to do
about it. All numbers come from outputs/, which run_pipeline.py creates.
"""
import streamlit as st

import config as C
import copilot
import run_pipeline
import views as V

st.set_page_config(page_title=f"{C.COMPANY}: inventory health", page_icon="📦", layout="wide")

STATUS_LABEL = {"Excess": "▲ Above range", "Short": "▼ Below range", "In range": "● In range"}
TYPE_COLUMNS = C.STOCK_TYPES


@st.cache_data
def get_data():
    if not (C.OUT_DIR / "run_info.json").exists():
        run_pipeline.main()
    return V.load()


def show(df, **formats):
    """Show a table: one decimal for numbers unless told otherwise, status with an icon."""
    df = df.copy()
    if "Status" in df.columns:
        df["Status"] = df["Status"].map(STATUS_LABEL).fillna(df["Status"])
    config = {}
    for col in df.columns:
        if str(df[col].dtype).startswith("float"):
            config[col] = st.column_config.NumberColumn(col, format=formats.get(col, "%.1f"))
    st.dataframe(df, hide_index=True, column_config=config)


d = get_data()
last = d["last"]
kpi = V.company_kpis(d)

with st.sidebar:
    st.header(C.COMPANY)
    st.caption(f"Latest month: {last:%B %Y}")
    vertical = st.selectbox("Vertical", ["All"] + list(C.VERTICALS), key="vertical")
    st.caption("The vertical filter applies to the business units and warnings tabs.")

st.title(f"{C.COMPANY}: inventory health")
st.caption(f"{last:%B %Y}. Demo data: the company, its numbers and its problems are made up.")

tabs = st.tabs(["Overview", "Business units", "Stock vs range", "ABC", "Warnings",
                "Data integrity", "Monthly summary", "Ask the copilot"])

# ---------------------------------------------------------------- overview
with tabs[0]:
    a, b, c, e, f = st.columns(5)
    mom = kpi.inventory_value / kpi.inventory_prev - 1
    a.metric("Inventory value", f"₦{kpi.inventory_value / V.BN:,.1f}bn", f"{mom:+.1%} vs last month", delta_color="off")
    b.metric("Share of annual sales", f"{kpi.pct_of_sales:.1%}")
    c.metric("Days of stock", f"{kpi.days_of_inventory:.0f}",
             f"{kpi.days_of_inventory - kpi.days_of_inventory_yoy:+.0f} vs a year ago", delta_color="inverse")
    e.metric("Above range", f"₦{kpi.excess_value / V.BN:,.1f}bn",
             f"≈ ₦{kpi.excess_cost_month / V.MN:,.0f}m a month to hold", delta_color="off")
    f.metric("Gap to finance", f"{kpi.gap_clean_pct:+.1%}", f"{kpi.gap_reported_pct:+.1%} before cleaning", delta_color="off")

    st.subheader("By vertical")
    show(V.vertical_table(d))

    st.subheader("Inventory value by type of stock (₦bn)")
    m = d["metrics"]
    m = m[(m["level"] == "vertical") & (m["month"] == last)].set_index("name")[TYPE_COLUMNS] / V.BN
    st.bar_chart(m.sort_values(TYPE_COLUMNS[0], ascending=False))

    st.subheader("Company inventory value (₦bn, after cleaning)")
    st.line_chart(V.company_trend(d)[["Cleaned"]])

# ---------------------------------------------------------------- business units
with tabs[1]:
    st.subheader("Business units" + ("" if vertical == "All" else f": {vertical}"))
    st.caption("Sorted with the units above their range first. Inventory is held at business unit level, "
               "so this is where decisions are made.")
    show(V.bu_table(d, vertical).drop(columns=["Stock vs target (x)", "Range low (x target)", "Range high (x target)"]))

# ---------------------------------------------------------------- stock vs range
with tabs[2]:
    bu_list = sorted(C.BU_TO_VERTICAL)
    bu = st.selectbox("Business unit", bu_list, index=bu_list.index("Biscuits"), key="range_bu")
    st.subheader(f"{bu}: stock held against its range (₦bn)")
    st.caption("The range moves with the seasons because it is based on the forecast usage for next month.")
    st.line_chart(V.bu_range_history(d, bu))
    st.subheader("By type of stock, latest month")
    show(V.store_table(d, bu))
    with st.expander("How well does the model work?"):
        st.write("Forecast error (WAPE) for next month's usage. Lower is better. The seasonal model is "
                 "compared with a 3-month moving average and a fixed level.")
        acc = d["accuracy"].copy()
        for col in acc.columns[1:]:
            acc[col] = acc[col] * 100
        acc.columns = ["Stock", "Seasonal model (%)", "3-month average (%)", "Fixed level (%)", "Seasonal model bias (%)"]
        show(acc, **{c: "%.1f" for c in acc.columns[1:]})
        fl = d["flags"].copy()
        for col in ("excess_share", "short_share", "flagged_share"):
            fl[col] = fl[col] * 100
        fl.columns = ["Range type", "Flagged above range (%)", "Flagged below range (%)", "Flagged in total (%)"]
        st.write("Share of store-months flagged. A fixed range raises more alarms because it ignores the seasons.")
        show(fl)

# ---------------------------------------------------------------- ABC
with tabs[3]:
    st.subheader("Where the value is: whole company")
    st.caption("Share held by each class. A items are the few that make up the first 80% of usage value.")
    st.bar_chart(V.abc_company(d).round(1))
    bu_abc = st.selectbox("Business unit", sorted(C.BU_TO_VERTICAL), key="abc_bu")
    st.subheader(f"{bu_abc}: ABC classes")
    show(V.abc_bu_table(d, bu_abc))
    st.subheader("Top A items by usage value")
    show(V.abc_top_items(d, bu_abc), **{"Usage, last 12 months (₦bn)": "%.2f", "Stock held (₦bn)": "%.2f"})

# ---------------------------------------------------------------- warnings
with tabs[4]:
    tot = V.warnings_totals(d, vertical)
    st.subheader("Early warnings" + ("" if vertical == "All" else f": {vertical}"))
    show(tot.rename(columns={"warning_type": "Warning", "items": "Items", "amount_bn": "Amount (₦bn)"})
         [["Warning", "Items", "Amount (₦bn)"]])
    for kind, text in (
        ("Slow-moving", "No use for 6 months (12 for spare parts) while stock remains."),
        ("Expiry risk", "Stock would take longer than 80% of shelf life to use up."),
        ("May run short", "Stock covers less than 60% of normal days of cover."),
    ):
        st.markdown(f"**{kind}.** {text}")
        view = V.warnings_view(d, kind, vertical)
        if view.empty:
            st.write("None.")
        else:
            show(view)

# ---------------------------------------------------------------- data integrity
with tabs[5]:
    st.subheader("One trusted number")
    st.write(f"As reported, inventory is {kpi.gap_reported_pct:+.1%} away from the finance balance. "
             f"After cleaning it is {kpi.gap_clean_pct:+.1%}.")
    st.line_chart(V.gap_trend(d))
    st.subheader("Biggest gaps to finance, latest month")
    show(V.recon_view(d))
    st.subheader("What was found and fixed")
    show(V.issues_summary(d), **{"Net effect, latest month (₦bn)": "%.2f", "Size of errors, latest month (₦bn)": "%.2f"})
    st.caption("Any gap left after cleaning looks like timing, such as receipts not yet posted. "
               "That needs a conversation with finance, not a rule.")

# ---------------------------------------------------------------- monthly summary
with tabs[6]:
    who = st.selectbox("Summary for", [C.COMPANY] + list(C.VERTICALS), key="summary_for")
    text, actions = V.summary_for(d, who)
    st.subheader(who)
    st.write(text)
    st.markdown("**What to do**")
    for a_ in actions:
        st.markdown(f"- {a_}")


# ---------------------------------------------------------------- copilot
with tabs[7]:
    st.subheader("Ask the copilot")
    st.caption("Ask about stock levels, excess or short units, risks, ABC items or the finance match. "
               "Answers come from the model's results, not from guesswork.")
    if "chat" not in st.session_state:
        st.session_state.chat = [("assistant", "Hello. Ask me about a business unit, for example 'Is Fertilizer okay?'")]
    cols = st.columns(3)
    quick = None
    for col, text_ in zip(cols, ["Which units have the most excess stock?", "What is at risk of expiring?", "Does the data match finance?"]):
        if col.button(text_, key=f"quick_{text_}"):
            quick = text_
    for role, msg in st.session_state.chat:
        with st.chat_message(role):
            st.text(msg)
    question = st.chat_input("Ask a question") or quick
    if question:
        st.session_state.chat.append(("user", question))
        st.session_state.chat.append(("assistant", copilot.rules_answer(question)))
        st.rerun()
