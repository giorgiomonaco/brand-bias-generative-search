"""Come lavoro/2026-10-21_outline_risultati_study1/regressione.py (OLS del tasso di menzione in pp, notorietà × ricerca
+ settore + notorietà × settore, SE raggruppati per brand × settore), ma sull'universo per settore."""
import json, gzip
from pathlib import Path as _P
DATA = _P(__file__).resolve().parents[1] / 'data'
import pickle, collections, json, sys
import numpy as np, pandas as pd, statsmodels.formula.api as smf
from pathlib import Path
HERE = Path(__file__).resolve().parent
R = json.load(gzip.open(DATA / "calls.json.gz", "rt"))['rows']
P = pd.read_csv(HERE / sys.argv[1]).dropna(subset=['notorieta_log10'])
U = P[P.ricerca == 'off'][['motore', 'settore', 'chiave', 'notorieta_log10']]
cnt = collections.Counter(); N = collections.Counter()
for r in R:
    cs = ['on' if r['search'] else 'off'] + (['searched'] if r['engine'] == 'gemini' and r['search'] and r['search_performed'] else [])
    for c in cs:
        N[(r['engine'], r['sector'], c)] += 1
        for k in set(r['B']): cnt[(r['engine'], r['sector'], c, k)] += 1
recs = []
for row in U.itertuples():
    for c in ('off', 'on', 'searched'):
        n = N[(row.motore, row.settore, c)]
        if n: recs.append(dict(motore=row.motore, settore=row.settore, cond=c, brand=row.chiave, noto=row.notorieta_log10, y=100 * cnt[(row.motore, row.settore, c, row.chiave)] / n))
df = pd.DataFrame(recs); df['noto_c'] = df.noto - df.noto.mean(); out = {}
for e in ['gpt', 'gemini', 'perplexity']:
    for v in [('off', 'on')] + ([('off', 'searched')] if e == 'gemini' else []):
        x = df[(df.motore == e) & df.cond.isin(v)].copy(); x['search'] = (x.cond != 'off').astype(int)
        f = smf.ols('y ~ noto_c * search + C(settore) + noto_c:C(settore)', data=x).fit(cov_type='cluster', cov_kwds={'groups': pd.factorize(x.brand + '|' + x.settore)[0]})
        out[f'{e}|{v[1]}'] = dict(interazione=round(float(f.params['noto_c:search']), 3), se=round(float(f.bse['noto_c:search']), 3), p=round(float(f.pvalues['noto_c:search']), 4), n=int(f.nobs))
print(json.dumps(out, indent=1))
