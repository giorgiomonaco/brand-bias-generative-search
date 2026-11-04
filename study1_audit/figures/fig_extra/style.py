"""Stile comune delle figure del paper (incontro del 23/10): minimale, font vicini a quelli del testo, pochi tick."""
import json, gzip
from pathlib import Path
import pickle
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

HERE = Path(__file__).resolve().parent
INP = HERE.parents[1] / "data"
FIG = HERE / "fig"
FIG.mkdir(exist_ok=True)

SEED = 20261014
S = ["assicurazioni", "moda_beauty", "sport", "viaggi"]
E = ["gpt", "gemini", "perplexity"]
SL = {"assicurazioni": "Insurance", "moda_beauty": "Fashion & beauty", "sport": "Sport", "viaggi": "Travel"}
EL = {"gpt": "GPT", "gemini": "Gemini", "perplexity": "Perplexity"}

# termini unici in tutto il paper
MENTION, CITATION = "mention", "citation"
MEN, CIT = "#1baf7a", "#eb6834"
INK, GREY = "#222222", "#7a7a7a"

# Persona labels agreed with co-author, 24 October 2026
PERSONA = {"nessuna": "No persona context", "A": "Baseline persona (A)", "B": "Price variant (B)", "C": "Profile variant (C)"}
PCOL = {"nessuna": "#222222", "A": "#3b6fb6", "B": "#e39c37", "C": "#9b6fd6", "mean": "#3b6fb6"}

# larghezza di riferimento: testo del template ACM manuscript
WF = 5.85  # figure del corpo: larghezza piena del testo, più basse, legenda a destra (call del 2/11)
W = 4.75  # larghezza reale della figura nel paper (circa 0.8 del testo), inclusa senza riscalare (30/10)
FS = 9  # come il testo del paper

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": FS, "axes.titlesize": FS + 0.25, "axes.labelsize": FS,
    "xtick.labelsize": FS - 0.5, "ytick.labelsize": FS - 0.5, "legend.fontsize": FS - 0.5,
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": False,
    "axes.edgecolor": "#444444", "xtick.color": "#333333", "ytick.color": "#333333",
    "legend.frameon": False, "savefig.bbox": "tight", "pdf.fonttype": 42, "svg.fonttype": "none",
})


def few_ticks(ax, y=4, x=None, integer=True):
    ax.yaxis.set_major_locator(MaxNLocator(nbins=y, min_n_ticks=3, integer=integer, steps=[1, 2, 5, 10]))
    if x:
        ax.xaxis.set_major_locator(MaxNLocator(nbins=x, min_n_ticks=3, integer=True))


def save(fig, name):
    for ext in ("pdf", "png"):
        fig.savefig(FIG / f"{name}.{ext}", dpi=300, facecolor="white")
    plt.close(fig)
    print("figura", name)


def brands():
    return pd.read_csv(INP / "P1_brand.csv")


def rows():
    d = json.load(gzip.open(INP / "calls.json.gz", "rt"))
    R = pd.DataFrame(d["rows"])
    for c in ("search", "search_performed", "ha_estrazione"):
        R[c] = R[c].astype(str).eq("True")
    return R


def stars(p, p_bh=None):
    if p_bh is not None and p_bh < 0.05:
        return "**"
    return "*" if p < 0.05 else ""


NQ = 5  # quintili di popolarità (call del 2/11, si torna ai quintili)


def quintile(v):
    return pd.qcut(v.rank(method="first"), NQ, labels=False) + 1


Q_LABELS = ["least\npopular"] + [""] * (NQ - 2) + ["most\npopular"]


def letters(axs, x=-0.16, y=1.13):
    """Lettera in grassetto per ogni pannello (a, b, c...), in alto a sinistra."""
    for i, ax in enumerate(np.ravel(axs)):
        ax.text(x, y, "abcdefghijkl"[i], transform=ax.transAxes, fontsize=FS + 1, fontweight="bold", va="top", ha="left")
