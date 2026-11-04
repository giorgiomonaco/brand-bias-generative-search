"""Pagine, regola 1 (protocollo sez. 4): URL sul dominio ufficiale del marchio citati dai motori nelle risposte
principali di Study 1 alla stessa domanda (escluso il braccio con la persona nel system prompt)."""
import json, collections
from urllib.parse import urlsplit
from comune_v3 import ROOT, D
sel = json.load(open(D / "selezione_v3.json"))
cit = collections.defaultdict(collections.Counter)
for l in open(ROOT / "data/processed/main_calls.jsonl"):
    r = json.loads(l)
    if r["prompt_id"] not in sel or r.get("level") == "A_sistema": continue
    for u in set(r.get("urls_citate") or []):
        cit[r["prompt_id"]][u.split("#")[0].split("?utm")[0]] += 1
def host_ok(u, dom):
    h = (urlsplit(u).hostname or "").lower()
    return h == dom or h.endswith("." + dom)
out = {}
for pid, v in sel.items():
    out[pid] = {}
    for p in v["pagine"]:
        c = [(u, n) for u, n in cit[pid].most_common() if host_ok(u, p["dominio"]) and not u.lower().endswith(".pdf")]
        out[pid][p["nome"]] = dict(chiave=p["chiave"], dominio=p["dominio"], citazioni=c)
json.dump(out, open(D / "pagine_candidate.json", "w"), ensure_ascii=False, indent=1)
if __name__ == "__main__":
    tot = sum(len(x) for x in out.values()); con = sum(bool(b["citazioni"]) for x in out.values() for b in x.values())
    print(f"marchi con almeno un URL citato sul proprio dominio: {con}/{tot}")
    for pid, x in out.items(): print(pid, {n: len(b["citazioni"]) for n, b in x.items()})
