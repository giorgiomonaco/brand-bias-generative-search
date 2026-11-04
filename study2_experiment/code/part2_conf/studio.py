"""Studio confermativo (protocollo sez. 7): 4 identità x 3 testi x ordini x ripetizioni x 12 domande."""
import json, re, sys
from urllib.parse import urlsplit
from comune import DOM, D, williams, testo_orig, messaggio, esegui
OUT = D / "studio.jsonl"
STIM = D / "stimoli"
IDENT = ("REALE", "BRAND", "MINORE", "INVENTATO")
TESTI = ("ORIG", "R1", "R2")
PIANO = {"gpt": (range(10), range(2)), "perplexity": (range(10), range(2)), "gemini_vertex": (range(10), range(2)),
         "deepseek": (range(5), range(1))}   # DeepSeek: quadrato latino dei primi 5 ordini, 1 ripetizione (emendamento 1)
DOMINI_MINORI = {"Kayland": "kayland.com", "Garsport": "garsport.it", "Dachstein": "dachstein.at", "Everfit": "everfit.it",
 "JK Fitness": "jkfitness.it", "Get Fit": "getfit.it", "Vibor-A": "vibora.es", "Royal Padel": "royalpadel.com",
 "Bioclin": "bioclin.it", "Lycia": "lycia.it", "Euphidra": "euphidra.com", "Wycon": "wycon.it", "Neve Cosmetics": "nevecosmetics.it",
 "Deborah Milano": "deborahmilano.com", "Nobis": "nobis.it", "Chapka": "chapkadirect.it", "ERGO": "ergoassicurazioneviaggi.it",
 "ITAS Mutua": "gruppoitas.it", "Assimoco": "assimoco.it", "Net Insurance": "netinsurance.it", "Barkibu": "barkibu.com",
 "Kel 12": "kel12.com", "Viaggi dell'Elefante": "viaggidellelefante.it", "Mistral Tour": "mistral.it",
 "Turisanda": "turisanda.it", "Settemari": "settemari.it", "Futura Vacanze": "futuravacanze.it"}
SUP = {}
DOMINI_SUPERIORI = {"Salomon": "salomon.com", "Decathlon": "decathlon.it", "Adidas": "adidas.it", "La Roche-Posay": "laroche-posay.it",
 "KIKO Milano": "kikocosmetics.com", "Unipol": "unipol.it", "AXA": "axa.it", "Prima": "prima.it", "Alpitour": "alpitour.it"}
def slug(s): return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
def adatta(nuovo, vero):
    if vero.isupper() and len(vero) > 1: return nuovo.upper()
    if vero.islower(): return nuovo.lower()
    return nuovo
def mappa(s, ident, minore, inventato):
    if ident == "REALE": return dict(s["mappa_reale"])
    m = {k: s["mappa_inventata"].get(k, v) for k, v in s["mappa_reale"].items()}
    for k, v in s["mappa_reale"].items():
        if k.startswith("BRAND"):
            nome = {"BRAND": v, "MINORE": minore, "INVENTATO": inventato, "SUPERIORE": SUP.get("_cur")}[ident]
            m[k] = v if ident == "BRAND" else adatta(nome, v)
    return m
def riempi(t, m): return re.sub(r"\{([A-Z0-9_]+)\}", lambda x: m.get(x.group(1), x.group(0)), t)
def pagina_bersaglio(q, ident, testo, sc):
    s = json.load(open(STIM / f"{q}_neutro.json"))
    base = s["modello"] if testo == "ORIG" else s["riscritture"][testo]
    SUP["_cur"] = sc.get("superiore", {}).get(q)
    m = mappa(s, ident, sc["minore"][q], sc["inventato"][q])
    t = riempi(base, m)
    prod = m.get("PRODOTTO") or s["mappa_inventata"].get("PRODOTTO") or "prodotto"
    host = urlsplit(s["url"]).hostname
    url = {"REALE": s["url"], "BRAND": f"https://{host}/it/{slug(prod)}",
           "MINORE": f"https://www.{DOMINI_MINORI[sc['minore'][q]]}/it/{slug(prod)}",
           "INVENTATO": f"https://www.{slug(sc['inventato'][q])}.it/it/{slug(prod)}",
           "SUPERIORE": f"https://www.{DOMINI_SUPERIORI.get(SUP['_cur'], '')}/it/{slug(prod)}"}[ident]
    return t, url
def piano(motori=("gpt", "deepseek", "perplexity")):
    sc = json.load(open(D / "scelte_finali.json"))
    items = []
    for q, v in DOM.items():
        b = sc["bersaglio"][q]
        altre = [(testo_orig(q, i), p[2]) for i, p in enumerate(v["pagine"])]
        for ident in IDENT:
            for testo in TESTI:
                pag = list(altre); pag[b] = pagina_bersaglio(q, ident, testo, sc)
                for m in motori:
                    ordini, rip = PIANO[m]
                    for j in ordini:
                        o = williams()[j]
                        for r in rip:
                            items.append(dict(call_id=f"S|{q}|{ident}|{testo}|{m}|{j}|{r}", fase="studio", qid=q, ident=ident,
                                              testo=testo, motore=m, j=j, rip=r, ordine=o, bersaglio=b,
                                              user_message=messaggio(v["domanda"], pag, o), system_prompt=None, search=False))
    return items
if __name__ == "__main__":
    a = sys.argv[1:]
    mot = tuple(x for x in a if not x.replace(".", "").isdigit()) or ("gpt", "deepseek", "perplexity")
    bud = float(next((x for x in a if x.replace(".", "").isdigit()), 150))
    parte = next((x for x in a if x.startswith("--parte=")), None)
    mot = tuple(x for x in mot if not x.startswith("--parte="))
    it = piano(mot)
    if "--dry" in mot:
        it = piano(); print(len(it)); print(it[5]["user_message"][:3000]); sys.exit()
    out = D / f"studio_{mot[0]}.jsonl" if len(mot) == 1 else OUT
    if parte:
        qs = sorted(DOM); half = set(qs[:6]) if parte.endswith("a") else set(qs[6:])
        it = [i for i in it if i["qid"] in half]
        if parte.endswith("b"):
            from comune import fatti
            gia, _ = fatti(out); it = [i for i in it if i["call_id"] not in gia]
            out = D / f"studio_{mot[0]}_b.jsonl"
    w = {"gpt": 28, "deepseek": 5, "perplexity": 8, "gemini_vertex": 10}
    esegui(it, out, budget_s=bud, workers=w)
