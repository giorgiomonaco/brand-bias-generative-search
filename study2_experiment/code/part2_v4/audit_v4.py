"""Audit dei 120 slot di pagina (24 domande × 5 pagine) di data/part2_v4. Nessuna chiamata ai modelli.
Per ogni slot: testo presente e lunghezza, quota di righe scartate dall'estrazione, lingua (parole funzionali italiane
contro inglesi, stessa regola della deviazione 9), indirizzo sul dominio verificato o no, PDF, metodo di cattura,
regola che ha scelto la pagina, duplicati di URL o di testo. Per ogni pannello: cinque marchi distinti, più noto fuori
dalle pagine e non variante di una pagina. Scrive AUDIT_PAGINE.md e audit_pagine.csv."""
import csv, collections, json, re, sys
from pathlib import Path
from urllib.parse import urlsplit
sys.path.insert(0, str(Path(__file__).resolve().parent))
from comune_v4 import D, kurl, read

IT = set("il lo la i gli le di da con per che non una un del della dei delle è sono più come anche questo".split())
EN = set("the and of to with for is are this your our you from on in by".split())


STOP = {"di","del","la","il","le","e","&","the","club","resort","hotel","village","villaggio","camping","viaggi","assicurazioni","assicurazione","spa","italia","world","travel","tour"}


def stesso(a, b):  # come scelte_v3.stesso (copiato per non importare il calcolo delle menzioni)
    from comune_v4 import NOME
    pa = set(re.findall(r"\w+", NOME.get(a, a).lower())) - STOP; pb = set(re.findall(r"\w+", NOME.get(b, b).lower())) - STOP
    return bool(pa) and bool(pb) and (pa <= pb or pb <= pa)


def lingua(t):
    w = re.findall(r"[a-zà-ù']+", t.lower()); i, e = sum(x in IT for x in w), sum(x in EN for x in w)
    return 'it' if i > e else 'en' if e > i else '?'


def main():
    sel = read(D / 'selezione.json'); rows = []; by_url = collections.defaultdict(list); by_sha = collections.defaultdict(list)
    for q, v in sel.items():
        for p in v['pagine']:
            t = read(D / 'testi' / f"{kurl(q + '|' + p['nome'])}.json"); u = p['url']; h = (urlsplit(u).hostname or '').lower()
            meta = read(D / 'pagine' / f'{kurl(u)}.json') if (D / 'pagine' / f'{kurl(u)}.json').exists() else {}
            dom = p['dominio'] or ''
            flags = []
            if t['parole'] < 120: flags.append('testo corto')
            if t.get('parole_grezze') and t['parole'] / t['parole_grezze'] < 0.05: flags.append('estratto <5% della pagina')
            lg = lingua(t['testo'])
            if lg != 'it': flags.append(f'lingua {lg}')
            if not (h == dom or h.endswith('.' + dom)): flags.append(f'host {h} ≠ {dom}')
            if urlsplit(u).path.lower().endswith('.pdf'): flags.append('PDF')
            if p['regola'] == '?': flags.append('regola non ricostruita')
            if meta.get('metodo') and meta['metodo'] not in ('requests', 'brightdata_unlocker_it'): flags.append(f"cattura {meta['metodo']}")
            r = dict(domanda=q, marchio=p['nome'], regola=p['regola'], fonte=p['fonte'], url=u, titolo=(meta.get('titolo') or '')[:90],
                     parole=t['parole'], lingua=lg, segnalazioni='; '.join(flags), inizio=re.sub(r'\s+', ' ', t['testo'])[:160])
            rows.append(r); by_url[u].append(f'{q}|{p["nome"]}'); by_sha[t['sha256']].append(f'{q}|{p["nome"]}')
    for r in rows:
        k = f"{r['domanda']}|{r['marchio']}"; u = r['url']
        d = [x for x in by_url[u] if x != k]
        if d: r['segnalazioni'] = '; '.join(filter(None, [r['segnalazioni'], 'stesso URL di ' + ', '.join(d)]))
    pan = []
    for q, v in sel.items():
        ks = [p['chiave'] for p in v['pagine']]; hi = v['piu_noto']['chiave']; e = []
        if len(set(ks)) != 5: e.append('marchi non distinti')
        if hi in ks: e.append('più noto fra le pagine')
        if any(stesso(hi, k) for k in ks): e.append('più noto variante di una pagina')
        pan.append((q, v['piu_noto']['nome'], ', '.join(p['nome'] for p in v['pagine']), '; '.join(e) or 'ok'))
    with (D / 'audit_pagine.csv').open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    flagged = [r for r in rows if r['segnalazioni']]
    L = ['# Audit delle pagine, Study 2 rivisto', '', f'{len(rows)} slot, {len(flagged)} con almeno una segnalazione. '
         'Le segnalazioni sono da leggere, non esclusioni automatiche.', '', '## Pannelli', '',
         '| Domanda | Più noto | Pagine | Esito |', '|---|---|---|---|'] + [f'| {a} | {b} | {c} | {d} |' for a, b, c, d in pan]
    L += ['', '## Slot con segnalazioni', '', '| Domanda | Marchio | Regola | Parole | Segnalazioni | URL |', '|---|---|---|---:|---|---|']
    L += [f"| {r['domanda']} | {r['marchio']} | {r['regola']} | {r['parole']} | {r['segnalazioni']} | {r['url']} |" for r in flagged]
    (D / 'AUDIT_PAGINE.md').write_text('\n'.join(L) + '\n')
    print(len(rows), 'slot;', len(flagged), 'con segnalazioni'); print('\n'.join(f'{a}: {d}' for a, _, _, d in pan if d != 'ok'))


if __name__ == '__main__':
    main()
