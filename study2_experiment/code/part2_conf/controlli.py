"""Emendamento 2: riconoscimento del testo e coerenza percepita marchio–testo.
Testo neutro = modello del bersaglio con i nomi inventati di prodotto/tecnologie e il marchio sostituito da [MARCHIO]."""
import json, re, sys, time, threading, statistics as st
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from comune import DOM, D
from estensione import SUPERIORI, OUT
P_RIC = ("Ecco la scheda di un prodotto in cui il nome del marchio è stato sostituito con [MARCHIO] e i nomi del prodotto e "
         "delle tecnologie con nomi di fantasia.\n\n---\n{t}\n---\n\nSecondo te, di quale marchio reale è questa scheda? Se non "
         "lo sai, scrivi \"non so\". Rispondi solo con due righe:\nMARCHIO: ...\nSICUREZZA: alta / media / bassa")
P_COE = ("Ecco la scheda di un prodotto in cui il nome del marchio è stato sostituito con [MARCHIO] e i nomi del prodotto e "
         "delle tecnologie con nomi di fantasia.\n\n---\n{t}\n---\n\nQuanto è plausibile che questa scheda sia del marchio "
         "«{b}»? Rispondi solo con una riga:\nPUNTEGGIO: un numero da 0 (per niente plausibile) a 3 (del tutto plausibile)")
def neutro(q):
    s = json.load(open(D / "stimoli" / f"{q}_neutro.json"))
    m = {k: ("[MARCHIO]" if k.startswith("BRAND") else s["mappa_inventata"].get(k, v)) for k, v in s["mappa_reale"].items()}
    return re.sub(r"\{([A-Z0-9_]+)\}", lambda x: m.get(x.group(1), x.group(0)), s["modello"]), s
def piano(motori):
    sc = json.load(open(D / "scelte_finali.json")); it = []
    for q in DOM:
        t, s = neutro(q)
        for m in motori:
            for r in range(3):
                it.append(dict(call_id=f"R|{q}|{m}|{r}", tipo="riconoscimento", qid=q, motore=m, rip=r, marchio=s["brand"],
                               user_message=P_RIC.format(t=t), system_prompt=None, search=False))
                for ruolo, b in (("proprio", s["mappa_reale"].get("BRAND", s["brand"])), ("minore", sc["minore"][q]),
                                 ("superiore", SUPERIORI[q]), ("inventato", sc["inventato"][q])):
                    it.append(dict(call_id=f"C|{q}|{ruolo}|{m}|{r}", tipo="coerenza", qid=q, motore=m, rip=r, ruolo=ruolo, marchio=b,
                                   user_message=P_COE.format(t=t, b=b), system_prompt=None, search=False))
    return it
def valore(r):
    t = re.sub(r"[*_]", "", r.get("response_text") or "")
    if r["tipo"] == "coerenza":
        m = re.search(r"PUNTEGGIO\W*([0-3])", t, re.I); return int(m.group(1)) if m else None
    m = re.search(r"MARCHIO\s*:\s*(.+)", t, re.I); return m.group(1).strip() if m else None
def esegui(m, budget):
    from motori import motore
    path = OUT / f"controlli_{m}.jsonl"; done = set()
    if path.exists():
        for l in path.open():
            r = json.loads(l)
            if valore(r) is not None: done.add(r["call_id"])
    todo = [i for i in piano((m,)) if i["call_id"] not in done]; t0 = time.monotonic(); lock = threading.Lock(); eng = motore(m)
    def run(it):
        if time.monotonic() - t0 > budget: return
        for _ in range(5):
            rec = eng.once(it)
            if not (rec.get("error") and "429" in str(rec.get("error"))[:12]): break
            time.sleep(6)
        out = {k: v for k, v in it.items() if k != "user_message"}
        out.update(response_text=rec.get("response_text"), error=rec.get("error"), timestamp=datetime.now(timezone.utc).isoformat())
        with lock:
            with path.open("a") as f: f.write(json.dumps(out, ensure_ascii=False) + "\n")
    with ThreadPoolExecutor({"deepseek": 4}.get(m, 12)) as ex: list(ex.map(run, todo))
    print(m, "fatte prima", len(done), "tentate ora", len(todo))
if __name__ == "__main__":
    esegui(sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else 100)
