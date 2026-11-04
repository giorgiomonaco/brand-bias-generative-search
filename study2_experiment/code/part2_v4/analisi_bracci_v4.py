"""Analisi dei bracci con marchio e prodotto reali (bracci_reali_v4.py), insieme alle firme della raccolta rivista.
Riraccolta v2 (28/10/2026): i bracci fanno parte del disegno e i contrasti sono fissati nell'emendamento
(Project: parte2/EMENDAMENTO_STUDIO2_V2_2026-10-28.md) prima della raccolta. Stessa procedura di
analisi_v4.py: punteggio = 6 − posizione del bersaglio; contrasti appaiati per motore, domanda, ordine e ripetizione;
ogni contrasto di firma in due versioni: media sui 4 testi (come la Tabella 2 del paper) e solo testo ORIGINALE (come la
figura di Study 2); in più l'effetto delle riscritture dentro i bracci nuovi. Stima = media sulle domande della media dei motori; IC95 bootstrap a grappolo sulle domande (2.000,
seed 20261023); test t a due code sulle medie per domanda; Holm sulla famiglia dei 7 contrasti dei bracci (versione 4 testi;
H2a resta nella famiglia principale).
Uso: python analisi_bracci_v4.py [CARTELLA_part2_v4]"""
import csv, json, random, statistics as st, sys
from collections import defaultdict
from pathlib import Path
D = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('/path/to/project/data/part2_v4')
sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'part2_conf')]
from comune import classifica
MOTORI = ('gpt', 'deepseek', 'perplexity', 'gemini_vertex'); SEED, NB = 20261023, 2000
CONTRASTI = {  # nome: (a, b) -> punteggio(a) − punteggio(b)
    'prodotto_reale_piu_noto': ('PIU_NOTO_REALE', 'PIU_NOTO'),
    'prodotto_reale_meno_noto': ('MENO_NOTO_REALE', 'MENO_NOTO'),
    'prodotto_reale_bersaglio (H2a)': ('REALE', 'BRAND'),
    'piu_noto_reale_vs_reale': ('PIU_NOTO_REALE', 'REALE'),
    'meno_noto_reale_vs_reale': ('MENO_NOTO_REALE', 'REALE'),
    'piu_noto_reale_vs_meno_noto_reale': ('PIU_NOTO_REALE', 'MENO_NOTO_REALE'),
    'piu_noto_reale_vs_inventato': ('PIU_NOTO_REALE', 'INVENTATO'),
    'meno_noto_reale_vs_inventato': ('MENO_NOTO_REALE', 'INVENTATO'),
}


def righe():
    out = {}
    for f in [D / f'studio_{m}.jsonl' for m in MOTORI] + [D / 'bracci_reali' / f'studio_{m}.jsonl' for m in MOTORI]:
        if not f.exists(): continue
        for l in f.open():
            r = json.loads(l)
            if r.get('error'): continue
            c = classifica(r.get('response_text'), r['ordine'])
            if c is None: continue
            out[r['call_id']] = dict(motore=r['motore'], q=r['qid'], firma=r['firma'], testo=r['testo'], j=r['j'], rip=r['rip'],
                                     punteggio=6 - (c.index(r['bersaglio']) + 1))
    return list(out.values())


def stima(pq):
    from scipy import stats
    qs = sorted(pq); xs = [pq[q] for q in qs]; rnd = random.Random(SEED)
    boots = sorted(st.mean(pq[rnd.choice(qs)] for _ in qs) for _ in range(NB))
    t = stats.ttest_1samp(xs, 0) if len(xs) > 1 else None
    return dict(stima=st.mean(xs), ic95=[boots[int(.025 * NB)], boots[int(.975 * NB) - 1]], n_domande=len(xs),
                p_due_code=float(t.pvalue) if t else None)


def main():
    R = righe(); P = defaultdict(dict)
    for r in R: P[(r['motore'], r['q'], r['j'], r['rip'])][(r['firma'], r['testo'])] = r['punteggio']
    n_nuove = sum(1 for r in R if r['firma'].endswith('_REALE') and r['firma'] != 'REALE')
    TESTI = ('ORIGINALE', 'STRUTTURA', 'FLUENCY', 'AUTHORITATIVE')
    def diff(cella, a, b, testi):
        xs = [cella[(a, t)] - cella[(b, t)] for t in testi if (a, t) in cella and (b, t) in cella]
        return st.mean(xs) if xs else None
    def contenuto(cella, f):
        xs = [cella[(f, t)] - cella[(f, 'ORIGINALE')] for t in TESTI[1:] if (f, t) in cella and (f, 'ORIGINALE') in cella]
        return st.mean(xs) if xs else None
    TUTTI = {}
    for nome, (a, b) in CONTRASTI.items():
        TUTTI[nome + ' | 4 testi'] = lambda c, a=a, b=b: diff(c, a, b, TESTI)
        TUTTI[nome + ' | originale'] = lambda c, a=a, b=b: diff(c, a, b, ('ORIGINALE',))
    for f in ('PIU_NOTO_REALE', 'MENO_NOTO_REALE', 'REALE', 'PIU_NOTO', 'MENO_NOTO'):
        TUTTI[f'riscritture_contro_originale {f}'] = lambda c, f=f: contenuto(c, f)
    res = {}
    for nome, fn in TUTTI.items():
        acc = defaultdict(list)
        for (m, q, j, rp), cella in P.items():
            v = fn(cella)
            if v is not None: acc[(m, q)].append(v)
        pmq = {k: st.mean(v) for k, v in acc.items()}
        qs = sorted({q for _, q in pmq})
        pq = {q: st.mean(pmq[(m, q)] for m in MOTORI if (m, q) in pmq) for q in qs}
        if not pq: continue
        res[nome] = stima(pq)
        res[nome]['per_motore'] = {m: st.mean(pmq[(m, q)] for q in qs if (m, q) in pmq) for m in MOTORI if any((m, q) in pmq for q in qs)}
        res[nome]['per_domanda'] = pq
    # posizione media per firma (rango 1–5), sulle domande che hanno entrambi i bracci nuovi
    rango = defaultdict(lambda: defaultdict(list))
    for r in R:
        if r['testo'] == 'ORIGINALE': rango[r['firma']][r['q']].append(6 - r['punteggio'])
    rango_medio = {f: st.mean(st.mean(v) for v in d.values()) for f, d in rango.items()}
    fam = [n + ' | 4 testi' for n in CONTRASTI if 'H2a' not in n and n + ' | 4 testi' in res and res[n + ' | 4 testi']['p_due_code'] is not None]
    ordine = sorted(fam, key=lambda n: res[n]['p_due_code']); corr = 0.0
    for i, n in enumerate(ordine):
        corr = max(corr, min(1.0, (len(ordine) - i) * res[n]['p_due_code'])); res[n]['p_holm'] = corr
    out = dict(classifiche_bracci_nuovi=n_nuove, contrasti=res, rango_medio_per_firma=rango_medio)
    (D / 'bracci_reali' / 'risultati_bracci.json').write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print('classifiche valide nei bracci nuovi:', n_nuove)
    for k, v in res.items():
        print(f"{k:52s} {v['stima']:+.3f} [{v['ic95'][0]:+.3f}; {v['ic95'][1]:+.3f}] p={v['p_due_code'] if v['p_due_code'] is None else round(v['p_due_code'], 4)} holm={round(v['p_holm'], 4) if 'p_holm' in v else '-'} "
              f"n={v['n_domande']} " + ' '.join(f"{m[:4]}={x:+.2f}" for m, x in v['per_motore'].items()))
    print('rango medio per firma, testo originale (1 = primo):', {k: round(v, 2) for k, v in sorted(rango_medio.items(), key=lambda x: x[1])})


if __name__ == '__main__':
    main()
