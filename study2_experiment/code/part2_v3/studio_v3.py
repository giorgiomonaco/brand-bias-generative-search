"""Studio completo (protocollo sez. 9): per ogni domanda 5 firme × 4 testi × 10 ordini di Williams × 2 ripetizioni, per
motore. Ricerca spenta, nessun system prompt, nessuna persona, cornice del messaggio identica al pilota.
Uso: python studio_v3.py MOTORE [secondi]     |   python studio_v3.py --prova  (stampa un messaggio, nessuna chiamata)"""
import json, re, sys
from pathlib import Path
from urllib.parse import urlsplit
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "part2_conf"))
from comune import williams, messaggio, esegui
from comune_v3 import D, NOME, DOM
from taratura_v3 import pagine, sel
STIM = D / "stimoli"
FIRME = ("REALE", "BRAND", "PIU_NOTO", "MENO_NOTO", "INVENTATO")
TESTI = ("ORIGINALE", "STRUTTURA", "FLUENCY", "AUTHORITATIVE")
def slug(s): return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
def adatta(nuovo, vero):
    if vero.isupper() and len(vero) > 1: return nuovo.upper()
    if vero.islower(): return nuovo.lower()
    return nuovo
def riempi(t, m): return re.sub(r"\{([A-Z0-9_]+)\}", lambda x: m.get(x.group(1), x.group(0)), t)
ARTICOLI = [("il", "l'"), ("Il", "L'"), ("del", "dell'"), ("Del", "Dell'"), ("al", "all'"), ("Al", "All'"), ("nel", "nell'"),
            ("Nel", "Nell'"), ("sul", "sull'"), ("dal", "dall'"), ("lo", "l'"), ("i", "gli "), ("I", "Gli ")]
FEMMINILI = ("Baia", "Villa", "Torre", "Masseria", "Tenuta", "Casa", "Corte", "Marina", "Riva")
ARTICOLI_F = [("il", "la"), ("Il", "La"), ("del", "della"), ("Del", "Della"), ("al", "alla"), ("Al", "Alla"), ("nel", "nella"),
              ("Nel", "Nella"), ("sul", "sulla"), ("dal", "dalla")]
def elidi(t, nome):
    """Correzione 28/10 (riraccolta v2): articolo davanti al nome della firma. Elisione davanti a vocale («il Engwe» ->
    «l'Engwe», anche con un a capo in mezzo) e femminile per i nomi che iniziano con un nome femminile («Al Baia» -> «Alla Baia»)."""
    if not nome: return t
    for f in {nome, nome.upper(), nome.lower()}:
        if nome[0].lower() in "aeiou":
            for art, el in ARTICOLI:
                t = re.sub(r"(?<![\w'’])" + art + r"\s+" + re.escape(f) + r"(?!\w)", el + f, t)
        elif nome.split()[0] in FEMMINILI:
            for art, fem in ARTICOLI_F:
                t = re.sub(r"(?<![\w'’])" + art + r"(\s+)" + re.escape(f) + r"(?!\w)", lambda m: fem + m.group(1) + f, t)
    return t
def pagina_bersaglio(s, firma, testo):
    base = s["modello"] if testo == "ORIGINALE" else s["riscritture"][testo]
    if firma == "REALE":
        return riempi(base, s["mappa_reale"]), s["url"]
    marchio = {"BRAND": NOME[s["bersaglio"]], "PIU_NOTO": NOME[s["piu_noto"]], "MENO_NOTO": NOME[s["meno_noto"]], "INVENTATO": s["inventato"]}[firma]
    m = {k: s["mappa_inventata"].get(k, v) for k, v in s["mappa_reale"].items()}
    for k, v in s["mappa_reale"].items():
        if k.startswith("BRAND"): m[k] = v if firma == "BRAND" else adatta(marchio, v)
    prod = m.get("PRODOTTO") or "prodotto"
    host = {"BRAND": urlsplit(s["url"]).hostname, "PIU_NOTO": "www." + DOM[s["piu_noto"]], "MENO_NOTO": "www." + DOM[s["meno_noto"]],
            "INVENTATO": f"www.{slug(s['inventato'])}.it"}[firma]
    # Correzione 24/10: un recapito interno non deve esporre un quarto marchio inventato.
    for k, v in s["mappa_reale"].items():
        if not k.startswith("CODICE"):
            continue
        if re.fullmatch(r"[^\s@]+@[^\s@]+\.[A-Za-z]{2,}", v):
            m[k] = m[k].split("@", 1)[0] + "@" + host.removeprefix("www.")
        elif re.match(r"^(?:https?://|www\.)", v) or re.fullmatch(r"[A-Za-z0-9.-]+\.[A-Za-z]{2,}", v):
            # Il percorso resta inventato; il dominio è quello della firma.
            parsed = urlsplit(m[k] if "://" in m[k] else "https://" + m[k])
            m[k] = "https://" + host + parsed.path
    testo_pagina = riempi(base, m)
    if firma != "BRAND": testo_pagina = elidi(testo_pagina, marchio)
    return testo_pagina, f"https://{host}/it/{slug(prod)}"
def piano(motori):
    sc = json.load(open(D / "scelte.json")); items = []
    for pid, v in sel.items():
        if sc[pid]["esito"] != "ok": continue
        s = json.load(open(STIM / f"{pid}.json")); altre = pagine(pid)
        b = [p["chiave"] for p in v["pagine"]].index(s["bersaglio"])
        for firma in FIRME:
            for testo in TESTI:
                pag = list(altre); pag[b] = pagina_bersaglio(s, firma, testo)
                for m in motori:
                    for j, o in enumerate(williams()):
                        for r in range(2):
                            items.append(dict(call_id=f"S|{pid}|{firma}|{testo}|{m}|{j}|{r}", fase="studio", qid=pid, firma=firma, testo=testo,
                                              motore=m, j=j, rip=r, ordine=o, bersaglio=b,
                                              user_message=messaggio(v["domanda"], pag, o), system_prompt=None, search=False))
    return items
if __name__ == "__main__":
    if sys.argv[1] == "--prova":
        it = piano(("gpt",)); print(len(it), "chiamate per motore"); print(it[len(it) // 3]["user_message"][:4000]); sys.exit()
    m = sys.argv[1]; bud = float(sys.argv[2]) if len(sys.argv) > 2 else 1e9
    esegui(piano((m,)), D / f"studio_{m}.jsonl", budget_s=bud, workers={"gpt": 28, "deepseek": 8, "perplexity": 10, "gemini_vertex": 12})
