"""Figura di Study 2 (3/11, v4): rango medio della pagina bersaglio per firma, con i bracci aggiunti il 27/10
(marchio più noto e meno noto con un loro prodotto reale).
(a) 7 firme, media sui 4 testi (originale + 3 riscritture): un punto per firma.
(b) 7 firme × 4 testi: 28 punti, colore = testo.
Valore per domanda: media per motore (su ordini e ripetizioni), poi media dei 4 motori. Punto: media sulle domande
disponibili (24; 15 per i due bracci con prodotto reale, cella jeans Agolde inclusa dal 3/11).
Effetto domanda: g_q = media delle 5 firme presenti in tutte le 24 domande, sui 4 testi; ogni valore è centrato
(y − g_q + G, G = media dei g_q). Per le 5 firme complete il punto coincide con la media grezza; per i due bracci
con prodotto reale il punto è corretto per la difficoltà delle domande in cui esistono.
IC95: bootstrap a grappolo sulle domande dei valori centrati (2.000, seed 20261023), come la v3 (fig. 6 del 2/11).
Righe classificate da carica.py (stessa classifica() di analisi_bracci_v4.py; 38.400 + 9.280 classifiche)."""
import csv
import pickle, random, statistics as st
from collections import defaultdict
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.transforms import blended_transform_factory
from matplotlib.ticker import MultipleLocator

HERE = Path(__file__).resolve().parent
SEED, B, FS = 20261023, 2000, 9
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": FS, "axes.titlesize": FS + 0.25, "axes.labelsize": FS,
    "xtick.labelsize": FS - 1, "ytick.labelsize": FS - 0.5, "legend.fontsize": FS - 0.5, "axes.spines.top": False,
    "axes.spines.right": False, "axes.grid": False, "axes.edgecolor": "#444444", "xtick.color": "#333333",
    "ytick.color": "#333333", "legend.frameon": False, "savefig.bbox": "tight", "pdf.fonttype": 42})
INK, GREY = "#222222", "#7a7a7a"
WF = 5.85
# ordine: prodotto reale (vero, più noto, meno noto) | prodotto inventato (vero, più noto, meno noto, inventato)
FIRME = [("REALE", "Real"), ("PIU_NOTO_REALE", "Better\nknown"), ("MENO_NOTO_REALE", "Less\nknown"),
         ("BRAND", "Invented\nproduct"), ("PIU_NOTO", "Better\nknown"), ("MENO_NOTO", "Less\nknown"),
         ("INVENTATO", "Invented\nbrand")]
X = [0, 1, 2, 3.6, 4.6, 5.6, 6.6]
GRUPPI = [((0, 2), "real product name"), ((3.6, 6.6), "invented product name")]
COMPLETE = ["REALE", "BRAND", "PIU_NOTO", "MENO_NOTO", "INVENTATO"]
TESTI = [("ORIGINALE", "Original", "#8a8a8a"), ("STRUTTURA", "Structure", "#3b6fb6"),
         ("FLUENCY", "Fluency", "#e39c37"), ("AUTHORITATIVE", "Authoritative", "#9b6fd6")]

rows = [(r[0], r[1], r[2], r[3], int(r[4]), int(r[5]), int(r[6])) for r in list(csv.reader(open(HERE.parent / "data" / "rankings.csv")))[1:]]  # (motore, q, firma, testo, j, rip, rango)
acc = defaultdict(list)
for m, q, f, t, j, rp, rk in rows:
    acc[(f, t, q, m)].append(rk)
y = defaultdict(dict)  # y[(f,t)][q] = media dei motori
for (f, t, q, m) in {k for k in acc}:
    pass
byft = defaultdict(lambda: defaultdict(list))
for (f, t, q, m), v in acc.items():
    byft[(f, t)][q].append(st.mean(v))
for k, d in byft.items():
    for q, v in d.items():
        assert len(v) == 4, (k, q, len(v))
        y[k][q] = st.mean(v)
QS = sorted(y[("REALE", "ORIGINALE")])
g = {q: st.mean(y[(f, t)][q] for f in COMPLETE for t, _, _ in TESTI) for q in QS}
G = st.mean(g.values())


def punto(per_q):
    """per_q: {q: valore centrato}. Media sulle domande e IC95 bootstrap a grappolo."""
    qs = sorted(per_q); rnd = random.Random(SEED)
    bs = sorted(st.mean(per_q[rnd.choice(qs)] for _ in qs) for _ in range(B))
    return st.mean(per_q.values()), bs[int(.025 * B)], bs[int(.975 * B) - 1], len(qs)


def centrato(f, testi):
    # v5 (4/11): il punto e' la media semplice sulle domande in cui la versione esiste (nessuna correzione per la
    # difficolta'); la difficolta' della domanda si toglie solo per l'ampiezza delle barre (variabilita' entro domanda),
    # ricentrando sulla media di g nelle stesse domande, cosi' la media dei valori resta la media semplice.
    qs = set.intersection(*(set(y[(f, t)]) for t in testi))
    Gf = st.mean(g[q] for q in qs)
    return {q: st.mean(y[(f, t)][q] for t in testi) - g[q] + Gf for q in qs}


res_a = {f: punto(centrato(f, [t for t, _, _ in TESTI])) for f, _ in FIRME}
res_b = {(f, t): punto(centrato(f, [t])) for f, _ in FIRME for t, _, _ in TESTI}
with open(HERE / "numeri_fig_study2.txt", "w") as fh:
    fh.write("pannello a: firma | media | IC95 | n domande | media grezza (non centrata)\n")
    for f, _ in FIRME:
        m, lo, hi, n = res_a[f]
        raw = st.mean(st.mean(y[(f, t)][q] for t, _, _ in TESTI) for q in centrato(f, [t for t, _, _ in TESTI]))
        fh.write(f"{f:16s} {m:.3f} [{lo:.3f}; {hi:.3f}] n={n} grezza={raw:.3f}\n")
    fh.write("\npannello b: firma testo | media | IC95 | n\n")
    for (f, t), (m, lo, hi, n) in res_b.items():
        fh.write(f"{f:16s} {t:14s} {m:.3f} [{lo:.3f}; {hi:.3f}] n={n}\n")
print((HERE / "numeri_fig_study2.txt").read_text())


# --- layout verticale come la Fig. 6 (v4, 3/11): due pannelli affiancati, rango sull'asse y.
# Sull'asse x chi firma la pagina (4 marchi); il nome del prodotto è nel simbolo: pieno = prodotto reale,
# vuoto = prodotto inventato. Così le etichette restano 4 e corte. True brand + vuoto = braccio Invented product (BRAND).
CAT = ["Original\nbrand", "Better\nknown", "Less\nknown", "Invented\nbrand"]
POS = {"REALE": (0, True), "BRAND": (0, False), "PIU_NOTO_REALE": (1, True), "PIU_NOTO": (1, False),
       "MENO_NOTO_REALE": (2, True), "MENO_NOTO": (2, False), "INVENTATO": (3, False)}
def xoff(f, side):  # spostamento del gruppo: prodotto reale a sinistra, inventato a destra; Invented brand al centro
    if f == "INVENTATO": return 0.0
    return -side if POS[f][1] else side
fig, axes = plt.subplots(1, 2, figsize=(WF, 2.3), sharey=True)
fig.subplots_adjust(left=0.085, right=0.785, bottom=0.2, top=0.87, wspace=0.08)
a, b = axes
def marker(ax, x, m, lo, hi, c, filled, ms, cs, lw):
    ax.errorbar(x, m, yerr=[[m - lo], [hi - m]], fmt="o", color=c, mfc=c if filled else "white", mec=c, mew=1.0,
                ms=ms, capsize=cs, lw=lw)
for f, _ in FIRME:
    x0, filled = POS[f]; m, lo, hi, _ = res_a[f]
    marker(a, x0 + xoff(f, 0.14), m, lo, hi, INK, filled, 4.0, 2.2, 1.1)
OFF = [-0.135, -0.045, 0.045, 0.135]
for f, _ in FIRME:
    x0, filled = POS[f]
    for (t, lab, c), dx in zip(TESTI, OFF):
        m, lo, hi, _ = res_b[(f, t)]
        marker(b, x0 + xoff(f, 0.19) + dx, m, lo, hi, c, filled, 2.9, 1.2, 0.9)
for ax, k, title in ((a, "a", "Mean over rewrites"), (b, "b", "Separate rewrites")):
    ax.set_xticks(range(4)); ax.set_xticklabels(CAT, fontsize=FS - 1, linespacing=1.0)
    ax.tick_params(axis="x", length=0, pad=3); ax.set_xlim(-0.55, 3.45)
    ax.set_title(title, pad=4)
    ax.text(-0.2 if k == "a" else -0.02, 1.13, k, transform=ax.transAxes, fontsize=FS + 1, fontweight="bold", va="top")
a.set_ylabel("mean rank"); a.set_ylim(3.85, 3.0)
a.yaxis.set_major_locator(MultipleLocator(0.2))
from matplotlib.lines import Line2D
h = [Line2D([], [], color=c, marker="o", ms=3.4, lw=0) for _, _, c in TESTI]
lab = [l for _, l, _ in TESTI]
h += [Line2D([], [], lw=0), Line2D([], [], color=INK, marker="o", ms=3.8, lw=0),
      Line2D([], [], color=INK, marker="o", ms=3.8, lw=0, mfc="white", mew=1.0)]
lab += ["", "Real product", "Invented product"]
b.legend(h, lab, loc="center left", bbox_to_anchor=(1.0, 0.5), handletextpad=0.2, handlelength=1.0,
         fontsize=FS - 1, labelspacing=0.45)
for ext in ("pdf", "png"):
    fig.savefig(HERE / f"fig6_study2_identity_content.{ext}", dpi=300, facecolor="white", bbox_inches="tight", pad_inches=0.02)
print("ok")
