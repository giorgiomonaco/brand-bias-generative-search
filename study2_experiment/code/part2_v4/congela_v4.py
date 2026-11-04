"""Congela la raccolta rivista: impronte SHA-256 di selezione, scelte, nomi inventati, testi delle 120 pagine, stimoli e
codice; conteggio delle chiamate dal piano effettivo (studio_v4.piano). Nessuna chiamata ai modelli. Il campo
via_libera_autore resta False: lo si mette a True solo dopo l'approvazione esplicita."""
import hashlib, json, sys
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from comune_v4 import D, ROOT, MOTORI, NOME, kurl, read, write
h = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
if __name__ == '__main__':
    from studio_v4 import piano
    sel, sc = read(D / 'selezione.json'), read(D / 'scelte.json')
    files = ['selezione.json', 'scelte.json', 'inventati.json'] + [f'stimoli/{q}.json' for q in sel]
    files += sorted(f"testi/{kurl(q + '|' + p['nome'])}.json" for q, v in sel.items() for p in v['pagine'])
    codice = sorted(str(p.relative_to(ROOT)) for d in ('analysis/part2_v4', 'analysis/part2_v3', 'analysis/part2_conf') for p in (ROOT / d).glob('*.py'))
    it = piano(('gpt',))
    man = dict(creato=datetime.now(timezone.utc).isoformat(), via_libera_autore=False,
               domande=len(sel), bersagli={q: dict(bersaglio=NOME[s['bersaglio']], piu_noto=NOME[s['piu_noto']], meno_noto=NOME[s['meno_noto']],
                                                   dentro_2_4=s['dentro_2_4']) for q, s in sc.items()},
               chiamate_per_motore=len(it), motori=list(MOTORI), chiamate_totali=len(it) * len(MOTORI),
               sha256={f: h(D / f) for f in files}, codice_sha256={c: h(ROOT / c) for c in codice})
    assert all(s['esito'] == 'ok' for s in sc.values()) and len(it) == 24 * 5 * 4 * 20
    write(D / 'MANIFEST_STUDIO.json', man); print('congelati', len(files), 'file e', len(codice), 'file di codice;', man['chiamate_totali'], 'chiamate')
