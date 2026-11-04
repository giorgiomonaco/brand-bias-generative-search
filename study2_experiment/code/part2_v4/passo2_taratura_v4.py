"""Passo 2 della revisione: (a) ripete l'estrazione del testo di viaggi_07|Eden Viaggi, vuota anche nella prima raccolta
(0 parole estratte da una pagina di 2.856); (b) taratura dei pannelli non identici alla prima raccolta, con la procedura
della v3 (5 pagine originali, 10 ordini di Williams, 1 ripetizione, motore per motore). viaggi_07 si ritara perché
cambia il testo di una pagina; le sue righe di taratura della prima raccolta si spostano in taratura_scartata_viaggi_07.
Uso: python passo2_taratura_v4.py estrai | python passo2_taratura_v4.py MOTORE"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from comune_v4 import D, MOTORI, kurl, read, sha
RITARARE_PER_TESTO = {'viaggi_07'}


def da_tarare(sel):
    riuso = {q for q, r in read(D / 'costruzione.json').items() if not q.startswith('_') and r['taratura_riusata']}
    return sorted(set(sel) - (riuso - RITARARE_PER_TESTO))


def estrai():
    from comune_v4 import usa_v4
    sel = usa_v4()
    import p4_estrai as ex
    ex.TD = D / 'testi'; ex.OUT = D / 'pagine'; ex.sel = sel
    key = 'viaggi_07|Eden Viaggi'; f = D / 'testi' / f'{kurl(key)}.json'; old = read(f)
    if old['parole'] > 0: print('già rifatta:', old['parole'], 'parole'); return
    (D / 'testi_sostituiti').mkdir(exist_ok=True); (D / 'testi_sostituiti' / f.name).write_text(f.read_text())
    # GPT-5.5 su Azure blocca la copia parola per parola di questa pagina (content_filter, verificato il 25/10): stessa
    # istruzione e stesso controllo riga per riga sul testo originale, con Gemini 3.6 Flash come estrattore.
    from motori import motore
    ex.motore = lambda _: motore('gemini_vertex')
    for tent in range(3):
        _, new = ex.estrai(key, old['url'])
        if new['parole'] > 0: break
    new.update(chiave=key, estrattore='gemini_vertex (GPT bloccato dal content filter di Azure)',
               fonte_preparazione='v3, estrazione ripetuta il 25/10 (prima: 0 parole)', estrazione_precedente_sha256=old['sha256'])
    f.write_text(json.dumps(new, ensure_ascii=False, indent=1)); print(key, 'parole:', new['parole'])
    for m in MOTORI:  # le righe di taratura di viaggi_07 non valgono più per questo pannello
        p = D / f'taratura_{m}.jsonl'; rows = p.read_text().splitlines()
        keep = [l for l in rows if json.loads(l)['qid'] not in RITARARE_PER_TESTO]
        with (D / 'taratura_scartata_viaggi_07.jsonl').open('a') as o:
            o.write(''.join(l + '\n' for l in rows if json.loads(l)['qid'] in RITARARE_PER_TESTO))
        p.write_text(''.join(l + '\n' for l in keep))


def tara(m):
    from comune_v4 import usa_v4
    sel = usa_v4()
    import taratura_v3
    from comune import esegui
    q = set(da_tarare(sel))
    assert read(D / 'testi' / f"{kurl('viaggi_07|Eden Viaggi')}.json")['parole'] > 0, 'prima: estrai'
    items = [i for i in taratura_v3.piano((m,)) if i['qid'] in q]
    print(m, 'domande da tarare:', len(q), 'chiamate:', len(items), flush=True)
    esegui(items, D / f'taratura_{m}.jsonl', budget_s=1e9, workers={'gpt': 24, 'deepseek': 6, 'perplexity': 8, 'gemini_vertex': 10})


if __name__ == '__main__':
    estrai() if sys.argv[1] == 'estrai' else tara(sys.argv[1])
