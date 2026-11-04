"""Study 2, raccolta rivista (24 domande, 25/10/2026): percorsi e dati comuni.
Dati della revisione in data/part2_v4 (disco locale, fuori da iCloud). La prima raccolta (data/part2_v3) resta intatta e
si legge soltanto. I moduli della v3 si riusano invariati, reindirizzando i loro percorsi con usa_v4()."""
import csv, json, os, re, sys, hashlib
from pathlib import Path
ROOT = Path(os.environ.get('TESI_ROOT', '/path/to/project'))  # sul Mac; variabile solo per controlli offline
D = ROOT / 'data/part2_v4'
V3 = ROOT / 'data/part2_v3'
SRC24 = Path(os.environ.get('TESI_SRC24', '/path/to/earlier_workdir'))
sys.path[:0] = [str(ROOT / 'analysis/part2_v3'), str(ROOT / 'analysis/part2_conf')]
from comune_v3 import NOME, DOM, norm, kurl  # noqa: E402
V = {r['chiave']: float(r['volume'] or 0) for r in csv.DictReader((ROOT / 'config/main_notorieta.csv').open())}
MOTORI = ('gpt', 'deepseek', 'perplexity', 'gemini_vertex')
read = lambda p: json.loads(Path(p).read_text())
sha = lambda b: hashlib.sha256(b if isinstance(b, bytes) else b.encode()).hexdigest()


def write(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp'); tmp.write_text(json.dumps(value, ensure_ascii=False, indent=1) + '\n'); tmp.replace(path)


def selezione():
    """{pid: dict(domanda, settore, pagine=[{chiave,nome,dominio}], ...)} nel formato che i moduli v3 si aspettano."""
    return read(D / 'selezione.json')


def usa_v4():
    """Reindirizza a data/part2_v4 i moduli v3 riusati (taratura, neutralizzazione, riscritture, studio, misure)."""
    import taratura_v3, neutralizza_v3, riscrivi_v3, studio_v3, misure_secondarie_v3, familiarita_v3
    sel = selezione()
    taratura_v3.D = D; taratura_v3.sel = sel; taratura_v3.OUT = D / 'taratura.jsonl'
    stim = D / 'stimoli'; stim.mkdir(parents=True, exist_ok=True); rev = D / 'revisione'; rev.mkdir(exist_ok=True)
    sc = read(D / 'scelte.json') if (D / 'scelte.json').exists() else {}
    inv = read(D / 'inventati.json') if (D / 'inventati.json').exists() else {}
    neutralizza_v3.D = D; neutralizza_v3.STIM = stim; neutralizza_v3.REV = rev; neutralizza_v3.sel = sel
    neutralizza_v3.sc = sc; neutralizza_v3.INV = inv
    riscrivi_v3.D = D; riscrivi_v3.STIM = stim
    studio_v3.D = D; studio_v3.STIM = stim; studio_v3.sel = sel
    misure_secondarie_v3.D = D; misure_secondarie_v3.STIM = stim; misure_secondarie_v3.sel = sel
    familiarita_v3.D = D
    familiarita_v3.PRODOTTO.update(read(SRC24 / 'prodotti_controlli24.json'))
    return sel
