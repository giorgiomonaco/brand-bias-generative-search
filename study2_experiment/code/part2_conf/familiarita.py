"""Sonda di familiarità (protocollo sez. 6)."""
import sys, json, re, time, threading, statistics as st
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from comune import DOM, D
OUT = D / "familiarita.jsonl"
SETTORE = {"sport_01": "scarpe da trekking", "sport_07": "tapis roulant", "sport_13": "racchette da padel",
 "moda_beauty_05": "cosmetici e sieri per il viso", "moda_beauty_19": "trucco e fondotinta",
 "assicurazioni_02": "assicurazioni di viaggio", "assicurazioni_05": "assicurazioni", "assicurazioni_10": "assicurazioni",
 "assicurazioni_13": "assicurazioni auto", "assicurazioni_19": "assicurazioni per animali domestici",
 "viaggi_10": "tour operator e viaggi di gruppo", "viaggi_15": "tour operator e villaggi turistici"}
MINORI = {"sport_01": ["Kayland", "Garsport", "Dachstein"], "sport_07": ["Everfit", "JK Fitness", "Get Fit"],
 "sport_13": ["Vibor-A", "Royal Padel"], "moda_beauty_05": ["Bioclin", "Lycia", "Euphidra"],
 "moda_beauty_19": ["Wycon", "Neve Cosmetics", "Deborah Milano"], "assicurazioni_02": ["Nobis", "Chapka", "ERGO"],
 "assicurazioni_05": ["ITAS Mutua", "Assimoco", "Net Insurance"], "assicurazioni_10": ["ITAS Mutua", "Assimoco", "Net Insurance"],
 "assicurazioni_13": ["ITAS Mutua", "Assimoco", "Net Insurance"], "assicurazioni_19": ["Barkibu", "ITAS Mutua", "Assimoco"],
 "viaggi_10": ["Kel 12", "Viaggi dell'Elefante", "Mistral Tour"], "viaggi_15": ["Turisanda", "Settemari", "Futura Vacanze"]}
INVENTATI = {"sport_01": "Kervino", "sport_07": "Tremola", "sport_13": "Zelvar", "moda_beauty_05": "Aurelys",
 "moda_beauty_19": "Velisse", "assicurazioni_02": "Ostria", "assicurazioni_05": "Pelora", "assicurazioni_10": "Marvento",
 "assicurazioni_13": "Corvalia", "assicurazioni_19": "Nidrava", "viaggi_10": "Velmora", "viaggi_15": "Brezzaria"}
P = ("Conosci il marchio «{b}» nel settore {s}? Rispondi solo con due righe:\n"
     "PUNTEGGIO: un numero da 0 (mai sentito, o non credo che esista) a 3 (lo conosco bene)\nDESCRIZIONE: una riga su cosa vende")
def marchi():
    out = []
    for q, v in DOM.items():
        for p in v["pagine"]: out.append((q, p[0], "pagina"))
        for b in MINORI[q]: out.append((q, b, "minore"))
        out.append((q, INVENTATI[q], "inventato"))
    return out
def piano():
    return [dict(call_id=f"F|{q}|{b}|{m}|{r}", qid=q, marchio=b, ruolo=ru, motore=m, rip=r,
                 user_message=P.format(b=b, s=SETTORE[q]), system_prompt=None, search=False)
            for q, b, ru in marchi() for m in ("gpt", "deepseek", "perplexity") for r in range(3)]
def punteggio(t):
    m = re.search(r"PUNTEGGIO\W*([0-3])", re.sub(r"[*_]", "", t or ""), re.I)
    return int(m.group(1)) if m else None
def esegui(budget):
    from motori import motore
    done = set()
    if OUT.exists():
        for l in OUT.open():
            r = json.loads(l)
            if punteggio(r.get("response_text")) is not None: done.add(r["call_id"])
    todo = [i for i in piano() if i["call_id"] not in done]
    t0 = time.monotonic(); lock = threading.Lock(); engs = {}
    def run(it):
        if time.monotonic() - t0 > budget: return
        m = it["motore"]
        with lock:
            if m not in engs: engs[m] = motore(m)
        for _ in range(5):
            rec = engs[m].once(it)
            if not (rec.get("error") and "429" in str(rec.get("error"))[:12]): break
            time.sleep(6)
        out = {k: it[k] for k in ("call_id", "qid", "marchio", "ruolo", "motore", "rip")}
        out.update(response_text=rec.get("response_text"), error=rec.get("error"), model_version=rec.get("model_version"),
                   punteggio=punteggio(rec.get("response_text")), timestamp=datetime.now(timezone.utc).isoformat())
        with lock:
            with OUT.open("a") as f: f.write(json.dumps(out, ensure_ascii=False) + "\n")
    with ThreadPoolExecutor(20) as ex: list(ex.map(run, todo))
    print("fatte", len(done), "da fare", len(todo))
def riepilogo():
    rows = {}
    for l in OUT.open():
        r = json.loads(l)
        if r["punteggio"] is not None: rows[r["call_id"]] = r
    agg = {}
    for r in rows.values():
        agg.setdefault((r["qid"], r["marchio"], r["ruolo"]), {}).setdefault(r["motore"], []).append(r["punteggio"])
    res = {}
    for (q, b, ru), pm in agg.items():
        res.setdefault(q, {})[b] = dict(ruolo=ru, media=round(st.mean(st.mean(x) for x in pm.values()), 2),
                                        per_motore={m: round(st.mean(x), 2) for m, x in pm.items()})
    json.dump(res, open(D / "familiarita_sintesi.json", "w"), ensure_ascii=False, indent=1)
    for q in res: print(q, {b: (x["ruolo"][0], x["media"]) for b, x in res[q].items()})
if __name__ == "__main__":
    riepilogo() if "--riepilogo" in sys.argv else esegui(float(sys.argv[1]))
