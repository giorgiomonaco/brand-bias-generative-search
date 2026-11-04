"""Fig. 1 (3/11, terza passata): stessa geometria della versione del mattino, font di prima (DejaVu Sans, come le altre
figure) ridotto di 0,5 pt. "× 4 personas" nel box di Study 1; H2, H3, H5 = Search queries effect, Personas effect,
GEO-rewrites effect; nel box "What we observe" di Study 2 solo "Rank of the target page"."""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
FIG = Path(__file__).resolve().parent / "fig"
FIG.mkdir(exist_ok=True)

plt.rcParams.update({"font.family": "DejaVu Sans", "pdf.fonttype": 42, "svg.fonttype": "none", "savefig.bbox": None})
INK = "#222222"
W = 430.00462 / 72.27
S1C, S2C, HC, NC = "#f0f3f8", "#fcf3ec", "#eef5f0", "#f6f6f6"
TF, BF = 7.5, 7                       # titolo e corpo (0,5 pt in meno, 3/11)
LH = BF / 72 * 1.38
TH = TF / 72 * 1.55
PAD = 0.07
GAP = 0.32
X1, W1 = 0.01, 1.68
X2, W2 = X1 + W1 + GAP, 1.5
X3 = X2 + W2 + GAP; W3 = W - X3 - 0.01


def h_box(n):
    return PAD + TH + n * LH + PAD


def box(ax, x, yc, w, title, lines, color, dashed=False, cols=None):
    n = len(lines) if cols is None else len(cols)
    h = h_box(n); y = yc - h / 2
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.05", fc=color, ec="#a0a5aa",
                                lw=0.6, ls="--" if dashed else "-"))
    ax.text(x + w / 2, y + h - PAD, title, ha="center", va="top", fontsize=TF, weight="bold", color=INK)
    top = y + h - PAD - TH
    if cols is None:
        for i, t in enumerate(lines):
            ax.text(x + w / 2, top - (i + 0.5) * LH, t, ha="center", va="center", fontsize=BF, color=INK)
    else:
        for i, (k, t) in enumerate(cols):
            yy = top - (i + 0.5) * LH
            ax.text(x + 0.14, yy, k, ha="left", va="center", fontsize=BF, weight="bold", color=INK)
            ax.text(x + 0.42, yy, t, ha="left", va="center", fontsize=BF, color=INK)
    return y, h


def arrow(ax, x0, x1, y):
    ax.add_patch(FancyArrowPatch((x0 + 0.03, y), (x1 - 0.03, y), arrowstyle="-|>", mutation_scale=6.5, lw=0.7,
                                 color="#60666c", shrinkA=0, shrinkB=0))


S1 = ["80 commercial prompts", "× 4 personas", "× 2 search settings", "× 10 repeats", "× 3 engines",
      "Total: 19,200 answers"]
S2 = ["24 prompts", "× 5 signatures × 4 texts", "× 10 orders × 2 repeats", "× 4 models, search off",
      "Total: 38,400 rankings"]
OBS1 = ["Search queries", "Sources → citation", "Answer text → mention"]
H1 = [("H1", "Brand popularity bias"), ("H2", "Search queries effect"), ("H3", "Personas effect")]
H2 = [("H4", "Brand familiarity bias"), ("H5", "GEO-rewrites effect")]

ho, hn, g = h_box(len(OBS1)), h_box(1), 0.08
hr1 = max(h_box(len(S1)), ho + g + hn); hr2 = h_box(len(S2)); link = 0.30
H = hr1 + link + hr2 + 0.02
fig, ax = plt.subplots(figsize=(W, H))
fig.subplots_adjust(left=0, right=1, bottom=0, top=1)
ax.set_xlim(0, W); ax.set_ylim(0, H); ax.axis("off")

# Study 1
yc1 = H - 0.01 - hr1 / 2
y1, _ = box(ax, X1, yc1, W1, "Study 1: the audit", S1, S1C)
tot = ho + g + hn
yo = yc1 + tot / 2 - ho / 2; yn = yc1 - tot / 2 + hn / 2
box(ax, X2, yo, W2, "What we observe", OBS1, S1C)
box(ax, X2, yn, W2, "Brand popularity", ["External search volume"], NC, dashed=True)
box(ax, X3, yc1, W3, "Hypotheses", None, HC, cols=H1)
arrow(ax, X1 + W1, X2, yo)
for yy in (yo, yn):
    ax.add_patch(FancyArrowPatch((X2 + W2 + 0.03, yy), (X3 - 0.03, yc1 + (0.1 if yy > yc1 else -0.1)), arrowstyle="-|>",
                                 mutation_scale=6.5, lw=0.7, color="#60666c", shrinkA=0, shrinkB=0))

# Study 2
yc2 = 0.01 + hr2 / 2
box(ax, X1, yc2, W1, "Study 2: the experiment", S2, S2C)
box(ax, X2, yc2, W2, "What we observe", ["Rank of the target page"], S2C)
box(ax, X3, yc2, W3, "Hypotheses", None, HC, cols=H2)
arrow(ax, X1 + W1, X2, yc2); arrow(ax, X2 + W2, X3, yc2)

# collegamento
ax.add_patch(FancyArrowPatch((X1 + W1 / 2, y1 - 0.02), (X1 + W1 / 2, yc2 + hr2 / 2 + 0.02), arrowstyle="-|>",
                             mutation_scale=6.5, lw=0.7, color="#60666c", shrinkA=0, shrinkB=0))
ax.text(X1 + W1 / 2 + 0.07, (y1 + yc2 + hr2 / 2) / 2, "prompts, brands and pages from Study 1", ha="left",
        va="center", fontsize=BF, style="italic", color="#555555")

name = "fig1_pipeline_study1_2"
for ext in ("pdf", "png"):
    fig.savefig(FIG / f"{name}.{ext}", dpi=300, facecolor="white")
print(name)
