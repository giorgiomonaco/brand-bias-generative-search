"""Riscritture GEO a fatti costanti (protocollo sez. 5.2), generate sul modello con segnaposto.
Accettazione: segnaposto conservati (stesso insieme, ciascuno almeno una volta), stesso multiinsieme di numeri,
lunghezza entro ±15%, giudice (DeepSeek) senza fatti aggiunti o tolti. Fino a 3 tentativi."""
import json, re, sys, collections
from comune import D
from motori import motore, with_retries
OUTD = D / "stimoli"
COMUNE = ("Il testo contiene segnaposto tra graffe come {{BRAND}} o {{TECH_1}}: copiali identici, senza toglierne nessuno "
 "e senza aggiungerne. Usa SOLO le informazioni presenti nel testo: non aggiungere fatti, numeri, statistiche, "
 "citazioni, fonti, giudizi di terzi o promesse nuove, e non togliere nessuna informazione. Mantieni tutte le cifre "
 "esattamente come sono. Scrivi in italiano. Lunghezza simile all'originale: circa {n} parole, mai più di {nmax}. Restituisci solo il "
 "testo riscritto, in testo semplice (puoi usare a capo, trattini per gli elenchi e brevi titoletti seguiti da due "
 "punti; niente markdown come # o **).\n\n=== TESTO ===\n{t}")
ISTR = {"R1": "Riscrivi questo testo di una pagina prodotto per renderlo più chiaro e facile da usare per chi deve scegliere: "
              "riorganizzalo con brevi titoletti ed elenchi, metti prima le informazioni decisive, elimina ripetizioni. ",
        "R2": "Riscrivi questo testo di una pagina prodotto in uno stile diretto e autorevole: apri con un riepilogo di due "
              "frasi dei punti di forza che il testo già contiene, poi esponi le stesse informazioni con frasi dichiarative "
              "e precise, senza enfasi pubblicitaria. "}
GIUDICE = ("Confronta due versioni di un testo (i segnaposto tra graffe sono nomi). Conta come differenza SOLO un'informazione "
 "fattuale presente in una versione e del tutto assente nell'altra, oppure un valore cambiato (un numero, una "
 "caratteristica, una condizione, un prezzo, una copertura). NON sono differenze: titoli o intestazioni aggiunti o tolti, "
 "elenchi al posto di paragrafi, ordine diverso, sinonimi, riformulazioni con lo stesso significato, un riepilogo che "
 "ripete informazioni presenti altrove, punteggiatura, refusi corretti, frasi esortative o di puro tono. Elenca solo le "
 "differenze vere, una per riga, poi un'ultima riga 'ESITO: UGUALI' se non ce ne sono, altrimenti 'ESITO: DIVERSI'.\n\n=== A ===\n{a}\n\n=== B ===\n{b}")
seg = lambda s: collections.Counter(re.findall(r"\{[A-Z0-9_]+\}", s))
num = lambda s: collections.Counter(re.findall(r"\d+(?:[.,]\d+)?", re.sub(r"\{[A-Z0-9_]+\}", "", s)))
def controlla(mod, nuovo):
    e = []
    if set(seg(mod)) != set(seg(nuovo)): e.append(f"segnaposto {set(seg(mod)) ^ set(seg(nuovo))}")
    if set(num(mod)) != set(num(nuovo)): e.append(f"numeri {set(num(mod)) ^ set(num(nuovo))}")
    r = len(nuovo.split()) / max(1, len(mod.split()))
    if not 0.85 <= r <= 1.15: e.append(f"lunghezza {r:.2f}")
    return e
def riscrivi(q, gpt, giud):
    s = json.load(open(OUTD / f"{q}_neutro.json"))
    mod = s["modello"]; n = len(mod.split()); s.setdefault("riscritture", {}); s.setdefault("log_riscritture", {})
    for v in ("R1", "R2"):
        if v in s["riscritture"]: continue
        s["riscritture"].pop(v + "_scartata", None); s["log_riscritture"].setdefault("v1_" + v, s["log_riscritture"].get(v))
        log = []
        for t in range(3):
            r = with_retries(gpt, dict(call_id=f"W|{q}|{v}|{t}", user_message=ISTR[v] + COMUNE.format(n=n, nmax=int(n*1.1), t=mod), system_prompt=None, search=False))
            nuovo = (r.get("response_text") or "").strip().replace("**", "")
            e = controlla(mod, nuovo)
            if not e:
                g = giud.once(dict(call_id="G", user_message=GIUDICE.format(a=mod, b=nuovo), system_prompt=None, search=False))
                gt = g.get("response_text") or str(g.get("error"))
                if "ESITO: UGUALI" not in gt.upper().replace("**", ""): e.append("giudice: " + gt[-400:])
            log.append(dict(tentativo=t, errori=e, parole=len(nuovo.split())))
            if not e:
                s["riscritture"][v] = nuovo; break
        s["log_riscritture"][v] = log
        if v not in s["riscritture"]:
            s["riscritture"][v + "_scartata"] = nuovo
    json.dump(s, open(OUTD / f"{q}_neutro.json", "w"), ensure_ascii=False, indent=1)
    return q, {v: [x["errori"] for x in s["log_riscritture"].get(v, [])] for v in ("R1", "R2")}, list(s["riscritture"])
if __name__ == "__main__":
    from concurrent.futures import ThreadPoolExecutor
    gpt, giud = motore("gpt"), motore(sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] in ("gpt","deepseek") else "deepseek")
    qs = [a for a in sys.argv[1:] if "_" in a] or [p.name.split("_neutro")[0] for p in OUTD.glob("*_neutro.json")]
    with ThreadPoolExecutor(12) as ex:
        for x in ex.map(lambda q: riscrivi(q, gpt, giud), qs): print(*x)
