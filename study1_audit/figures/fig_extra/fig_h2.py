"""Appendice: H2 (26/10 sera, v2, indicazioni di co-author del 23/10): stessa figura della tesi (s1r_p2_curve) ripulita.
Asse Y «Answer similarity», asse X «Query similarity» scritto una volta e condiviso, legenda senza misure fra parentesi;
Jaccard, coseno, scala normalizzata e fasce vanno nella caption. Dati: P2_fasce_bande.csv (analisi_aggiuntive_2026-10-19),
media per fascia e IC95 bootstrap per prompt, copiati in input_h2/."""
from style import *
F = pd.read_csv(INP / "h2" / "P2_fasce_bande.csv")
MS = [("y_fonti_norm", "Sources", "#eb6834"), ("y_brand_norm", "Brands", "#1baf7a"), ("y_testo_norm", "Answer text", "#6250d6")]
fig, axs = plt.subplots(1, 3, figsize=(WF, 2.0), sharey=True, sharex=True)
for ax, e in zip(axs, E):
    for k, lab, c in MS:
        f = F[(F.motore == e) & (F.misura == k)].sort_values("fascia")
        ax.fill_between(f.x_media, f.lo, f.hi, color=c, alpha=0.15, lw=0)
        ax.plot(f.x_media, f.media, "-o", color=c, ms=2.8, lw=1.3, label=lab)
    for y in (0, 1): ax.axhline(y, color=GREY, lw=0.7, ls="--")
    ax.set_title(EL[e])
axs[0].text(0.58, 1.04, "as similar as\ntwo repeats", fontsize=FS - 2, color=GREY, va="bottom", linespacing=1.1)
axs[0].text(0.58, -0.04, "as similar as two\ndifferent prompts", fontsize=FS - 2, color=GREY, va="top", linespacing=1.1)
axs[0].set_ylim(-0.52, 1.5)
axs[0].set_ylabel("Answer similarity"); axs[0].set_yticks([0, 0.5, 1.0])
axs[0].set_xlim(0.57, 0.93); axs[0].set_xticks([0.6, 0.7, 0.8, 0.9])
axs[1].set_xlabel("Query similarity")
h, l = axs[0].get_legend_handles_labels()
RL = 0.797
fig.legend(h, l, ncol=1, loc="center left", bbox_to_anchor=(RL, .5), handlelength=1.4, frameon=False)
letters(axs)
fig.tight_layout(w_pad=0.8, rect=(0, 0, RL, 1))
save(fig, "figA_h2_query_similarity")
