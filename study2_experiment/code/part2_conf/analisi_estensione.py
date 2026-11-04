import json, re, sys, numpy as np, pandas as pd
from scipy import stats
from comune import D, DOM, classifica
from estensione import OUT, SUPERIORI
import controlli
def carica():
    rows = []
    for f in OUT.glob("est_*.jsonl"):
        seen = {}
        for l in open(f):
            r = json.loads(l)
            if r.get("error"): continue
            cl = classifica(r.get("response_text"), r["ordine"])
            if cl is None: continue
            seen[r["call_id"]] = dict(qid=r["qid"], ident=r["ident"], motore=r["motore"], j=r["j"], rip=r["rip"], pos=cl.index(r["bersaglio"]) + 1)
        rows += seen.values()
    df = pd.DataFrame(rows); df["score"] = 6 - df["pos"]; return df
def contrasti(df):
    cm = df.groupby(["motore", "qid", "ident"])["score"].mean().unstack("ident")
    cm["SUP_BRAND"] = cm["SUPERIORE"] - cm["BRAND"]; cm["MIN_BRAND"] = cm["MINORE"] - cm["BRAND"]
    cm["INCOERENZA"] = -(cm["SUP_BRAND"] + cm["MIN_BRAND"]) / 2
    return cm
def riassunto(cm, col, B=4000, seed=1):
    perq = cm[col].groupby("qid").mean(); q = perq.index.values; rng = np.random.default_rng(seed)
    pt = cm[col].groupby("motore").apply(lambda s: s.mean()).mean()
    boots = []
    for _ in range(B):
        qb = rng.choice(q, len(q)); boots.append(np.mean([cm[col].xs(m, level="motore").reindex(qb).mean() for m in cm.index.get_level_values(0).unique()]))
    se = perq.std(ddof=1) / np.sqrt(len(perq)); t = stats.t.ppf(.975, len(perq) - 1)
    return dict(stima=round(float(pt), 3), ic95_boot=[round(float(x), 3) for x in np.percentile(boots, [2.5, 97.5])],
                ic95_t=[round(float(perq.mean() - t * se), 3), round(float(perq.mean() + t * se), 3)],
                p_t=round(float(2 * stats.t.sf(abs(perq.mean() / se), len(perq) - 1)), 4), positivi=f"{int((perq > 0).sum())}/{len(perq)}")
def controlli_df():
    rows = []
    for f in OUT.glob("controlli_*.jsonl"):
        seen = {}
        for l in open(f):
            r = json.loads(l); v = controlli.valore(r)
            if v is not None: seen[r["call_id"]] = {**{k: r.get(k) for k in ("tipo", "qid", "motore", "rip", "ruolo", "marchio")}, "valore": v}
        rows += seen.values()
    return pd.DataFrame(rows)
def riconosciuto(r):
    alias = {"Bravo": ["bravo", "alpitour"], "AXA": ["axa"], "Redion": ["redion", "europ assistance"], "WeRoad": ["weroad"]}
    keys = alias.get(r["marchio"], [r["marchio"].lower().split()[0]])
    return any(k in str(r["valore"]).lower() for k in keys)
if __name__ == "__main__":
    df = carica(); res = {"n": df.groupby("motore").size().to_dict()}
    cm = contrasti(df)
    for col in ("SUP_BRAND", "MIN_BRAND", "INCOERENZA"):
        res[col] = riassunto(cm, col)
        res[col + "_per_motore"] = {m: round(float(cm[col].xs(m, level="motore").mean()), 3) for m in cm.index.get_level_values(0).unique()}
    res["per_domanda"] = cm[["SUP_BRAND", "MIN_BRAND"]].groupby("qid").mean().round(2).to_dict("index")
    c = controlli_df()
    if len(c):
        ric = c[c.tipo == "riconoscimento"].copy(); ric["ok"] = ric.apply(riconosciuto, axis=1)
        res["riconoscimento_quota"] = round(float(ric.ok.mean()), 3)
        res["riconoscimento_per_domanda"] = ric.groupby("qid").ok.mean().round(2).to_dict()
        res["riconoscimento_per_motore"] = ric.groupby("motore").ok.mean().round(2).to_dict()
        coe = c[c.tipo == "coerenza"].copy(); coe["valore"] = coe.valore.astype(float)
        res["coerenza_media_per_ruolo"] = coe.groupby("ruolo").valore.mean().round(2).to_dict()
        piv = coe.groupby(["qid", "ruolo"]).valore.mean().unstack()
        res["coerenza_per_domanda"] = piv.round(2).to_dict("index")
        pq = cm[["SUP_BRAND", "MIN_BRAND"]].groupby("qid").mean()
        x = list(piv["superiore"] - piv["proprio"]) + list(piv["minore"] - piv["proprio"]); y = list(pq.loc[piv.index, "SUP_BRAND"]) + list(pq.loc[piv.index, "MIN_BRAND"])
        res["corr_diff_coerenza_diff_posizione"] = round(float(np.corrcoef(x, y)[0, 1]), 3)
        rq = ric.groupby("qid").ok.mean(); hi = rq[rq >= .5].index; lo = rq[rq < .5].index
        res["SUP_BRAND_testo_riconosciuto"] = dict(n=len(hi), stima=round(float(pq.loc[pq.index.isin(hi), "SUP_BRAND"].mean()), 3) if len(hi) else None)
        res["SUP_BRAND_testo_non_riconosciuto"] = dict(n=len(lo), stima=round(float(pq.loc[pq.index.isin(lo), "SUP_BRAND"].mean()), 3) if len(lo) else None)
    json.dump(res, open(D / "risultati" / "risultati_estensione.json", "w"), ensure_ascii=False, indent=1, default=str)
    print(json.dumps(res, ensure_ascii=False, indent=1, default=str))
