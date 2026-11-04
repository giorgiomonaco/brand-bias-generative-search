"""Costruisce data/part2_v4 dalla selezione a 24 domande (25/10/2026). Nessuna chiamata ai modelli.
- selezione.json: domande, cinque pagine per domanda (con le sostituzioni D2 delle fonti), più noto di base, candidati
  con la notorietà congelata di Study 1;
- testi/ e pagine/: copie dei testi estratti e delle catture (dalla prima raccolta, se la stessa pagina c'era già, o dal
  recupero del 25/10), con provenienza;
- taratura_<motore>.jsonl: per i pannelli identici alla prima raccolta (stesse cinque pagine, stesso ordine, stessi
  testi) si copiano le chiamate di taratura già fatte; gli altri pannelli vanno tarati;
- inventati.json: i nomi inventati della prima raccolta e, per le domande nuove, nomi nuovi con dominio .it inesistente
  (controllo DNS pubblico di Google, come inventati.py).
Uso: python costruisci_v4.py"""
import json, shutil, sys
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from comune_v4 import D, V3, SRC24, NOME, DOM, V, MOTORI, norm, kurl, read, write, sha

NUOVI_INVENTATI = {  # fissati il 25/10 prima di qualunque chiamata; alternative in ordine se il dominio esiste
    'sport_17': ['Brovale', 'Tarvino', 'Quernia'], 'moda_beauty_05': ['Ilvessa', 'Morvane', 'Selvira'],
    'assicurazioni_03': ['Dalveris', 'Corvessa', 'Nalvoria'], 'assicurazioni_09': ['Velunia', 'Trevalda', 'Orsilve'],
    'assicurazioni_10': ['Corlenta', 'Marvesia', 'Ostrelia']}


def dns_inesistente(nome):
    import requests
    r = requests.get('https://dns.google/resolve', params=dict(name=nome.lower() + '.it', type='SOA'), timeout=15).json()
    return r.get('Status') == 3, r.get('Status')


def main():
    D.mkdir(parents=True, exist_ok=True)
    for n in ('testi', 'pagine', 'salvate_a_mano'): (D / n).mkdir(exist_ok=True)
    s24 = read(SRC24 / 'selezione24.json'); sel24 = s24['selection']
    pannelli = read(SRC24 / 'dati_pagine24/pannelli_D2.json')
    v3sel = read(V3 / 'selezione_v3.json')
    reg = {'v3': (read(V3 / 'regola1.json'), read(V3 / 'regola2.json')),
           'rev': (read(SRC24 / 'dati_pagine24/regola1.json'), read(SRC24 / 'dati_pagine24/regola2.json'))}
    src = {'v3': (V3 / 'testi', V3 / 'pagine'), 'rev': (SRC24 / 'dati_pagine24/testi', SRC24 / 'dati_pagine24/pagine')}
    out, report = {}, {}
    for q, s in sel24.items():
        pages = pannelli[q]['pages'] if q in pannelli else s['pages']
        righe = []
        for k in pages:
            key = f'{q}|{NOME[k]}'; h = kurl(key)
            fonte = 'v3' if (V3 / 'testi' / f'{h}.json').exists() else 'rev'
            t = read(src[fonte][0] / f'{h}.json'); u = t['url']
            r1, r2 = reg[fonte]
            regola = 'regola 1' if r1.get(key, {}).get('scelta') == u else (r2.get(key, {}).get('regola') or '?')
            (D / 'testi' / f'{h}.json').write_text(json.dumps(dict(t, chiave=key, fonte_preparazione=fonte), ensure_ascii=False, indent=1))
            hu = kurl(u); copiati = []
            for ext in ('.json', '.txt', '.html.gz'):
                f = src[fonte][1] / f'{hu}{ext}'
                if f.exists(): shutil.copy2(f, D / 'pagine' / f.name); copiati.append(ext)
            meta = read(D / 'pagine' / f'{hu}.json') if '.json' in copiati else {}
            righe.append(dict(chiave=k, nome=NOME[k], dominio=DOM.get(k), notorieta_s1=V[k], url=u, regola=regola, fonte=fonte,
                              metodo=meta.get('metodo'), parole=t.get('parole'), testo_sha256=t.get('sha256')))
        hi = s['base_higher']
        out[q] = dict(domanda=s['prompt'], settore=s['sector'], volume_domanda=s['volume'], sottotema=s.get('subtopic'),
                      piu_noto=dict(chiave=hi, nome=NOME[hi], dominio=DOM.get(hi), notorieta_s1=V[hi]), pagine=righe,
                      candidati=[dict(chiave=k, nome=NOME[k], dominio=DOM.get(k), notorieta_s1=V[k]) for k in s['candidates']],
                      sostituzioni=pannelli.get(q, {}).get('substitutions', []))
        # taratura riusabile solo se pannello, ordine e testi coincidono con la prima raccolta
        old = [p['chiave'] for p in v3sel.get(q, {}).get('pagine', [])]
        report[q] = dict(taratura_riusata=old == pages and all(r['fonte'] == 'v3' for r in righe))
    for p in (SRC24 / 'dati_pagine24/salvate_a_mano').glob('*'):
        shutil.copy2(p, D / 'salvate_a_mano' / p.name)
    write(D / 'selezione.json', out)
    # taratura della prima raccolta per i pannelli identici
    riuso = {q for q, r in report.items() if r['taratura_riusata']}
    for m in MOTORI:
        f = V3 / f'taratura_{m}.jsonl'; n = 0
        with (D / f'taratura_{m}.jsonl').open('w') as o:
            for l in f.open():
                if json.loads(l)['qid'] in riuso: o.write(l); n += 1
        report.setdefault('_righe_taratura_copiate', {})[m] = n
    # nomi inventati
    inv3 = read(V3 / 'inventati.json'); reali = {norm(n) for n in NOME.values()}; inv = {}
    for q in out:
        if q in inv3: inv[q] = dict(inv3[q], origine='prima raccolta'); continue
        for nome in NUOVI_INVENTATI[q]:
            nx, st = dns_inesistente(nome)
            if nx and norm(nome) not in reali:
                inv[q] = dict(nome=nome, dominio=nome.lower() + '.it', dns_status=st, nxdomain=True, uguale_a_marchio_noto=False,
                              controllato=datetime.now(timezone.utc).isoformat(), origine='25/10 revisione'); break
        assert q in inv, q
    write(D / 'inventati.json', inv)
    report['_creato'] = datetime.now(timezone.utc).isoformat()
    report['_sha256'] = {p.name: sha(p.read_bytes()) for p in (D / 'selezione.json', D / 'inventati.json')}
    write(D / 'costruzione.json', report)
    print('domande:', len(out), '| pannelli con taratura riusata:', sorted(riuso))
    print('righe di taratura copiate:', report['_righe_taratura_copiate'])
    print('inventati nuovi:', {q: v['nome'] for q, v in inv.items() if v['origine'] != 'prima raccolta'})


if __name__ == '__main__':
    main()
