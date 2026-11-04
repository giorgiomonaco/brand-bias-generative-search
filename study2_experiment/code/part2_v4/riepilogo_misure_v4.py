"""Riepilogo delle misure secondarie (nessuna chiamata): per domanda, media sui 4 motori (ogni motore: media delle 3
ripetizioni) di familiarità di bersaglio, più noto e meno noto, notorietà secondo i modelli (più noto e bersaglio),
quota di riconoscimenti del marchio vero dal testo neutralizzato, coerenza percepita per firma. Scrive
MISURE_SECONDARIE.md e misure_secondarie.json. Le misure non cambiano nessuna scelta (decisione del 25/10)."""
import json, re, statistics as st, sys, unicodedata
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from comune_v4 import D, NOME, MOTORI, read, write
fold = lambda s: ''.join(c for c in unicodedata.normalize('NFKD', s or '').casefold() if c.isalnum())


def num(t, lo, hi):
    t = re.sub(r'[*_]', '', t or ''); m = re.search(r'PUNTEGGIO\W*(\d+(?:[.,]\d+)?)', t, re.I) or re.match(r'\s*(\d+(?:[.,]\d+)?)\s*(?:\n|$)', t)
    if not m: return None
    v = float(m.group(1).replace(',', '.')); return v if lo <= v <= hi else None


def media_motori(d):
    per = [st.mean(v) for v in d.values() if v]; return round(st.mean(per), 2) if per else None


def main():
    sc = read(D / 'scelte.json'); fam, sec = {}, {}
    for m in MOTORI:
        last = {}
        for l in (D / f'familiarita_{m}.jsonl').open():
            r = json.loads(l)
            if r.get('punteggio') is not None: last[r['call_id']] = r
        for r in last.values(): fam.setdefault((r['pid'], r['chiave']), {}).setdefault(m, []).append(r['punteggio'])
        last = {}
        for l in (D / f'secondarie_{m}.jsonl').open():
            r = json.loads(l)
            if r.get('response_text') and not r.get('error'): last[r['call_id']] = r
        for r in last.values():
            t = r['response_text']
            if r['tipo'] == 'notorieta_modelli': v, k = num(t, 0, 10), ('N', r['pid'], fold(r['marchio']))
            elif r['tipo'] == 'coerenza': v, k = num(t, 0, 3), ('C', r['pid'], r['firma'])
            else:
                mm = re.search(r'MARCHIO\s*:\s*(.+)', t, re.I); g = fold(mm.group(1) if mm else '')
                v, k = float(bool(g) and (fold(r['marchio']) in g or g in fold(r['marchio']))), ('R', r['pid'])
            if v is not None: sec.setdefault(k, {}).setdefault(m, []).append(v)
    out, L = {}, ['# Misure secondarie della raccolta rivista', '',
                  'Media dei 4 motori (3 ripetizioni ciascuno). Controlli e moderatori, non criteri di scelta.', '',
                  '| Domanda | Bersaglio | Fam. bers. | Più noto | Fam. | Meno noto | Fam. | Not. modelli più noto / bers. (0-10) | Riconosc. | Coerenza REALE / PIÙ NOTO / MENO NOTO / INVENTATO (0-3) |',
                  '|---|---|---:|---|---:|---|---:|---|---:|---|']
    for q, s in sc.items():
        t, a, b = s['bersaglio'], s['piu_noto'], s['meno_noto']
        f = lambda k: media_motori(fam.get((q, k), {}))
        o = dict(fam_bersaglio=f(t), fam_piu_noto=f(a), fam_meno_noto=f(b),
                 not_piu_noto=media_motori(sec.get(('N', q, fold(NOME[a])), {})), not_bersaglio=media_motori(sec.get(('N', q, fold(NOME[t])), {})),
                 riconoscimento=media_motori(sec.get(('R', q), {})),
                 coerenza={fi: media_motori(sec.get(('C', q, fi), {})) for fi in ('REALE', 'PIU_NOTO', 'MENO_NOTO', 'INVENTATO')})
        out[q] = o; c = o['coerenza']
        L.append(f"| {q} | {NOME[t]} | {o['fam_bersaglio']} | {NOME[a]} | {o['fam_piu_noto']} | {NOME[b]} | {o['fam_meno_noto']} | "
                 f"{o['not_piu_noto']} / {o['not_bersaglio']} | {o['riconoscimento']} | {c['REALE']} / {c['PIU_NOTO']} / {c['MENO_NOTO']} / {c['INVENTATO']} |")
    write(D / 'misure_secondarie.json', out); (D / 'MISURE_SECONDARIE.md').write_text('\n'.join(L) + '\n'); print('\n'.join(L))


if __name__ == '__main__':
    main()
