import gzip
import json, sys, csv, pickle
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'code'/'part2_conf')]
from comune import classifica
D = ROOT/'data'/'raw'
MOTORI = ('gpt','deepseek','perplexity','gemini_vertex')
out = {}
for f in [D/s/f'studio_{m}.jsonl.gz' for s in ('main', 'real_product_arms', 'real_product_arms_extra') for m in MOTORI]:
    if not f.exists(): print('manca', f); continue
    for l in gzip.open(f, 'rt'):
        r = json.loads(l)
        if r.get('error'): continue
        c = classifica(r.get('response_text'), r['ordine'])
        if c is None: continue
        out[r['call_id']] = (r['motore'], r['qid'], r['firma'], r['testo'], r['j'], r['rip'], c.index(r['bersaglio'])+1)
rows = list(out.values())
with open(ROOT/'data'/'rankings.csv', 'w', newline='') as fh:
    w = csv.writer(fh); w.writerow(['engine', 'question', 'signature', 'text', 'order', 'repetition', 'target_rank']); w.writerows(rows)
print(len(rows))
