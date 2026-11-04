"""GPT, prima azione di ricerca come indicatore di ciò che il modello conosce già (incontro del 23/10).
Per ogni brand nominato in una risposta di GPT con ricerca (brand H1 con notorietà), dove compare per la prima volta
il suo nome nelle azioni di ricerca: nella prima azione (scritta prima di qualsiasi risultato), solo in azioni
successive, in nessuna. Quote per quintile di notorietà dentro settore. Stessa regola di riconoscimento dei nomi
dell'analisi del 20/10 (alias univoci, alias_lookup.json) e stesse azioni (gpt_azioni.json).
Intervalli: 1.000 ricampionamenti dei prompt dentro settore (seme 20261014).
Test: differenza fra quintile più noto e meno noto nella quota «prima azione», p bootstrap, Benjamini-Hochberg sui 4 settori."""
import json
import re
import unicodedata
from collections import Counter
import numpy as np
import pandas as pd
from statsmodels.stats.multitest import multipletests
from style import *

LOOK = json.load(open(INP / "alias_lookup.json"))
TR = {}
for sector, aliases in LOOK["strict"].items():
    trie = {}
    for surface, roots in aliases.items():
        node = trie
        for w_ in surface.split():
            node = node.setdefault(w_, {})
        node[None] = roots
    TR[sector] = trie


def norm(t):
    s = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower().replace("&", " and ")
    return re.sub(r"\s+", " ", re.sub("[^a-z0-9 ]", " ", s)).strip()


def match(text, sector):
    words = norm(text).split()
    good = set()
    i = 0
    trie = TR[sector]
    while i < len(words):
        node = trie
        j = i
        best = None
        while j < len(words) and words[j] in node:
            node = node[words[j]]
            j += 1
            if None in node:
                best = (j, node[None])
        if best is None:
            i += 1
        else:
            good.update(best[1])
            i = best[0]
    return good


A = json.load(open(INP / "gpt_azioni.json"))
R = rows()
B = brands()
NOT = {(r.settore, r.chiave): r.notorieta_log10 for r in B[(B.motore == "gpt") & (B.ricerca == "on")].itertuples()
       if r.notorieta_log10 == r.notorieta_log10}
G = R[(R.engine == "gpt") & R.search]
rec = []
for r in G.itertuples():
    acts = A.get(r.key) or []
    if not acts:
        continue
    first = {k for q in acts[0] for k in match(q, r.sector)}
    later = {k for qs in acts[1:] for q in qs for k in match(q, r.sector)} - first
    for k in set(r.B):
        if (r.sector, k) in NOT:
            rec.append((r.sector, r.prompt_id, k, "first" if k in first else ("later" if k in later else "none"),
                        NOT[(r.sector, k)]))
D = pd.DataFrame(rec, columns=["settore", "prompt_id", "chiave", "fase", "notorieta"])
print(D.groupby(["settore", "fase"]).notorieta.agg(["count", "mean"]).round(3))  # controllo con N10

# quintili sui brand (non sulle menzioni), dentro settore
bq = (B[(B.motore == "gpt") & (B.ricerca == "on")].dropna(subset=["notorieta_log10"])
      .assign(q=lambda d: d.groupby("settore").notorieta_log10.transform(quintile)))
QMAP = {(r.settore, r.chiave): r.q for r in bq.itertuples()}
D["q"] = [QMAP[(s, k)] for s, k in zip(D.settore, D.chiave)]
for f in ("first", "later", "none"):
    D[f] = (D.fase == f).astype(float)

rng = np.random.default_rng(SEED)
res, tests = {}, []
for s in S:
    g = D[D.settore == s]
    prompts = sorted(g.prompt_id.unique())
    by_p = {p: gg for p, gg in g.groupby("prompt_id")}

    def shares(gg):
        m = gg.groupby("q")[["first", "later"]].mean().reindex(range(1, NQ + 1))
        return m["first"].values, m["later"].values

    f0, l0 = shares(g)
    bf, bl = [], []
    for _ in range(1000):
        draw = pd.concat([by_p[prompts[i]] for i in rng.integers(0, len(prompts), len(prompts))])
        f, l_ = shares(draw)
        bf.append(f)
        bl.append(l_)
    bf, bl = np.array(bf), np.array(bl)
    res[s] = (f0, l0, bf, bl, g.groupby("q").size().reindex(range(1, NQ + 1)).values)
    d = bf[:, -1] - bf[:, 0]
    d = d[~np.isnan(d)]
    p = float(min(1, 2 * min((d <= 0).mean(), (d >= 0).mean())))
    tests.append(dict(sector=s, first_q1=f0[0], first_qtop=f0[-1], diff=f0[-1] - f0[0], lo=np.percentile(d, 2.5),
                      hi=np.percentile(d, 97.5), p=p, n_mentions=len(g)))
T = pd.DataFrame(tests)
T["p_bh"] = multipletests(T.p, method="fdr_bh")[1]
print(T.round(3).to_string())
T.round(4).to_csv(FIG / "fig4_first_query_test.csv", index=False)

FIRST, LATER = "#1f4e8c", "#8fb3e0"
QL = ["l.p."] + [""] * (NQ - 2) + ["m.p."]  # 3/11: etichette brevi, spiegate in didascalia
fig, axs = plt.subplots(1, 4, figsize=(WF, 1.45), sharey=True, sharex=True)
for ax, s in zip(axs, S):
    f0, l0, bf, bl, n = res[s]
    for v, b, c, lab, off in ((f0, bf, FIRST, "first search", -0.06), (l0, bl, LATER, "later searches only", 0.06)):
        lo, hi = np.nanpercentile(b, [2.5, 97.5], axis=0)
        ax.errorbar(np.arange(1, NQ + 1) + off, 100 * v, yerr=[100 * (v - lo), 100 * (hi - v)], color=c, marker="o",
                    ms=3.2, lw=1.5, capsize=1.8, label=lab, alpha=.75)
    t = T[T.sector == s].iloc[0]
    ax.set_title(SL[s] + ("*" if t.p_bh < 0.05 else ""))
    ax.set_xticks(range(1, NQ + 1), QL)
    ax.set_xlim(0.4, NQ + 0.6)
    ax.set_ylim(0, 100)
    few_ticks(ax, 3)
axs[0].set_ylabel("share (%)")
h, lab = axs[0].get_legend_handles_labels()
RL = 0.80
fig.legend(h, lab, ncol=1, loc="center left", bbox_to_anchor=(RL, .5), handlelength=1.4, frameon=False)
fig.tight_layout(w_pad=1.2, rect=(0, 0, RL, 1))
save(fig, "fig4_first_query_quintiles")
