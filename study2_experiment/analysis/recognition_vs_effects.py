"""Neutralisation check of Study 2 (appendix): recognition of the original brand vs. the effects of the signature.
Reads the per-question recognition rate written by misure_identita.py and the per-question contrasts of the main
collection (data/scores_main/risultati/risultati_v4.json, from code/part2_v4/analisi_v4.py; contrast names as in the
preregistration: H1 = true brand vs invented brand, H2a = real vs invented product name (H4b in the paper)).
Prints the Spearman correlation between recognition and each effect over the 24 questions, and the mean effect on
the questions recognised at most a quarter of the time and on the others (two-sided one-sample t test).
Run misure_identita.py first."""
import json
import statistics as st
from pathlib import Path
from scipy import stats

R = Path(__file__).resolve().parents[1]
ris = json.loads((R / 'data' / 'scores_main' / 'risultati' / 'risultati_v4.json').read_text())['per_domanda']
ric = json.loads((Path(__file__).with_name('misure_identita.json')).read_text())['riconoscibilita_v1']['per_domanda']
qs = sorted(set(ric) & set(ris))
print(f'mean recognition {st.mean(ric[q] for q in qs):.3f} over {len(qs)} questions')
for h in ('H1', 'H2a', 'H4'):
    r = stats.spearmanr([ric[q] for q in qs], [ris[q][h] for q in qs])
    print(f'Spearman recognition vs {h}: rho = {r[0]:.3f}, p = {r[1]:.3f}')
for name, sel in (('recognised <= 0.25', [q for q in qs if ric[q] <= 0.25]), ('recognised > 0.25', [q for q in qs if ric[q] > 0.25])):
    for h in ('H1', 'H2a', 'H2c', 'H4'):
        v = [ris[q][h] for q in sel]
        print(f'{name:19s} n={len(sel):2d} {h:4s} mean {st.mean(v):.3f}  p (two-sided) {stats.ttest_1samp(v, 0).pvalue:.4f}')
