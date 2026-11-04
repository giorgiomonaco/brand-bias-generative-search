"""Popularity bias per livello di persona, aggregato su motori e settori (29/10/2026).
Stessa definizione di d_slopes.py (seed_unico): tasso di menzione per brand (%), ricerca off e on insieme, livello
system prompt escluso; pendenza OLS su log10 popolarità. Aggregato: pendenza comune con effetti fissi motore x settore
(x e y centrati nella cella). IC: 1000 bootstrap dei prompt stratificati per settore (seed 20261014), come nel paper."""
import gzip
import sys, json, pickle
from collections import Counter
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent
INP = HERE.parents[1] / 'data'
SECTORS=['assicurazioni','moda_beauty','sport','viaggi']; ENGINES=['gpt','gemini','perplexity']; LV=['nessuna','A','B','C']
d=json.load(gzip.open(INP / "calls.json.gz", "rt"))
R=pd.DataFrame(d['rows']); R['search']=R.search.astype(str).eq('True')
R=R[R.ha_estrazione.astype(str).eq('True')]
PB=pd.read_csv(INP/'P1_brand.csv')
PBS={s:sorted(R[R.sector==s].prompt_id.unique()) for s in SECTORS}
rng=np.random.default_rng(20261014); BOOTS=[]
for _ in range(1000):
    w=Counter()
    for s,ps in PBS.items():
        for i in rng.integers(0,len(ps),len(ps)): w[ps[i]]+=1
    BOOTS.append(w)
def prep(sub,u):
    idx={k:i for i,k in enumerate(u)}; out={}
    for p,g in sub.groupby('prompt_id'):
        c=np.zeros(len(u))
        for B in g.B:
            for k in B:
                if k in idx: c[idx[k]]+=1
        out[p]=(len(g),c)
    return out
def rate(parts,w=None):
    n=0; c=0
    for p,(np_,cp) in parts.items():
        ww=1 if w is None else w.get(p,0)
        if ww: n+=ww*np_; c=c+ww*cp
    return 100*c/n if n else None
cells=[]
for e in ENGINES:
    for s in SECTORS:
        u0=PB[(PB.motore==e)&(PB.settore==s)&(PB.ricerca=='off')]
        u=list(u0.chiave); x=u0.notorieta_log10.to_numpy(); ok=~np.isnan(x)
        sub=R[(R.engine==e)&(R.sector==s)&(R.level!='A_sistema')]
        cells.append(dict(e=e,s=s,x=x[ok],ok=ok,P={l:prep(sub[sub.level==l],u) for l in LV}))
def pooled(l,w=None):
    num=den=0
    for c in cells:
        y=rate(c['P'][l],w)
        if y is None: continue
        y=y[c['ok']]; xc=c['x']-c['x'].mean(); yc=y-y.mean()
        num+=(xc*yc).sum(); den+=(xc**2).sum()
    return num/den
def cell_slope(c,l,w=None):
    y=rate(c['P'][l],w); return np.polyfit(c['x'],y[c['ok']],1)[0]
# controllo: pendenze per cella identiche a persona_pendenze_seed1014.json
ref={(r['motore'],r['settore']):r for r in json.load(open(INP/'persona_pendenze_seed1014.json'))}
mx=max(abs(cell_slope(c,l)-ref[(c['e'],c['s'])][l]) for c in cells for l in LV)
print('max scarto dalle pendenze per cella già pubblicate:', round(mx,6))
est={l:pooled(l) for l in LV}; bs={l:np.array([pooled(l,w) for w in BOOTS]) for l in LV}
out={}
for l in LV:
    r=dict(slope=round(est[l],3), ci=[round(float(np.percentile(bs[l],2.5)),3), round(float(np.percentile(bs[l],97.5)),3)])
    if l!='nessuna':
        dd=bs[l]-bs['nessuna']
        r.update(diff=round(est[l]-est['nessuna'],3), diff_ci=[round(float(np.percentile(dd,2.5)),3), round(float(np.percentile(dd,97.5)),3)],
                 p=float(min(1,2*min((dd<=0).mean(),(dd>=0).mean()))))
    out[l]=r
# media delle tre persone
mp=np.mean([bs[l] for l in 'ABC'],axis=0); m0=np.mean([est[l] for l in 'ABC'])
out['media_ABC']=dict(slope=round(m0,3), diff=round(m0-est['nessuna'],3),
     diff_ci=[round(float(np.percentile(mp-bs['nessuna'],2.5)),3), round(float(np.percentile(mp-bs['nessuna'],97.5)),3)])
# per motore, aggregato sui settori
for e in ENGINES:
    sel=[c for c in cells if c['e']==e]; keep=cells[:]
    cells[:]=sel
    pe={l:pooled(l) for l in LV}; pb={l:np.array([pooled(l,w) for w in BOOTS]) for l in LV}
    cells[:]=keep
    out['per_motore_'+e]={l:dict(slope=round(pe[l],3), diff=(round(pe[l]-pe['nessuna'],3) if l!='nessuna' else None),
        diff_ci=([round(float(np.percentile(pb[l]-pb['nessuna'],2.5)),3), round(float(np.percentile(pb[l]-pb['nessuna'],97.5)),3)] if l!='nessuna' else None)) for l in LV}
json.dump(out,open(HERE/'persona_pooled.json','w'),indent=1); print(json.dumps(out,indent=1))
