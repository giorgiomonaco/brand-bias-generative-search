"""Estrae dai file della raccolta rivista una riga per chiamata valida (ultimo record valido per call_id):
motore, domanda, firma, testo, ordine, ripetizione, posizione del bersaglio e punteggio = 6 − posizione.
Nessuna chiamata ai modelli. Scrive data/part2_v4/risultati/punteggi.csv."""
import csv, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from comune_v4 import D, MOTORI
from comune import classifica
if __name__ == '__main__':
    out = {}
    for m in MOTORI:
        for l in (D / f'studio_{m}.jsonl').open():
            r = json.loads(l)
            if r.get('error'): continue
            c = classifica(r.get('response_text'), r['ordine'])
            if c is None: continue
            pos = c.index(r['bersaglio']) + 1
            out[r['call_id']] = dict(motore=m, domanda=r['qid'], firma=r['firma'], testo=r['testo'], j=r['j'], rip=r['rip'],
                                     posizione_nel_messaggio=r['ordine'].index(r['bersaglio']) + 1, rango=pos, punteggio=6 - pos,
                                     lunghezza_risposta=len(r.get('response_text') or ''))
    (D / 'risultati').mkdir(exist_ok=True)
    with (D / 'risultati' / 'punteggi.csv').open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['call_id'] + list(next(iter(out.values())))); w.writeheader()
        for k, v in out.items(): w.writerow(dict(call_id=k, **v))
    print(len(out), 'righe')
