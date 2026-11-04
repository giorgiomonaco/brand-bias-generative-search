"""Analisi della raccolta rivista di Study 2 (protocollo v2.0 sez. 10; robustezza in REVISIONE_STUDY2.md).
Stessi contrasti e stessa procedura di analysis/part2_v3/analisi_v3.py, calcolati da risultati/punteggi.csv
(estrai_punteggi_v4.py): punteggio = 6 − posizione del bersaglio; contrasti appaiati per motore, domanda, ordine e
ripetizione; stima per motore = media dei contrasti per domanda; stima principale = media sulle domande della media dei
motori. IC95 bootstrap a grappolo sulle domande (2.000 ricampionamenti, seed 20261023), test t a una coda sulle medie per
domanda, Holm sulla famiglia H1, H2a, H2b, H2b', H2c, H3, H4. Robustezza: sottoinsiemi di domande dichiarati il 25/10,
stime per motore e per settore, H3 di GPT contro gli altri motori, modello lineare misto, modello ordinale, ordine.
Uso: python analisi_v4.py CARTELLA_DATI   (cartella con risultati/punteggi.csv, scelte.json, misure_secondarie.json)"""
import csv, json, random, statistics as st, sys
from collections import defaultdict
from pathlib import Path
D = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('/path/to/project/data/part2_v4')
FIRME = ("REALE", "BRAND", "PIU_NOTO", "MENO_NOTO", "INVENTATO"); TESTI = ("ORIGINALE", "STRUTTURA", "FLUENCY", "AUTHORITATIVE")
RISC = TESTI[1:]; SEED, B = 20261023, 2000; FAM = ["H1", "H2a", "H2b", "H2b'", "H2c", "H3", "H4"]
URL_SOLO = {'assicurazioni_10', 'moda_beauty_23', 'sport_21', 'viaggi_18'}


def carica():
    rows = list(csv.DictReader((D / 'risultati' / 'punteggi.csv').open()))
    P = defaultdict(dict)
    for r in rows: P[(r['motore'], r['domanda'], int(r['j']), int(r['rip']))][(r['firma'], r['testo'])] = int(r['punteggio'])
    return rows, P


def contrasti(cella):  # identico a analisi_v3.contrasti
    g = lambda f, t: cella.get((f, t))
    def id_(a, b):
        xs = [g(a, t) - g(b, t) for t in TESTI if g(a, t) is not None and g(b, t) is not None]; return st.mean(xs) if xs else None
    def ct(r, firme=FIRME):
        xs = [g(f, r) - g(f, "ORIGINALE") for f in firme if g(f, r) is not None and g(f, "ORIGINALE") is not None]; return st.mean(xs) if xs else None
    out = {"H1": id_("REALE", "INVENTATO"), "H2a": id_("REALE", "BRAND"), "H2c": id_("MENO_NOTO", "INVENTATO")}
    pm, mb = id_("PIU_NOTO", "MENO_NOTO"), (id_("PIU_NOTO", "BRAND"), id_("MENO_NOTO", "BRAND"))
    out["H2b"] = pm / 2 if pm is not None else None
    out["H2b'"] = -(mb[0] + mb[1]) / 2 if None not in mb else None
    for r in RISC: out[f"H3_{r}"] = ct(r)
    h3 = [out[f"H3_{r}"] for r in RISC if out[f"H3_{r}"] is not None]; out["H3"] = st.mean(h3) if h3 else None
    out["H4"] = out["H1"] - out["H3"] if out["H1"] is not None and out["H3"] is not None else None
    for f in FIRME: out[f"H5_H3_{f}"] = st.mean([x for x in (ct(r, (f,)) for r in RISC) if x is not None]) if any(ct(r, (f,)) is not None for r in RISC) else None
    return out


def per_domanda(P, motori=None):
    acc = defaultdict(lambda: defaultdict(list))
    for (m, q, j, r), cella in P.items():
        if motori and m not in motori: continue
        for k, v in contrasti(cella).items():
            if v is not None: acc[(m, q)][k].append(v)
    pmq = {mq: {k: st.mean(v) for k, v in d.items()} for mq, d in acc.items()}
    qs = sorted({q for _, q in pmq}); mot = sorted({m for m, _ in pmq})
    pq = {q: {k: st.mean([pmq[(m, q)][k] for m in mot if (m, q) in pmq and k in pmq[(m, q)]])
              for k in {k for m in mot if (m, q) in pmq for k in pmq[(m, q)]}} for q in qs}
    return pmq, pq, qs, mot


def holm(ps):
    o = sorted(ps, key=ps.get); out, mx = {}, 0
    for i, k in enumerate(o): mx = max(mx, min(1, (len(o) - i) * ps[k])); out[k] = mx
    return out


def stima(pq, qs, chiavi):
    from scipy import stats
    rnd = random.Random(SEED); res = {}
    for k in chiavi:
        xs = [pq[q][k] for q in qs if k in pq[q]]; sub = [q for q in qs if k in pq[q]]
        boots = sorted(st.mean(pq[rnd.choice(sub)][k] for _ in sub) for _ in range(B))
        t = stats.ttest_1samp(xs, 0, alternative="greater")
        res[k] = dict(stima=st.mean(xs), ic95=[boots[int(0.025 * B)], boots[int(0.975 * B) - 1]], t=float(t.statistic),
                      p_una_coda=float(t.pvalue), df=len(xs) - 1, n=len(xs))
    return res


def main():
    rows, P = carica(); pmq, pq, qs, mot = per_domanda(P)
    sc = json.loads((D / 'scelte.json').read_text()); ms = json.loads((D / 'misure_secondarie.json').read_text())
    chiavi = FAM + [f"H3_{r}" for r in RISC]
    res = stima(pq, qs, chiavi)
    for k, p in holm({k: res[k]["p_una_coda"] for k in FAM}).items(): res[k]["p_holm"] = p
    for k in chiavi: res[k]["per_motore"] = {m: st.mean(pmq[(m, q)][k] for q in qs if (m, q) in pmq and k in pmq[(m, q)]) for m in mot}
    sub = {'dentro_2_4': [q for q in qs if sc[q]['dentro_2_4']],
           'modelli_vedono_piu_noto_sopra': [q for q in qs if ms[q]['not_piu_noto'] > ms[q]['not_bersaglio']],
           'coerenza_piu_meno_simile': [q for q in qs if abs(ms[q]['coerenza']['PIU_NOTO'] - ms[q]['coerenza']['MENO_NOTO']) <= 0.5],
           'riconoscimento_basso': [q for q in qs if ms[q]['riconoscimento'] <= 0.5],
           'senza_firma_solo_url': [q for q in qs if q not in URL_SOLO]}
    rob = {n: dict(domande=v, stime=stima(pq, v, FAM)) for n, v in sub.items()}
    settori = defaultdict(list)
    for q in qs: settori[q.rsplit('_', 1)[0]].append(q)
    per_settore = {s: {k: st.mean(pq[q][k] for q in v) for k in FAM} for s, v in settori.items()}
    _, pq_gpt, _, _ = per_domanda(P, {'gpt'}); _, pq_alt, _, _ = per_domanda(P, {'deepseek', 'perplexity', 'gemini_vertex'})
    h3_gpt = dict(gpt=st.mean(pq_gpt[q]['H3'] for q in qs), altri=st.mean(pq_alt[q]['H3'] for q in qs),
                  per_riscrittura={r: dict(gpt=st.mean(pq_gpt[q][f'H3_{r}'] for q in qs), altri=st.mean(pq_alt[q][f'H3_{r}'] for q in qs)) for r in RISC})
    h5 = {f: st.mean(pq[q][f'H5_H3_{f}'] for q in qs) for f in FIRME}
    # ordine: rango medio del bersaglio per posizione nel messaggio (media dei motori, solo condizione REALE-ORIGINALE e tutte)
    pos = defaultdict(lambda: defaultdict(list))
    for r in rows: pos[r['motore']][int(r['posizione_nel_messaggio'])].append(int(r['rango']))
    ordine = {p: st.mean(st.mean(pos[m][p]) for m in mot) for p in range(1, 6)}
    # modello lineare misto e modello ordinale (robustezza)
    import pandas as pd, statsmodels.formula.api as smf
    df = pd.DataFrame(rows); df['punteggio'] = df.punteggio.astype(int); df['rango'] = df.rango.astype(int)
    f = "punteggio ~ C(firma, Treatment('INVENTATO')) + C(testo, Treatment('ORIGINALE')) + C(posizione_nel_messaggio) + C(motore)"
    lmm = smf.mixedlm(f, df, groups=df['domanda']).fit(reml=True)
    misto = {k: dict(coef=float(lmm.params[k]), se=float(lmm.bse[k]), p=float(lmm.pvalues[k])) for k in lmm.params.index if 'firma' in k or 'testo' in k}
    from statsmodels.miscmodels.ordinal_model import OrderedModel
    X = pd.get_dummies(df[['firma', 'testo', 'posizione_nel_messaggio', 'motore', 'domanda']].astype(str), drop_first=False)
    X = X.drop(columns=['firma_INVENTATO', 'testo_ORIGINALE', 'posizione_nel_messaggio_1', 'motore_gpt', f"domanda_{qs[0]}"]).astype(float)
    om = OrderedModel(6 - df['rango'], X, distr='logit').fit(method='bfgs', disp=False, maxiter=2000)
    ordinale = {k: dict(coef=float(om.params[k]), se=float(om.bse[k]), p=float(om.pvalues[k])) for k in om.params.index if k.startswith(('firma_', 'testo_'))}
    out = dict(n_domande=len(qs), motori=mot, n_chiamate_valide=len(rows), n_celle=len(P), risultati=res, robustezza=rob,
               per_settore=per_settore, h3_gpt_contro_altri=h3_gpt, h5_h3_per_firma=h5, rango_medio_per_posizione=ordine,
               modello_misto=misto, modello_ordinale=ordinale, per_domanda=pq)
    (D / 'risultati' / 'risultati_v4.json').write_text(json.dumps(out, ensure_ascii=False, indent=1))
    for k in chiavi:
        r = res[k]; print(f"{k:16s} {r['stima']:+.3f} [{r['ic95'][0]:+.3f}; {r['ic95'][1]:+.3f}] p={r['p_una_coda']:.4f} holm={r.get('p_holm', float('nan')):.4f} "
                          + ' '.join(f"{m[:4]}={v:+.2f}" for m, v in r['per_motore'].items()))
    for n, v in rob.items():
        print(n, len(v['domande']), ' '.join(f"{k}={v['stime'][k]['stima']:+.2f}(p{v['stime'][k]['p_una_coda']:.3f})" for k in FAM))
    print('settori', {s: {k: round(v[k], 2) for k in FAM} for s, v in per_settore.items()})
    print('H3 GPT/altri', h3_gpt); print('H5', h5); print('ordine', ordine)
    print('misto', {k: round(v['coef'], 3) for k, v in misto.items()}); print('ordinale', {k: round(v['coef'], 3) for k, v in ordinale.items()})


if __name__ == '__main__':
    main()
