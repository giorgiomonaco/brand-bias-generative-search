"""Ricostruisce la tabella brand × motore × settore × ricerca da rows_light.pkl (19.200 risposte, A_sistema escluso)
in due versioni dell'universo dei brand:
  per_motore  : brand con >= SOGLIA risposte in quel motore × settore (bracci sommati) — la versione del paper al 29/10
  per_settore : brand con >= SOGLIA risposte in ALMENO UN motore del settore; tassi per tutti e tre i motori, zeri compresi
Notorietà da P1_brand.csv (un valore per brand). Citazione: dominio del brand fra le fonti (fonti_s), solo ricerca on,
brand senza dominio = NaN. Nessuna chiamata API."""
import json, gzip
from pathlib import Path as _P
DATA = _P(__file__).resolve().parents[1] / 'data'
import pickle, sys, collections
import numpy as np, pandas as pd
from pathlib import Path
HERE = Path(__file__).resolve().parent
INP = DATA
d = json.load(gzip.open(DATA / "calls.json.gz", "rt")); R = d['rows']
import csv, re
DOM = collections.defaultdict(set)  # tabella domini del paper: config/domini_v2B.csv (683 brand), varianti comprese
for r in csv.DictReader(open(DATA.parent / 'config' / 'domini_v2B.csv')):
    if r['stato'] in ('no_verified_domain', 'shared_domain_not_attributable'): continue
    for dd in re.split(r'[;, ]+', r['dominio'] or ''):
        if dd.strip(): DOM[r['chiave']].add(dd.strip().lower())
REV = collections.defaultdict(set)
for k, ds in DOM.items():
    for dd in ds: REV[dd].add(k)
P1 = pd.read_csv(INP / 'P1_brand.csv')
NOT = P1.drop_duplicates('chiave').set_index('chiave')['notorieta_log10']
NOME = P1.drop_duplicates('chiave').set_index('chiave')['brand']

men = collections.Counter(); cit = collections.Counter(); N = collections.Counter()
for r in R:
    arm = 'on' if r['search'] else 'off'; cell = (r['engine'], r['sector'], arm); N[cell] += 1
    for k in set(r['B']): men[cell + (k,)] += 1
    if arm == 'on':  # citazione: il dominio del brand fra le fonti, che il brand sia nominato o no
        cits = set()
        for f in set(r.get('fonti_s') or []): cits |= REV.get(f, set())
        for k in cits: cit[cell + (k,)] += 1
E = ['gpt', 'gemini', 'perplexity']; S = sorted({r['sector'] for r in R})
tot = collections.Counter()  # risposte per motore×settore×brand (bracci sommati)
for (e, s, a, k), v in men.items(): tot[(e, s, k)] += v

def tabella(universo, soglia):
    rows = []
    for s in S:
        brands_e = {e: {k for (e2, s2, k), v in tot.items() if e2 == e and s2 == s and v >= soglia} for e in E}
        uni = set().union(*brands_e.values())
        for e in E:
            bs = brands_e[e] if universo == 'per_motore' else uni
            for a in ('off', 'on'):
                n = N[(e, s, a)]
                for k in bs:
                    m = men[(e, s, a, k)]; has_dom = bool(DOM.get(k))
                    c = cit[(e, s, a, k)] if (a == 'on' and has_dom) else np.nan
                    rows.append(dict(motore=e, settore=s, ricerca=a, chiave=k, brand=NOME.get(k, k),
                                     notorieta_log10=NOT.get(k, np.nan), risposte=n, menzioni=m, tasso_menzione=m / n,
                                     tasso_citazione=(c / n) if a == 'on' and has_dom else np.nan,
                                     citazioni_su_menzioni=(c / m) if (a == 'on' and has_dom and m) else np.nan))
    return pd.DataFrame(rows)

if __name__ == '__main__':
    for u in ('per_motore', 'per_settore'):
        for so in (1, 5, 10):
            t = tabella(u, so); t.to_csv(HERE / f'P1_{u}_s{so}.csv', index=False)
            print(u, so, 'righe', len(t), 'brand', t.chiave.nunique(), 'unità motore×settore', len(t[['motore','settore','chiave']].drop_duplicates()),
                  'con notorietà', t.dropna(subset=['notorieta_log10']).chiave.nunique())
    # confronto con P1 del paper
    t = pd.read_csv(HERE / 'P1_per_motore_s5.csv')
    m = P1.merge(t, on=['motore', 'settore', 'ricerca', 'chiave'], how='outer', suffixes=('_p', '_n'), indicator=True)
    print(m._merge.value_counts().to_dict())
    b = m[m._merge == 'both']
    print('diff menzione max', (b.tasso_menzione_p - b.tasso_menzione_n).abs().max(),
          'diff citazione max', (b.tasso_citazione_p - b.tasso_citazione_n).abs().max(),
          'citazione NaN p/n', b.tasso_citazione_p.isna().sum(), b.tasso_citazione_n.isna().sum())
