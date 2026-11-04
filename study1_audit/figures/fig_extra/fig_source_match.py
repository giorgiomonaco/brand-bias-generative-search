"""Appendice (meeting 26/10): il nome del brand menzionato compare nelle fonti restituite? Per quintile di notorietà, tre motori.
Riga 1: quota di menzioni con nome trovato / verifica insufficiente / nessun riscontro, per quintile (come la tesi, con GPT).
Riga 2 (richiesta del co-author): per ogni esito, come si distribuiscono le menzioni fra i quintili.
Quintili sui brand (non sulle menzioni) dentro motore x settore, come in Fig. 2-3 del paper (P1_brand.csv, ricerca disponibile).
Dati: mention_source_classification_v6 (riclassifica Bright Data del 21/10), solo chiamate con query osservate."""
from style import *
import json
V = pd.read_csv(INP / "mention_source_classification_v6.csv.gz")
V = V[V.actual_queries].copy()
B = brands()
print("ricerca:", B.ricerca.unique()[:5])
Bon = B[B.ricerca == "on"]
Bon = Bon.dropna(subset=["notorieta_log10"]).drop_duplicates(["motore", "settore", "chiave"]).copy()
Bon["q"] = Bon.groupby(["motore", "settore"]).notorieta_log10.transform(quintile)
V = V.merge(Bon[["motore", "settore", "chiave", "q"]], left_on=["engine", "sector", "brand"], right_on=["motore", "settore", "chiave"], how="left")
print("menzioni", len(V), "con quintile", V.q.notna().sum())
V = V[V.q.notna()]; V["q"] = V.q.astype(int)
ST = [("name_observed", "Name found", "#1baf7a"), ("verification_insufficient", "Not verifiable", "#c9c8c2"),
      ("no_name_in_verified_observable_sources", "No match", "#eb6834")]
import matplotlib
QC = [matplotlib.colors.to_hex(c) for c in matplotlib.colormaps["Blues"](np.linspace(0.18, 0.95, NQ))]
fig, axs = plt.subplots(2, 3, figsize=(W * 1.25, 4.35), sharey="row")
out = {}
for j, e in enumerate(E):
    g = V[V.engine == e]; out[e] = {}
    tab = g.groupby("q").status.value_counts(normalize=True).unstack(fill_value=0) * 100
    bot = np.zeros(NQ); ax = axs[0, j]
    for k, lab, c in ST:
        vals = tab.get(k, pd.Series(0, index=tab.index)).reindex(range(1, NQ + 1), fill_value=0).values
        ax.bar(range(1, NQ + 1), vals, bottom=bot, color=c, width=0.72, label=lab, edgecolor="white", lw=0.5); bot += vals
    out[e]["quota_per_quintile"] = tab.round(1).to_dict()
    ax.set_title(EL[e]); ax.set_xticks(range(1, NQ + 1)); ax.set_xticklabels(Q_LABELS, fontsize=FS - 1.5); ax.set_ylim(0, 100)
    # riga 2: composizione per quintile di ciascun esito
    ax = axs[1, j]; xs, labs = [], []
    for i, (k, lab, _) in enumerate(ST):
        s = g[g.status == k]
        if len(s) < 30:
            ax.text(i, 50, "none" if len(s) == 0 else f"n={len(s)}", ha="center", va="center", fontsize=FS - 1.5, color=GREY)
        else:
            comp = s.q.value_counts(normalize=True).reindex(range(1, NQ + 1), fill_value=0).values * 100
            b0 = 0
            for qq in range(NQ):
                ax.bar(i, comp[qq], bottom=b0, color=QC[qq], width=0.62, edgecolor="white", lw=0.5); b0 += comp[qq]
            ax.text(i, 101.5, f"{len(s):,}", ha="center", va="bottom", fontsize=FS - 2, color=GREY)
            out[e][f"composizione_{k}"] = dict(zip(range(1, NQ + 1), np.round(comp, 1)))
        labs.append(lab.replace(" ", "\n"))
    ax.set_xticks(range(3)); ax.set_xticklabels(labs, fontsize=FS - 1.5); ax.set_ylim(0, 112); ax.set_xlim(-0.75, 2.75)
axs[0, 0].set_ylabel("share of mentions (%)"); axs[1, 0].set_ylabel("share of the outcome (%)")
for ax in axs.flat: few_ticks(ax, 3)
h, l = axs[0, 0].get_legend_handles_labels()
fig.legend(h, l, loc="upper center", ncol=3, bbox_to_anchor=(0.5, 1.035), fontsize=FS - 0.5)
from matplotlib.patches import Patch
fig.legend([Patch(color=c) for c in QC], ["least popular"] + [""] * (NQ - 2) + ["most popular"], loc="lower center", ncol=NQ, handlelength=1.0, columnspacing=0.4,
           bbox_to_anchor=(0.5, -0.035), fontsize=FS - 1, title="popularity quintile", title_fontsize=FS - 1)
fig.tight_layout(rect=(0, 0.06, 1, 0.97), h_pad=2.2)
save(fig, "figA_source_match_quintiles")
json.dump(out, open(FIG / "figA_source_match_quintiles.json", "w"), indent=1, default=str)
for e in E:
    print(e, {k: v for k, v in out[e].items() if k.startswith("comp")})
