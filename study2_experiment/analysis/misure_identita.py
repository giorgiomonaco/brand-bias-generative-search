"""Misure sull'identità per Study 2, riraccolta v2 (29/10/2026). Nessuna chiamata.
1. Attribuzione nelle risposte vere: quota di risposte che nominano il marchio originale della pagina, per firma.
2. Riconoscibilità V1 (test_ric_v2): quota per domanda e media; relazione per domanda con l'effetto dell'identità (H1).
3. Distanze di notorietà fra bersaglio, più noto e meno noto (log10 del volume di ricerca di Study 1)."""
import gzip
import json, re, csv, glob, math, statistics as st, unicodedata, collections
from pathlib import Path
from scipy import stats
R = Path(__file__).resolve().parents[1]; D = R / 'materials'; H = Path(__file__).parent
def n(s): return ' ' + re.sub(r'[^a-z0-9]+', ' ', unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode().lower()) + ' '
st_ = {json.load(open(f))['pid']: json.load(open(f)) for f in glob.glob(str(D / 'stimoli/*.json'))}
def chiave(b): return n(b.replace('.it', '').replace('’', "'"))
cnt = collections.defaultdict(lambda: [0, 0]); perq = collections.defaultdict(lambda: [0, 0])
for m in ('gpt', 'deepseek', 'perplexity', 'gemini_vertex'):
    for l in gzip.open(R / 'data' / 'raw' / 'main' / f'studio_{m}.jsonl.gz', 'rt'):
        r = json.loads(l)
        if r.get('error') or not r.get('response_text'): continue
        s = st_[r['qid']]; hit = chiave(s['brand']) in n(r['response_text'])
        cnt[r['firma']][0] += hit; cnt[r['firma']][1] += 1
        perq[(r['qid'], r['firma'])][0] += hit; perq[(r['qid'], r['firma'])][1] += 1
attr = {f: round(a / b, 4) for f, (a, b) in cnt.items()}
reale = {q: perq[(q, 'REALE')][0] / perq[(q, 'REALE')][1] for q in st_}
leggibili = [q for q, v in reale.items() if v >= 0.5]   # domande in cui il nome si aggancia nelle risposte con firma vera
attr_legg = {f: round(sum(perq[(q, f)][0] for q in leggibili) / sum(perq[(q, f)][1] for q in leggibili), 4) for f in cnt}
# riconoscibilità V1
sys_path = R / 'data' / 'recognition'
import sys; sys.path.insert(0, str(sys_path))
rv = collections.defaultdict(list)
def norm(s): return re.sub(r'[^a-z0-9]+', '', unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode().lower())
def giusto(brand, risp):
    m = re.search(r'MARCHIO\W*(.+)', risp or '', re.I); a = norm(m.group(1) if m else risp)
    vero = norm(brand).replace('it', '') if brand == 'ConTe.it' else norm(brand)
    return bool(vero) and vero in a
ult = {}
for l in open(sys_path / 'risposte_v2.jsonl'):
    r = json.loads(l)
    if not r.get('error'): ult[r['call_id']] = r
for r in ult.values(): rv[r['pid']].append(giusto(r['marchio'], r.get('response_text')))
ric = {q: round(sum(v) / len(v), 3) for q, v in rv.items()}
ric_motore = collections.defaultdict(list)
for r in ult.values(): ric_motore[r['motore']].append(giusto(r['marchio'], r.get('response_text')))
ris = json.loads((R / 'data' / 'scores_main' / 'risultati' / 'risultati_v4.json').read_text())
h1q = ris['risultati']['H1'].get('per_domanda') if isinstance(ris.get('risultati', {}).get('H1'), dict) else None
rho = None
if h1q:
    qs = sorted(set(ric) & set(h1q)); rho = [round(float(x), 3) for x in stats.spearmanr([ric[q] for q in qs], [h1q[q] for q in qs])]
# distanze
V = {r['chiave']: float(r['volume'] or 0) for r in csv.DictReader(open(R.parent / 'study1_audit' / 'config' / 'main_notorieta.csv'))}
N = {r['chiave']: r['nome'] for r in csv.DictReader(open(R.parent / 'study1_audit' / 'config' / 'main_notorieta.csv'))}
sc = json.loads((D / 'scelte.json').read_text()); dist = {}
for q in st_:
    t, p, m = sc[q]['bersaglio'], sc[q]['piu_noto'], sc[q]['meno_noto']
    dist[q] = dict(bersaglio=N[t], piu_noto=N[p], meno_noto=N[m], su=round(math.log10(V[p] / V[t]), 2), giu=round(math.log10(V[t] / V[m]), 2))
out = dict(attribuzione=attr, attribuzione_domande_leggibili=dict(n=len(leggibili), quote=attr_legg), riconoscibilita_v1=dict(media=round(st.mean(ric.values()), 3),
      per_domanda=ric, per_motore={m: round(sum(v) / len(v), 3) for m, v in ric_motore.items()}, spearman_con_H1=rho), distanze=dist,
      distanze_riassunto=dict(su_media=round(st.mean(d['su'] for d in dist.values()), 2), giu_media=round(st.mean(d['giu'] for d in dist.values()), 2),
                              giu_maggiore=sum(d['giu'] > d['su'] for d in dist.values()), min_totale=round(min(d['su'] + d['giu'] for d in dist.values()), 2)))
(H / 'misure_identita.json').write_text(json.dumps(out, ensure_ascii=False, indent=1))
print(json.dumps({k: v for k, v in out.items() if k != 'distanze'}, ensure_ascii=False, indent=1)[:2500])
