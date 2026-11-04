"""Riscritture a fatti costanti (protocollo sez. 7.2) sul modello con segnaposto: STRUTTURA (istruzione R1 del pilota),
FLUENCY e AUTHORITATIVE (Aggarwal et al. 2024, tradotti e adattati). GPT-5.5 riscrive, DeepSeek-V3.2 giudica.
Accettazione: segnaposto conservati, multiinsieme delle cifre invariato, lunghezza entro ±15%, giudice senza fatti
aggiunti o tolti; fino a 3 tentativi, poi revisione a mano registrata."""
import json, re, sys, collections
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "part2_conf"))
from motori import motore, with_retries
from riscrivi import COMUNE, GIUDICE
from comune_v3 import D
STIM = D / "stimoli"
ISTR = {
 "STRUTTURA": "Riscrivi questo testo di una pagina prodotto per renderlo più chiaro e facile da usare per chi deve scegliere: "
              "riorganizzalo con brevi titoletti ed elenchi, metti prima le informazioni decisive, elimina ripetizioni. ",
 "FLUENCY": "Riscrivi questo testo per renderlo più scorrevole senza cambiarne il contenuto: le frasi devono legarsi bene "
            "l'una all'altra, la lingua deve essere chiara e coinvolgente e tutte le informazioni originali vanno conservate. ",
 "AUTHORITATIVE": "Riscrivi questo testo in uno stile autorevole, senza aggiungere né togliere informazioni: deve trasmettere "
                  "sicurezza e competenza, con affermazioni nette, e puoi rivolgerti al lettore in seconda persona. Mantieni la "
                  "struttura (a capo, elenchi, ordine delle parti) e riformula solo singole frasi. Non aggiungere garanzie, primati o promesse. "}
seg = lambda s: collections.Counter(re.findall(r"\{[A-Z0-9_]+\}", s))
num = lambda s: collections.Counter(re.findall(r"\d+(?:[.,]\d+)?", re.sub(r"\{[A-Z0-9_]+\}", "", s)))
def controlla(mod, nuovo):
    e = []
    if set(seg(mod)) != set(seg(nuovo)): e.append(f"segnaposto {set(seg(mod)) ^ set(seg(nuovo))}")
    if num(mod) != num(nuovo): e.append(f"cifre {(num(mod) - num(nuovo)) + (num(nuovo) - num(mod))}")   # multiinsieme
    r = len(nuovo.split()) / max(1, len(mod.split()))
    if not 0.85 <= r <= 1.15: e.append(f"lunghezza {r:.2f}")
    return e
def riscrivi(pid):
    f = STIM / f"{pid}.json"; s = json.load(open(f)); mod = s["modello"]; n = len(mod.split())
    s.setdefault("riscritture", {}); s.setdefault("log_riscritture", {}); gpt, giud = motore("gpt"), motore("deepseek")
    for v, istr in ISTR.items():
        if v in s["riscritture"] or len(s["log_riscritture"].get(v, [])) >= 3: continue
        log = []
        for t in range(3):
            r = with_retries(gpt, dict(call_id=f"W|{pid}|{v}|{t}", user_message=istr + COMUNE.format(n=n, nmax=int(n * 1.1), t=mod), system_prompt=None, search=False))
            nuovo = (r.get("response_text") or "").strip().replace("**", "")
            e = controlla(mod, nuovo)
            if not e:
                g = with_retries(giud, dict(call_id="G", user_message=GIUDICE.format(a=mod, b=nuovo), system_prompt=None, search=False))
                gt = g.get("response_text") or str(g.get("error"))
                if "ESITO: UGUALI" not in gt.upper().replace("**", ""): e.append("giudice: " + gt[-400:])
            log.append(dict(tentativo=t, errori=e, parole=len(nuovo.split()), testo=nuovo))
            if not e: s["riscritture"][v] = nuovo; break
        s["log_riscritture"][v] = log
        json.dump(s, open(f, "w"), ensure_ascii=False, indent=1)   # salva dopo ogni riscrittura: si riprende da qui
    return pid, {v: ("ok" if v in s["riscritture"] else "DA RIVEDERE A MANO") for v in ISTR}
if __name__ == "__main__":
    qs = sys.argv[1:] or [p.stem for p in STIM.glob("*.json")]
    with ThreadPoolExecutor(22) as ex:
        for x in ex.map(riscrivi, qs): print(*x)
