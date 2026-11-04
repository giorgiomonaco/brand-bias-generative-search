"""Analisi normalizzata menzione/citazione (richiesta di co-author, meeting 29/10/2026).
Ricerca on, brand con dominio noto e popolarità (gli stessi della Fig. 3). Dentro ogni motore × settore il tasso di
menzione e quello di citazione di ogni brand sono divisi per la media del proprio tasso nella cella: 1 = brand medio.
Così la differenza di livello fra menzione e citazione (GPT menziona circa il doppio di quanto cita) non entra nel
confronto. Pendenza = OLS del tasso normalizzato su log10 popolarità, effetti fissi motore × settore; differenza
menzione − citazione; IC95 da 2.000 ricampionamenti dei brand dentro cella (seed 20261027, come Tab. A search)."""
import json
import numpy as np, pandas as pd
from style import *

B = brands()
B = B[B.ricerca == "on"].dropna(subset=["notorieta_log10", "tasso_citazione"]).copy()
B["cella"] = B.motore + "|" + B.settore
for col, out in (("tasso_menzione", "m"), ("tasso_citazione", "c")):
    mu = B.groupby("cella")[col].transform("mean")
    B[out] = B[col] / mu
B = B[np.isfinite(B.c) & np.isfinite(B.m)]
B["x"] = B.notorieta_log10 - B.groupby("cella").notorieta_log10.transform("mean")
for k in ("m", "c"):
    B[k + "_c"] = B[k] - B.groupby("cella")[k].transform("mean")

def slope(g, k):
    x = g.x.values; y = g[k + "_c"].values
    return float((x * y).sum() / (x * x).sum())

rng = np.random.default_rng(20261027); NB = 2000
def stima(g):
    idx = [np.flatnonzero(g.cella.values == c) for c in g.cella.unique()]
    est = {k: slope(g, k) for k in ("m", "c")}; est["d"] = est["m"] - est["c"]
    bs = {k: [] for k in ("m", "c", "d")}
    for _ in range(NB):
        s = np.concatenate([rng.choice(i, len(i)) for i in idx]); h = g.iloc[s]
        hm = h.copy()
        for k in ("m", "c"):
            hm[k + "_c"] = hm[k] - hm.groupby("cella")[k].transform("mean")
        hm["x"] = hm.notorieta_log10 - hm.groupby("cella").notorieta_log10.transform("mean")
        a, b = slope(hm, "m"), slope(hm, "c"); bs["m"].append(a); bs["c"].append(b); bs["d"].append(a - b)
    return {k: dict(stima=round(est[k], 3), ic95=[round(float(np.percentile(bs[k], 2.5)), 3), round(float(np.percentile(bs[k], 97.5)), 3)]) for k in est} | {"n_brand": int(len(g))}

res = {e: stima(B[B.motore == e]) for e in E}
res["tutti"] = stima(B)
for (e, s), g in B.groupby(["motore", "settore"]):
    res[f"{e}|{s}"] = {k: round(v, 3) for k, v in (("m", slope(g, "m")), ("c", slope(g, "c")))} | {"n_brand": int(len(g))}
(FIG / "figA_mention_citation_normalized.json").write_text(json.dumps(res, indent=1))
for k in ["tutti"] + E:
    r = res[k]; print(f"{k:12s} menzione {r['m']['stima']:+.2f} {r['m']['ic95']}  citazione {r['c']['stima']:+.2f} {r['c']['ic95']}  differenza {r['d']['stima']:+.2f} {r['d']['ic95']}  n={r['n_brand']}")

# figura: quintili come la Fig. 3, tassi normalizzati
fig, axs = plt.subplots(1, 3, figsize=(WF, 1.75), sharey=True, sharex=True)
rows = []
for ax, e in zip(axs, E):
    g = B[B.motore == e].copy(); g["q"] = g.groupby("settore").notorieta_log10.transform(quintile)
    m = g.groupby("q")[["m", "c"]].mean(); se = g.groupby("q")[["m", "c"]].sem()
    for col, c, lab in (("m", MEN, MENTION), ("c", CIT, CITATION)):
        ax.errorbar(m.index, m[col], yerr=1.96 * se[col], color=c, marker="o", ms=3.5, lw=1.6, capsize=2, label=lab, alpha=.75)
    ax.axhline(1, color="#888888", lw=.8, ls="--", zorder=0)
    for q in m.index: rows.append(dict(engine=e, quintile=q, mention=round(m.loc[q, "m"], 2), citation=round(m.loc[q, "c"], 2)))
    ax.set_title(EL[e]); ax.set_xticks(range(1, NQ + 1), Q_LABELS); few_ticks(ax, 4)
axs[0].set_ylabel("rate relative to the\nengine-sector mean")
h, l = axs[0].get_legend_handles_labels()
RL = 0.836
fig.legend(h, l, ncol=1, loc="center left", bbox_to_anchor=(RL, .5), handlelength=1.4, frameon=False)
fig.tight_layout(w_pad=1.3, rect=(0, 0, RL, 1))
letters(axs)
save(fig, "figA_mention_citation_normalized")
pd.DataFrame(rows).to_csv(FIG / "figA_mention_citation_normalized.csv", index=False)
print(pd.DataFrame(rows).to_string(index=False))
