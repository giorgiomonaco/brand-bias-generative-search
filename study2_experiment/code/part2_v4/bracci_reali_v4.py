"""Study 2, bracci aggiunti il 27/10/2026 (riunione con co-author e co-author): marchio più noto e meno noto con un loro
prodotto REALE, al posto del nome di prodotto inventato. Servono a separare due cose che nel braccio PIU_NOTO della
raccolta rivista vanno insieme: la firma di un marchio diverso e un nome di prodotto che nessun modello conosce.

Firme nuove, con tutti e 4 i testi come la raccolta rivista (ORIGINALE, STRUTTURA, FLUENCY, AUTHORITATIVE; le riscritture
sono quelle già congelate, con il nome del prodotto come segnaposto):
  PIU_NOTO_REALE   marchio più noto + il suo prodotto reale
  MENO_NOTO_REALE  marchio meno noto + il suo prodotto reale
Tutto il resto è identico al braccio PIU_NOTO / MENO_NOTO della raccolta rivista (stesse 4 pagine non bersaglio, stessi
recapiti, stessa cornice, stesse riscritture, 10 ordini di Williams × 2 ripetizioni, ricerca spenta, 4 motori): cambia solo il nome del
prodotto principale (e le sue varianti di scrittura) e il percorso dell'URL che lo contiene. Le firme già raccolte
(REALE, BRAND, PIU_NOTO, MENO_NOTO, INVENTATO) non si rifanno: si leggono da data/part2_v4/studio_<motore>.jsonl.
Il nome del prodotto viene da data/part2_v4/bracci_reali/prodotti_reali.json (regola scritta lì, prima delle chiamate).

Uso: python bracci_reali_v4.py --prova     controlli offline, nessuna chiamata
     python bracci_reali_v4.py --congela   impronte SHA-256 di stimoli, prodotti e codice
     python bracci_reali_v4.py MOTORE      raccolta (solo dal Mac, dopo il congelamento)"""
import hashlib, json, re, sys
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from comune_v4 import D, ROOT, MOTORI, NOME, read, write, selezione
B = D / 'bracci_reali'
PROD = B / 'prodotti_reali.json'
MANIFEST = B / 'MANIFEST_BRACCI.json'
FIRME = {'PIU_NOTO_REALE': ('piu_noto', 'PIU_NOTO'), 'MENO_NOTO_REALE': ('meno_noto', 'MENO_NOTO')}
TESTI = ('ORIGINALE', 'STRUTTURA', 'FLUENCY', 'AUTHORITATIVE')
WORKERS = {'gpt': 28, 'deepseek': 8, 'perplexity': 10, 'gemini_vertex': 12}


def _moduli():
    """Reindirizza a data/part2_v4 i moduli v3 che servono (come comune_v4.usa_v4, senza la parte di familiarità)."""
    import taratura_v3, studio_v3
    sel = selezione()
    taratura_v3.D = D; taratura_v3.sel = sel
    studio_v3.D = D; studio_v3.STIM = D / 'stimoli'; studio_v3.sel = sel
    return sel, taratura_v3, studio_v3


def pagina(s, firma, x, studio_v3, testo='ORIGINALE'):
    """Pagina bersaglio della firma nuova: quella di PIU_NOTO/MENO_NOTO con il prodotto reale al posto di quello inventato."""
    base = FIRME[firma][1]
    s2 = dict(s); s2['mappa_inventata'] = dict(s['mappa_inventata'])
    for k, v in nuovi_nomi(s, x, studio_v3).items():
        s2['mappa_inventata'][k] = v
    return studio_v3.pagina_bersaglio(s2, base, testo)


def nuovi_nomi(s, x, studio_v3):
    """{chiave: valore} per il prodotto principale, le sue varianti di scrittura e i livelli derivati dal suo nome."""
    out = {k: studio_v3.adatta(x['nome'], s['mappa_reale'][k]) for k in x['chiavi_prodotto']}
    out.update({k: studio_v3.adatta(x['nome'], s['mappa_reale']['PRODOTTO']) + suf for k, suf in x.get('derivate', {}).items()})
    return out


def piano(motori):
    sel, taratura_v3, studio_v3 = _moduli()
    from comune import williams, messaggio
    pr = read(PROD); items = []
    for pid, v in sel.items():
        s = read(D / 'stimoli' / f'{pid}.json'); altre = taratura_v3.pagine(pid)
        b = [p['chiave'] for p in v['pagine']].index(s['bersaglio'])
        for firma, (ruolo, _) in FIRME.items():
            x = pr[pid][ruolo]
            if not x['nome']:
                continue
            assert x['chiave'] == s[ruolo]
            for testo in TESTI:
                pag = list(altre); pag[b] = pagina(s, firma, x, studio_v3, testo)
                for m in motori:
                    for j, o in enumerate(williams()):
                        for r in range(2):
                            items.append(dict(call_id=f"S|{pid}|{firma}|{testo}|{m}|{j}|{r}", fase='bracci_reali', qid=pid, firma=firma,
                                              testo=testo, motore=m, j=j, rip=r, ordine=o, bersaglio=b,
                                              user_message=messaggio(v['domanda'], pag, o), system_prompt=None, search=False))
    return items


def prova():
    """Controlli prima di spendere: per ogni braccio la pagina bersaglio nuova deve differire da quella del braccio con il
    solo marchio esattamente nel nome del prodotto (e nell'URL); le altre 4 pagine devono essere identiche."""
    sel, taratura_v3, studio_v3 = _moduli()
    pr = read(PROD); problemi = []; righe = []
    for pid, v in sel.items():
        s = read(D / 'stimoli' / f'{pid}.json')
        for firma, (ruolo, base) in FIRME.items():
            x = pr[pid][ruolo]
            if not x['nome']:
                continue
            for testo in TESTI:
              t_new, u_new = pagina(s, firma, x, studio_v3, testo)
              t_old, u_old = studio_v3.pagina_bersaglio(s, base, testo)
              nn = nuovi_nomi(s, x, studio_v3)
              inv = {s['mappa_inventata'][k] for k in nn}
              if not re.search(re.escape(x['nome']), t_new, re.I):
                  problemi.append(f'{pid} {firma}/{testo}: il nome reale non compare nella pagina')
              for i in inv:
                  if re.search(r'(?<![\w])' + re.escape(i.rstrip(' +')) + r'(?![\w])', t_new):
                      problemi.append(f'{pid} {firma}/{testo}: resta il prodotto inventato «{i}»')
              # in avanti: nella pagina del braccio base, i nomi inventati (dal più lungo) diventano quelli reali -> pagina nuova
              fw = t_old
              for k in sorted(nn, key=lambda k: -len(s['mappa_inventata'][k])):
                  fw = re.sub(r'(?<![\w])' + re.escape(s['mappa_inventata'][k]) + r'(?![\w])', lambda _m, v=nn[k]: v, fw)
              if fw != t_new:
                  problemi.append(f'{pid} {firma}/{testo}: la pagina differisce dal braccio {base} oltre al nome del prodotto')
              vero = NOME[s['bersaglio']]
              if re.search(r'(?<![\w])' + re.escape(vero) + r'(?![\w])', t_new, re.I) and not re.search(r'(?<![\w])' + re.escape(vero) + r'(?![\w])', t_old, re.I):
                  problemi.append(f'{pid} {firma}/{testo}: compare il marchio vero del bersaglio')
              righe.append((pid, f'{firma}/{testo}', NOME[s[ruolo]], x['nome'], t_new.count(x['nome']) + t_new.lower().count(x['nome'].lower()) // 2, u_new))
    it = piano(('gpt',))
    # le pagine non bersaglio devono coincidere con quelle della raccolta rivista
    import studio_v3 as sv
    vecchio = {i['call_id']: i['user_message'] for i in sv.piano(('gpt',)) if i['firma'] in ('PIU_NOTO', 'MENO_NOTO')}
    def blocchi(msg): return re.split(r'\n\n(?=\[\d\] Fonte: )', msg)
    for i in it:
        base = FIRME[i['firma']][1]
        old = vecchio[i['call_id'].replace(f"|{i['firma']}|", f'|{base}|')]
        a, b_ = blocchi(i['user_message']), blocchi(old)
        diff = [k for k in range(len(a)) if a[k] != b_[k]]
        pos = i['ordine'].index(i['bersaglio']) + 1  # blocco 0 = domanda; blocco k = pagina in posizione k
        if diff != [pos]:
            problemi.append(f"{i['call_id']}: blocchi diversi {diff}, atteso [{pos}]"); break
    print(f"{len(it)} chiamate per motore, {len(it) * len(MOTORI)} in tutto ({len(righe) // len(TESTI)} bracci × {len(TESTI)} testi × 10 ordini × 2 ripetizioni)")
    for r in righe[::len(TESTI)]:
        print(f"  {r[0]:18} {r[1]:16} {r[2]:20} {r[3]:45} {r[5]}")
    print('PROBLEMI:' if problemi else 'nessun problema', *problemi, sep='\n  ')
    print('\n--- esempio di messaggio ---\n' + it[len(it) // 2]['user_message'][:2500])
    return not problemi


def congela():
    assert prova(), 'controlli non superati'
    h = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
    sel = selezione(); it = piano(('gpt',))
    files = {str(p.relative_to(ROOT)): h(p) for p in [PROD] + [D / 'stimoli' / f'{q}.json' for q in sel] + [D / 'selezione.json']}
    codice = {c: h(ROOT / c) for c in ['analysis/part2_v4/bracci_reali_v4.py', 'analysis/part2_v4/comune_v4.py', 'analysis/part2_v3/studio_v3.py',
                                      'analysis/part2_v3/taratura_v3.py', 'analysis/part2_conf/comune.py', 'analysis/part2_conf/motori.py',
                                      'lavoro/2026-10-27_bracci_reali/conta_prodotti.py']}
    man = dict(creato=datetime.now(timezone.utc).isoformat(),
               via_libera_autore=True, via_libera_quando='2026-10-27T17:38+01:00',
               via_libera_testo='«prepara i bracci reali dello study 2 così lo lancio» (chat del 27/10)',
               bracci=len(it) // (20 * len(TESTI)), testi=list(TESTI), chiamate_per_motore=len(it), motori=list(MOTORI), chiamate_totali=len(it) * len(MOTORI),
               sha256=files, codice_sha256=codice)
    write(MANIFEST, man); print('congelato:', man['chiamate_totali'], 'chiamate')


def raccolta(m):
    assert m in MOTORI
    man = read(MANIFEST)
    for p, hh in {**man['sha256'], **man['codice_sha256']}.items():
        assert hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == hh, f'file cambiato dopo il congelamento: {p}'
    assert man.get('via_libera_autore'), 'manca il via libera di co-author'
    from comune import esegui
    esegui(piano((m,)), B / f'studio_{m}.jsonl', budget_s=1e9, workers=WORKERS)


if __name__ == '__main__':
    a = sys.argv[1]
    if a == '--prova': sys.exit(0 if prova() else 1)
    elif a == '--congela': congela()
    else: raccolta(a)
