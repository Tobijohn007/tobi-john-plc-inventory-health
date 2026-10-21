"""Builds outputs/copilot.html: a chat page you can open in any browser, no server needed.
Answers are pre-computed by copilot.py from the model's results, so they are the same answers as the terminal copilot.
Re-run after each monthly refresh (refresh.py can call it).

    python make_copilot_page.py
"""
import json

import config as C
import copilot
import copilot_tools as T

QUESTIONS = {"overview": "How are we doing overall?", "excess": "Which units have the most excess stock?", "short": "Which units are short?",
             "risk": "What are the risks?", "expiry": "What is at risk of expiring?", "slow": "What is slow moving?",
             "abc": "Which items are class A?", "finance": "Does the data match finance?"}


def build():
    ans = {f"all|{k}": copilot.rules_answer(q) for k, q in QUESTIONS.items()}
    for u in T.units():
        ans[f"unit|{u}|status"] = copilot.rules_answer(f"How is {u}?")
        ans[f"unit|{u}|risk"] = copilot.rules_answer(f"What are the risks in {u}?")
        ans[f"unit|{u}|expiry"] = copilot.rules_answer(f"expiry risk in {u}")
        ans[f"unit|{u}|slow"] = copilot.rules_answer(f"slow moving in {u}")
        ans[f"unit|{u}|abc"] = copilot.rules_answer(f"class A items in {u}")
        ans[f"unit|{u}|finance"] = copilot.rules_answer(f"does {u} match finance")
    for v in T.verticals():
        ans[f"vertical|{v}"] = copilot.rules_answer(f"tell me about {v}")
    month = T.company_overview()["month"]
    html = TEMPLATE.replace("__DATA__", json.dumps({"answers": ans, "units": T.units(), "verticals": T.verticals(), "company": C.COMPANY, "month": month}))
    p = C.OUT_DIR / "copilot.html"
    p.write_text(html, encoding="utf-8")
    return p


TEMPLATE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Inventory Copilot</title>
<style>
:root{--bg:#f6f4ef;--card:#fff;--ink:#14202b;--mut:#5b6872;--line:#ddd5c6;--acc:#c4691a;--me:#14202b;--meink:#f4efe6}
@media (prefers-color-scheme:dark){:root{--bg:#10171e;--card:#1a2631;--ink:#f1ece2;--mut:#a3b1bd;--line:#2c3b49;--acc:#e8913f;--me:#e8913f;--meink:#10171e}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 system-ui,Segoe UI,Arial,sans-serif}
.wrap{max-width:760px;margin:0 auto;padding:16px;display:flex;flex-direction:column;min-height:100vh}
h1{font-size:20px;margin:8px 0 2px}.sub{color:var(--mut);font-size:14px;margin-bottom:12px}
#log{flex:1;display:flex;flex-direction:column;gap:10px;padding-bottom:12px}
.m{max-width:88%;padding:10px 14px;border-radius:14px;white-space:pre-wrap;overflow-wrap:anywhere}
.bot{background:var(--card);border:1px solid var(--line);align-self:flex-start}.me{background:var(--me);color:var(--meink);align-self:flex-end}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin:6px 0 10px}
.chip{border:1px solid var(--line);background:var(--card);color:var(--ink);padding:8px 12px;border-radius:999px;font:inherit;font-size:14px;cursor:pointer}
.chip:hover{border-color:var(--acc)}
form{display:flex;gap:8px;position:sticky;bottom:0;background:var(--bg);padding:10px 0}
input{flex:1;padding:12px 14px;border-radius:12px;border:1px solid var(--line);background:var(--card);color:var(--ink);font:inherit}
button.send{padding:12px 18px;border:0;border-radius:12px;background:var(--acc);color:#fff;font:inherit;font-weight:600;cursor:pointer}
.note{color:var(--mut);font-size:12px;margin-top:4px}
</style></head><body><div class="wrap">
<h1>Inventory Copilot</h1><div class="sub" id="sub"></div>
<div class="chips" id="chips"></div><div id="log" aria-live="polite"></div>
<form id="f"><input id="q" autocomplete="off" placeholder="Ask about stock, risks, a business unit..." aria-label="Your question"><button class="send">Ask</button></form>
<div class="note">Answers come from the model's latest results, not from guesswork. This page answers common questions; for anything else use the terminal copilot with a language model.</div>
</div>
<script>
const D=__DATA__;
document.getElementById('sub').textContent=D.company+' · '+D.month;
const log=document.getElementById('log');
function add(t,c){const d=document.createElement('div');d.className='m '+c;d.textContent=t;log.appendChild(d);window.scrollTo(0,document.body.scrollHeight)}
function find(list,q){let b=null;for(const x of list){if(q.includes(x.toLowerCase())&&(!b||x.length>b.length))b=x}return b}
function answer(raw){
 const q=raw.toLowerCase(),u=find(D.units,q),v=find(D.verticals,q);
 const A=k=>D.answers[k];
 if(/\\bhelp\\b|what can you/.test(q))return 'Try one of the buttons above, or ask about a business unit, for example "Is Fertilizer okay?"';
 const intent=/expir/.test(q)?'expiry':/slow|dead|idle/.test(q)?'slow':/risk|warning/.test(q)?'risk':/class a|abc|important|focus|priorit/.test(q)?'abc':/financ|reconcil|match|accura|trust|error|clean/.test(q)?'finance':null;
 if(intent)return u?A('unit|'+u+'|'+intent):A('all|'+intent);
 if(!u&&/short|run out|shortage|too little|low stock/.test(q))return A('all|short');
 if(!u&&/excess|too much|overstock|most|biggest|worst|cash/.test(q))return A('all|excess');
 if(v&&!u)return A('vertical|'+v);
 if(u)return A('unit|'+u+'|status');
 if(/overall|company|group|total|how are we|summary/.test(q))return A('all|overview');
 return "I can answer questions about stock levels, excess and shortages, risks, ABC items and the finance match. Try one of the buttons, or name a business unit.";
}
function ask(t){t=t.trim();if(!t)return;add(t,'me');add(answer(t),'bot')}
['How are we doing overall?','Which units have the most excess stock?','Which units are short?','What is at risk of expiring?','Does the data match finance?','Is '+D.units[0]+' okay?'].forEach(t=>{const b=document.createElement('button');b.className='chip';b.type='button';b.textContent=t;b.onclick=()=>ask(t);document.getElementById('chips').appendChild(b)});
document.getElementById('f').onsubmit=e=>{e.preventDefault();const i=document.getElementById('q');ask(i.value);i.value=''};
add('Hello. Ask me about stock levels, excess or short units, risks, ABC items, or any business unit by name.','bot');
</script></body></html>"""

if __name__ == "__main__":
    print("wrote", build())
