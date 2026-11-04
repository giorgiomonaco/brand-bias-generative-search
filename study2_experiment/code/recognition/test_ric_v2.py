"""Versione v2 (28/10/2026, sera): solo la variante V1 (marchio sostituito da [MARCHIO], nomi inventati come nello
studio, domanda corretta) su tutte le 24 domande, sui testi della neutralizzazione v2. Misura del limite superiore di
riconoscibilità, come il leak test di Chen & Koudas (2026).
--- testo originale del test ---
Test diagnostico del 28/10/2026: da dove viene il riconoscimento del marchio vero dal testo neutralizzato?
Nessuna conseguenza sulle analisi di Study 2: serve a capire quale indizio pesa. Testo ORIGINALE della pagina bersaglio,
4 motori, 3 ripetizioni, ricerca spenta, nessun system prompt.
  V0  come la misura del 25/10: pagina con firma inventata, stessa domanda («da cui sono stati tolti i nomi…»)
  V1  marchio sostituito da [MARCHIO]; nomi inventati di prodotto e tecnologie come nello studio
  V2  come V1, ma prodotti e tecnologie diventano segnaposto senza forma: [PRODOTTO], [TECNOLOGIA 1]…
  V3  come V2, togliendo le righe che contengono una tecnologia
Domande: le 5 col riconoscimento più alto non toccate dalla correzione dei nomi + le 3 corrette il 28/10.
Uso: python test_ric.py --prova (nessuna chiamata) | python test_ric.py (dal Mac)"""
import json, re, sys, time, threading, collections, unicodedata
from pathlib import Path
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
R = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(R / 'analysis/part2_v4'), str(R / 'analysis/part2_v3'), str(R / 'analysis/part2_conf')]
import bracci_reali_v4 as b
sel, tv3, sv3 = b._moduli()
Q = sorted(json.loads((R / 'data/part2_v4/selezione.json').read_text()))
MOTORI = ('gpt', 'deepseek', 'perplexity', 'gemini_vertex')
OUT = Path(__file__).with_name('risposte_v2.jsonl')
P0 = ("Questo è il testo di una pagina prodotto da cui sono stati tolti i nomi del marchio e del prodotto.\n---\n{t}\n---\n"
      "Di quale marchio reale pensi che sia? Rispondi con una sola riga: MARCHIO: nome del marchio, oppure MARCHIO: NON SO")
P1 = ("Questo è il testo di una pagina prodotto in cui il nome del marchio è stato sostituito da [MARCHIO]{extra}.\n---\n{t}\n---\n"
      "Di quale marchio reale pensi che sia? Rispondi con una sola riga: MARCHIO: nome del marchio, oppure MARCHIO: NON SO")
def norm(s):
    s = unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '', s)
def testo(s, var):
    s2 = json.loads(json.dumps(s))
    if var == 'V0':
        return sv3.pagina_bersaglio(s2, 'INVENTATO', 'ORIGINALE')[0]
    s2['inventato'] = '[MARCHIO]'
    if var in ('V2', 'V3'):
        np = nt = 0
        for k in s2['mappa_reale']:
            if k.startswith('PRODOTTO'):
                np += 1; s2['mappa_inventata'][k] = '[PRODOTTO]' if k == 'PRODOTTO' else f'[PRODOTTO {np}]'
            elif k.startswith('TECH'):
                nt += 1; s2['mappa_inventata'][k] = f'[TECNOLOGIA {nt}]'
    t = sv3.pagina_bersaglio(s2, 'INVENTATO', 'ORIGINALE')[0]
    t = t.replace('[marchio]', '[MARCHIO]')
    if var == 'V3':
        t = '\n'.join(l for l in t.splitlines() if '[TECNOLOGIA' not in l)
    return t
def piano():
    it = []
    for pid in Q:
        s = b.read(b.D / 'stimoli' / f'{pid}.json')
        for var in ('V1',):
            t = testo(s, var)
            extra = '' if var == 'V1' else ' e i nomi del prodotto e delle tecnologie da segnaposto tra parentesi quadre'
            msg = P0.format(t=t) if var == 'V0' else P1.format(t=t, extra=extra)
            for m in MOTORI:
                for r in range(3):
                    it.append(dict(call_id=f'T2|{pid}|{var}|{m}|{r}', pid=pid, var=var, marchio=s['brand'], motore=m, rip=r,
                                   user_message=msg, system_prompt=None, search=False))
    return it
def giusto(brand, risp):
    m = re.search(r'MARCHIO\W*(.+)', risp or '', re.I); a = norm(m.group(1) if m else risp)
    vero = norm(brand).replace('it', '') if brand == 'ConTe.it' else norm(brand)
    return bool(vero) and vero in a
def riepilogo():
    ult = {}
    for l in OUT.open():
        r = json.loads(l)
        if not r.get('error'): ult[r['call_id']] = r
    tab = collections.defaultdict(list)
    for r in ult.values(): tab[(r['pid'], r['var'])].append(giusto(r['marchio'], r.get('response_text')))
    print(f"{'domanda':18} " + ' '.join(f'{v:>6}' for v in ('V0', 'V1', 'V2', 'V3')))
    for pid in Q:
        print(f'{pid:18} ' + ' '.join(f"{sum(tab[(pid, v)]) / len(tab[(pid, v)]):6.2f}" if tab[(pid, v)] else '     -' for v in ('V0', 'V1', 'V2', 'V3')))
    for v in ('V0', 'V1', 'V2', 'V3'):
        xs = [sum(tab[(p, v)]) / len(tab[(p, v)]) for p in Q if tab[(p, v)]]
        print(f'media {v}: {sum(xs) / len(xs):.2f}' if xs else '')
if __name__ == '__main__':
    it = piano()
    if sys.argv[1:] == ['--prova']:
        print(len(it), 'chiamate')
        for v in ('V1',):
            x = next(i for i in it if i['pid'] == 'sport_21' and i['var'] == v); print('=====', v); print(x['user_message'][:1300])
        sys.exit()
    if sys.argv[1:] == ['--riepilogo']: riepilogo(); sys.exit()
    from motori import motore
    done = set()
    if OUT.exists():
        for l in OUT.open():
            r = json.loads(l)
            if not r.get('error') and r.get('response_text'): done.add(r['call_id'])
    todo = [i for i in it if i['call_id'] not in done]; print('da fare', len(todo), flush=True)
    lock = threading.Lock(); engs = {}
    def run(i):
        m = i['motore']
        with lock:
            if m not in engs: engs[m] = motore(m)
        for _ in range(5):
            rec = engs[m].once(i)
            if not (rec.get('error') and '429' in str(rec.get('error'))[:40]): break
            time.sleep(8)
        out = {k: i[k] for k in ('call_id', 'pid', 'var', 'marchio', 'motore', 'rip')}
        out.update(response_text=rec.get('response_text'), error=rec.get('error'), model_version=rec.get('model_version'),
                   timestamp=datetime.now(timezone.utc).isoformat())
        with lock:
            with OUT.open('a') as f: f.write(json.dumps(out, ensure_ascii=False) + '\n')
    with ThreadPoolExecutor(24) as ex: list(ex.map(run, todo))
    riepilogo()
