"""Analisi confermativa (protocollo sez. 8). Uso: python3 analisi.py  -> data/part2_conf/risultati/*.json, *.md"""
import json, re, sys, random, statistics as st
from collections import defaultdict
from pathlib import Path
import numpy as np, pandas as pd
from comune import D, DOM, classifica
RIS = D / "risultati"; RIS.mkdir(exist_ok=True)
MOT = [m for m in ("gpt", "deepseek", "perplexity", "gemini_vertex") if (D / f"studio_{m}.jsonl").exists()]
def carica():
    rows = []
    for m in MOT:
        seen = {}
        files = [D / f"studio_{m}.jsonl"] + ([D / f"studio_{m}_b.jsonl"] if (D / f"studio_{m}_b.jsonl").exists() else [])
        for l in (x for f in files for x in open(f)):
            r = json.loads(l)
            if r.get("error"): continue
            cl = classifica(r.get("response_text"), r["ordine"])
            if cl is None: continue
            seen[r["call_id"]] = dict(qid=r["qid"], ident=r["ident"], testo=r["testo"], motore=m, j=r["j"], rip=r["rip"],
                                      pos=cl.index(r["bersaglio"]) + 1, bpos=r["ordine"].index(r["bersaglio"]) + 1,
                                      settore=DOM[r["qid"]]["settore"], primo=int(cl[0] == r["bersaglio"]))
        rows += list(seen.values())
    df = pd.DataFrame(rows); df["score"] = 6 - df["pos"]
    return df
CONTRASTI = {
 "H1 identità (REALE − INVENTATO)": [("REALE", None, 1), ("INVENTATO", None, -1)],
 "H2a prodotto (REALE − BRAND)": [("REALE", None, 1), ("BRAND", None, -1)],
 "H2b notorietà (BRAND − MINORE)": [("BRAND", None, 1), ("MINORE", None, -1)],
 "H2c nome inventato (MINORE − INVENTATO)": [("MINORE", None, 1), ("INVENTATO", None, -1)],
 "H3 R1 struttura (R1 − ORIG)": [(None, "R1", 1), (None, "ORIG", -1)],
 "H3 R2 dichiarativa (R2 − ORIG)": [(None, "R2", 1), (None, "ORIG", -1)],
 "H3 contenuto medio ((R1+R2)/2 − ORIG)": [(None, "R1", .5), (None, "R2", .5), (None, "ORIG", -1)],
}
def cell_means(df):
    return df.groupby(["motore", "qid", "ident", "testo"])["score"].mean()
def contrasto(cm, spec, qids, motori):
    """media sui motori della media sulle domande del contrasto (celle bilanciate: media marginale)."""
    vals = []
    for m in motori:
        per_q = []
        for q in qids:
            try:
                c = cm.loc[(m, q)]
            except KeyError:
                continue
            tot = 0
            for ident, testo, w in spec:
                sel = c
                if ident: sel = sel[sel.index.get_level_values(0) == ident]
                if testo: sel = sel[sel.index.get_level_values(1) == testo]
                tot += w * sel.mean()
            per_q.append(tot)
        if per_q: vals.append(np.mean(per_q))
    return float(np.mean(vals)) if vals else float("nan")
def stima(df, motori=None, qids=None, B=1000, seed=20261019):
    motori = motori or sorted(df.motore.unique()); qids = qids or sorted(df.qid.unique())
    cm = cell_means(df)
    rng = np.random.default_rng(seed)
    punti = {k: contrasto(cm, s, qids, motori) for k, s in CONTRASTI.items()}
    punti["H4 |identità| − |contenuto|"] = abs(punti["H1 identità (REALE − INVENTATO)"]) - abs(punti["H3 contenuto medio ((R1+R2)/2 − ORIG)"])
    boot = defaultdict(list)
    for _ in range(B):
        qb = list(rng.choice(qids, size=len(qids), replace=True))
        v = {k: contrasto(cm, s, qb, motori) for k, s in CONTRASTI.items()}
        v["H4 |identità| − |contenuto|"] = abs(v["H1 identità (REALE − INVENTATO)"]) - abs(v["H3 contenuto medio ((R1+R2)/2 − ORIG)"])
        for k, x in v.items(): boot[k].append(x)
    out = {}
    for k, p in punti.items():
        b = np.array(boot[k]); lo, hi = np.percentile(b, [2.5, 97.5])
        pval = 2 * min((b <= 0).mean(), (b >= 0).mean())
        out[k] = dict(stima=round(p, 3), ic95=[round(lo, 3), round(hi, 3)], p_boot=round(max(pval, 1 / B), 4))
    return out
def holm(res, keys):
    ps = sorted((res[k]["p_boot"], k) for k in keys); m = len(ps); prev = 0
    for i, (p, k) in enumerate(ps):
        adj = min(1, max(prev, (m - i) * p)); res[k]["p_holm"] = round(adj, 4); prev = adj
def misto(df):
    import statsmodels.formula.api as smf
    d = df.copy(); d["qo"] = d["qid"] + "_" + d["j"].astype(str)
    md = smf.mixedlm("score ~ C(ident, Treatment('INVENTATO')) * C(testo, Treatment('ORIG')) + C(motore)", d,
                     groups=d["qid"], re_formula="1", vc_formula={"qo": "0 + C(qo)"})
    f = md.fit(method="lbfgs", reml=True)
    return {k: dict(coef=round(v, 3), se=round(f.bse[k], 3), p=round(f.pvalues[k], 4)) for k, v in f.params.items() if k != "Group Var"}
def ordinale(df):
    from statsmodels.miscmodels.ordinal_model import OrderedModel
    d = pd.get_dummies(df[["ident", "testo", "motore", "qid"]], drop_first=False).astype(float)
    X = d.drop(columns=["ident_INVENTATO", "testo_ORIG", f"motore_{sorted(df.motore.unique())[0]}", f"qid_{sorted(df.qid.unique())[0]}"])
    f = OrderedModel(df["score"].astype(int), X, distr="logit").fit(method="bfgs", disp=False, maxiter=2000)
    return {k: dict(coef=round(f.params[k], 3), se=round(f.bse[k], 3), p=round(f.pvalues[k], 4)) for k in X.columns if k.startswith(("ident", "testo"))}
def tabella(df):
    t = df.groupby(["ident", "testo", "motore"])["pos"].mean().unstack("motore").round(2)
    return t.reindex(pd.MultiIndex.from_product([["REALE", "BRAND", "MINORE", "INVENTATO"], ["ORIG", "R1", "R2"]]))
def main():
    df = carica()
    res = {"n_risposte_valide": int(len(df)), "per_motore": df.motore.value_counts().to_dict(), "motori": MOT}
    res["primaria"] = stima(df); holm(res["primaria"], [k for k in res["primaria"] if k.startswith(("H1", "H2", "H3 R", "H4"))])
    res["per_motore"] = {m: stima(df[df.motore == m], motori=[m], B=300) for m in df.motore.unique()}
    res["per_settore"] = {s: stima_veloce(df[df.settore == s], B=2000) for s in df.settore.unique()}
    # interazione H5: contenuto medio per livello d'identità
    res["H5_contenuto_per_identita"] = {}
    for idn in ["REALE", "BRAND", "MINORE", "INVENTATO"]:
        sub = df[df.ident == idn]
        cm = cell_means(sub)
        res["H5_contenuto_per_identita"][idn] = round(contrasto(cm, CONTRASTI["H3 contenuto medio ((R1+R2)/2 − ORIG)"], sorted(df.qid.unique()), sorted(df.motore.unique())), 3)
    # per domanda: effetto identità e contenuto
    cm = cell_means(df)
    res["per_domanda"] = {q: {"identita": round(contrasto(cm, CONTRASTI["H1 identità (REALE − INVENTATO)"], [q], sorted(df.motore.unique())), 2),
                              "contenuto": round(contrasto(cm, CONTRASTI["H3 contenuto medio ((R1+R2)/2 − ORIG)"], [q], sorted(df.motore.unique())), 2),
                              "pos_reale_orig": round(df[(df.qid == q) & (df.ident == "REALE") & (df.testo == "ORIG")].pos.mean(), 2)} for q in sorted(df.qid.unique())}
    # robustezza: senza domande con REALE-ORIG sempre 1 o 5
    est = [q for q, v in res["per_domanda"].items() if v["pos_reale_orig"] in (1.0, 5.0)]
    res["robustezza_esclusioni"] = {"escluse": est, "stime": stima(df[~df.qid.isin(est)], B=300) if est else "nessuna esclusione"}
    try: res["misto"] = misto(df)
    except Exception as e: res["misto"] = f"errore: {e}"
    try: res["ordinale"] = ordinale(df)
    except Exception as e: res["ordinale"] = f"errore: {e}"
    # posizione nel contesto (effetto primato)
    res["posizione_nel_contesto"] = df.groupby("bpos")["pos"].mean().round(2).to_dict()
    # moderatore familiarità
    sc = json.load(open(D / "scelte_finali.json"))
    res["familiarita"] = {q: dict(bersaglio=sc["familiarita_bersaglio"][q], minore=sc["familiarita_minore"][q], effetto_identita=res["per_domanda"][q]["identita"]) for q in sc["bersaglio"] if q in res["per_domanda"]}
    xs = [v["bersaglio"] for v in res["familiarita"].values()]; ys = [v["effetto_identita"] for v in res["familiarita"].values()]
    res["corr_familiarita_effetto"] = round(float(np.corrcoef(xs, ys)[0, 1]), 3) if len(set(xs)) > 1 else None
    json.dump(res, open(RIS / "risultati.json", "w"), ensure_ascii=False, indent=1, default=str)
    tabella(df).to_csv(RIS / "posizione_media_per_cella.csv")
    df.to_csv(RIS / "dati_lunghi.csv", index=False)
    print(json.dumps(res["primaria"], ensure_ascii=False, indent=1)); print(tabella(df))
def main_parte(p):
    df = carica(); path = RIS / "risultati.json"
    res = json.load(open(path)) if (p == 2 and path.exists()) else {}
    if p == 1:
        res = {"n_risposte_valide": int(len(df)), "n_per_motore": df.motore.value_counts().to_dict(), "motori": MOT}
        res["primaria"] = stima(df); holm(res["primaria"], [k for k in res["primaria"] if k.startswith(("H1", "H2", "H3 R", "H4"))])
        res["per_motore"] = {m: stima(df[df.motore == m], motori=[m], B=300) for m in df.motore.unique()}
    else:
        res["per_settore"] = {s: stima_veloce(df[df.settore == s], B=2000) for s in df.settore.unique()}
        res["H5_contenuto_per_identita"] = {}
        for idn in ["REALE", "BRAND", "MINORE", "INVENTATO"]:
            cm = cell_means(df[df.ident == idn])
            res["H5_contenuto_per_identita"][idn] = round(contrasto(cm, CONTRASTI["H3 contenuto medio ((R1+R2)/2 − ORIG)"], sorted(df.qid.unique()), sorted(df.motore.unique())), 3)
        cm = cell_means(df); M = sorted(df.motore.unique())
        res["per_domanda"] = {q: {k.split(" (")[0]: round(contrasto(cm, sp, [q], M), 2) for k, sp in CONTRASTI.items()} |
                              {"pos_reale_orig": round(df[(df.qid == q) & (df.ident == "REALE") & (df.testo == "ORIG")].pos.mean(), 2)} for q in sorted(df.qid.unique())}
        est = [q for q, v in res["per_domanda"].items() if v["pos_reale_orig"] in (1.0, 5.0)]
        res["robustezza_esclusioni"] = {"escluse": est}
        try: res["misto"] = misto(df)
        except Exception as e: res["misto"] = f"errore: {e}"
        try: res["ordinale"] = ordinale(df)
        except Exception as e: res["ordinale"] = f"errore: {e}"
        res["posizione_nel_contesto"] = {int(k): v for k, v in df.groupby("bpos")["pos"].mean().round(2).to_dict().items()}
        sc = json.load(open(D / "scelte_finali.json"))
        fam = {q: dict(bersaglio=sc["familiarita_bersaglio"][q], minore=sc["familiarita_minore"][q],
                       H1=res["per_domanda"][q]["H1 identità"], H2b=res["per_domanda"][q]["H2b notorietà"]) for q in res["per_domanda"]}
        res["familiarita"] = fam
        gap = [v["bersaglio"] - v["minore"] for v in fam.values()]; h2b = [v["H2b"] for v in fam.values()]
        res["corr_gap_familiarita_H2b"] = round(float(np.corrcoef(gap, h2b)[0, 1]), 3)
        res["corr_familiarita_bersaglio_H1"] = round(float(np.corrcoef([v["bersaglio"] for v in fam.values()], [v["H1"] for v in fam.values()])[0, 1]), 3)
        res["primo_posto_quota"] = df.groupby("ident")["primo"].mean().round(3).to_dict()
        tabella(df).to_csv(RIS / "posizione_media_per_cella.csv"); df.to_csv(RIS / "dati_lunghi.csv", index=False)
    json.dump(res, open(path, "w"), ensure_ascii=False, indent=1, default=str)
    print("parte", p, "ok")

if __name__ == "__main__":
    main_parte(int(sys.argv[1]) if len(sys.argv) > 1 else 1)


# --- versione veloce (stessa definizione dei contrasti): matrice motore × domanda dei contrasti, poi bootstrap ---
ID4 = ["REALE", "BRAND", "MINORE", "INVENTATO"]; TX3 = ["ORIG", "R1", "R2"]
def matrice(df, spec):
    M = sorted(df.motore.unique()); Q = sorted(df.qid.unique())
    cm = df.groupby(["motore", "qid", "ident", "testo"])["score"].mean()
    A = np.full((len(M), len(Q)), np.nan)
    for i, m in enumerate(M):
        for k, q in enumerate(Q):
            tot = 0
            for ident, testo, w in spec:
                vals = [cm.get((m, q, a, b), np.nan) for a in ([ident] if ident else ID4) for b in ([testo] if testo else TX3)]
                tot += w * np.nanmean(vals)
            A[i, k] = tot
    return A, M, Q
def stima_veloce(df, B=2000, seed=20261019):
    mats = {k: matrice(df, s)[0] for k, s in CONTRASTI.items()}
    k1, k3 = "H1 identità (REALE − INVENTATO)", "H3 contenuto medio ((R1+R2)/2 − ORIG)"
    nq = next(iter(mats.values())).shape[1]; rng = np.random.default_rng(seed)
    idx = rng.integers(0, nq, size=(B, nq))
    out = {}
    def f(A, I): return np.nanmean(np.nanmean(A[:, I], axis=-1), axis=0) if I.ndim == 1 else np.nanmean(np.nanmean(A[:, I], axis=2), axis=0)
    allq = np.arange(nq)
    for k, A in list(mats.items()) + [("H4 |identità| − |contenuto|", None)]:
        if A is None:
            p = abs(f(mats[k1], allq)) - abs(f(mats[k3], allq)); b = np.abs(f(mats[k1], idx)) - np.abs(f(mats[k3], idx))
        else:
            p = f(A, allq); b = f(A, idx)
        lo, hi = np.percentile(b, [2.5, 97.5]); pv = 2 * min((b <= 0).mean(), (b >= 0).mean())
        out[k] = dict(stima=round(float(p), 3), ic95=[round(float(lo), 3), round(float(hi), 3)], p_boot=round(float(max(pv, 1 / B)), 4))
    return out
