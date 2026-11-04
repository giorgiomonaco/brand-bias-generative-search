"""Misure secondarie (protocollo sez. 8), con i 4 motori dello studio, 3 ripetizioni: notorietà di categoria secondo i
modelli (0–10, più noto e bersaglio), riconoscimento del marchio vero dal testo neutralizzato, coerenza percepita (0–3)
del testo con ciascuna firma. Uso: python misure_secondarie_v3.py MOTORE [secondi]"""
import json, re, sys, time, threading
from pathlib import Path
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "part2_conf"))
from comune_v3 import D, NOME
from familiarita_v3 import PRODOTTO
from studio_v3 import pagina_bersaglio, FIRME
from taratura_v3 import sel
STIM = D / "stimoli"
PN = ("Domanda di un utente: «{q}»\nMarchio: «{b}»\n\nQuanto è conosciuto in Italia questo marchio PER il tipo di prodotto o "
      "servizio che la domanda chiede (non per altri prodotti che vende)? Rispondi solo con una riga:\n"
      "PUNTEGGIO: un numero da 0 (sconosciuto per questo prodotto) a 10 (è il riferimento più noto di questa categoria)")
PR = ("Questo è il testo di una pagina prodotto da cui sono stati tolti i nomi del marchio e del prodotto.\n---\n{t}\n---\n"
      "Di quale marchio reale pensi che sia? Rispondi con una sola riga: MARCHIO: nome del marchio, oppure MARCHIO: NON SO")
PC = ("Questo è il testo di una pagina prodotto firmata dal marchio {b}.\n---\n{t}\n---\nQuanto è plausibile che questa pagina "
      "sia davvero di {b}? Rispondi solo con una riga:\nPUNTEGGIO: un numero da 0 (per niente plausibile) a 3 (del tutto plausibile)")
def items(m):
    out = []
    for f in sorted(STIM.glob("*.json")):
        s = json.load(open(f)); pid = s["pid"]; q = sel[pid]["domanda"]
        for r in range(3):
            for k in (s["bersaglio"], s["piu_noto"]):
                out.append(dict(call_id=f"N|{pid}|{k}|{m}|{r}", tipo="notorieta_modelli", pid=pid, marchio=NOME[k], motore=m, rip=r, user_message=PN.format(q=q, b=NOME[k])))
            t, _ = pagina_bersaglio(s, "INVENTATO", "ORIGINALE")
            out.append(dict(call_id=f"R|{pid}|{m}|{r}", tipo="riconoscimento", pid=pid, marchio=s["brand"], motore=m, rip=r, user_message=PR.format(t=t)))
            for fi in FIRME:
                if fi == "BRAND": continue
                t, _ = pagina_bersaglio(s, fi, "ORIGINALE")
                b = {"REALE": s["brand"], "PIU_NOTO": NOME[s["piu_noto"]], "MENO_NOTO": NOME[s["meno_noto"]], "INVENTATO": s["inventato"]}[fi]
                out.append(dict(call_id=f"C|{pid}|{fi}|{m}|{r}", tipo="coerenza", pid=pid, firma=fi, marchio=b, motore=m, rip=r, user_message=PC.format(b=b, t=t)))
    for it in out: it.update(system_prompt=None, search=False)
    return out
def esegui(m, budget):
    from motori import motore
    OUT = D / f"secondarie_{m}.jsonl"; done = set()
    if OUT.exists():
        for l in OUT.open():
            r = json.loads(l)
            if r.get("response_text") and not r.get("error"): done.add(r["call_id"])
    todo = [i for i in items(m) if i["call_id"] not in done]; print(m, "da fare:", len(todo), flush=True)
    t0 = time.monotonic(); lock = threading.Lock(); eng = motore(m)
    def run(it):
        if time.monotonic() - t0 > budget: return
        for _ in range(6):
            rec = eng.once(it)
            if not (rec.get("error") and "429" in str(rec.get("error"))[:40]): break
            time.sleep(8)
        o = {k: v for k, v in it.items() if k != "user_message"}
        o.update(response_text=rec.get("response_text"), error=rec.get("error"), model_version=rec.get("model_version"), timestamp=datetime.now(timezone.utc).isoformat())
        with lock:
            with OUT.open("a") as f: f.write(json.dumps(o, ensure_ascii=False) + "\n")
    with ThreadPoolExecutor(16 if m != "deepseek" else 8) as ex: list(ex.map(run, todo))
if __name__ == "__main__":
    esegui(sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else 1e9)
