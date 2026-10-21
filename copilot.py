"""Inventory copilot: ask questions in plain English, get answers from the model's results.

    python copilot.py                 chat in the terminal

Two modes, chosen automatically:
  - With ANTHROPIC_API_KEY set (and `pip install anthropic`): Claude reads your question, calls the tools in
    copilot_tools.py to fetch the facts, and writes the answer. Numbers still come only from the tools.
  - Without a key: a built-in question matcher answers the common questions from the same tools.
"""
import json
import os
import re

import copilot_tools as T

EXAMPLES = ["How are we doing overall?", "Which units have the most excess stock?", "Is Fertilizer okay?",
            "What is at risk of expiring?", "Which items should we focus on in Pasta?", "Does the data match finance?"]


def _find_unit(q):
    q = q.lower()
    best = [u for u in T.units() if u.lower() in q]
    return max(best, key=len) if best else None


def _fmt(d):
    return "\n".join(f"  {k.replace('_', ' ')}: {v}" for k, v in d.items() if not isinstance(v, (list, dict)))


def rules_answer(q):
    ql = q.lower()
    u = _find_unit(q)
    if re.search(r"\bhelp\b|what can you", ql):
        return "Try: " + " | ".join(EXAMPLES)
    if re.search(r"expir|slow|dead|idle|risk|warning", ql):
        kind = "expir" if "expir" in ql else "slow" if re.search(r"slow|dead|idle", ql) else None
        w = T.warnings_for(u, kind)
        head = f"{w['count']} flagged items worth {w['total_value']}" + (f" in {u}" if u else "") + ". Largest:"
        return head + "\n" + "\n".join(f"  - {x['item']}: {x['value']} ({x['type']}; {x['why']})" for x in w["top"])
    if re.search(r"class a|abc|important|focus|priorit", ql):
        a = T.abc(u)
        return ("ABC split" + (f" for {u}" if u else " for the group") + ":\n" +
                "\n".join(f"  class {c}: {v['items']} items, {v['share_of_usage']} of usage, {v['share_of_inventory']} of inventory" for c, v in a.items()))
    if re.search(r"financ|reconcil|match|accura|trust|error|clean", ql):
        f = T.finance_check(u)
        return (f"Stock records were {f['company_gap_before_cleaning']} off finance before cleaning and {f['company_gap_after_cleaning']} after. "
                f"{f['errors_fixed']} errors worth {f['value_fixed']} were fixed.\nLargest remaining gaps: " +
                "; ".join(f"{x['unit']} {x['gap']}" for x in f["largest_remaining_gaps"]))
    if re.search(r"short|run out|shortage|too little|low stock", ql) and not u:
        r = T.rank_units("short")
        return "Below range: " + ("; ".join(f"{x['business_unit']} ({x['amount']} short of {x['range']})" for x in r) or "none")
    if re.search(r"excess|too much|overstock|most|biggest|worst|cash", ql) and not u:
        r = T.rank_units("excess")
        return "Above range, biggest first:\n" + "\n".join(f"  {i}. {x['business_unit']}: {x['amount']} above range (stock {x['stock_now']}, range {x['range']})" for i, x in enumerate(r, 1))
    v = next((x for x in T.verticals() if x.lower() in ql), None)
    if v and not u:
        d = T.vertical_summary(v)
        return f"{d['summary']}\n{d['actions']}"
    if u:
        s = T.unit_status(u)
        return f"{s['summary']}\n{s.get('suggested_actions', '')}\n" + _fmt({k: s[k] for k in ('status', 'stock_now', 'range', 'days_of_stock') if k in s})
    if re.search(r"overall|company|group|total|how are we|summary", ql):
        return _fmt(T.company_overview())
    return "I can answer questions about stock levels, excess and shortages, risks, ABC items and the finance match. Say 'help' for examples."


TOOLS = [
    {"name": "company_overview", "description": "Group-level inventory numbers.", "input_schema": {"type": "object", "properties": {}}},
    {"name": "unit_status", "description": "Status, range, days of stock, summary and actions for one business unit.", "input_schema": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}},
    {"name": "rank_units", "description": "Units above range (kind=excess) or below range (kind=short), biggest first.", "input_schema": {"type": "object", "properties": {"kind": {"type": "string", "enum": ["excess", "short"]}, "n": {"type": "integer"}}}},
    {"name": "warnings_for", "description": "Slow-moving, expiry-risk or may-run-short items, optionally for one unit and one kind (slow, expir, short).", "input_schema": {"type": "object", "properties": {"unit": {"type": "string"}, "kind": {"type": "string"}, "n": {"type": "integer"}}}},
    {"name": "abc", "description": "ABC classification split, optionally for one unit.", "input_schema": {"type": "object", "properties": {"unit": {"type": "string"}}}},
    {"name": "finance_check", "description": "How well stock records match finance, and what was fixed.", "input_schema": {"type": "object", "properties": {"unit": {"type": "string"}}}},
]
SYSTEM = ("You are an inventory copilot for supply chain leaders at " + "Tobi John PLC" + ". Answer only from the tool results. "
          "Never invent numbers. If the tools cannot answer, say so. Be brief and lead with the answer. Valid business units: " + ", ".join(T.units()))


def llm_answer(client, history):
    while True:
        r = client.messages.create(model=os.environ.get("COPILOT_MODEL", "claude-sonnet-5-5"), max_tokens=800, system=SYSTEM, tools=TOOLS, messages=history)
        history.append({"role": "assistant", "content": r.content})
        calls = [b for b in r.content if b.type == "tool_use"]
        if not calls:
            return "".join(b.text for b in r.content if b.type == "text")
        history.append({"role": "user", "content": [{"type": "tool_result", "tool_use_id": c.id, "content": json.dumps(getattr(T, c.name)(**c.input))} for c in calls]})


def main():
    client = None
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            import anthropic
            client = anthropic.Anthropic()
        except ImportError:
            print("(pip install anthropic to use the language-model mode; using the built-in matcher)")
    print(f"Inventory copilot ({'language model' if client else 'built-in matcher'} mode). Type 'quit' to leave.\nTry: {EXAMPLES[1]}")
    history = []
    while True:
        q = input("\nYou: ").strip()
        if q.lower() in ("quit", "exit", ""):
            break
        if client:
            history.append({"role": "user", "content": q})
            print("\nCopilot:", llm_answer(client, history))
        else:
            print("\nCopilot:", rules_answer(q))


if __name__ == "__main__":
    main()
