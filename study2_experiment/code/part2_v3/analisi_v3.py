"""Analisi principale (protocollo sez. 10). Punteggio = 6 − posizione del bersaglio. Contrasti appaiati per domanda,
ordine, ripetizione e motore; stima per motore = media dei contrasti; stima principale = media dei motori con lo stesso
peso. Incertezza: IC95 bootstrap a grappolo sulle domande (2.000 ricampionamenti, seed 20261023) e test t a una coda
sulle medie per domanda, con correzione di Holm sulla famiglia H1, H2a, H2b, H2b', H2c, H3 (media), H4.
Uso: python analisi_v3.py   (scrive data/part2_v3/risultati/risultati.json)"""
import json, sys, statistics as st, random
from pathlib import Path
from collections import defaultdict
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "part2_conf"))
from comune import classifica
from comune_v3 import D
from studio_v3 import FIRME, TESTI
MOTORI = ("gpt", "deepseek", "perplexity", "gemini_vertex"); SEED, B = 20261023, 2000
RISC = ("STRUTTURA", "FLUENCY", "AUTHORITATIVE")
def carica():
    """punteggio[(motore, domanda, j, rip)][(firma, testo)] = 6 − posizione; per chiamata vale l'ultimo record valido."""
    P = defaultdict(dict)
    for m in MOTORI:
        f = D / f"studio_{m}.jsonl"
        if not f.exists(): continue
        for l in f.open():
            r = json.loads(l)
            if r.get("error"): continue
            c = classifica(r.get("response_text"), r["ordine"])
            if c is None: continue
            P[(m, r["qid"], r["j"], r["rip"])][(r["firma"], r["testo"])] = 6 - (c.index(r["bersaglio"]) + 1)
    return P
def contrasti(cella):
    g = lambda f, t: cella.get((f, t))
    def id_(a, b):   # media sui 4 testi di firma a − firma b
        xs = [g(a, t) - g(b, t) for t in TESTI if g(a, t) is not None and g(b, t) is not None]; return st.mean(xs) if xs else None
    def ct(r):       # media sulle 5 firme di riscrittura r − originale
        xs = [g(f, r) - g(f, "ORIGINALE") for f in FIRME if g(f, r) is not None and g(f, "ORIGINALE") is not None]; return st.mean(xs) if xs else None
    out = {"H1": id_("REALE", "INVENTATO"), "H2a": id_("REALE", "BRAND"), "H2c": id_("MENO_NOTO", "INVENTATO")}
    pm, mb = id_("PIU_NOTO", "MENO_NOTO"), (id_("PIU_NOTO", "BRAND"), id_("MENO_NOTO", "BRAND"))
    out["H2b"] = pm / 2 if pm is not None else None
    out["H2b'"] = -(mb[0] + mb[1]) / 2 if None not in mb else None
    for r in RISC: out[f"H3_{r}"] = ct(r)
    h3 = [out[f"H3_{r}"] for r in RISC if out[f"H3_{r}"] is not None]; out["H3"] = st.mean(h3) if h3 else None
    out["H4"] = out["H1"] - out["H3"] if out["H1"] is not None and out["H3"] is not None else None
    return out
def per_domanda(P):
    """media per (motore, domanda) di ogni contrasto, poi per domanda la media dei motori."""
    acc = defaultdict(lambda: defaultdict(list))
    for (m, q, j, r), cella in P.items():
        for k, v in contrasti(cella).items():
            if v is not None: acc[(m, q)][k].append(v)
    pmq = {mq: {k: st.mean(v) for k, v in d.items()} for mq, d in acc.items()}
    qs = sorted({q for _, q in pmq}); mot = sorted({m for m, _ in pmq})
    pq = {q: {k: st.mean([pmq[(m, q)][k] for m in mot if (m, q) in pmq and k in pmq[(m, q)]]) for k in pmq[(mot[0], q)]} for q in qs}
    return pmq, pq, qs, mot
def holm(ps):
    o = sorted(ps, key=ps.get); out, mx = {}, 0
    for i, k in enumerate(o): mx = max(mx, min(1, (len(o) - i) * ps[k])); out[k] = mx
    return out
def main():
    from scipy import stats
    P = carica(); pmq, pq, qs, mot = per_domanda(P); rnd = random.Random(SEED); res = {}
    chiavi = list(next(iter(pq.values())))
    for k in chiavi:
        xs = [pq[q][k] for q in qs]; est = st.mean(xs)
        boots = sorted(st.mean(pq[rnd.choice(qs)][k] for _ in qs) for _ in range(B))
        t = stats.ttest_1samp(xs, 0, alternative="greater")
        res[k] = dict(stima=est, ic95=[boots[int(0.025 * B)], boots[int(0.975 * B) - 1]], t=t.statistic, p_una_coda=t.pvalue, df=len(xs) - 1,
                      per_motore={m: st.mean(pmq[(m, q)][k] for q in qs if (m, q) in pmq) for m in mot})
    fam = ["H1", "H2a", "H2b", "H2b'", "H2c", "H3", "H4"]
    for k, p in holm({k: res[k]["p_una_coda"] for k in fam}).items(): res[k]["p_holm"] = p
    out = D / "risultati"; out.mkdir(exist_ok=True)
    json.dump(dict(n_domande=len(qs), motori=mot, n_celle=len(P), risultati=res, per_domanda=pq), open(out / "risultati.json", "w"), ensure_ascii=False, indent=1)
    for k in chiavi:
        r = res[k]; print(f"{k:16s} {r['stima']:+.3f} [{r['ic95'][0]:+.3f}; {r['ic95'][1]:+.3f}] p={r['p_una_coda']:.4f} holm={r.get('p_holm', float('nan')):.4f}")
if __name__ == "__main__":
    main()
