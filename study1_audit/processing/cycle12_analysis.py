#!/usr/bin/env python
"""Ciclo 12, Fase 4 — il system prompt conta? Criterio di equivalenza, controllo 3b su Perplexity, costi.

    python analysis/cycle12_analysis.py [--no-embedding]

Regole (brief «Operativo ciclo 12», scritte prima dei dati):
  - cella = motore x settore x prompt x ricerca; V = vuoto, R = rumore, P = persona (5 repliche ciascuno);
  - misura primaria: Jaccard dei domini delle fonti a ricerca accesa (citate su GPT e Gemini, recuperate su
    Perplexity); Jaccard dei brand nominati a ricerca spenta. Coppie con due insiemi vuoti escluse;
  - Delta_P = s_PV - media(s_VV, s_PP); Delta*_P = Delta_P / (s_VV - s_diversi), denominatore per settore x motore x
    ricerca (s_VV medio dei due prompt del settore, s_diversi = coppie V-V fra i due prompt); sotto 0,05 solo grezzo;
  - stesso calcolo per R; effetto specifico della persona = Delta*_P - Delta*_R (per prompt, poi media);
  - media sui prompt per motore x ricerca, intervallo al 90% con bootstrap clusterizzato per prompt (2.000, seed);
  - margine 0,15 (sensibilità 0,10 e 0,20); letture: Equivalente / Effetto della persona / Effetto del testo, non
    della persona / Inconcludente.
Output in results/cycle12/ e chiave cycle12 in results/metrics.json.
"""
from __future__ import annotations

import argparse
import csv
import itertools
import json
import math
import random
import re
import statistics
import sys
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "analysis"))
from common import jaccard, normalize_domain  # noqa: E402

RAW = ROOT / "data" / "raw"
OUT = ROOT / "results/cycle12"
FIG = OUT / "figure"
ENGINES = ("gpt", "gemini", "perplexity")
LEVELS = ("vuoto", "rumore", "persona")
MARGIN, SENS = 0.15, (0.10, 0.20)
N_BOOT, SEED_BOOT = 2000, 20261016
DEN_MIN = 0.05
NAN = float("nan")



def _loads(line: str):
    """Una riga troncata (processo chiuso a metà scrittura nella sandbox) si salta."""
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return None

def mean(xs):
    xs = [x for x in xs if x is not None and not (isinstance(x, float) and math.isnan(x))]
    return sum(xs) / len(xs) if xs else NAN


def load(engine: str, part: str = "test") -> list[dict]:
    f = RAW / (f"cycle12_{engine}.jsonl" if part == "test" else f"cycle12_3b_{engine}.jsonl")
    if not f.exists():
        return []
    latest = {}
    for line in f.open():
        r = _loads(line)
        if r is None:
            continue
        if not r.get("error"):
            latest[r["call_id"]] = r
    return list(latest.values())


def source_domains(r: dict) -> set[str]:
    if r["engine"] == "perplexity":
        return {x["domain"] for x in r.get("retrieved_results") or [] if x.get("domain")}
    out = set()
    for c in r.get("grounding_chunks") or []:
        if r["engine"] == "gemini":
            d = normalize_domain(c.get("title") or "")
        else:
            d = normalize_domain(urlsplit(c.get("uri") or c.get("url") or "").netloc)
        if d:
            out.add(d)
    return out


_SUFFIX = re.compile(r"\b(s ?p ?a|s ?r ?l|inc|ltd|llc|gmbh|group|gruppo|italia|italy)\b")


def canon(name: str) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    s = s.replace("&", " and ")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = _SUFFIX.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


TABELLA_NOMI = ROOT / "config" / "tabella_nomi_v1.csv"
TIPI_ESTESI = ("brand", "rivenditore", "componente")


def load_brands(usa_tabella: bool = True):
    """Brand di ogni risposta.

    Con la tabella dei nomi (config/tabella_nomi_v1.csv, rivista a mano l'11/10): si leggono entrambe le liste
    dell'estrattore, ogni nome va al suo brand (unioni e nomi doppi divisi) e si tengono i nomi di tipo brand;
    la versione estesa aggiunge rivenditori e componenti. Senza tabella: la lista brand dell'estrattore, come il 10/10.
    """
    f = RAW / "cycle12_brands.jsonl"
    per_key, per_key_ext, variants = {}, {}, defaultdict(set)
    if not f.exists():
        return per_key, per_key_ext, {}
    radici, tipo = {}, {}
    if usa_tabella and TABELLA_NOMI.exists():
        for r in csv.DictReader(TABELLA_NOMI.open()):
            radici[r["chiave"]] = [x.strip() for x in r["unito_a"].split("|")] if r["unito_a"] else [r["chiave"]]
            tipo[r["chiave"]] = r["tipo"]
    for line in f.open():
        r = _loads(line)
        if r is None or r.get("error"):
            continue
        ks = set()
        for b in r.get("brand") or []:
            k = canon(b)
            if k:
                ks.add(k)
                variants[k].add(b)
        if radici:
            rt = {x for b in (r.get("brand") or []) + (r.get("fonti_e_aggregatori") or []) if canon(b)
                  for x in radici[canon(b)]}
            per_key[r["key"]] = {x for x in rt if tipo[x] == "brand"}
            per_key_ext[r["key"]] = {x for x in rt if tipo[x] in TIPI_ESTESI}
        else:
            per_key[r["key"]] = per_key_ext[r["key"]] = ks
    return per_key, per_key_ext, {k: sorted(v) for k, v in variants.items()}


def boot_ci(values_by_prompt: dict[str, tuple], n=N_BOOT, seed=SEED_BOOT):
    """values_by_prompt: prompt -> tuple of statistics; returns list of (mean, lo, hi) per component."""
    keys = sorted(values_by_prompt)
    k = len(next(iter(values_by_prompt.values()))) if keys else 0
    est = [mean([values_by_prompt[p][i] for p in keys]) for i in range(k)]
    rng = random.Random(seed)
    boots = [[] for _ in range(k)]
    for _ in range(n):
        smp = [rng.choice(keys) for _ in keys]
        for i in range(k):
            v = mean([values_by_prompt[p][i] for p in smp])
            if not math.isnan(v):
                boots[i].append(v)
    out = []
    for i in range(k):
        b = sorted(boots[i])
        if len(b) < 20:
            out.append((est[i], NAN, NAN))
        else:
            out.append((est[i], b[int(0.05 * len(b))], b[int(0.95 * len(b)) - 1]))
    return out


def reading(ciP: tuple, ciD: tuple, m: float) -> str:
    lo, hi = ciP
    if math.isnan(lo):
        return "non calcolabile"
    if lo >= -m and hi <= m:
        return "Equivalente"
    if hi < -m:
        dlo, dhi = ciD
        if not math.isnan(dlo) and dhi < -m:
            return "Effetto della persona"
        if not math.isnan(dlo) and dlo >= -m and dhi <= m:
            return "Effetto del testo, non della persona"
    return "Inconcludente"


def pair_mean(sim, xs, ys=None):
    pairs = itertools.combinations(xs, 2) if ys is None else itertools.product(xs, ys)
    vals = [sim(a, b) for a, b in pairs]
    ok = [v for v in vals if not math.isnan(v)]
    return (sum(ok) / len(ok) if ok else NAN), len(vals) - len(ok), len(vals)


# ----------------------------------------------------------------------------- embeddings (secondary)

CACHE = Path.home() / "emb12_cache.pkl"   # fuori dal repo: vettori ricalcolabili


class Emb:
    """Embedding del pilot (MiniLM, revisione in models/*.lock.json): passaggi di al più 120 token, media, norma 1.
    I vettori si tengono in una cache su disco, perché nella sandbox ogni comando dura al più 45 secondi."""

    def __init__(self):
        import hashlib
        import pickle
        from sentence_transformers import SentenceTransformer
        self.h = lambda t: hashlib.sha1((t or "").encode()).hexdigest()
        self.pickle = pickle
        self.m = SentenceTransformer(str(ROOT / "models" / "paraphrase-multilingual-MiniLM-L12-v2"), device="cpu")
        self.tok = self.m.tokenizer
        self.cache = pickle.loads(CACHE.read_bytes()) if CACHE.exists() else {}

    def save(self) -> None:
        tmp = CACHE.with_suffix(".tmp")
        tmp.write_bytes(self.pickle.dumps(self.cache))
        tmp.replace(CACHE)

    def vec(self, text: str):
        import numpy as np
        k = self.h(text)
        if k in self.cache:
            return self.cache[k]
        ids = self.tok(text or "", add_special_tokens=False)["input_ids"]
        chunks = [self.tok.decode(ids[i:i + 120]) for i in range(0, max(len(ids), 1), 120)] or [""]
        v = self.m.encode(chunks, normalize_embeddings=True)
        v = np.mean(v, axis=0)
        v = v / (np.linalg.norm(v) or 1.0)
        self.cache[k] = v
        return v

    def warm(self, texts: list[str], budget_s: float) -> int:
        """Calcola i vettori mancanti finché c'è tempo; salva ogni 25. Ritorna quanti ne mancano."""
        import time as _t
        t0 = _t.monotonic()
        todo = [t for t in dict.fromkeys(texts) if self.h(t) not in self.cache]
        for i, t in enumerate(todo):
            if _t.monotonic() - t0 > budget_s:
                self.save()
                return len(todo) - i
            self.vec(t)
            if i % 25 == 24:
                self.save()
        self.save()
        return 0

    def cos(self, a: str, b: str) -> float:
        import numpy as np
        return float(np.dot(self.vec(a), self.vec(b)))

    def qsim(self, qa: list[str], qb: list[str]) -> float:
        if not qa or not qb:
            return NAN
        def one(x, y):
            return mean([max(self.cos(q, p) for p in y) for q in x])
        return (one(qa, qb) + one(qb, qa)) / 2


# ----------------------------------------------------------------------------- main

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-embedding", action="store_true")
    ap.add_argument("--solo-cache", type=float, default=None, help="secondi: calcola solo i vettori mancanti e esce")
    ap.add_argument("--senza-tabella-nomi", action="store_true",
                    help="brand dalla sola lista dell'estrattore, come nell'analisi del 10/10")
    a = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    FIG.mkdir(exist_ok=True)
    brands, brands_ext, variants = load_brands(not a.senza_tabella_nomi)
    emb = None
    if not a.no_embedding:
        try:
            emb = Emb()
        except Exception as e:  # noqa: BLE001
            print("embedding non disponibili:", e)
    if a.solo_cache:
        texts = []
        for e in ENGINES:
            for r in load(e) + (load(e, "3b") if e == "perplexity" else []):
                texts.append(r.get("response_text") or "")
                texts += r.get("web_search_queries") or []
        print("vettori mancanti:", emb.warm(texts, a.solo_cache))
        return
    prompts = list(csv.DictReader((ROOT / "config" / "cycle12_prompts.csv").open()))
    sector_of = {p["prompt_id"]: p["sector"] for p in prompts}
    by_sector = defaultdict(list)
    for p in prompts:
        by_sector[p["sector"]].append(p["prompt_id"])

    recs = {e: load(e) for e in ENGINES}
    for e in ENGINES:
        for r in recs[e]:
            r["S"] = source_domains(r)
            r["B"] = brands.get(f"{e}|test|{r['call_id']}", set())
            r["BX"] = brands_ext.get(f"{e}|test|{r['call_id']}", set())
    measures = {
        ("on", "fonti"): lambda x, y: jaccard(x["S"], y["S"]),
        ("off", "brand"): lambda x, y: jaccard(x["B"], y["B"]),
        ("on", "brand"): lambda x, y: jaccard(x["B"], y["B"]),
        ("off", "brand_esteso"): lambda x, y: jaccard(x["BX"], y["BX"]),
    }
    if emb:
        measures[("on", "query")] = lambda x, y: emb.qsim(x.get("web_search_queries") or [], y.get("web_search_queries") or [])
        measures[("on", "testo")] = lambda x, y: emb.cos(x.get("response_text") or "", y.get("response_text") or "")
        measures[("off", "testo")] = lambda x, y: emb.cos(x.get("response_text") or "", y.get("response_text") or "")
    primary = {("on", "fonti"), ("off", "brand")}

    cell_rows, eq_rows, metrics = [], [], {"generated_at": datetime.now(timezone.utc).isoformat(), "margine": MARGIN,
                                           "sensibilita": list(SENS), "equivalenza": [], "descrittivi": [], "costi": []}
    for e in ENGINES:
        if not recs[e]:
            continue
        for (srch, meas), sim in measures.items():
            want = srch == "on"
            cells = defaultdict(lambda: defaultdict(list))
            for r in recs[e]:
                if r["search"] == want:
                    cells[r["prompt_id"]][r["level"]].append(r)
            den = {}
            svv = {}
            for p, c in cells.items():
                svv[p] = pair_mean(sim, c["vuoto"])[0]
            for s, pids in by_sector.items():
                pids = [p for p in pids if p in cells]
                if len(pids) < 2:
                    continue
                diff = mean([pair_mean(sim, cells[x]["vuoto"], cells[y]["vuoto"])[0] for x, y in itertools.combinations(pids, 2)])
                den[s] = (mean([svv[p] for p in pids]), diff, mean([svv[p] for p in pids]) - diff)
            per_prompt = {}
            for p, c in sorted(cells.items()):
                s_vv, x_vv, _ = pair_mean(sim, c["vuoto"])
                s_pp, x_pp, _ = pair_mean(sim, c["persona"])
                s_rr, x_rr, _ = pair_mean(sim, c["rumore"])
                s_pv, x_pv, _ = pair_mean(sim, c["persona"], c["vuoto"])
                s_rv, x_rv, _ = pair_mean(sim, c["rumore"], c["vuoto"])
                d_p = s_pv - mean([s_vv, s_pp])
                d_r = s_rv - mean([s_vv, s_rr])
                s_rep, s_div, D = den.get(sector_of[p], (NAN, NAN, NAN))
                ok = not math.isnan(D) and D >= DEN_MIN
                dsp = d_p / D if ok else NAN
                dsr = d_r / D if ok else NAN
                per_prompt[p] = (dsp, dsr, dsp - dsr if ok else NAN, d_p, d_r)
                cell_rows.append({"motore": e, "ricerca": srch, "misura": meas, "primaria": (srch, meas) in primary,
                                  "prompt_id": p, "settore": sector_of[p],
                                  "n_V": len(c["vuoto"]), "n_R": len(c["rumore"]), "n_P": len(c["persona"]),
                                  "s_VV": s_vv, "s_PP": s_pp, "s_RR": s_rr, "s_PV": s_pv, "s_RV": s_rv,
                                  "delta_P": d_p, "delta_R": d_r, "s_rep_settore": s_rep, "s_diversi_settore": s_div,
                                  "denominatore": D, "delta_star_P": dsp, "delta_star_R": dsr,
                                  "coppie_vuote_escluse": x_vv + x_pp + x_rr + x_pv + x_rv})
            if not per_prompt:
                continue
            (mP, loP, hiP), (mR, loR, hiR), (mD, loD, hiD), (rP, rPlo, rPhi), (rR, rRlo, rRhi) = boot_ci(per_prompt)
            row = {"motore": e, "ricerca": srch, "misura": meas, "primaria": (srch, meas) in primary,
                   "n_prompt": sum(1 for v in per_prompt.values() if not math.isnan(v[0])),
                   "delta_star_P": mP, "P_lo90": loP, "P_hi90": hiP, "delta_star_R": mR, "R_lo90": loR, "R_hi90": hiR,
                   "P_meno_R": mD, "PmR_lo90": loD, "PmR_hi90": hiD,
                   "delta_P_grezzo": rP, "Pg_lo90": rPlo, "Pg_hi90": rPhi, "delta_R_grezzo": rR}
            for m in (MARGIN, *SENS):
                row[f"lettura_{m:.2f}"] = reading((loP, hiP), (loD, hiD), m)
            eq_rows.append(row)

    # pooled over engines (secondary): per prompt, mean of the engines' values, bootstrap over prompts
    for (srch, meas) in sorted(primary):
        pooled = defaultdict(list)
        for c in cell_rows:
            if c["ricerca"] == srch and c["misura"] == meas:
                pooled[c["prompt_id"]].append((c["delta_star_P"], c["delta_star_R"], c["delta_star_P"] - c["delta_star_R"]))
        vals = {p: tuple(mean([x[i] for x in v]) for i in range(3)) for p, v in pooled.items()}
        if vals:
            (mP, loP, hiP), (mR, loR, hiR), (mD, loD, hiD) = boot_ci(vals)
            row = {"motore": "tutti (media per prompt)", "ricerca": srch, "misura": meas, "primaria": False,
                   "n_prompt": len(vals), "delta_star_P": mP, "P_lo90": loP, "P_hi90": hiP, "delta_star_R": mR,
                   "R_lo90": loR, "R_hi90": hiR, "P_meno_R": mD, "PmR_lo90": loD, "PmR_hi90": hiD}
            for m in (MARGIN, *SENS):
                row[f"lettura_{m:.2f}"] = reading((loP, hiP), (loD, hiD), m)
            eq_rows.append(row)

    # descriptives and costs
    desc_rows, cost_rows = [], []
    for e in ENGINES:
        for srch in (False, True):
            for lv in LEVELS:
                rs = [r for r in recs[e] if r["search"] == srch and r["level"] == lv]
                if not rs:
                    continue
                desc_rows.append({"motore": e, "ricerca": "on" if srch else "off", "livello": lv, "n": len(rs),
                                  "quota_con_ricerca": mean([1.0 if r.get("search_performed") else 0.0 for r in rs]),
                                  "fonti_per_risposta": mean([len(r["S"]) for r in rs]),
                                  "risposte_senza_fonti": sum(1 for r in rs if not r["S"]),
                                  "brand_per_risposta": mean([len(r["B"]) for r in rs]),
                                  "risposte_senza_brand": sum(1 for r in rs if not r["B"]),
                                  "query_per_risposta": mean([len(r.get("web_search_queries") or []) for r in rs]),
                                  "caratteri_risposta": mean([len(r.get("response_text") or "") for r in rs])})
            rs = [r for r in recs[e] if r["search"] == srch]
            cs = [r.get("cost_usd_est") for r in rs if r.get("cost_usd_est") is not None]
            lat = [r.get("latency_s") for r in rs if r.get("latency_s") is not None]
            if cs:
                cost_rows.append({"motore": e, "ricerca": "on" if srch else "off", "n": len(cs),
                                  "costo_medio": mean(cs), "costo_mediano": statistics.median(cs), "costo_totale": sum(cs),
                                  "latenza_media_s": mean(lat)})
    proj = []
    for e in ENGINES:
        cm = {c["ricerca"]: c["costo_medio"] for c in cost_rows if c["motore"] == e}
        if len(cm) == 2:
            ts = sorted(datetime.fromisoformat(r["timestamp"]) for r in recs[e])
            wall_h = (ts[-1] - ts[0]).total_seconds() / 3600 if len(ts) > 1 else NAN
            proj.append({"motore": e, "chiamate_studio_principale": 6400, "costo_proiettato": 3200 * cm["on"] + 3200 * cm["off"],
                         "ore_alla_stessa_velocita": wall_h / len(recs[e]) * 6400 if wall_h == wall_h else NAN,
                         "chiamate_ciclo12": len(recs[e]), "ore_ciclo12": wall_h})

    # 3b — Perplexity, persona in the user message
    b3 = load("perplexity", "3b")
    b3_rows, b3_summary = [], {}
    if b3:
        for r in b3:
            r["S"] = source_domains(r)
        ref = [r for r in recs["perplexity"] if r["search"] and r["level"] == "vuoto"] or \
              [r for r in b3 if False]
        def nres(r):
            return len(r.get("retrieved_results") or [])
        for p in sorted({r["prompt_id"] for r in b3}):
            u = [r for r in b3 if r["prompt_id"] == p]
            v = [r for r in ref if r["prompt_id"] == p]
            sim = lambda x, y: jaccard(x["S"], y["S"])  # noqa: E731
            b3_rows.append({"prompt_id": p, "n_persona_utente": len(u), "n_vuoto": len(v),
                            "risultati_mediana_persona_utente": statistics.median([nres(r) for r in u]) if u else NAN,
                            "risultati_mediana_vuoto": statistics.median([nres(r) for r in v]) if v else NAN,
                            "query_media_persona_utente": mean([len(r.get("web_search_queries") or []) for r in u]),
                            "query_media_vuoto": mean([len(r.get("web_search_queries") or []) for r in v]),
                            "J_dentro_persona_utente": pair_mean(sim, u)[0], "J_dentro_vuoto": pair_mean(sim, v)[0],
                            "J_persona_utente_vs_vuoto": pair_mean(sim, u, v)[0] if v else NAN})
        allu = [nres(r) for r in b3]
        allv = [nres(r) for r in ref if r["prompt_id"] in {x["prompt_id"] for x in b3}]
        ju, jv = mean([x["J_dentro_persona_utente"] for x in b3_rows]), mean([x["J_dentro_vuoto"] for x in b3_rows])
        med_u, med_v = statistics.median(allu), (statistics.median(allv) if allv else NAN)
        collapse = (med_u < 0.5 * med_v) or (ju < 0.5 * jv)
        b3_summary = {"risultati_mediana_persona_utente": med_u, "risultati_mediana_vuoto": med_v,
                      "J_dentro_persona_utente": ju, "J_dentro_vuoto": jv,
                      "J_persona_utente_vs_vuoto": mean([x["J_persona_utente_vs_vuoto"] for x in b3_rows]),
                      "crollo": bool(collapse)}

    # write
    def wcsv(name, rows):
        if not rows:
            return
        fields = list(dict.fromkeys(k for r in rows for k in r))
        with (OUT / name).open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            for r in rows:
                w.writerow({k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()})
    wcsv("celle.csv", cell_rows)
    wcsv("equivalenza.csv", eq_rows)
    wcsv("descrittivi.csv", desc_rows)
    wcsv("costi.csv", cost_rows)
    wcsv("proiezione_studio_principale.csv", proj)
    wcsv("controllo_3b.csv", b3_rows)
    alias = {"descrizione": "Ciclo 12 — tabella degli alias v1: chiave normalizzata -> varianti viste (analysis/cycle12_analysis.py)",
             "alias": variants}
    keys = sorted(variants)
    cand = [(x, y) for x in keys for y in keys if x != y and (y.startswith(x + " ") or y.endswith(" " + x))]
    alias["candidati_da_unire"] = [f"{x} <-> {y}" for x, y in cand]
    (OUT / "alias_v1.json").write_text(json.dumps(alias, ensure_ascii=False, indent=1))
    metrics.update({"equivalenza": eq_rows, "descrittivi": desc_rows, "costi": cost_rows, "proiezione": proj,
                    "controllo_3b": b3_summary, "n_risposte": {e: len(recs[e]) for e in ENGINES},
                    "n_brand_distinti": len(variants), "embedding": bool(emb),
                    "brand_da": "estrattore" if a.senza_tabella_nomi or not TABELLA_NOMI.exists() else "tabella_nomi_v1"})
    def clean(o):
        if isinstance(o, float) and math.isnan(o):
            return None
        if isinstance(o, dict):
            return {k: clean(v) for k, v in o.items()}
        if isinstance(o, list):
            return [clean(v) for v in o]
        return o
    (OUT / "metrics_cycle12.json").write_text(json.dumps(clean(metrics), ensure_ascii=False, indent=1, default=str))
    mpath = ROOT / "results" / "metrics.json"
    allm = json.loads(mpath.read_text())
    allm["cycle12"] = clean(metrics)
    mpath.write_text(json.dumps(allm, ensure_ascii=False, indent=1, default=str))

    # figure
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        prim = [r for r in eq_rows if r["primaria"]]
        fig, axes = plt.subplots(1, 2, figsize=(10, 4), sharey=True)
        for ax, srch, title in ((axes[0], "off", "Search off: brands named (Jaccard)"),
                                (axes[1], "on", "Search on: sources (Jaccard)")):
            rows = [r for r in prim if r["ricerca"] == srch]
            ax.axhspan(-MARGIN, MARGIN, color="#dde7f3", zorder=0)
            for m in SENS:
                ax.axhline(m, ls=":", c="#8a99ad", lw=0.8)
                ax.axhline(-m, ls=":", c="#8a99ad", lw=0.8)
            ax.axhline(0, c="#555", lw=0.8)
            for i, r in enumerate(rows):
                for dx, key, lo, hi, col, lab in ((-0.12, "delta_star_P", "P_lo90", "P_hi90", "#1f5aa6", "persona"),
                                                  (0.12, "delta_star_R", "R_lo90", "R_hi90", "#d4772c", "noise")):
                    y = r[key]
                    ax.errorbar(i + dx, y, yerr=[[y - r[lo]], [r[hi] - y]], fmt="o", color=col, capsize=3,
                                label=lab if i == 0 else None)
            ax.set_xticks(range(len(rows)))
            ax.set_xticklabels([r["motore"] for r in rows])
            ax.set_title(title, fontsize=10)
        axes[0].set_ylabel("Normalized difference vs empty system prompt\n(0 = like repeats, −1 = like a different question)")
        axes[1].legend(loc="lower right", fontsize=8)
        fig.suptitle(f"System prompt test: 90% intervals, equivalence band ±{MARGIN} (dotted ±{SENS[0]}, ±{SENS[1]})", fontsize=10)
        fig.tight_layout()
        fig.savefig(FIG / "fig_equivalenza.png", dpi=160)
    except Exception as ex:  # noqa: BLE001
        print("figura non generata:", ex)
    print(json.dumps(clean({"equivalenza": [{k: r[k] for k in ("motore", "ricerca", "misura", "delta_star_P", "P_lo90",
                                                             "P_hi90", "P_meno_R", f"lettura_{MARGIN:.2f}")}
                                           for r in eq_rows]}), ensure_ascii=False, indent=0, default=str))


if __name__ == "__main__":
    main()
