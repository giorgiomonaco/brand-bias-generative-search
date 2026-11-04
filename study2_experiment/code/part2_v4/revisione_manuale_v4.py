"""Revisione a mano registrata (protocollo sez. 7.2: «fino a 3 tentativi, poi revisione a mano registrata»).
sport_21 STRUTTURA: dopo la revisione registrata della v3 la sola eccedenza era la lunghezza (1,16 contro il limite 1,15).
Correzione a mano del 25/10: si toglie la frase introduttiva che ripeteva in prosa le specifiche già elencate sotto
(strada, supporto neutro, ammortizzazione normale, obiettivo più veloce) e si rinomina il titoletto. Poi stessi
controlli automatici e stesso giudice (DeepSeek-V3.2)."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from comune_v4 import D, read, write, usa_v4
VECCHIO = ("Per chi è pensata:\nLa scarpa da running {PRODOTTO} è pensata per la strada, con supporto neutro, ammortizzazione "
           "normale e obiettivo più veloce. Garantisce una buona ammortizzazione, robustezza e un efficace sostegno.")
NUOVO = "In sintesi:\nLa scarpa da running {PRODOTTO} garantisce una buona ammortizzazione, robustezza e un efficace sostegno."
if __name__ == '__main__':
    usa_v4()
    from riscrivi_v3 import controlla, GIUDICE
    from motori import motore, with_retries
    f = D / 'stimoli' / 'sport_21.json'; s = read(f); mod = s['modello']
    if 'STRUTTURA' in s['riscritture']: print('già fatto'); sys.exit()
    att = s['log_revisione']['STRUTTURA'][-1]['testo']; assert att.count(VECCHIO) == 1
    nuovo = att.replace(VECCHIO, NUOVO); e = controlla(mod, nuovo)
    if not e:
        g = with_retries(motore('deepseek'), dict(call_id='G', user_message=GIUDICE.format(a=mod, b=nuovo), system_prompt=None, search=False))
        gt = g.get('response_text') or ''
        if 'ESITO: UGUALI' not in gt.upper().replace('**', ''): e.append('giudice: ' + gt[-300:])
    s['log_revisione']['STRUTTURA'].append(dict(passo='a mano 25/10', errori=e, testo=nuovo, modifica=dict(da=VECCHIO, a=NUOVO)))
    if not e: s['riscritture']['STRUTTURA'] = nuovo; s.setdefault('riscritture_riviste', []).append('STRUTTURA (a mano)')
    write(f, s); print('sport_21 STRUTTURA', 'ok' if not e else e, len(nuovo.split()), len(mod.split()))
