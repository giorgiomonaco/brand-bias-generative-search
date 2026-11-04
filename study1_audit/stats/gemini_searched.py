"""Gemini: pendenza della menzione sulla popolarità con ricerca spenta e nelle sole chiamate 'on' che hanno cercato
(e in quelle che non hanno cercato), stesso metodo di slope_on_off (OLS dentro settore, effetti fissi, punti %)."""
import json, gzip
from pathlib import Path as _P
DATA = _P(__file__).resolve().parents[1] / 'data'
import sys, pickle, collections
import numpy as np, pandas as pd
from pathlib import Path
HERE = Path(__file__).resolve().parent
R = json.load(gzip.open(DATA / "calls.json.gz", "rt"))['rows']
P = pd.read_csv(sys.argv[1]).dropna(subset=['notorieta_log10']); P = P[(P.motore == 'gemini') & (P.ricerca == 'off')]
cnt = collections.Counter(); N = collections.Counter()
for r in R:
    if r['engine'] != 'gemini': continue
    g = 'off' if not r['search'] else ('cercato' if r['search_performed'] else 'non_cercato')
    N[(r['sector'], g)] += 1
    for k in set(r['B']): cnt[(r['sector'], g, k)] += 1
rng = np.random.default_rng(20261027)
for g in ('off', 'cercato', 'non_cercato'):
    xs, ys, cells = [], [], []
    for s, d in P.groupby('settore'):
        y = np.array([100 * cnt[(s, g, k)] / N[(s, g)] for k in d.chiave]); x = d.notorieta_log10.values
        xs.append(x - x.mean()); ys.append(y - y.mean())
    X = np.concatenate(xs); Y = np.concatenate(ys); b = (X * Y).sum() / (X ** 2).sum()
    print(g, 'pendenza', round(b, 3), 'chiamate', {s: N[(s, g)] for s in sorted({s for s, _ in N})})
