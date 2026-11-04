#!/usr/bin/env python
"""Studio principale — P1, P2, P3 e ricerca accesa contro spenta, con le figure chieste il 06/10.

    python analysis/main_analysis.py [--emb bge-m3|tfidf-prova] [--brand estrattore|regex-prova] [--boot 1000]

Prima: main_prepare.py (tabella snella), main_brands.py (brand estratti), main_embed.py (vettori bge-m3).
Le modalità «-prova» servono solo a collaudare il codice prima che ci siano brand ed embedding veri: i loro numeri
non vanno usati e i file in uscita lo dichiarano.

Regole (scritte prima di guardare i dati del run, pagina «Hypotheses and design» e incontro del 06/10):
  P1  per motore, settore e ricerca: tasso di menzione di ogni brand (quota di risposte che lo nominano), tasso di
      citazione del suo sito (quota di risposte a ricerca accesa con il dominio del brand fra le fonti), rapporto
      citazioni/menzioni, MRR (1/rango della prima menzione, 0 se assente) e rango quando nominato.
      Notorietà = log10(1 + ricerche mensili medie in Italia, DataForSEO), da config/main_notorieta.csv.
      Spearman notorietà-esito, pendenza della menzione sulla notorietà a ricerca spenta e accesa, Gini delle
      menzioni spenta/accesa. Intervalli al 95% con bootstrap per prompt (stratificato per settore).
      Entrano i brand nominati in almeno MIN_RISPOSTE risposte del motore e del settore (le due braccia insieme).
  P2  coppie di chiamate dello stesso prompt e dello stesso motore a ricerca accesa, entrambe con query:
      x = somiglianza delle query (best-match simmetrico sui coseni), y = Jaccard delle fonti, Jaccard dei brand,
      coseno del testo. Prima la somiglianza fra repliche della stessa chiamata (stesso prompt e livello), poi le
      curve in unità grezze, poi la scala normalizzata s* = (s - s_diversi) / (s_repliche - s_diversi), con
      s_repliche e s_diversi per motore e settore. Pendenze con effetti fissi per prompt, bootstrap per prompt.
  P3  le stesse coppie, etichettate: stessa persona (A-A, B-B, C-C), persone diverse (A-B, A-C, B-C), nessuna-nessuna
      (controllo), A nel messaggio contro A nel system prompt. Coefficiente di «persone diverse» sul Jaccard delle
      fonti senza x, lineare in x e dentro le fasce di x, sempre con effetti fissi per prompt. A ricerca spenta:
      lo stesso confronto sul Jaccard dei brand.
  On/off brand per risposta, quota di risposte senza brand, Gini, sovrapposizione dei brand fra le due braccia.
Uscite in results/main/ (CSV, metrics_main.json, figure/ in PNG e SVG).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import math
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "analysis"))
from cycle12_analysis import canon  # noqa: E402

PROC = ROOT / "data" / "processed"
RAW = ROOT / "data" / "raw"
OUT = ROOT / "results/main"
FIG = OUT / "figure"
ENGINES = ("gpt", "gemini", "perplexity")
ENGINE_LABEL = {"gpt": "GPT", "gemini": "Gemini", "perplexity": "Perplexity"}
SECTORS = ("assicurazioni", "moda_beauty", "sport", "viaggi")
SECTOR_LABEL = {"assicurazioni": "Insurance", "moda_beauty": "Fashion & beauty", "sport": "Sport", "viaggi": "Travel"}
LEVELS = ("nessuna", "A", "B", "C", "A_sistema")
PERSONE = ("A", "B", "C")
MIN_RISPOSTE = 5
N_FASCE = 8
SEED = 20261014
NAN = float("nan")
SENZA_TESTO = False

TABELLE = [ROOT / "config" / "tabella_nomi_v2.csv", ROOT / "config" / "tabella_nomi_v1.csv"]
NOTORIETA = ROOT / "config" / "main_notorieta.csv"
DOMINI = ROOT / "config" / "main_brand_domini.csv"


def _loads(line: str):
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return None


def sha(t: str) -> str:
    return hashlib.sha1((t or "").encode()).hexdigest()


def jac(a: set, b: set) -> float:
    if not a and not b:
        return NAN
    return len(a & b) / len(a | b)


def nanmean(xs) -> float:
    xs = [x for x in xs if x == x]
    return sum(xs) / len(xs) if xs else NAN


# ----------------------------------------------------------------------------- dati

def load_calls(include_system: bool = False) -> list[dict]:
    rows = [r for r in map(_loads, (PROC / "main_calls.jsonl").open()) if r]
    if not include_system:
        rows = [r for r in rows if r["level"] != "A_sistema"]
    for r in rows:
        r["key"] = f"{r['engine']}|main|{r['call_id']}"
        r["fonti_s"] = set(r.get("fonti") or [])
    return rows


class Nomi:
    """Tabella dei nomi: chiave normalizzata -> radici (unioni e nomi doppi) e tipo. Nomi assenti dalla tabella:
    radice = se stesso, tipo dalla lista dell'estrattore (brand o fonte), contati a parte come «non in tabella»."""

    def __init__(self):
        self.radici, self.tipo, self.nome, self.dominio = {}, {}, {}, defaultdict(set)
        self.fonte = None
        for t in TABELLE:
            if t.exists():
                self.fonte = t.name
                for r in csv.DictReader(t.open()):
                    k = r["chiave"]
                    self.radici[k] = [x.strip() for x in r["unito_a"].split("|")] if r["unito_a"] else [k]
                    self.tipo[k] = r["tipo"]
                    self.nome[k] = r["nome"]
                    if r.get("dominio_ciclo10"):
                        self.dominio[k].add(r["dominio_ciclo10"].strip().lower())
                break
        if self.fonte == "tabella_nomi_v2.csv":
            self.dominio.clear()  # v2 consumes only the explicitly reviewed mapping below
        if DOMINI.exists():
            for r in csv.DictReader(DOMINI.open()):
                domain = (r.get("dominio") or "").strip().lower()
                if domain:
                    self.dominio[r["chiave"]].add(domain)
        self.esclusioni, self.per_settore = {}, {}
        if self.fonte == "tabella_nomi_v2.csv":
            for r in csv.DictReader(TABELLE[0].open()):
                self.esclusioni[r["chiave"]] = {s.strip() for s in (r.get("escludi_brand_settori") or "").split("|") if s.strip()}
                self.per_settore[r["chiave"]] = json.loads(r.get("radici_per_settore") or "{}")
        self.fuori = Counter()

    def risolvi(self, nome: str, lista: str, settore: str | None = None) -> list[tuple[str, str]]:
        k = canon(nome)
        if not k:
            return []
        if settore in getattr(self, "esclusioni", {}).get(k, set()):
            return []
        if k in self.radici:
            roots = getattr(self, "per_settore", {}).get(k, {}).get(settore, self.radici[k])
            return [(x, self.tipo.get(x, self.tipo[k])) for x in roots
                    if settore not in getattr(self, "esclusioni", {}).get(x, set())]
        self.fuori[(k, lista)] += 1
        return [(k, "brand" if lista == "brand" else "aggregatore_o_fonte")]

    def etichetta(self, k: str, varianti: Counter | None = None) -> str:
        if k in self.nome:
            return self.nome[k]
        if varianti and varianti[k]:
            return varianti[k].most_common(1)[0][0]
        return k


def offset(text_l: str, nome: str) -> int | None:
    n = nome.lower().strip()
    if not n:
        return None
    m = re.search(r"(?<![\w])" + re.escape(n) + r"(?![\w])", text_l)
    if m:
        return m.start()
    i = text_l.find(n)
    return i if i >= 0 else None


def attach_brands(rows: list[dict], nomi: Nomi, modo: str) -> dict:
    """Aggiunge a ogni chiamata la lista ordinata dei brand (radici di tipo brand, in ordine di prima menzione)."""
    estratti = {}
    if modo == "estrattore":
        f = RAW / "main_brands.jsonl"
        for r in map(_loads, f.open()) if f.exists() else []:
            if r and not r.get("error"):
                estratti[r["key"]] = r
    else:  # regex-prova: varianti della tabella cercate nel testo, solo per collaudo
        pats = []
        for t in TABELLE:
            if t.exists():
                for r in csv.DictReader(t.open()):
                    for v in r["varianti"].split("|"):
                        v = v.strip()
                        if len(v) >= 3:
                            pats.append((v, r["tipo"]))
                break
        rx = [(v, tp, re.compile(r"(?<![\w])" + re.escape(v.lower()) + r"(?![\w])")) for v, tp in pats]
        for r in rows:
            tl = (r.get("response_text") or "").lower()
            b = [v for v, tp, p in rx if tp == "brand" and p.search(tl)]
            fo = [v for v, tp, p in rx if tp != "brand" and p.search(tl)]
            estratti[r["key"]] = {"brand": b, "fonti_e_aggregatori": fo}
    varianti = defaultdict(Counter)
    copertura = Counter()
    for r in rows:
        e = estratti.get(r["key"])
        r["ha_estrazione"] = e is not None and not (e.get("vuota") and tl_nonvuoto(r))
        if not r["ha_estrazione"]:
            e = None
        if e is None:
            r["brand_ord"], r["B"] = [], set()
            continue
        tl = (r.get("response_text") or "").lower()
        # Retain product-link labels, remove only URL destinations for the literal mention check.
        visible = re.sub(r"!?\[([^\]]*)\]\([^\n]*?\)", r"\1", tl)
        visible = re.sub(r"https?://[^\s<>]+", " ", visible)
        prose = re.sub(r"!?\[[^\]]*\]\([^\n]*?\)", " ", tl)
        prose = re.sub(r"https?://[^\s<>]+", " ", prose)
        pos = {}
        for lista, campo in (("brand", "brand"), ("fonti", "fonti_e_aggregatori")):
            for n in e.get(campo) or []:
                is_domain = bool(re.fullmatch(r"(?:[a-z0-9-]+\.)+(?:it|com|org|net|eu|info|io|de|fr|es|uk|ch|nl|re|fi|me|travel)", n.casefold().strip()))
                if lista == "fonti" and (offset(visible, n) is None or (is_domain and offset(prose, n) is None)):
                    continue
                o = offset(tl, n)
                for k, tp in nomi.risolvi(n, lista, r["sector"]):
                    if tp != "brand":
                        continue
                    varianti[k][n] += 1
                    if o is not None:
                        pos[k] = min(pos.get(k, o), o)
                        copertura["trovati"] += 1
                    else:
                        pos.setdefault(k, None)
                        copertura["non_trovati_nel_testo"] += 1
        trovati = sorted((k for k, o in pos.items() if o is not None), key=lambda k: pos[k])
        r["brand_ord"] = trovati
        r["B"] = set(pos)
    return {"varianti": varianti, "copertura": dict(copertura), "con_estrazione": sum(r["ha_estrazione"] for r in rows)}


# ----------------------------------------------------------------------------- embedding

class Vettori:
    def __init__(self, rows: list[dict], modo: str):
        self.modo = modo
        if modo == "bge-m3":
            from main_embed import carica
            self.v = carica()
            if not self.v:
                raise SystemExit("nessun vettore bge-m3: lanciare prima python analysis/main_embed.py")
        else:  # tfidf-prova: solo collaudo
            from sklearn.feature_extraction.text import TfidfVectorizer
            testi = {}
            for r in rows:
                for t in [r.get("response_text") or ""] + (r.get("queries") or []):
                    if t.strip():
                        testi.setdefault(sha(t), t)
            ks = list(testi)
            m = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=2, max_features=50000)
            X = m.fit_transform([testi[k] for k in ks])
            from sklearn.decomposition import TruncatedSVD
            Z = TruncatedSVD(128, random_state=0).fit_transform(X)
            Z /= np.linalg.norm(Z, axis=1, keepdims=True) + 1e-12
            self.v = {k: Z[i].astype("float32") for i, k in enumerate(ks)}
        self.dim = len(next(iter(self.v.values())))

    def get(self, t: str):
        return self.v.get(sha(t))

    def testo(self, t: str):
        """Vettore di una risposta; None con --senza-testo (embedding delle risposte non ancora completi)."""
        return None if SENZA_TESTO else self.get(t)


# ----------------------------------------------------------------------------- statistica

def spearman(x, y) -> float:
    from scipy.stats import spearmanr
    x, y = np.asarray(x, float), np.asarray(y, float)
    ok = ~(np.isnan(x) | np.isnan(y))
    if ok.sum() < 5 or np.nanstd(x[ok]) == 0 or np.nanstd(y[ok]) == 0:
        return NAN
    return float(spearmanr(x[ok], y[ok]).statistic)


def ols_slope(x, y) -> float:
    x, y = np.asarray(x, float), np.asarray(y, float)
    ok = ~(np.isnan(x) | np.isnan(y))
    if ok.sum() < 5 or np.std(x[ok]) == 0:
        return NAN
    return float(np.polyfit(x[ok], y[ok], 1)[0])


def gini(counts) -> float:
    c = np.sort(np.asarray(counts, float))
    if len(c) == 0 or c.sum() == 0:
        return NAN
    n = len(c)
    return float((2 * np.arange(1, n + 1) - n - 1).dot(c) / (n * c.sum()))


def ci(vals, est=None) -> tuple[float, float]:
    v = np.asarray([x for x in vals if x == x], float)
    if len(v) < 50:
        return NAN, NAN
    return float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))


def prompt_boot(prompts_by_sector: dict[str, list[str]], n: int, seed: int):
    """Estrazioni bootstrap di prompt, stratificate per settore: lista di Counter prompt -> peso."""
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n):
        w = Counter()
        for s, ps in prompts_by_sector.items():
            for i in rng.integers(0, len(ps), len(ps)):
                w[ps[i]] += 1
        out.append(w)
    return out


# ----------------------------------------------------------------------------- P1

def p1(rows, nomi, info, boots, prompts_by_sector):
    noto = {}
    if NOTORIETA.exists():
        for r in csv.DictReader(NOTORIETA.open()):
            try:
                noto[r["chiave"]] = math.log10(1 + float(r["volume"]))
            except (ValueError, KeyError):
                pass
    brand_rows, stat_rows = [], []
    ranks_rows = []
    for e in ENGINES:
        for s in SECTORS:
            sub = [r for r in rows if r["engine"] == e and r["sector"] == s and r["ha_estrazione"]]
            if not sub:
                continue
            tot = Counter(k for r in sub for k in r["B"])
            universo = sorted(k for k, c in tot.items() if c >= MIN_RISPOSTE)
            idx = {k: i for i, k in enumerate(universo)}
            cand_dom = {k: candidati_dominio(k, nomi) for k in universo}
            prompts = sorted({r["prompt_id"] for r in sub})
            pidx = {p: i for i, p in enumerate(prompts)}
            for srch in (False, True):
                rs = [r for r in sub if r["search"] == srch]
                if not rs or not universo:
                    continue
                # matrici prompt x brand: risposte, menzioni, citazioni, somma di 1/rango
                n_p = np.zeros(len(prompts))
                men = np.zeros((len(prompts), len(universo)))
                cit = np.zeros_like(men)
                rr = np.zeros_like(men)
                for r in rs:
                    i = pidx[r["prompt_id"]]
                    n_p[i] += 1
                    for j, k in enumerate(r["brand_ord"]):
                        if k in idx:
                            rr[i, idx[k]] += 1 / (j + 1)
                            ranks_rows.append({"motore": e, "settore": s, "ricerca": "on" if srch else "off",
                                               "chiave": k, "rango": j + 1, "prompt_id": r["prompt_id"]})
                    for k in r["B"]:
                        if k in idx:
                            men[i, idx[k]] += 1
                    if srch:
                        lab = {d.split(".")[0] for d in r["fonti_s"]}
                        for k in universo:
                            if dominio_proprio(cand_dom[k], lab, r["fonti_s"]):
                                cit[i, idx[k]] += 1

                def rates(w=None):
                    ww = np.ones(len(prompts)) if w is None else np.array([w.get(p, 0) for p in prompts], float)
                    N = (ww * n_p).sum()
                    if N == 0:
                        return None
                    m = (ww[:, None] * men).sum(0) / N
                    c = (ww[:, None] * cit).sum(0) / N
                    q = (ww[:, None] * rr).sum(0) / N
                    return m, c, q

                m, c, q = rates()
                for k in universo:
                    if not cand_dom[k][0]:
                        c[idx[k]] = NAN
                x = np.array([noto.get(k, NAN) for k in universo])
                for k in universo:
                    j = idx[k]
                    brand_rows.append({"motore": e, "settore": s, "ricerca": "on" if srch else "off", "chiave": k,
                                       "brand": nomi.etichetta(k, info["varianti"]), "notorieta_log10": x[j],
                                       "risposte": int(n_p.sum()), "menzioni": int(men[:, j].sum()),
                                       "tasso_menzione": m[j], "tasso_citazione": c[j] if srch else NAN,
                                       "citazioni_su_menzioni": (cit[:, j].sum() / men[:, j].sum()) if srch and men[:, j].sum() and cand_dom[k][0] else NAN,
                                       "mrr": q[j]})
                # statistiche sul settore
                bs_w = [{p: w[p] for p in prompts} for w in boots]
                def stats(mm, cc, qq):
                    cc = cc.copy()
                    for k in universo:
                        if not cand_dom[k][0]:
                            cc[idx[k]] = NAN
                    ratio = np.where(mm > 0, cc / np.where(mm > 0, mm, 1), NAN)
                    return {"rho_menzione": spearman(x, mm), "rho_citazione": spearman(x, cc) if srch else NAN,
                            "rho_cit_su_menz": spearman(x, ratio) if srch else NAN, "rho_mrr": spearman(x, qq),
                            "pendenza_menzione": ols_slope(x, mm), "gini_menzioni": gini(mm)}
                est = stats(m, c, q)
                bb = defaultdict(list)
                if not np.isnan(x).all():
                    for w in bs_w:
                        rt = rates(w)
                        if rt is None:
                            continue
                        for kk, vv in stats(*rt).items():
                            bb[kk].append(vv)
                else:
                    for w in bs_w:
                        rt = rates(w)
                        if rt is not None:
                            bb["gini_menzioni"].append(gini(rt[0]))
                row = {"motore": e, "settore": s, "ricerca": "on" if srch else "off", "brand": len(universo),
                       "brand_con_notorieta": int((~np.isnan(x)).sum()),
                       "brand_con_dominio": sum(bool(cand_dom[k][0]) for k in universo),
                       "brand_con_notorieta_e_dominio": sum(bool(cand_dom[k][0]) and not np.isnan(x[idx[k]]) for k in universo),
                       "risposte": int(n_p.sum())}
                for kk, vv in est.items():
                    lo, hi = ci(bb.get(kk, []))
                    row.update({kk: vv, kk + "_lo": lo, kk + "_hi": hi})
                stat_rows.append(row)
    return brand_rows, stat_rows, ranks_rows, bool(noto)


def candidati_dominio(k: str, nomi: Nomi) -> tuple[set, set]:
    """Only explicitly mapped domains count as a brand's own site."""
    return set(nomi.dominio.get(k, set())), set()


def dominio_proprio(cd: tuple[set, set], etichette: set, domini: set) -> bool:
    return bool(cd[0] & domini)


# ----------------------------------------------------------------------------- coppie (P2, P3)

def qsim_matrix(Qs: list, idx_a: list, idx_b: list, M) -> float:
    if not idx_a or not idx_b:
        return NAN
    blk = M[np.ix_(idx_a, idx_b)]
    return float((blk.max(1).mean() + blk.max(0).mean()) / 2)


def coppie(rows, vett: Vettori):
    """Tutte le coppie dello stesso motore e prompt a ricerca accesa, con le quattro misure. Le misure su query,
    fonti e testo non dipendono dall'estrazione dei brand: una risposta non ancora estratta entra lo stesso e ha il
    Jaccard dei brand mancante."""
    out, rep_rows = [], []
    gruppi = defaultdict(list)
    for r in rows:
        if r["search"] and r.get("queries"):
            gruppi[(r["engine"], r["prompt_id"])].append(r)
    for (e, p), rs in sorted(gruppi.items()):
        qv, qidx = [], []
        for r in rs:
            ids = []
            for q in r["queries"]:
                v = vett.get(q)
                if v is not None:
                    ids.append(len(qv))
                    qv.append(v)
            qidx.append(ids)
        if not qv:
            continue
        Q = np.vstack(qv)
        M = Q @ Q.T
        tv = [vett.testo(r.get("response_text") or "") for r in rs]
        for i, j in itertools.combinations(range(len(rs)), 2):
            a, b = rs[i], rs[j]
            x = qsim_matrix(None, qidx[i], qidx[j], M)
            ct = float(tv[i] @ tv[j]) if tv[i] is not None and tv[j] is not None else NAN
            la, lb = a["level"], b["level"]
            if la == lb:
                etich = "stessa_cella"
            elif {la, lb} <= set(PERSONE):
                etich = "persone_diverse"
            elif {la, lb} == {"A", "A_sistema"}:
                etich = "A_messaggio_vs_sistema"
            elif "nessuna" in (la, lb):
                etich = "persona_vs_nessuna"
            else:
                etich = "altro"
            out.append({"motore": e, "settore": a["sector"], "prompt_id": p, "livello_a": la, "livello_b": lb,
                        "etichetta": etich, "stessa_persona": la == lb and la in PERSONE,
                        "x_query": x, "y_fonti": jac(a["fonti_s"], b["fonti_s"]),
                        "y_brand": jac(a["B"], b["B"]) if a["ha_estrazione"] and b["ha_estrazione"] else NAN,
                        "y_testo": ct, "dt_min": abs((_ts(a) - _ts(b))) / 60})
    return out


def _ts(r) -> float:
    return datetime.fromisoformat(r["timestamp"]).timestamp()


def ancore_diversi(rows, vett: Vettori, rng):
    """s_diversi per motore x settore x misura: coppie di prompt diversi dello stesso settore, livello «nessuna»."""
    out = {}
    for e in ENGINES:
        for s in SECTORS:
            rs = [r for r in rows if r["engine"] == e and r["sector"] == s and r["search"] and r["level"] == "nessuna"
                  and r.get("queries")]
            pairs = [(a, b) for a, b in itertools.combinations(rs, 2) if a["prompt_id"] != b["prompt_id"]]
            if len(pairs) > 4000:
                pairs = [pairs[i] for i in rng.choice(len(pairs), 4000, replace=False)]
            if not pairs:
                continue
            vals = defaultdict(list)
            for a, b in pairs:
                vals["y_fonti"].append(jac(a["fonti_s"], b["fonti_s"]))
                vals["y_brand"].append(jac(a["B"], b["B"]) if a["ha_estrazione"] and b["ha_estrazione"] else NAN)
                ta, tb = vett.testo(a.get("response_text") or ""), vett.testo(b.get("response_text") or "")
                vals["y_testo"].append(float(ta @ tb) if ta is not None and tb is not None else NAN)
                qa = [v for v in (vett.get(q) for q in a["queries"]) if v is not None]
                qb = [v for v in (vett.get(q) for q in b["queries"]) if v is not None]
                if qa and qb:
                    Mab = np.vstack(qa) @ np.vstack(qb).T
                    vals["x_query"].append(float((Mab.max(1).mean() + Mab.max(0).mean()) / 2))
            out[(e, s)] = {k: nanmean(v) for k, v in vals.items()}
    return out


def fasce(xs, n=N_FASCE):
    xs = np.asarray(xs, float)
    q = np.nanpercentile(xs, np.linspace(0, 100, n + 1))
    q[0], q[-1] = -np.inf, np.inf
    return np.clip(np.searchsorted(q, xs, side="right") - 1, 0, n - 1)


def fe_parti(df, ycol: str, xcols: list[str], per_fascia: bool = False) -> dict:
    """Prodotti incrociati per prompt dopo aver tolto la media dentro il prompt (o dentro prompt x fascia).
    Così la stima con effetti fissi e il bootstrap per prompt sono somme pesate di questi pezzi."""
    d = df[[ycol, *xcols, "prompt_id"] + (["fascia"] if per_fascia else [])].dropna()
    if d.empty:
        return {}
    grp = d["prompt_id"].astype(str) + ("|" + d["fascia"].astype(str) if per_fascia else "")
    X = d[xcols].astype(float)
    Xd = (X - X.groupby(grp).transform("mean")).values
    yd = (d[ycol] - d[ycol].groupby(grp).transform("mean")).values
    out = {}
    for p, ix in d.groupby("prompt_id").indices.items():
        out[p] = (Xd[ix].T @ Xd[ix], Xd[ix].T @ yd[ix], len(ix))
    return out


def fe_stima(parti: dict, pesi: dict | None = None) -> float:
    if not parti:
        return NAN
    k = next(iter(parti.values()))[0].shape[0]
    XtX, Xty, n = np.zeros((k, k)), np.zeros(k), 0
    for p, (a, b, m) in parti.items():
        w = 1.0 if pesi is None else pesi.get(p, 0)
        if w:
            XtX += w * a
            Xty += w * b
            n += w * m
    if n < 30 or abs(np.linalg.det(XtX)) < 1e-12:
        return NAN
    return float(np.linalg.solve(XtX, Xty)[0])


def fe_con_ci(df, ycol, xcols, boots, per_fascia=False):
    parti = fe_parti(df, ycol, xcols, per_fascia)
    est = fe_stima(parti)
    lo, hi = ci([fe_stima(parti, w) for w in boots])
    return est, lo, hi


def tl_nonvuoto(r):
    return bool((r.get("response_text") or "").strip())


def preflight(rows, nomi, info, *, senza_testo=False, require_final=True):
    issues = []
    keys = [r["key"] for r in rows]
    if len(keys) != len(set(keys)):
        issues.append("duplicate call keys")
    if any(not tl_nonvuoto(r) for r in rows):
        issues.append("empty answer texts")
    missing = sum(not r["ha_estrazione"] for r in rows)
    if missing:
        issues.append(f"{missing} answers without a valid brand extraction")
    from main_embed import gia_fatti
    done = gia_fatti()
    query_keys = {sha(q) for r in rows for q in r.get("queries", []) if q.strip()}
    text_keys = {sha(r["response_text"]) for r in rows if tl_nonvuoto(r)}
    missing_queries = len(query_keys - done)
    missing_texts = len(text_keys - done)
    if missing_queries:
        issues.append(f"{missing_queries} query embeddings missing")
    if missing_texts and not senza_testo:
        issues.append(f"{missing_texts} answer embeddings missing")
    if require_final:
        if senza_testo:
            issues.append("answer-text similarity omitted")
        if nomi.fonte != "tabella_nomi_v2.csv":
            issues.append("main-study name table v2 missing")
        if nomi.fuori:
            issues.append(f"{len({k for k, _ in nomi.fuori})} names not classified in the name table")
        if not DOMINI.exists():
            issues.append("reviewed brand-to-domain table missing")
        if not NOTORIETA.exists():
            issues.append("brand notoriety data missing")
    counts = Counter((r["engine"], r["sector"], k) for r in rows for k in r["B"])
    eligible = {k for (_, _, k), count in counts.items() if count >= MIN_RISPOSTE}
    measured = set()
    if NOTORIETA.exists():
        for rec in csv.DictReader(NOTORIETA.open()):
            try:
                if math.isfinite(float(rec["volume"])): measured.add(rec["chiave"])
            except (ValueError, KeyError):
                pass
    coverage = {"eligible_P1_brands": len(eligible),
                "with_notoriety": len(eligible & measured),
                "with_attributable_domain": sum(bool(nomi.dominio.get(k)) for k in eligible),
                "unknown_domains_are_missing_not_zero": True}
    return {"issues": issues, "P1_coverage": coverage, "calls": len(rows), "valid_extractions": info["con_estrazione"],
            "missing_query_embeddings": missing_queries, "missing_answer_embeddings": missing_texts}


# ----------------------------------------------------------------------------- main

def main() -> None:
    import pandas as pd
    ap = argparse.ArgumentParser()
    ap.add_argument("--emb", default="bge-m3", choices=["bge-m3", "tfidf-prova"])
    ap.add_argument("--brand", default="estrattore", choices=["estrattore", "regex-prova"])
    ap.add_argument("--boot", type=int, default=1000)
    ap.add_argument("--senza-testo", action="store_true",
                    help="senza la somiglianza del testo delle risposte (se i loro embedding non sono completi)")
    ap.add_argument("--include-system", action="store_true", help="include the set-aside system-prompt arm")
    ap.add_argument("--out", type=Path, default=ROOT / "results/main_centrale")
    ap.add_argument("--preliminary", action="store_true", help="explicitly allow incomplete descriptive results")
    ap.add_argument("--check-only", action="store_true", help="report prerequisites without running the analysis")
    a = ap.parse_args()
    global SENZA_TESTO, OUT, FIG, LEVELS
    OUT = a.out.resolve()
    FIG = OUT / "figure"
    LEVELS = ("nessuna", "A", "B", "C", "A_sistema") if a.include_system else ("nessuna", "A", "B", "C")
    SENZA_TESTO = a.senza_testo
    prova = a.emb != "bge-m3" or a.brand != "estrattore"
    rng = np.random.default_rng(SEED)

    import time as _t
    t0 = _t.monotonic()
    def tappa(nome):
        print(f"[{_t.monotonic() - t0:6.0f} s] {nome}", flush=True)
    rows = load_calls(include_system=a.include_system)
    nomi = Nomi()
    info = attach_brands(rows, nomi, a.brand)
    status = preflight(rows, nomi, info, senza_testo=a.senza_testo, require_final=not a.preliminary)
    if a.check_only:
        print(json.dumps(status, ensure_ascii=False, indent=2))
        return
    if status["issues"] and not a.preliminary:
        raise SystemExit("Cannot produce final results: " + "; ".join(status["issues"]))
    OUT.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(exist_ok=True)
    tappa(f"{len(rows)} chiamate, brand agganciati")
    prompts_by_sector = defaultdict(list)
    for p in sorted({(r["sector"], r["prompt_id"]) for r in rows}):
        prompts_by_sector[p[0]].append(p[1])
    boots = prompt_boot(prompts_by_sector, a.boot, SEED)
    metrics = {"generated_at": datetime.now(timezone.utc).isoformat(), "prova": prova, "emb": a.emb,
               "brand": a.brand, "senza_testo": a.senza_testo, "preliminary": a.preliminary,
               "include_system": a.include_system, "preflight": status, "tabella_nomi": nomi.fonte, "n_chiamate": len(rows),
               "n_con_estrazione": info["con_estrazione"], "copertura_offset": info["copertura"],
               "con_estrazione_per_motore": dict(Counter(r["engine"] for r in rows if r["ha_estrazione"])),
               "nomi_fuori_tabella": len(nomi.fuori),
               "menzioni_fuori_tabella": sum(c for (k, l), c in nomi.fuori.items() if l == "brand")}

    def wcsv(name, recs):
        if not recs:
            return
        fields = list(dict.fromkeys(k for r in recs for k in r))
        with (OUT / name).open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            for r in recs:
                w.writerow({k: (round(v, 5) if isinstance(v, float) else v) for k, v in r.items()})

    # descrittivi e on/off
    desc = []
    for e in ENGINES:
        for srch in (False, True):
            for lv in LEVELS:
                rs = [r for r in rows if r["engine"] == e and r["search"] == srch and r["level"] == lv]
                if not rs:
                    continue
                re_ = [r for r in rs if r["ha_estrazione"]]
                desc.append({"motore": e, "ricerca": "on" if srch else "off", "livello": lv, "n": len(rs),
                             "quota_con_ricerca": nanmean([1.0 if r.get("search_performed") else 0.0 for r in rs]),
                             "query_per_risposta": nanmean([len(r.get("queries") or []) for r in rs]),
                             "fonti_per_risposta": nanmean([len(r["fonti_s"]) for r in rs]),
                             "brand_per_risposta": nanmean([len(r["B"]) for r in re_]),
                             "quota_senza_brand": nanmean([0.0 if r["B"] else 1.0 for r in re_]),
                             "caratteri": nanmean([len(r.get("response_text") or "") for r in rs])})
    wcsv("descrittivi.csv", desc)
    onoff = []
    for e in ENGINES:
        for s in SECTORS:
            per = {}
            for srch in (False, True):
                rs = [r for r in rows if r["engine"] == e and r["sector"] == s and r["search"] == srch and r["ha_estrazione"]]
                per[srch] = rs
            if not per[False] or not per[True]:
                continue
            on_c = Counter(k for r in per[True] for k in r["B"])
            off_c = Counter(k for r in per[False] for k in r["B"])
            union = set(on_c) | set(off_c)
            top_on = {k for k, _ in on_c.most_common(10)}
            top_off = {k for k, _ in off_c.most_common(10)}
            onoff.append({"motore": e, "settore": s,
                          "brand_per_risposta_off": nanmean([len(r["B"]) for r in per[False]]),
                          "brand_per_risposta_on": nanmean([len(r["B"]) for r in per[True]]),
                          "brand_distinti_off": len(off_c), "brand_distinti_on": len(on_c),
                          "gini_off": gini([off_c.get(k, 0) for k in union]),
                          "gini_on": gini([on_c.get(k, 0) for k in union]),
                          "jaccard_top10": jac(top_on, top_off)})
    wcsv("on_off.csv", onoff)

    # P1
    tappa("descrittivi")
    brand_rows, p1_stats, ranks_rows, ha_noto = p1(rows, nomi, info, boots, prompts_by_sector)
    tappa("P1")
    wcsv("P1_brand.csv", brand_rows)
    wcsv("P1_statistiche.csv", p1_stats)
    wcsv("P1_ranghi.csv", ranks_rows)
    metrics["P1_notorieta_disponibile"] = ha_noto
    # Sensitivity analysis: search-available calls restricted to actual searches.
    searched_rows = [r for r in rows if not r["search"] or r.get("search_performed")]
    sb, ss, sr, _ = p1(searched_rows, nomi, info, boots, prompts_by_sector)
    wcsv("P1_searched_brand.csv", sb)
    wcsv("P1_searched_statistiche.csv", ss)
    wcsv("P1_searched_ranghi.csv", sr)
    metrics["P1_searched"] = ss

    # P2 e P3
    vett = Vettori(rows, a.emb)
    tappa("vettori")
    pairs = pd.DataFrame(coppie(rows, vett))
    tappa(f"{len(pairs)} coppie")
    anch = ancore_diversi(rows, vett, rng)
    tappa("ancore")
    p2_rows, p2_fasce, p3_rows, p3_fasce = [], [], [], []
    if not pairs.empty:
        pairs["fascia"] = -1
        for e in ENGINES:
            m = pairs["motore"] == e
            if m.any():
                pairs.loc[m, "fascia"] = fasce(pairs.loc[m, "x_query"].values)
        # repliche della stessa chiamata
        rep = pairs[pairs["etichetta"] == "stessa_cella"]
        rep_cell = rep.groupby(["motore", "settore", "prompt_id", "livello_a"])[["x_query", "y_fonti", "y_brand", "y_testo"]].mean().reset_index()
        wcsv("P2_repliche_per_cella.csv", rep_cell.to_dict("records"))
        s_rep = rep.groupby(["motore", "settore"])[["x_query", "y_fonti", "y_brand", "y_testo"]].mean()
        # normalizzazione
        for y in ("y_fonti", "y_brand", "y_testo"):
            def norm(row, y=y):
                k = (row["motore"], row["settore"])
                if k not in anch or k not in s_rep.index:
                    return NAN
                hi, lo = s_rep.loc[k, y], anch[k].get(y, NAN)
                return (row[y] - lo) / (hi - lo) if hi - lo > 0.02 else NAN
            pairs[y + "_norm"] = pairs.apply(norm, axis=1)
        for e in ENGINES:
            d = pairs[pairs["motore"] == e]
            if d.empty:
                continue
            for y in ("y_fonti", "y_brand", "y_testo", "y_fonti_norm", "y_brand_norm", "y_testo_norm"):
                est, lo, hi = fe_con_ci(d, y, ["x_query"], boots)
                p2_rows.append({"motore": e, "misura": y, "pendenza": est, "lo": lo, "hi": hi, "coppie": int(d[y].notna().sum())})
            for (f,), g in d.groupby(["fascia"]):
                p2_fasce.append({"motore": e, "fascia": int(f), "x_media": g["x_query"].mean(), "coppie": len(g),
                                 **{y: g[y].mean() for y in ("y_fonti", "y_brand", "y_testo", "y_fonti_norm", "y_brand_norm", "y_testo_norm")}})
        # P3
        for e in ENGINES:
            d = pairs[(pairs["motore"] == e) & (pairs["etichetta"].isin(["stessa_cella", "persone_diverse"]))
                      & (pairs["livello_a"].isin(PERSONE)) & (pairs["livello_b"].isin(PERSONE))].copy()
            if d.empty:
                continue
            d["diverse"] = (d["etichetta"] == "persone_diverse").astype(float)
            for nome, xc, pf in (("senza_controllo", ["diverse"], False), ("lineare_x", ["diverse", "x_query"], False),
                                 ("fasce_x", ["diverse"], True)):
                est, lo, hi = fe_con_ci(d, "y_fonti", xc, boots, pf)
                p3_rows.append({"motore": e, "ricerca": "on", "misura": "y_fonti", "modello": nome, "coef_persone_diverse": est,
                                "lo": lo, "hi": hi, "coppie": len(d)})
            for (f, et), g in d.groupby(["fascia", "etichetta"]):
                p3_fasce.append({"motore": e, "fascia": int(f), "etichetta": et, "x_media": g["x_query"].mean(),
                                 "y_fonti": g["y_fonti"].mean(), "coppie": len(g)})
            # canale: A nel messaggio contro A nel system prompt (rispetto ad A-A)
            dd = pairs[(pairs["motore"] == e) & (((pairs["livello_a"] == "A") & (pairs["livello_b"] == "A"))
                                                 | (pairs["etichetta"] == "A_messaggio_vs_sistema"))].copy()
            if a.include_system and not dd.empty:
                dd["diverse"] = (dd["etichetta"] == "A_messaggio_vs_sistema").astype(float)
                for nome, xc in (("senza_controllo", ["diverse"]), ("lineare_x", ["diverse", "x_query"])):
                    est, lo, hi = fe_con_ci(dd, "y_fonti", xc, boots)
                    p3_rows.append({"motore": e, "ricerca": "on", "misura": "y_fonti (A utente vs A sistema)", "modello": nome,
                                    "coef_persone_diverse": est, "lo": lo, "hi": hi, "coppie": len(dd)})
        wcsv("P2_pendenze.csv", p2_rows)
        wcsv("P2_fasce.csv", p2_fasce)
        wcsv("P2_ancore.csv", [{"motore": k[0], "settore": k[1], "tipo": "s_diversi", **v} for k, v in anch.items()]
             + [{"motore": k[0], "settore": k[1], "tipo": "s_repliche", **v} for k, v in s_rep.to_dict("index").items()])
    # P3 a ricerca spenta: Jaccard dei brand fra persone
    off_rows = []
    for e in ENGINES:
        recs = []
        g = defaultdict(list)
        for r in rows:
            if r["engine"] == e and not r["search"] and r["ha_estrazione"] and r["level"] in PERSONE:
                g[r["prompt_id"]].append(r)
        for p, rs in g.items():
            for x, y in itertools.combinations(rs, 2):
                recs.append({"prompt_id": p, "settore": x["sector"], "diverse": float(x["level"] != y["level"]),
                             "y_brand": jac(x["B"], y["B"])})
        d = pd.DataFrame(recs)
        if d.empty:
            continue
        est, lo, hi = fe_con_ci(d, "y_brand", ["diverse"], boots)
        off_rows.append({"motore": e, "ricerca": "off", "misura": "y_brand", "modello": "senza_controllo",
                         "coef_persone_diverse": est, "lo": lo, "hi": hi, "coppie": len(d),
                         "media_stessa": d.loc[d["diverse"] == 0, "y_brand"].mean(),
                         "media_diverse": d.loc[d["diverse"] == 1, "y_brand"].mean()})
    p3_rows += off_rows
    wcsv("P3_coefficienti.csv", p3_rows)
    wcsv("P3_fasce.csv", p3_fasce)
    metrics.update({"P1": p1_stats, "P2": p2_rows, "P3": p3_rows, "on_off": onoff, "descrittivi": desc,
                    "coppie": int(len(pairs))})

    def clean(o):
        if isinstance(o, float) and math.isnan(o):
            return None
        if isinstance(o, (np.floating,)):
            return clean(float(o))
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, dict):
            return {str(k): clean(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)):
            return [clean(v) for v in o]
        return o
    (OUT / "metrics_main.json").write_text(json.dumps(clean(metrics), ensure_ascii=False, indent=1, default=str))
    if not nomi.fuori:
        pass
    wcsv("nomi_fuori_tabella.csv", [{"chiave": k, "lista": l, "volte": c} for (k, l), c in nomi.fuori.most_common()])

    tappa("P2, P3, scrittura")
    import main_figures
    main_figures.disegna(OUT, prova)
    tappa("figure")
    print(json.dumps(clean({k: metrics[k] for k in ("n_chiamate", "n_con_estrazione", "coppie", "nomi_fuori_tabella",
                                                     "menzioni_fuori_tabella", "P1_notorieta_disponibile")}), indent=1))


if __name__ == "__main__":
    main()
