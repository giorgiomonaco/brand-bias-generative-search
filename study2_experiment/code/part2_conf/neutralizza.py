"""Neutralizzazione del bersaglio (protocollo sez. 5.1): modello con segnaposto + nomi inventati.
Controlli: (1) il modello riempito con i valori veri ricostruisce esattamente l'originale; (2) riempito con i valori
inventati non contiene più nomi veri (marchio, prodotto, tecnologie, codici); (3) lettura umana del risultato."""
import json, re, sys
from pathlib import Path
from comune import DOM, D, testo_orig
from motori import motore, with_retries
OUTD = D / "stimoli"; OUTD.mkdir(exist_ok=True)
P1 = ("Ti do il testo di una pagina prodotto di {brand} («{prod}»). Devo usarlo in un esperimento in cui il marchio e il "
 "prodotto vanno resi irriconoscibili senza cambiare nient'altro.\n"
 "Restituisci SOLO un JSON con due chiavi:\n"
 "\"modello\": il testo identico, carattere per carattere, in cui sostituisci con segnaposto tra graffe ogni indizio "
 "d'identità: {{BRAND}} per ogni forma del nome del marchio o del gruppo/società che lo possiede (anche in maiuscolo, "
 "abbreviato, con ® o ™ attaccati, dentro altre parole); {{PRODOTTO}} per il nome del prodotto o del modello o della linea; "
 "{{TECH_1}}, {{TECH_2}}, ... per i nomi propri di tecnologie, materiali, programmi, garanzie o servizi esclusivi del "
 "marchio (non per componenti di altri marchi come GORE-TEX, Vibram, Bosch, che restano); {{CODICE_1}}, ... per codici "
 "articolo, numeri di iscrizione, partite IVA, numeri di telefono, indirizzi web o email; {{PERSONA_1}}, ... per nomi di "
 "testimonial o persone. Lo stesso valore va sempre nello stesso segnaposto. Non toccare nient'altro: spazi, a capo, "
 "punteggiatura e parole restano identici.\n"
 "\"mappa\": un oggetto che associa ogni segnaposto (senza graffe) al testo esatto che sostituisce; se un segnaposto "
 "sostituisce forme diverse (es. maiuscolo e minuscolo), usa segnaposto diversi (BRAND, BRAND_2, ...).\n\n"
 "=== TESTO ===\n{testo}")
P2 = ("Per un esperimento devo sostituire nomi propri di un prodotto con nomi INVENTATI. Settore: {sett}. Per ogni voce "
 "qui sotto proponi un nome inventato plausibile, dello stesso tipo e lunghezza simile, che non sia un marchio o prodotto "
 "esistente e non somigli a nessun marchio noto; per i codici inventa un codice dello stesso formato. Non inventare "
 "nulla per BRAND. Restituisci SOLO un JSON {{segnaposto: valore inventato}}.\n{voci}")
def js(t):
    t = re.sub(r"^```(?:json)?|```$", "", (t or "").strip(), flags=re.M).strip()
    return json.loads(t[t.find("{"): t.rfind("}") + 1])
def riempi(mod, mappa):
    return re.sub(r"\{([A-Z0-9_]+)\}", lambda m: mappa.get(m.group(1), m.group(0)), mod)
norm = lambda s: re.sub(r"\s+", " ", s).strip()
def neutralizza(qid, bi, eng):
    brand, prod, url = DOM[qid]["pagine"][bi]
    orig = testo_orig(qid, bi)
    for tent in range(3):
        r = with_retries(eng, dict(call_id=f"N|{qid}", user_message=P1.format(brand=brand, prod=prod, testo=orig), system_prompt=None, search=False))
        try:
            j = js(r["response_text"]); mod, mappa = j["modello"], {k.strip("{}"): v for k, v in j["mappa"].items()}
        except Exception as e:
            print("json", e); continue
        if norm(riempi(mod, mappa)) == norm(orig):
            break
        print(qid, "ricostruzione diversa, tentativo", tent)
    else:
        raise SystemExit(f"{qid}: ricostruzione fallita")
    voci = "\n".join(f"{k}: {v}" for k, v in mappa.items() if not k.startswith("BRAND"))
    inv = {}
    if voci:
        r2 = with_retries(eng, dict(call_id=f"N2|{qid}", user_message=P2.format(sett=qid.split("_")[0], voci=voci), system_prompt=None, search=False))
        inv = {k.strip("{}"): v for k, v in js(r2["response_text"]).items()}
    return dict(qid=qid, bersaglio=bi, brand=brand, prodotto=prod, url=url, modello=mod, mappa_reale=mappa, mappa_inventata=inv)
if __name__ == "__main__":
    sc = json.load(open(D / "taratura_scelta.json"))
    eng = motore("gpt")
    qs = sys.argv[1:] or list(DOM)
    from concurrent.futures import ThreadPoolExecutor
    def f(q):
        try:
            res = neutralizza(q, sc[q]["bersaglio"], eng)
            json.dump(res, open(OUTD / f"{q}_neutro.json", "w"), ensure_ascii=False, indent=1)
            return q, "ok", len(res["mappa_reale"])
        except SystemExit as e:
            return q, str(e), 0
    with ThreadPoolExecutor(12) as ex:
        for x in ex.map(f, qs): print(*x)
