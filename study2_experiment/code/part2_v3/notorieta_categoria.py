"""Notorietà di categoria (protocollo sez. 3) per tutti i candidati delle 24 domande.
- domande con misura «nome del marchio»: la notorietà di Study 1 (config/main_notorieta.csv);
- le altre: somma, sui termini di prodotto fissati per la domanda (origine_22_10/termini.py), delle ricerche
  «marchio + termine»; per ogni termine il massimo fra il nome del marchio e la query del marchio di Study 1.
DataForSEO Google Ads search_volume, Italia (2380), italiano, media degli ultimi 12 mesi. Risposte grezze in data/raw."""
import json, sys
from pathlib import Path
import re, unicodedata
from comune_v3 import ROOT, D, P, VOL, NOME, QUERY, DOM, CAT, menzioni
def norm(b):
    """Stessa normalizzazione delle query del 22/10 (origine_22_10/base.py): punteggiatura -> spazio."""
    b = unicodedata.normalize("NFKD", b).encode("ascii", "ignore").decode().lower(); b = re.sub(r"[^\w\s]", " ", b)
    return re.sub(r"\s+", " ", b).strip()
sys.path.insert(0, str(ROOT / "pipeline")); sys.path.insert(0, str(Path(__file__).parent / "origine_22_10"))
from termini import TERM
from tabella_protocollo import T
AGG = json.load(open(Path(__file__).parent / "origine_22_10/categoria_marchi_v3_aggiunte.json"))
def cat_ok(pid, k):
    v = CAT.get(f"{pid}|{k}") or AGG.get(f"{pid}|{k}") or AGG.get(f"{pid}|{norm(NOME.get(k, k))}")
    return v is not None and "NO" not in v
M, _ = menzioni()
def candidati(pid):
    return [k for k, n in M[pid].most_common() if n >= 5 and VOL.get(k, 0) > 0 and k in DOM and cat_ok(pid, k)]
def m12(ms):
    if not ms: return 0
    ms = sorted(ms, key=lambda m: (m["year"], m["month"]), reverse=True)[:12]; v = [m["search_volume"] for m in ms if m.get("search_volume") is not None]
    return sum(v) / len(v) if v else 0
F = D / "volumi_marchio_prodotto.json"
def scarica_volumi():
    import cycle10_dataforseo as d
    kws = sorted({f"{norm(x)} {t}" for pid, mis, *_ in T if mis == "marchio+prodotto" for k in candidati(pid)
                  for x in (NOME.get(k, k), QUERY.get(k) or NOME.get(k, k)) for t in TERM[pid]})
    V = {}
    for i in range(0, len(kws), 1000):
        data = d.call("keywords_data/google_ads/search_volume/live", [dict(keywords=kws[i:i + 1000], location_code=2380, language_code="it")],
                      f"study2_v3_marchio_prodotto_{i // 1000}", est=d.estimate("google_ads"))
        for r in data["tasks"][0].get("result") or []: V[r["keyword"]] = m12(r.get("monthly_searches"))
    json.dump(dict(n_keyword=len(kws), volumi=V), open(F, "w"), ensure_ascii=False, indent=1)
def notorieta():
    V = json.load(open(F))["volumi"]; out = {}
    for pid, mis, *_ in T:
        out[pid] = {}
        for k in candidati(pid):
            out[pid][k] = VOL.get(k, 0) if mis == "nome del marchio" else sum(
                max(V.get(f"{norm(NOME.get(k, k))} {t}", 0), V.get(f"{norm(QUERY.get(k) or NOME.get(k, k))} {t}", 0)) for t in TERM[pid])
    return out
if __name__ == "__main__":
    if not F.exists(): scarica_volumi()
    S = notorieta(); json.dump(S, open(D / "notorieta_categoria.json", "w"), ensure_ascii=False, indent=1)
    print("candidati per domanda:", {p: len(v) for p, v in S.items()})
