"""Appendice: pendenza della menzione sulla popolarità con ogni persona contro senza persona, una cella motore x settore
per punto (36 punti). Sotto la diagonale = popolarità conta meno con la persona. Pieni: differenza che supera
Benjamini-Hochberg sulle 36. Dati: persona_pendenze_seed1014.json (le stesse stime della §4.3)."""
import sys, json
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'fig_extra'))
import style
from style import plt, np, W, FS, E, S, EL, SL
from statsmodels.stats.multitest import multipletests
style.FIG = HERE / 'fig'; style.FIG.mkdir(exist_ok=True)
P = json.load(open(HERE.parents[1] / 'data' / 'persona_pendenze_seed1014.json'))
rows = [(r['motore'], r['settore'], l, r['nessuna'], r[l], r[l + '_p']) for r in P for l in 'ABC']
rej = multipletests([x[5] for x in rows], method='fdr_bh')[0]
print('p<.05:', sum(x[5] < .05 for x in rows), 'BH:', sum(rej), 'BH flatter:', sum(r and x[4] < x[3] for x, r in zip(rows, rej)))
from style import PCOL as COL
LAB = {'A': 'Baseline persona (A)', 'B': 'Price variant (B)', 'C': 'Profile variant (C)'}
fig, ax = plt.subplots(figsize=(W * 0.62, W * 0.62))
lim = (0, max(max(x[3], x[4]) for x in rows) * 1.08)
ax.plot(lim, lim, color='#999999', lw=.9, ls=(0, (3, 3)), zorder=0)
for l in 'ABC':
    for x, r in zip(rows, rej):
        if x[2] != l: continue
        ax.scatter(x[3], x[4], s=22, color=COL[l] if r else 'white', edgecolor=COL[l], lw=1.1, zorder=3)
for l in 'ABC':
    ax.scatter([], [], s=22, color=COL[l], edgecolor=COL[l], label=LAB[l])
ax.scatter([], [], s=22, color='white', edgecolor='#555555', label='not significant after correction')
ax.set_xlim(lim); ax.set_ylim(lim); ax.set_aspect('equal')
ax.set_xlabel('slope without a persona context'); ax.set_ylabel('slope with the persona')
style.few_ticks(ax, 4, 4, integer=True)
ax.legend(loc='upper center', bbox_to_anchor=(.5, -.18), ncol=1, handletextpad=.4, fontsize=FS - 1)
fig.tight_layout()
style.save(fig, 'figA_persona_slopes')
