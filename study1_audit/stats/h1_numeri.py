"""Numeri di H1 per una tabella P1 (stessa forma di P1_brand.csv): Spearman popolarità–menzione per cella (24),
Pearson senza i due brand più menzionati, Spearman popolarità–citazione (12 celle, ricerca on), quintili di menzione e
citazione, logistica per motore con interazione popolarità × ricerca. Uso: python3 h1_numeri.py <P1.csv>"""
import json, gzip
from pathlib import Path as _P
DATA = _P(__file__).resolve().parents[1] / 'data'
import sys, json
import numpy as np, pandas as pd, statsmodels.api as sm, statsmodels.formula.api as smf
from scipy import stats
P = pd.read_csv(sys.argv[1]).dropna(subset=['notorieta_log10'])
def bh(ps):
    ps = np.asarray(ps, float); m = len(ps); o = np.argsort(ps); adj = np.empty(m); prev = 1
    for rank, i in reversed(list(enumerate(o, 1))): prev = min(prev, ps[i] * m / rank); adj[i] = prev
    return adj
out = {}
# Spearman menzione, 24 celle
rows = []
for (e, s, a), g in P.groupby(['motore', 'settore', 'ricerca']):
    rho, p = stats.spearmanr(g.notorieta_log10, g.tasso_menzione)
    r_all = stats.pearsonr(g.notorieta_log10, g.tasso_menzione)[0]
    g2 = g.drop(g.nlargest(2, 'tasso_menzione').index); r_cut = stats.pearsonr(g2.notorieta_log10, g2.tasso_menzione)[0]
    rows.append(dict(cella=f'{e}|{s}|{a}', rho=rho, p=p, n=len(g), pearson=r_all, pearson_senza_top2=r_cut))
S = pd.DataFrame(rows); S['p_bh'] = bh(S.p)
out['spearman_menzione'] = dict(positivi=int((S.rho > 0).sum()), sig_005=int((S.p < .05).sum()), sig_bh=int((S.p_bh < .05).sum()),
    rho_min=round(S.rho.min(), 2), rho_max=round(S.rho.max(), 2), p_max=float(S.p.max()),
    calo_pearson_max=round(float((S.pearson - S.pearson_senza_top2).max()), 3), n_brand_min=int(S.n.min()), n_brand_max=int(S.n.max()))
# Spearman citazione, ricerca on, brand con dominio
rows = []
for (e, s), g in P[P.ricerca == 'on'].dropna(subset=['tasso_citazione']).groupby(['motore', 'settore']):
    rho, p = stats.spearmanr(g.notorieta_log10, g.tasso_citazione); rows.append(dict(cella=f'{e}|{s}', rho=rho, p=p, n=len(g)))
CI = pd.DataFrame(rows); CI['p_bh'] = bh(CI.p)
out['spearman_citazione'] = dict(sig_005=int((CI.p < .05).sum()), sig_bh=int((CI.p_bh < .05).sum()),
    celle_sig_bh=CI[CI.p_bh < .05].cella.tolist(), celle_sig_005=CI[CI.p < .05].cella.tolist(),
    rho=dict(zip(CI.cella, CI.rho.round(2))))
# quintili (ricerca on): brand in quinti di popolarità dentro motore × settore
Q = P[P.ricerca == 'on'].copy()
Q['q'] = Q.groupby(['motore', 'settore']).notorieta_log10.transform(lambda x: pd.qcut(x.rank(method='first'), 5, labels=False) + 1)
qq = Q.groupby(['motore', 'q']).agg(menzione=('tasso_menzione', 'mean'), citazione=('tasso_citazione', 'mean')) * 100
out['quintili_on'] = {m: {int(q): dict(menzione=round(r.menzione, 2), citazione=round(r.citazione, 2)) for q, r in g.droplevel(0).iterrows()} for m, g in qq.groupby(level=0)}
# citazione quando menzionato (ricerca on, brand con dominio): quota sulle menzioni, per motore × settore
W = P[(P.ricerca == 'on')].dropna(subset=['tasso_citazione'])
# logistica per motore: menzioni/risposte ~ popolarità centrata × ricerca + settore, pesi = risposte
lg = {}
for e, g in P.groupby('motore'):
    g = g.copy(); g['x'] = g.notorieta_log10 - g.notorieta_log10.mean(); g['on'] = (g.ricerca == 'on').astype(int)
    m = smf.glm('tasso_menzione ~ x * on + C(settore)', data=g, family=sm.families.Binomial(), var_weights=g.risposte).fit()
    lg[e] = dict(interazione=round(float(m.params['x:on']), 3), p=round(float(m.pvalues['x:on']), 3), pop=round(float(m.params['x']), 3))
out['logistica'] = lg
print(json.dumps(out, ensure_ascii=False, indent=1))
