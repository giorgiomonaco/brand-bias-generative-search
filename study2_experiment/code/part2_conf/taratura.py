"""Taratura (protocollo sez. 4): 5 pagine originali con identità reale, 10 ordini di Williams, 1 ripetizione."""
import sys, json, statistics as st
from comune import DOM, D, williams, testo_orig, messaggio, esegui
OUT = D / "taratura.jsonl"
MOTORI = ("gpt", "deepseek", "perplexity")
def piano():
    items = []
    for q, v in DOM.items():
        pag = [(testo_orig(q, i), p[2]) for i, p in enumerate(v["pagine"])]
        for m in MOTORI:
            for j, o in enumerate(williams()):
                items.append(dict(call_id=f"T|{q}|{m}|{j}", fase="taratura", qid=q, motore=m, ordine=o, j=j,
                                  user_message=messaggio(v["domanda"], pag, o), system_prompt=None, search=False))
    return items
def riepilogo():
    rows = [json.loads(l) for l in OUT.open()]
    ok = {}
    for r in rows:
        from comune import classifica as C
        if not r.get("error") and C(r.get("response_text"), r["ordine"]) is not None: r["classifica"] = C(r.get("response_text"), r["ordine"]); ok[r["call_id"]] = r
    scelta = {}
    for q, v in DOM.items():
        pos = {i: [] for i in range(5)}; pm = {i: {} for i in range(5)}
        for r in ok.values():
            if r["qid"] != q: continue
            for p, idx in enumerate(r["classifica"]):
                pos[idx].append(p + 1); pm[idx].setdefault(r["motore"], []).append(p + 1)
        media = {i: st.mean([st.mean(x) for x in pm[i].values()]) for i in range(5) if pm[i]}
        var = {i: st.pvariance(pos[i]) for i in range(5) if pos[i]}
        best = sorted(media, key=lambda i: (abs(media[i] - 3), var[i], v["pagine"][i][0]))[0]
        scelta[q] = dict(bersaglio=best, brand=v["pagine"][best][0], medie={v["pagine"][i][0]: round(media[i], 2) for i in media},
                         per_motore={v["pagine"][i][0]: {m: round(st.mean(x), 2) for m, x in pm[i].items()} for i in media},
                         n=len([r for r in ok.values() if r["qid"] == q]))
        print(q, "->", scelta[q]["brand"], scelta[q]["medie"], scelta[q]["n"])
    json.dump(scelta, open(D / "taratura_scelta.json", "w"), ensure_ascii=False, indent=1)
if __name__ == "__main__":
    if "--riepilogo" in sys.argv: riepilogo()
    else: esegui(piano(), OUT, budget_s=float(sys.argv[1]) if len(sys.argv) > 1 else 150)
