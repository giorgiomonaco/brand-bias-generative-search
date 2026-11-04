"""Raccolta rivista di Study 2 (protocollo v2.0 sez. 9, con le deviazioni in data/part2_v4/REVISIONE_STUDY2.md):
per ogni domanda 5 firme × 4 testi × 10 ordini di Williams × 2 ripetizioni, per motore; ricerca spenta, nessun system
prompt, nessuna persona, cornice del messaggio identica. Usa studio_v3 senza modifiche, reindirizzato su data/part2_v4;
le risposte vanno in data/part2_v4/studio_<motore>.jsonl, separate dalla prima raccolta.
Uso: python studio_v4.py --prova   (nessuna chiamata)   |   python studio_v4.py MOTORE   (solo dopo il via di co-author)"""
import hashlib, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from comune_v4 import D, MOTORI, read, usa_v4
MANIFEST = D / 'MANIFEST_STUDIO.json'


def piano(motori):
    usa_v4()
    import studio_v3
    return studio_v3.piano(motori)


if __name__ == '__main__':
    if sys.argv[1] == '--prova':
        it = piano(('gpt',)); print(len(it), 'chiamate per motore;', len(it) * len(MOTORI), 'in tutto')
        print(it[len(it) // 3]['user_message'][:3000]); sys.exit()
    m = sys.argv[1]; assert m in MOTORI
    man = read(MANIFEST)  # il manifest congelato deve corrispondere ai file attuali
    for p, h in man['sha256'].items():
        assert hashlib.sha256((D / p).read_bytes()).hexdigest() == h, f'file cambiato dopo il congelamento: {p}'
    assert man.get('via_libera_autore'), 'manca il via libera di co-author nel manifest'
    from comune import esegui
    esegui(piano((m,)), D / f'studio_{m}.jsonl', budget_s=1e9, workers={'gpt': 28, 'deepseek': 8, 'perplexity': 10, 'gemini_vertex': 12})
