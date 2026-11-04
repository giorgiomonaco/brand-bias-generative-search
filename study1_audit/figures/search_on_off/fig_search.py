"""Figure search on/off di Study 1 (riunione del 27/10). Stile della Fig. 2 del paper (lavoro/2026-10-23_figure_paper_v2/style.py):
niente griglia, niente riquadri di legenda, etichette dirette. Numeri da slope_on_off.py.
- fig2_search_effect (corpo): (a) menzione per quintile di notorietà, ricerca spenta e disponibile, tutti i motori e settori;
  (b) un punto per brand: effetto della ricerca (on − off) contro la notorietà, retta OLS con banda bootstrap.
- figA_search_grid (appendice): (a) per motore × settore."""
import sys, json
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'fig_core'))
import style
from style import plt, np, pd, W, WF, FS, MEN, INK, GREY, S, E, SL, EL, Q_LABELS, few_ticks, quintile, NQ, letters
style.FIG = HERE / 'fig'; style.FIG.mkdir(exist_ok=True)
OFF = '#9a9a9a'
D = pd.read_csv(HERE / 'brand_on_off.csv')
R = json.loads((HERE / 'slope_on_off.json').read_text())
D['q'] = D.groupby('cella').notorieta_log10.transform(quintile)
rng = np.random.default_rng(20261027)


def by_q(g):
    m = g.groupby('q')[['off', 'on']].mean(); se = g.groupby('q')[['off', 'on']].sem()
    return m, se


def curves(ax, g, labels=True):
    m, se = by_q(g)
    for col, c, lab in (('off', OFF, 'search off'), ('on', MEN, 'search on')):
        ax.errorbar(m.index, m[col], yerr=1.96 * se[col], color=c, marker='o', ms=3.5, lw=1.6, capsize=2, alpha=.75)
        ax.lines[-1].set_label(lab) if False else None
    if labels:
        ax.legend([plt.Line2D([], [], color=c, lw=1.6, marker='o', ms=3.5) for c in (OFF, MEN)], ['search off', 'search on'],
                  loc='upper left', handlelength=1.4)
    ax.set_xticks(range(1, NQ + 1), Q_LABELS)


def stars(p):
    return '**' if p < 0.01 else ('*' if p < 0.05 else '')


# ------------------------------------------------------------------ corpo
# (a) menzione per quintile, on e off; (b) differenza on − off per quintile. Stesso asse x, niente titoli di pannello.
fig, (a, b) = plt.subplots(1, 2, figsize=(W, 2.7), sharex=True)
curves(a, D, labels=False)
a.set_ylabel('share of mentions (%)'); a.set_ylim(bottom=0); few_ticks(a, 4)
m = D.groupby('q').delta.mean(); se = D.groupby('q').delta.sem()
b.axhline(0, color=GREY, lw=.8, ls=(0, (3, 3)))
b.errorbar(m.index, m, yerr=1.96 * se, color=INK, marker='o', ms=3.5, lw=1.6, capsize=2)
b.set_ylabel('effect of search (pp)'); few_ticks(b, 4, integer=False)
lim = max(abs((m - 1.96 * se).min()), abs((m + 1.96 * se).max())) * 1.6
b.set_ylim(-lim, lim)
for ax in (a, b): ax.set_xticks(range(1, NQ + 1), Q_LABELS)
fig.tight_layout(w_pad=1.6)
fig.subplots_adjust(bottom=0.36)
fig.text(0.5, 0.14, 'popularity quintile', ha='center', va='center', fontsize=FS)
fig.legend([plt.Line2D([], [], color=c, lw=1.6, marker='o', ms=3.5) for c in (OFF, MEN)], ['search off', 'search on'],
           ncol=2, loc='lower center', bbox_to_anchor=(.5, -.01), handlelength=1.4)
style.save(fig, 'fig2_search_effect')
pd.DataFrame(dict(delta=m.round(3), ic_basso=(m - 1.96 * se).round(3), ic_alto=(m + 1.96 * se).round(3))).to_csv(style.FIG / 'fig2_search_effect_delta_quintili.csv')

# ------------------------------------------------------------------ call del 2/11: 2b in appendice, due versioni della 2a
LEG = [plt.Line2D([], [], color=c, lw=1.6, marker='o', ms=3.5) for c in (OFF, MEN)]
# versione A: tutti i motori insieme, un pannello, legenda a destra
fig, a = plt.subplots(figsize=(WF * 0.62, 2.0))
curves(a, D, labels=False)
a.set_ylabel('answers mentioning\nthe brand (%)'); a.set_ylim(bottom=0); few_ticks(a, 4); a.set_xlabel('popularity quintile')
a.legend(LEG, ['search off', 'search on'], loc='center left', bbox_to_anchor=(1.02, .5), handlelength=1.4, frameon=False)
fig.tight_layout()
style.save(fig, 'fig2_search_effect_pooled')
# versione B: un pannello per motore
fig, axs = plt.subplots(1, 3, figsize=(WF, 1.75), sharey=True, sharex=True)
for ax, e in zip(axs, E):
    curves(ax, D[D.motore == e], labels=False); ax.set_title(EL[e]); few_ticks(ax, 4)
axs[0].set_ylim(bottom=0)
axs[0].set_ylabel('answers mentioning\nthe brand (%)')
RL = 0.819
fig.legend(LEG, ['search off', 'search on'], ncol=1, loc='center left', bbox_to_anchor=(RL, .5), handlelength=1.4, frameon=False)
fig.tight_layout(w_pad=1.3, rect=(0, 0, RL, 1))
letters(axs)
style.save(fig, 'fig2_search_effect_engines')

# ------------------------------------------------------------------ variante: pannello b con lo scatter
fig, (a, b) = plt.subplots(1, 2, figsize=(W, 2.75))
curves(a, D, labels=False)
a.set_ylabel('answers mentioning\nthe brand (%)'); a.set_ylim(bottom=0); few_ticks(a, 4); a.set_xlabel('popularity quintile')
x, y = D.notorieta_log10_c.values, D.delta.values
lo, hi = np.percentile(y, [0.5, 99.5]); keep = (y >= lo) & (y <= hi)
b.scatter(x[keep], y[keep], s=5, color=INK, alpha=.18, lw=0)
b.axhline(0, color=GREY, lw=.8, ls=(0, (3, 3)))
grid = np.linspace(x.min(), x.max(), 60)
idx = [np.flatnonzero(D.cella.values == c) for c in D.cella.unique()]
fits = []
for _ in range(2000):
    s_ = np.concatenate([rng.choice(i, len(i)) for i in idx])
    k, c0 = np.polyfit(x[s_], y[s_], 1); fits.append(k * grid + c0)
fits = np.array(fits); k, c0 = np.polyfit(x, y, 1)
b.fill_between(grid, *np.percentile(fits, [2.5, 97.5], axis=0), color=MEN, alpha=.25, lw=0)
b.plot(grid, k * grid + c0, color=MEN, lw=1.8)
t = R['totale']['delta']
b.text(.97, .03, f"slope {t['pendenza']:+.2f} [{t['ic95'][0]:+.2f}; {t['ic95'][1]:+.2f}]".replace("-", "−"), transform=b.transAxes, va='bottom', ha='right', fontsize=FS - 1, color=INK)
b.set_ylim(lo * 1.05, hi * 1.05); few_ticks(b, 4, 4)
b.set_xlabel('popularity (log$_{10}$, centred)'); b.set_ylabel('effect of search (pp)')
a.legend([plt.Line2D([], [], color=c, lw=1.6, marker='o', ms=3.5) for c in (OFF, MEN)], ['search off', 'search on'],
         ncol=2, loc='upper center', bbox_to_anchor=(.5, -.42), handlelength=1.4, columnspacing=1.0)
letters([a, b])
fig.tight_layout(w_pad=1.6)
style.save(fig, 'fig2_search_effect_scatter')

# ------------------------------------------------------------------ appendice: scatter con la retta (la pendenza del testo)
fig, b = plt.subplots(figsize=(W * 0.62, 2.6))
x, y = D.notorieta_log10_c.values, D.delta.values
lo, hi = np.percentile(y, [0.5, 99.5]); keep = (y >= lo) & (y <= hi)
b.scatter(x[keep], y[keep], s=5, color=INK, alpha=.18, lw=0)
b.axhline(0, color=GREY, lw=.8, ls=(0, (3, 3)))
grid = np.linspace(x.min(), x.max(), 60)
idx = [np.flatnonzero(D.cella.values == c) for c in D.cella.unique()]
fits = []
for _ in range(2000):
    s_ = np.concatenate([rng.choice(i, len(i)) for i in idx])
    k, c0 = np.polyfit(x[s_], y[s_], 1); fits.append(k * grid + c0)
fits = np.array(fits); k, c0 = np.polyfit(x, y, 1)
b.fill_between(grid, *np.percentile(fits, [2.5, 97.5], axis=0), color=MEN, alpha=.25, lw=0)
b.plot(grid, k * grid + c0, color=MEN, lw=1.8)
t = R['totale']['delta']
b.text(.97, .97, f"slope {t['pendenza']:+.2f} [{t['ic95'][0]:+.2f}; {t['ic95'][1]:+.2f}]", transform=b.transAxes, va='top', ha='right', fontsize=FS - 1, color=INK)
b.set_ylim(lo * 1.05, hi * 1.05); few_ticks(b, 4, 4)
b.set_xlabel('popularity (log$_{10}$, centred)'); b.set_ylabel('effect of search (pp)')
fig.tight_layout()
style.save(fig, 'figA_search_scatter')
print('punti fuori scala nello scatter:', int((~keep).sum()), 'su', len(y))

# ------------------------------------------------------------------ appendice
fig, axs = plt.subplots(3, 4, figsize=(W * 1.25, W * 0.95), sharex=True)
for i, e in enumerate(E):
    for j, s_ in enumerate(S):
        ax = axs[i][j]; g = D[(D.motore == e) & (D.settore == s_)]
        curves(ax, g, labels=False)
        r = R['celle'][f'{e}|{s_}']['delta']
        ax.text(.03, .97, f"Δslope {r['pendenza']:+.2f}{'**' if r['p_bh'] < 0.05 else ('*' if r['p'] < 0.05 else '')}",
                transform=ax.transAxes, va='top', fontsize=FS - 1.5, color=INK)
        ax.set_ylim(bottom=0); few_ticks(ax, 3)
        if i == 0: ax.set_title(SL[s_])
        if j == 0: ax.set_ylabel(f"{EL[e]}\nmention (%)")
        if i == 2: ax.set_xticks(range(1, NQ + 1), [str(i) if i in (1, NQ) else '' for i in range(1, NQ + 1)])
h = [plt.Line2D([], [], color=OFF, lw=2, marker='o', ms=3.5), plt.Line2D([], [], color=MEN, lw=2, marker='o', ms=3.5)]
fig.legend(h, ['search off', 'search on'], ncol=2, loc='lower center', bbox_to_anchor=(.5, -.01))
fig.supxlabel('popularity quintile within engine and sector', y=0.065, fontsize=FS)
fig.tight_layout(h_pad=0.8, w_pad=0.6, rect=(0, 0.075, 1, 1))
style.save(fig, 'figA_search_grid')
pd.concat([by_q(D)[0].round(3).assign(livello='totale')] + [by_q(g)[0].round(3).assign(livello=c) for c, g in D.groupby('cella')]).to_csv(style.FIG / 'fig2_search_effect_quintili.csv')
