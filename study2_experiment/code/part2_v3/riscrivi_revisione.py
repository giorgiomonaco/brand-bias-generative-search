"""Revisione registrata delle riscritture che dopo 3 tentativi non passano i controlli (protocollo sez. 7.2). Si parte dal
tentativo con meno errori e si chiede a GPT di reinserire, con le stesse parole dell'originale, solo le frasi con le cifre
mancanti (o di togliere quelle in più); poi stessi controlli e stesso giudice. Ogni passaggio resta in log_revisione."""
import json, sys
from concurrent.futures import ThreadPoolExecutor
from riscrivi_v3 import STIM, controlla, num, motore, with_retries, GIUDICE
PR = ("Ecco un testo ORIGINALE e una sua RISCRITTURA. Nella riscrittura le cifre non coincidono con l'originale: {diff}.\n"
      "Correggi la RISCRITTURA cambiando il meno possibile: reinserisci le frasi dell'originale che contengono le cifre "
      "mancanti, con le stesse parole e nella posizione che ha più senso, e togli le cifre che nell'originale non ci sono. "
      "Ogni cifra deve comparire esattamente tante volte quante nell'originale. Non toccare i segnaposto tra graffe e non "
      "cambiare nient'altro. Restituisci solo la riscrittura corretta.\n\n=== ORIGINALE ===\n{o}\n\n=== RISCRITTURA ===\n{r}")
def rivedi(pid, v):
    f = STIM / f"{pid}.json"; s = json.load(open(f)); mod = s["modello"]
    att = min(s["log_riscritture"][v], key=lambda x: len(str(x["errori"])))["testo"]; log = []
    for t in range(3):
        diff = f"mancano {dict(num(mod) - num(att))}, in più {dict(num(att) - num(mod))}"
        r = with_retries(motore("gpt"), dict(call_id=f"RV|{pid}|{v}|{t}", user_message=PR.format(diff=diff, o=mod, r=att), system_prompt=None, search=False))
        att = (r.get("response_text") or "").strip().replace("**", ""); e = controlla(mod, att)
        if not e:
            g = with_retries(motore("deepseek"), dict(call_id="G", user_message=GIUDICE.format(a=mod, b=att), system_prompt=None, search=False))
            gt = g.get("response_text") or ""
            if "ESITO: UGUALI" not in gt.upper().replace("**", ""): e.append("giudice: " + gt[-300:])
        log.append(dict(passo=t, errori=e, testo=att))
        if not e: break
    s.setdefault("log_revisione", {})[v] = log
    if not log[-1]["errori"]: s["riscritture"][v] = att; s.setdefault("riscritture_riviste", []).append(v)
    json.dump(s, open(f, "w"), ensure_ascii=False, indent=1)
    return pid, v, "ok" if not log[-1]["errori"] else log[-1]["errori"]
if __name__ == "__main__":
    jobs = []
    for f in STIM.glob("*.json"):
        s = json.load(open(f))
        for v in ("STRUTTURA", "FLUENCY", "AUTHORITATIVE"):
            if v not in s.get("riscritture", {}): jobs.append((s["pid"], v))
    with ThreadPoolExecutor(8) as ex:
        for x in ex.map(lambda j: rivedi(*j), jobs): print(*x)
