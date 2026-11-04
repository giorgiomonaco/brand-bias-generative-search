"""Popolarità media dei brand nominati, per persona (come f_p56.py §6.2 di earlier working folder, analisi_aggiuntive_2026-10-20):
per risposta, media di log10(1+volume) sui brand dell'universo nominati con popolarità nota; media per prompt × livello;
contrasti B−A e C−A appaiati per prompt, t-test a un campione, BH. Uso: python3 persona_popolarita.py <P1.csv>"""
import json, gzip
from pathlib import Path as _P
DATA = _P(__file__).resolve().parents[1] / 'data'
import pickle, sys
import numpy as np, pandas as pd
from scipy import stats
from scipy.stats import false_discovery_control
from pathlib import Path
HERE = Path(__file__).resolve().parent
R = json.load(gzip.open(DATA / "calls.json.gz", "rt"))['rows']
P = pd.read_csv(HERE / sys.argv[1]).dropna(subset=['notorieta_log10'])
U = {(r.motore, r.settore, r.chiave): r.notorieta_log10 for r in P[P.ricerca == 'off'].itertuples()}
rec = []
for r in R:
    if r['level'] not in ('A', 'B', 'C') or not r.get('ha_estrazione'): continue
    v = [U[(r['engine'], r['sector'], k)] for k in set(r['B']) if (r['engine'], r['sector'], k) in U]
    rec.append(dict(motore=r['engine'], settore=r['sector'], ricerca='on' if r['search'] else 'off', prompt_id=r['prompt_id'], livello=r['level'], m=np.mean(v) if v else np.nan))
N = pd.DataFrame(rec); rows = []
for (e, s, ri), g in N.groupby(['motore', 'settore', 'ricerca']):
    pm = g.groupby(['prompt_id', 'livello']).m.mean().unstack()
    for a, b in (('B', 'A'), ('C', 'A')):
        d = (pm[a] - pm[b]).dropna()
        if len(d) < 2: rows.append(dict(cella=f'{e}|{s}|{ri}|{a}-{b}', n=len(d), diff=np.nan, p=np.nan)); continue
        t, p = stats.ttest_1samp(d, 0); rows.append(dict(cella=f'{e}|{s}|{ri}|{a}-{b}', n=len(d), diff=d.mean(), p=p))
Q = pd.DataFrame(rows); m = Q.p.notna(); Q.loc[m, 'p_bh'] = false_discovery_control(Q.p[m])
print('contrasti stimabili', int(m.sum()), 'p<.05', int((Q.p < .05).sum()), 'di cui positivi', int(((Q.p < .05) & (Q['diff'] > 0)).sum()), 'BH<.05', int((Q.p_bh < .05).sum()))
print(Q[Q.p < .05].round(3).to_string(index=False))
