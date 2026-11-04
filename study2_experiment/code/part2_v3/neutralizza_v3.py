"""Neutralizzazione del bersaglio (protocollo sez. 7.1): modello con segnaposto, stessa istruzione del pilota
(analysis/part2_conf/neutralizza.py). Controlli: (1) il modello riempito con i valori veri ridà esattamente l'originale;
(2) nessun nome reale (marchio, prodotto, tecnologie, dominio, e i nomi di più noto e meno noto) resta nel modello;
(3) lettura umana: file revisione/<domanda>.md da leggere a mano prima delle riscritture.
Uso: python neutralizza_v3.py [domanda ...]"""
import json, re, sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "part2_conf"))
from motori import motore, with_retries
from neutralizza import P1, P2, js, riempi, norm
from comune_v3 import D, NOME, DOM
from comune_v3 import kurl
STIM = D / "stimoli"; STIM.mkdir(exist_ok=True); REV = D / "revisione"; REV.mkdir(exist_ok=True)
sel = json.load(open(D / "selezione_v3.json")); sc = json.load(open(D / "scelte.json")); INV = json.load(open(D / "inventati.json"))
def nomi_reali(pid, t):
    """Stringhe che non possono restare nel modello: marchio del bersaglio (anche senza spazi), dominio, più noto e meno noto."""
    b = NOME[t]; dom = DOM.get(t, "")
    out = {b, b.replace(" ", ""), dom.split(".")[0]} if dom else {b, b.replace(" ", "")}
    return {x for x in out if len(x) >= 3}
def controllo_nomi(mod, mappa, pid, t):
    """Nomi rimasti. Non contano le parole comuni che il modello ha messo in un segnaposto (es. «Animali» dentro il nome
    di una polizza) e che compaiono anche minuscole nel testo: le vede comunque la lettura umana."""
    rimasti = []
    comuni = {v for v in mappa.values() if " " not in v.strip() and re.search(r"(?<![A-Za-z])" + re.escape(v.lower()) + r"(?![A-Za-z])", mod)}
    for x in nomi_reali(pid, t) | {v for k, v in mappa.items() if not k.startswith("CODICE") and len(v) >= 3 and v not in comuni}:
        if re.search(r"(?<![A-Za-z])" + re.escape(x) + r"(?![A-Za-z])", mod, re.I): rimasti.append(x)
    return rimasti
def neutralizza(pid):
    t = sc[pid]["bersaglio"]; b = NOME[t]; eng = motore("gpt")
    x = json.load(open(D / "testi" / f"{kurl(pid + '|' + b)}.json")); orig = x["testo"]
    for tent in range(3):
        r = with_retries(eng, dict(call_id=f"N|{pid}", user_message=P1.format(brand=b, prod=sel[pid]["domanda"], testo=orig), system_prompt=None, search=False))
        try:
            j = js(r["response_text"]); mod, mappa = j["modello"], {k.strip("{}"): v for k, v in j["mappa"].items()}
        except Exception: continue
        if norm(riempi(mod, mappa)) == norm(orig) and not controllo_nomi(mod, mappa, pid, t): break
    else:
        return pid, "FALLITA: ricostruzione o nomi rimasti"
    voci = "\n".join(f"{k}: {v}" for k, v in mappa.items() if not k.startswith("BRAND"))
    inv = {}
    if voci:
        r2 = with_retries(eng, dict(call_id=f"N2|{pid}", user_message=P2.format(sett=sel[pid]["settore"], voci=voci), system_prompt=None, search=False))
        inv = {k.strip("{}"): v for k, v in js(r2["response_text"]).items()}
    s = dict(pid=pid, bersaglio=t, brand=b, url=x["url"], testo_sha256=x["sha256"], modello=mod, mappa_reale=mappa, mappa_inventata=inv,
             piu_noto=sc[pid]["piu_noto"], meno_noto=sc[pid]["meno_noto"], inventato=INV[pid]["nome"])
    json.dump(s, open(STIM / f"{pid}.json", "w"), ensure_ascii=False, indent=1)
    esempio = riempi(mod, {**{k: v for k, v in mappa.items()}, **inv, **{k: INV[pid]["nome"] for k in mappa if k.startswith("BRAND")}})
    (REV / f"{pid}.md").write_text(
        f"# {pid}: {sel[pid]['domanda']}\n\nBersaglio: **{b}** ({x['url']})\n\n## Segnaposto\n\n| segnaposto | valore vero | valore inventato |\n|---|---|---|\n"
        + "\n".join(f"| {k} | {v} | {inv.get(k, INV[pid]['nome'] if k.startswith('BRAND') else '')} |" for k, v in mappa.items())
        + f"\n\n## Da controllare\nNel testo qui sotto, firmato col nome inventato, non deve restare nessun indizio del marchio vero "
          f"(nomi, tecnologie, linee, codici, indirizzi, persone).\n\n---\n\n{esempio}\n")
    return pid, "ok"
if __name__ == "__main__":
    qs = sys.argv[1:] or [p for p, v in sc.items() if v["esito"] == "ok" and not (STIM / f"{p}.json").exists()]
    with ThreadPoolExecutor(22) as ex:
        for x in ex.map(neutralizza, qs): print(*x)
