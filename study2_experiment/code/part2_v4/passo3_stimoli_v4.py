"""Passo 3 della revisione: stimoli dei bersagli (protocollo sez. 7).
  riuso      copia gli stimoli della prima raccolta quando bersaglio e testo coincidono (con le correzioni del 24/10),
             aggiornando solo più noto, meno noto e nome inventato;
  neutralizza  neutralizzazione dei bersagli nuovi con la procedura della v3 (GPT-5.5); se il content filter di Azure
             blocca la risposta, la stessa istruzione va a Gemini 3.6 Flash e lo si registra;
  riscrivi   le tre riscritture con la procedura della v3 (GPT-5.5 riscrive, DeepSeek-V3.2 giudica), stesso ripiego.
Uso: python passo3_stimoli_v4.py riuso|neutralizza|riscrivi"""
import json, sys, threading
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from comune_v4 import D, V3, NOME, kurl, read, write, usa_v4
RIPIEGHI = {}; _lock = threading.Lock()


class ConRipiego:
    """GPT-5.5; se la risposta è bloccata dal content filter di Azure, la stessa richiesta a gemini_vertex."""
    def __init__(self):
        from motori import motore
        self.gpt, self.alt = motore('gpt'), None
        self.name = 'gpt'
    def once(self, it):
        r = self.gpt.once(it)
        if 'content_filter' in str(r.get('error') or ''):
            from motori import motore
            self.alt = self.alt or motore('gemini_vertex'); r = self.alt.once(it)
            with _lock: RIPIEGHI.setdefault(it.get('call_id', '?'), 0); RIPIEGHI[it.get('call_id', '?')] += 1
            r['motore_ripiego'] = 'gemini_vertex'
        return r


def riuso():
    sc = read(D / 'scelte.json'); sc3 = read(V3 / 'scelte.json'); inv = read(D / 'inventati.json'); fatti = []
    for q, s in sc.items():
        if s['esito'] != 'ok' or sc3.get(q, {}).get('bersaglio') != s['bersaglio'] or (D / 'stimoli' / f'{q}.json').exists(): continue
        x = read(V3 / 'stimoli' / f'{q}.json'); t = read(D / 'testi' / f"{kurl(q + '|' + NOME[s['bersaglio']])}.json")
        if x['testo_sha256'] != t['sha256']: print(q, 'testo diverso: non riusato'); continue
        x['firme_prima_raccolta'] = dict(piu_noto=x['piu_noto'], meno_noto=x['meno_noto'], inventato=x['inventato'])
        x.update(piu_noto=s['piu_noto'], meno_noto=s['meno_noto'], inventato=inv[q]['nome'],
                 origine='stimolo della prima raccolta (data/part2_v3/stimoli), con le correzioni del 24/10; firme aggiornate il 25/10')
        write(D / 'stimoli' / f'{q}.json', x); fatti.append(q)
    print('riusati:', fatti)


def neutralizza():
    usa_v4()
    import neutralizza_v3 as n
    n.motore = lambda _: ConRipiego()
    sc = read(D / 'scelte.json')
    qs = [q for q, s in sc.items() if s['esito'] == 'ok' and not (D / 'stimoli' / f'{q}.json').exists()]
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(11) as ex:
        for x in ex.map(n.neutralizza, qs): print(*x, flush=True)
    write(D / 'ripieghi_neutralizzazione.json', RIPIEGHI); print('ripieghi su Gemini:', RIPIEGHI)


def riscrivi():
    usa_v4()
    import riscrivi_v3 as r
    from motori import motore
    r.motore = lambda m: ConRipiego() if m == 'gpt' else motore(m)
    qs = [f.stem for f in (D / 'stimoli').glob('*.json') if len(read(f).get('riscritture', {})) < 3]
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(12) as ex:
        for x in ex.map(r.riscrivi, qs): print(*x, flush=True)
    write(D / 'ripieghi_riscritture.json', RIPIEGHI); print('ripieghi su Gemini:', RIPIEGHI)


def rivedi():
    """Revisione registrata della v3 (deviazione 13, riscrivi_revisione.py) per le riscritture rimaste senza esito."""
    usa_v4()
    import riscrivi_revisione as rv
    rv.STIM = D / 'stimoli'
    jobs = [(read(f)['pid'], v) for f in (D / 'stimoli').glob('*.json') for v in ('STRUTTURA', 'FLUENCY', 'AUTHORITATIVE')
            if v not in read(f).get('riscritture', {})]
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(8) as ex:
        for x in ex.map(lambda j: rv.rivedi(*j), jobs): print(*x, flush=True)


if __name__ == '__main__':
    {'riuso': riuso, 'neutralizza': neutralizza, 'riscrivi': riscrivi, 'rivedi': rivedi}[sys.argv[1]]()
