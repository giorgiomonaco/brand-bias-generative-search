"""Pagine, regola 1: fra gli URL citati sul dominio del marchio (dal più citato), il primo che è la pagina di un solo
prodotto pertinente alla domanda (controllo GPT fisso, stessa istruzione del test di fattibilità v2). Riprende da dove
si era fermato: gli esiti sono salvati in data/part2_v3/regola1.json."""
import sys, json, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "part2_conf"))
from motori import motore
from scarica import scarica, OUT, kurl
from comune_v3 import D
cand = json.load(open(D / "pagine_candidate.json")); sel = json.load(open(D / "selezione_v3.json"))
F = D / "regola1.json"; R = json.load(open(F)) if F.exists() else {}
P = ("Domanda di un utente: «{q}». Ecco l'inizio del testo di una pagina web del marchio {b}.\n---\n{t}\n---\n"
     "La pagina presenta UN SINGOLO prodotto o servizio di {b} (una scheda prodotto, una polizza, un tour, una struttura) "
     "pertinente alla domanda? Rispondi NO se è una home page di un'azienda con più prodotti, un elenco o una categoria di "
     "prodotti, un articolo di blog, una pagina di ricerca o un PDF. Rispondi solo SI o NO.")
def estratto(u):
    """Cosa vede il controllo: titolo, indirizzo e i primi 12.000 caratteri del testo. Con solo 3.500 caratteri
    (prima versione del 23/10) i menu dei siti grandi coprivano la scheda e il controllo diceva NO a schede vere."""
    m = json.loads((OUT / f"{kurl(u)}.json").read_text()); txt = (OUT / f"{kurl(u)}.txt").read_text()
    return f"Titolo: {m.get('titolo','')}\nIndirizzo: {u}\n\n{txt[:12000]}"
eng = motore("gpt"); T0 = time.time(); LIM = 150
def marchio(j):
    pid, b = j; key = f"{pid}|{b}"; st = R.get(key, dict(prove=[], scelta=None, finito=False))
    fatti = {p["url"] for p in st["prove"]}
    for u, n in cand[pid][b]["citazioni"]:
        if st["finito"] or time.time() - T0 > LIM: break
        if u in fatti: continue
        m = scarica(u)
        if not m["ok"]: st["prove"].append(dict(url=u, citazioni=n, esito="non_leggibile", metodo=m["metodo"], parole=m["parole"])); continue
        r = eng.once(dict(call_id="p", user_message=P.format(q=sel[pid]["domanda"], b=b, t=estratto(u)), system_prompt=None, search=False))
        v = (r.get("response_text") or "").strip().upper()[:2]
        st["prove"].append(dict(url=u, citazioni=n, esito=v, metodo=m["metodo"], parole=m["parole"]))
        if v == "SI": st["scelta"] = u; st["finito"] = True
    if not st["finito"] and len(st["prove"]) == len(cand[pid][b]["citazioni"]): st["finito"] = True
    return key, st
if __name__ == "__main__":
    LIM = float(sys.argv[1]) if len(sys.argv) > 1 else 150
    jobs = [(pid, b) for pid, bs in cand.items() for b in bs if not R.get(f"{pid}|{b}", {}).get("finito")]
    with ThreadPoolExecutor(16) as ex:
        for k, st in ex.map(marchio, jobs):
            R[k] = st; json.dump(R, open(F, "w"), ensure_ascii=False, indent=1)
    fin = sum(v["finito"] for v in R.values()); sc = sum(bool(v["scelta"]) for v in R.values())
    print(f"marchi chiusi {fin}/120, con pagina dalla regola 1: {sc}; da riprendere: {120 - fin}")
