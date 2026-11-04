"""Mention contro citation per notorietà (Study 1, ricerca disponibile).
Opzione B (corpo del paper): quote medie per quintile di notorietà dentro motore x settore.
Opzione A (appendice): un punto per brand, curva logistica (non scende sotto zero) con banda al 95%."""
import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats
from style import *

B = brands()
B = B[B.ricerca == "on"].dropna(subset=["notorieta_log10"])

# ---------------------------------------------------------------- opzione B
fig, axs = plt.subplots(1, 3, figsize=(W, 2.35), sharey=True, sharex=True)
out = []
for ax, e in zip(axs, E):
    g = B[B.motore == e].dropna(subset=["tasso_citazione"]).copy()
    g["q"] = g.groupby("settore").notorieta_log10.transform(quintile)
    m = g.groupby("q")[["tasso_menzione", "tasso_citazione"]].mean() * 100
    se = g.groupby("q")[["tasso_menzione", "tasso_citazione"]].sem() * 100
    for col, c, lab in (("tasso_menzione", MEN, MENTION), ("tasso_citazione", CIT, CITATION)):
        ax.errorbar(m.index, m[col], yerr=1.96 * se[col], color=c, marker="o", ms=3.5, lw=1.6, capsize=2, label=lab, alpha=.75)
    for q in m.index:
        out.append(dict(engine=e, quintile=q, mention=round(m.loc[q, "tasso_menzione"], 2),
                        citation=round(m.loc[q, "tasso_citazione"], 2), n_brands=int((g.q == q).sum())))
    ax.set_title(EL[e])
    ax.set_xticks(range(1, NQ + 1), Q_LABELS)
    few_ticks(ax, 4)
axs[0].set_ylabel("share of answers (%)")
h, l = axs[0].get_legend_handles_labels()
fig.legend(h, l, ncol=2, loc="lower center", bbox_to_anchor=(.5, -.01), handlelength=1.4)
fig.tight_layout(w_pad=0.6, rect=(0, 0.1, 1, 1))
letters(axs)
save(fig, "fig3_mention_citation_quintiles")
pd.DataFrame(out).to_csv(FIG / "fig3_mention_citation_quintiles.csv", index=False)

# ---------------------------------------------------------------- opzione A


def logit_fit(x, rate, n, grid):
    X = sm.add_constant(x)
    res = sm.GLM(rate, X, family=sm.families.Binomial(), var_weights=n).fit(scale="X2")
    pr = res.get_prediction(sm.add_constant(grid)).summary_frame(alpha=0.05)
    return pr["mean"].values, pr["mean_ci_lower"].values, pr["mean_ci_upper"].values


fig, axs = plt.subplots(3, 4, figsize=(W * 1.25, W * 0.95), sharex="col")
rho = []
for i, e in enumerate(E):
    for j, s in enumerate(S):
        ax = axs[i][j]
        g = B[(B.motore == e) & (B.settore == s)]
        gd = g.dropna(subset=["tasso_citazione"])
        xs = B[B.settore == s].notorieta_log10
        grid = np.linspace(xs.min(), xs.max(), 80)
        lines = []
        for col, c, lab, dd in (("tasso_menzione", MEN, MENTION, g), ("tasso_citazione", CIT, CITATION, gd)):
            x = dd.notorieta_log10.values
            y = dd[col].values
            ax.scatter(x, 100 * y, s=5, color=c, alpha=.28, lw=0)
            mu, lo, hi = logit_fit(x, y, dd.risposte.values, grid)
            ax.fill_between(grid, 100 * lo, 100 * hi, color=c, alpha=.18, lw=0)
            ax.plot(grid, 100 * mu, color=c, lw=1.6)
            r, p = stats.spearmanr(x, y)
            rho.append(dict(engine=e, sector=s, measure=lab, rho=round(r, 3), p=p, n=len(x)))
            lines.append(f"ρ {r:.2f}{stars(p)}")
        ax.text(.03, .97, lines[0], transform=ax.transAxes, color=MEN, fontsize=FS - 1.5, va="top", weight="bold")
        ax.text(.03, .85, lines[1], transform=ax.transAxes, color=CIT, fontsize=FS - 1.5, va="top", weight="bold")
        top = np.percentile(np.r_[100 * g.tasso_menzione.values, 100 * gd.tasso_citazione.values], 99.3)
        ax.set_ylim(0, max(top, 5) * 1.12)
        few_ticks(ax, 3, 4)
        if i == 0:
            ax.set_title(SL[s])
        if j == 0:
            ax.set_ylabel(f"{EL[e]}\nshare of answers (%)")
        if i == 2:
            ax.set_xlabel("popularity")
h = [plt.Line2D([], [], color=MEN, lw=2), plt.Line2D([], [], color=CIT, lw=2)]
fig.legend(h, [MENTION, CITATION], ncol=2, loc="lower center", bbox_to_anchor=(.5, -.035))
fig.tight_layout(h_pad=0.8, w_pad=0.6)
save(fig, "figA_mention_citation_fits")
pd.DataFrame(rho).to_csv(FIG / "figA_mention_citation_rho.csv", index=False)
