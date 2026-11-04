"""Study 1: quanto la notorietà fa salire la menzione con la ricerca spenta e con la ricerca disponibile, e la differenza.
Unità: il brand (marchi con notorietà nota, tutte le persone insieme, braccio del system prompt escluso), da P1_brand.csv
(la stessa tabella delle Figg. 2 e A1). Pendenza = OLS del tasso di menzione (punti percentuali) sul log10 della
notorietà, dentro motore × settore. Effetto della ricerca per brand: delta = menzione(on) − menzione(off); la pendenza di
delta sulla notorietà è esattamente pendenza(on) − pendenza(off). Stime aggregate con effetti fissi motore × settore
(notorietà e menzione centrate dentro la cella). IC95 bootstrap sui brand dentro ogni cella (2.000, seed 20261027);
p dal test t con errori HC3; Benjamini–Hochberg sulle 12 celle. Nessuna chiamata ai modelli."""
import json
import numpy as np, pandas as pd, statsmodels.api as sm
from scipy import stats
from pathlib import Path
HERE = Path(__file__).resolve().parent
INP = HERE.parents[1] / 'data' / 'P1_brand.csv'
B = pd.read_csv(INP).dropna(subset=['notorieta_log10'])
W = B.pivot_table(index=['motore', 'settore', 'chiave', 'notorieta_log10'], columns='ricerca', values='tasso_menzione').reset_index()
W['on'] *= 100; W['off'] *= 100; W['delta'] = W.on - W.off
W['cella'] = W.motore + '|' + W.settore
for c in ('notorieta_log10', 'on', 'off', 'delta'):
    W[c + '_c'] = W[c] - W.groupby('cella')[c].transform('mean')
SEED, NB = 20261027, 2000


def ols(x, y):
    r = sm.OLS(y, sm.add_constant(x)).fit(cov_type='HC3')
    return float(np.asarray(r.params)[1]), float(np.asarray(r.pvalues)[1])


def boot(g, ycol, xcol, rng):
    """bootstrap dei brand dentro ogni cella (stratificato), pendenza OLS."""
    out = []
    idx = [np.flatnonzero(g.cella.values == c) for c in g.cella.unique()]
    x, y = g[xcol].values, g[ycol].values
    for _ in range(NB):
        s = np.concatenate([rng.choice(i, len(i)) for i in idx])
        xs, ys = x[s], y[s]
        out.append(np.polyfit(xs, ys, 1)[0])
    return np.percentile(out, [2.5, 97.5]).tolist()


def stima(g, centrato, rng):
    xc = 'notorieta_log10_c' if centrato else 'notorieta_log10'
    r = {}
    for k in ('off', 'on', 'delta'):
        yc = k + '_c' if centrato else k
        b, p = ols(g[xc].values, g[yc].values)
        r[k] = dict(pendenza=round(b, 3), ic95=[round(v, 3) for v in boot(g, yc, xc, rng)], p=p)
    r['rapporto_on_off'] = round(r['on']['pendenza'] / r['off']['pendenza'], 3) if r['off']['pendenza'] else None
    r['menzione_media'] = dict(off=round(g.off.mean(), 3), on=round(g.on.mean(), 3))
    r['spearman_delta'] = dict(zip(('rho', 'p'), map(float, stats.spearmanr(g.notorieta_log10, g.delta))))
    r['n_brand'] = int(len(g))
    return r


rng = np.random.default_rng(SEED)
out = dict(note=__doc__, celle={}, motori={}, totale=None)
for c, g in W.groupby('cella'):
    out['celle'][c] = stima(g, False, rng)
for m, g in W.groupby('motore'):
    out['motori'][m] = stima(g, True, rng)
out['totale'] = stima(W, True, rng)
# Benjamini–Hochberg sulle 12 celle per la differenza
cs = list(out['celle']); ps = np.array([out['celle'][c]['delta']['p'] for c in cs])
o = np.argsort(ps); adj = np.empty_like(ps); m = len(ps); prev = 1
for rank, i in reversed(list(enumerate(o, 1))):
    prev = min(prev, ps[i] * m / rank); adj[i] = prev
for c, a in zip(cs, adj): out['celle'][c]['delta']['p_bh'] = float(a)
(HERE / 'slope_on_off.json').write_text(json.dumps(out, ensure_ascii=False, indent=1))
W.to_csv(HERE / 'brand_on_off.csv', index=False)
f = lambda d: f"{d['pendenza']:+.2f} [{d['ic95'][0]:+.2f}; {d['ic95'][1]:+.2f}] p={d['p']:.3f}"
print(f"{'':28} {'off':28} {'on':28} {'on−off':28}")
for k, r in [('TOTALE', out['totale'])] + [(m, v) for m, v in out['motori'].items()] + list(out['celle'].items()):
    extra = f" bh={r['delta']['p_bh']:.3f}" if 'p_bh' in r['delta'] else ''
    print(f"{k:28} {f(r['off']):28} {f(r['on']):28} {f(r['delta'])}{extra}  n={r['n_brand']}  media off/on={r['menzione_media']['off']:.2f}/{r['menzione_media']['on']:.2f}")
