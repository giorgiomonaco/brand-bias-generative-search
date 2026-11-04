"""Citazione del sito proprio quando il brand è nominato (sezione 6 di fonti_descrittive.py, earlier working folder/scrittura/
analisi_aggiuntive_2026-10-19), con una tabella domini a scelta. Chiamate con ricerca e query osservate, livelli
nessuna/A/B/C; tutti i brand con dominio (non dipende dall'universo di H1). Uso: python3 ... <tabella_domini.csv>"""
import json, gzip
from pathlib import Path as _P
DATA = _P(__file__).resolve().parents[1] / 'data'
import pickle, csv, re, sys
from collections import defaultdict
import numpy as np, pandas as pd
from pathlib import Path
HERE = Path(__file__).resolve().parent
rows = json.load(gzip.open(DATA / "calls.json.gz", "rt"))['rows']
on = [r for r in rows if r['search'] and r['queries']]
BD = defaultdict(set)
for r in csv.DictReader(open(sys.argv[1])):
    if r.get('stato') in ('no_verified_domain', 'shared_domain_not_attributable'): continue
    for d in re.split(r'[;, ]+', r['dominio'] or ''):
        if d.strip(): BD[r['chiave']].add(d.strip().lower())
cnd = defaultdict(lambda: [0, 0])
for r in on:
    if not r['ha_estrazione']: continue
    for k in r['B']:
        if k not in BD: continue
        cnd[(r['engine'], r['sector'])][0] += bool(BD[k] & set(r['fonti_s'])); cnd[(r['engine'], r['sector'])][1] += 1
out = pd.DataFrame([dict(motore=e, settore=s, menzioni=n, quota=round(100 * a / n, 1)) for (e, s), (a, n) in cnd.items()]).sort_values(['motore', 'settore'])
print(out.to_string(index=False)); print(out.groupby('motore').quota.agg(['min', 'max']))
