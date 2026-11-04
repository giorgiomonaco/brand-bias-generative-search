"""Persona e peso della notorietà nello stile dell'opzione B (incontro del 23/10).
Quota di risposte che menzionano il brand, media per quintile di notorietà (dentro motore x settore), per livello di persona.
Ricerca spenta e disponibile insieme, brand dell'insieme H1 con notorietà, come la Fig. 17 della tesi.
Intervalli: 1.000 ricampionamenti dei prompt (stratificati per settore, seme 20261014), appaiati fra i livelli.
Gap = quintile più noto meno quintile meno noto; p bootstrap della differenza rispetto a nessuna persona."""
from collections import Counter
import numpy as np
import pandas as pd
from style import *

R = rows()
R = R[R.ha_estrazione & (R.level != "A_sistema")]
PB = brands()
LV = ["nessuna", "A", "B", "C"]

PBS = {s: sorted(R[R.sector == s].prompt_id.unique()) for s in S}
rng = np.random.default_rng(SEED)
BOOTS = []
for _ in range(1000):
    w = Counter()
    for s, ps in PBS.items():
        for i in rng.integers(0, len(ps), len(ps)):
            w[ps[i]] += 1
    BOOTS.append(w)


def counts(sub, u):
    idx = {k: i for i, k in enumerate(u)}
    out = {}
    for p, g in sub.groupby("prompt_id"):
        c = np.zeros(len(u))
        for Bs in g.B:
            for k in Bs:
                if k in idx:
                    c[idx[k]] += 1
        out[p] = (len(g), c)
    return out


def rate(parts, w=None):
    n, c = 0, 0
    for p, (n_p, c_p) in parts.items():
        ww = 1 if w is None else w.get(p, 0)
        if ww:
            n += ww * n_p
            c = c + ww * c_p
    return 100 * c / n


# per motore: tasso per brand, livello e ricampionamento; poi medie per quintile
res = {}
for e in E:
    blocks = {l: [] for l in LV}
    bblocks = {l: [] for l in LV}
    qs = []
    secs = []
    for s in S:
        u0 = PB[(PB.motore == e) & (PB.settore == s) & (PB.ricerca == "off")].dropna(subset=["notorieta_log10"])
        u = list(u0.chiave)
        q = quintile(u0.notorieta_log10).to_numpy()
        qs.append(q)
        secs += [s] * len(u)
        sub = R[(R.engine == e) & (R.sector == s)]
        for l in LV:
            P = counts(sub[sub.level == l], u)
            blocks[l].append(rate(P))
            bblocks[l].append(np.array([rate(P, w) for w in BOOTS]))
    q = np.concatenate(qs)
    y = {l: np.concatenate(blocks[l]) for l in LV}
    yb = {l: np.concatenate(bblocks[l], axis=1) for l in LV}  # 1000 x brand
    y["mean"] = np.mean([y[l] for l in "ABC"], axis=0)
    yb["mean"] = np.mean([yb[l] for l in "ABC"], axis=0)
    secs = np.array(secs)
    res[e] = dict(q=q, y=y, yb=yb, secs=secs)


def qmeans(v, q):
    return np.array([np.nanmean(v[..., q == k], axis=-1) for k in range(1, NQ + 1)]).T


# etichette della legenda su due righe (legenda a destra, call del 2/11)
LEG2 = {"nessuna": "No persona\ncontext", "A": "Baseline\npersona (A)", "B": "Price\nvariant (B)", "C": "Profile\nvariant (C)"}


def draw(levels, name, title_note=None):
    fig, axs = plt.subplots(1, 3, figsize=(WF, 1.75), sharey=True, sharex=True)
    for ax, e in zip(axs, E):
        r = res[e]
        for l in levels:
            mu = qmeans(r["y"][l], r["q"])
            bb = qmeans(r["yb"][l], r["q"])
            lo, hi = np.percentile(bb, [2.5, 97.5], axis=0)
            off = {"nessuna": -0.12, "mean": 0.12, "A": -0.04, "B": 0.04, "C": 0.12}[l] if len(levels) > 2 else {"nessuna": -0.06}.get(l, 0.06)
            ax.errorbar(np.arange(1, NQ + 1) + off, mu, yerr=[mu - lo, hi - mu], color=PCOL[l], marker="o", ms=3.2,
                        lw=1.5, capsize=1.8, label=LEG2.get(l, "Persona\n(mean of three)"), alpha=.75)
        ax.set_title(EL[e])
        ax.set_xticks(range(1, NQ + 1), Q_LABELS)
        few_ticks(ax, 4)
    axs[0].set_ylabel("answers mentioning\nthe brand (%)")
    h, lab = axs[0].get_legend_handles_labels()
    RL = 0.764
    fig.legend(h, lab, ncol=1, loc="center left", bbox_to_anchor=(RL, .5), handlelength=1.4, frameon=False)
    fig.tight_layout(w_pad=1.3, rect=(0, 0, RL, 1))
    letters(axs)
    save(fig, name)



draw(["nessuna", "mean"], "fig5_persona_mean_quintiles")
draw(["nessuna", "A", "B", "C"], "fig5_persona_all_quintiles")
draw(["nessuna", "A"], "figA_persona_baseline")
draw(["nessuna", "B"], "figA_persona_spending")
draw(["nessuna", "C"], "figA_persona_profile")

# appendice: griglia motore x settore, tutti i livelli
fig, axs = plt.subplots(3, 4, figsize=(W * 1.25, W * 1.1), sharex=True)
for i, e in enumerate(E):
    r = res[e]
    for j, s in enumerate(S):
        ax = axs[i][j]
        m = r["secs"] == s
        for l in LV:
            v = r["y"][l][m]
            vb = r["yb"][l][:, m]
            qq = r["q"][m]
            mu = np.array([v[qq == k].mean() for k in range(1, NQ + 1)])
            bb = np.array([vb[:, qq == k].mean(axis=1) for k in range(1, NQ + 1)]).T
            lo, hi = np.percentile(bb, [2.5, 97.5], axis=0)
            ax.plot(range(1, NQ + 1), mu, color=PCOL[l], marker="o", ms=2.5, lw=1.3, label=PERSONA[l])
            ax.fill_between(range(1, NQ + 1), lo, hi, color=PCOL[l], alpha=.10, lw=0)
        few_ticks(ax, 3)
        ax.set_xticks(range(1, NQ + 1), [str(i) if i in (1, NQ) else "" for i in range(1, NQ + 1)])
        if i == 0:
            ax.set_title(SL[s])
        if j == 0:
            ax.set_ylabel(f"{EL[e]}\nmentioning (%)")

h, lab = axs[0][0].get_legend_handles_labels()
fig.legend(h, lab, ncol=2, loc="lower center", bbox_to_anchor=(.5, -.01))
fig.supxlabel("popularity quintile", y=.075, fontsize=FS)
fig.tight_layout(h_pad=0.8, rect=(0,.10,1,1))
save(fig, "figA_persona_quintiles_grid")
