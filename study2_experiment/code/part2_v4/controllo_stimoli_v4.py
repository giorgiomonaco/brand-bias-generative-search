"""Audit offline: legge solo file espliciti, nessuna API né import dei moduli dello studio.
Uso: python3 controllo_stimoli.py ROOT OUTPUT_DIRECTORY
I controlli semantici sotto sono screening, non prova di equivalenza dei fatti.
"""
import ast
import collections
import csv
import hashlib
import json
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(sys.argv[1]); OUT = Path(sys.argv[2]); OUT.mkdir(parents=True, exist_ok=True)
D = ROOT / 'data/part2_v4'  # stesso controllo del 24/10, applicato alla raccolta rivista
read = lambda p: json.loads(p.read_text())
names = {r['chiave']: r['nome'] for r in csv.DictReader((ROOT/'config/main_notorieta.csv').open())}
domains = {r['chiave']: r['dominio'] for r in csv.DictReader((ROOT/'config/main_brand_domini.csv').open()) if r['stato']=='mapped_explicit'}
choices = read(D/'scelte.json')
ph = re.compile(r'\{([A-Z0-9_]+)\}')
norm = lambda s: re.sub(r'\s+', ' ', s).strip()
fold = lambda s: ''.join(c for c in unicodedata.normalize('NFKD',s).casefold() if c.isalnum())
numbers = lambda s: collections.Counter(re.findall(r'\d+(?:[.,]\d+)?',ph.sub('',s)))
fill = lambda s,m: ph.sub(lambda x:m.get(x[1], x[0]),s)
# Execute only the runner's four pure functions, verbatim from its AST; no imports/top-level code.
runner = ROOT/'analysis/part2_v3/studio_v3.py'
tree = ast.parse(runner.read_text())
pure = [n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('slug','adatta','riempi','pagina_bersaglio')]
assert len(pure)==4
env = {'re':re,'urlsplit':urlsplit,'NOME':names,'DOM':domains}
exec(compile(ast.Module(body=pure,type_ignores=[]),str(runner),'exec'), env)
rows=[]; issues=[]; manifest=[]
def add(pid,level,kind,detail): issues.append(dict(pid=pid,level=level,kind=kind,detail=detail))
def check(row,key,value,detail=''):
    row[key]=bool(value)
    if not value: add(row['pid'],'FAIL',key,detail)
alltexts = {}
for p in (D/'testi').glob('*.json'):
    x=read(p); alltexts[p.stem]=(x,p)
accepted = {k for k,v in choices.items() if v['esito']=='ok'}
stimfiles=sorted((D/'stimoli').glob('*.json'))
assert {f.stem for f in stimfiles} == accepted, 'Stimoli mancanti o in eccesso'
for f in stimfiles:
    s=read(f); pid=s['pid']; real=s['mappa_reale']; inv=s['mappa_inventata']; mod=s['modello']; row={'pid':pid,'brand':s['brand']}
    key=hashlib.sha256((pid+'|'+s['brand']).encode()).hexdigest()[:16]
    x,p=alltexts[key]
    check(row,'reconstruction_normalized',norm(fill(mod,real))==norm(x['testo']))
    row['reconstruction_exact']=fill(mod,real)==x['testo']
    check(row,'source_hash',hashlib.sha256(x['testo'].encode()).hexdigest()==x['sha256']==s['testo_sha256'])
    check(row,'choices_match',all(s[k]==choices[pid][k] for k in ('bersaglio','piu_noto','meno_noto')))
    check(row,'placeholder_map',set(ph.findall(mod))==set(real))
    check(row,'invented_map_complete',all(k in inv for k in real if not k.startswith('BRAND')))
    variants={'ORIGINALE':mod,**s['riscritture']}
    check(row,'four_texts',set(variants)=={'ORIGINALE','STRUTTURA','FLUENCY','AUTHORITATIVE'})
    br=[k for k in ph.findall(mod) if k.startswith('BRAND')]
    row['brand_placeholder_occurrences']=len(br)
    if not br: add(pid,'REVIEW','no_brand_in_body','BRAND/PIU_NOTO/MENO_NOTO/INVENTATO differiscono solo nell’URL: firma assente nel corpo.')
    row['rewrites']=[]
    for label,t in variants.items():
        if label=='ORIGINALE': continue
        r={'variant':label,'ratio':len(t.split())/len(mod.split())}
        r['placeholder_set']=set(ph.findall(t))==set(ph.findall(mod))
        r['placeholder_multiset']=collections.Counter(ph.findall(t))==collections.Counter(ph.findall(mod))
        r['numbers_multiset']=numbers(t)==numbers(mod)
        r['length_15pct']=.85<=r['ratio']<=1.15
        r['within_prompt_110pct']=len(t.split())<=int(len(mod.split())*1.1)
        logs=s.get('log_riscritture',{}).get(label,[])+s.get('log_revisione',{}).get(label,[])
        r['accepted_log']=any(z.get('testo')==t and z.get('errori')==[] for z in logs)
        for k in ('placeholder_set','numbers_multiset','length_15pct','accepted_log'):
            if not r[k]: add(pid,'FAIL',k,label)
        if not r['placeholder_multiset']: add(pid,'REVIEW','placeholder_frequency',label+': set conservato, frequenze diverse (consentito dal vecchio codice; da distinguere dalle informazioni perse).')
        if not r['within_prompt_110pct']: add(pid,'REVIEW','prompt_length',label+': oltre il limite nel prompt, ma entro ±15% del criterio di accettazione.')
        row['rewrites'].append(r)
    row['materialized']=0
    for label,t in variants.items():
        for identity in ('REALE','BRAND','PIU_NOTO','MENO_NOTO','INVENTATO'):
            text,url=env['pagina_bersaglio'](s,identity,label); row['materialized']+=1
            if ph.search(text): add(pid,'FAIL','unresolved_placeholder',identity+' '+label)
            if identity not in ('REALE','BRAND'):
                for raw in {s['brand'],names[s['bersaglio']],domains.get(s['bersaglio'],'')}:
                    if len(fold(raw))>=3 and fold(raw) in fold(text): add(pid,'REVIEW','target_brand_residue',identity+' '+label+': '+raw)
    for k,v in real.items():
        if k.startswith('BRAND'): continue
        new=inv.get(k,v)
        if new==v: add(pid,'REVIEW','unchanged_invented_value',k+': '+v)
        if not k.startswith('CODICE') and numbers(v)!=numbers(new):
            add(pid,'REVIEW','numeric_change_inside_placeholder',f'{k}: {v} → {new}')
        # Conservative lexicon: factual words removed by identity swaps need semantic assessment.
        for term in ('avocado','retinol','squalane','etna','catania','taormina','zanzibar','made in italy','assicurazione moto'):
            if term in v.lower() and term not in new.lower():
                add(pid,'REVIEW','factual_term_in_identity_map',f'{k}: {v} → {new} (termine: {term})')
        if not k.startswith('CODICE') and len(v)>=5 and v!=new and re.search(re.escape(v),mod,re.I):
            add(pid,'REVIEW','mapped_value_still_in_template',k+': '+v)
    for k,v in real.items():
        if k.startswith('BRAND') and fold(v) not in fold(s['brand']) and fold(s['brand']) not in fold(v):
            add(pid,'REVIEW','brand_role',k+': '+v+'; bersaglio: '+s['brand'])
    # Full logs do not retain successful judge response, only absence of errors.
    rows.append(row)
    manifest.append({'path':str(f.relative_to(ROOT)),'sha256':hashlib.sha256(f.read_bytes()).hexdigest()})
summary={'date_utc':datetime.now(timezone.utc).isoformat(),'questions':len(rows),'rewrites':sum(len(r['rewrites']) for r in rows),
         'materialized_pages':sum(r['materialized'] for r in rows),'failures':sum(i['level']=='FAIL' for i in issues),
         'review_flags':sum(i['level']=='REVIEW' for i in issues),'source_text_files':len(alltexts),
         'judge_evidence':'Solo log di accettazione senza errori; risposte positive complete del giudice non conservate.',
         'scope':'Offline, nessuna API, nessuna modifica agli stimoli; equivalenza semantica non certificata da regole lessicali.'}
(OUT/'audit.json').write_text(json.dumps({'summary':summary,'rows':rows,'issues':issues,'inputs':manifest},ensure_ascii=False,indent=2))
print(json.dumps(summary,ensure_ascii=False,indent=2))
for i in issues: print(i['level'],i['pid'],i['kind'],i['detail'])
