"""Study 2, studio completo: dati comuni alla selezione (protocollo v2.0, sez. 3)."""
import csv, json, re, unicodedata, collections, hashlib
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "data/part2_v3"; D.mkdir(parents=True, exist_ok=True)
V2 = ROOT / "data/part2_v2"
P = {r["prompt_id"]: r for r in csv.DictReader(open(ROOT / "config/main_study_prompts.csv"))}
NOT = {r["chiave"]: r for r in csv.DictReader(open(ROOT / "config/main_notorieta.csv"))}
VOL = {k: float(r["volume"] or 0) for k, r in NOT.items()}
NOME = {k: r["nome"] for k, r in NOT.items()}
QUERY = {k: r["query"] for k, r in NOT.items()}
DOM = {r["chiave"]: r["dominio"] for r in csv.DictReader(open(ROOT / "config/main_brand_domini.csv")) if r["stato"] == "mapped_explicit"}
CAT = json.load(open(V2 / "categoria_marchi.json"))
_AL = json.load(open(ROOT / "lavoro/2026-10-18_recupero_fonti_v3/alias_lookup.json"))["strict"]

def norm(s):
    """Nome senza accenti, punteggiatura e maiuscole (protocollo sez. 3)."""
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", s.replace("'", "").replace("’", ""))).strip()

AL = {sec: {} for sec in _AL}
for sec, m in _AL.items():
    for k, v in m.items():
        AL[sec].setdefault(norm(k), v)

def canon(sec, b):
    v = AL.get(sec, {}).get(norm(b))
    return v[0] if v else None

def menzioni():
    """prompt -> Counter(chiave marchio -> risposte principali che lo nominano). Una volta per risposta;
    escluso il braccio con la persona nel system prompt; per ogni chiamata vale l'ultimo record."""
    ultimo = {}
    for l in open(ROOT / "data/raw/main_brands.jsonl"):
        r = json.loads(l)
        ultimo[r["key"]] = r
    out = collections.defaultdict(collections.Counter); n = collections.Counter()
    for key, r in ultimo.items():
        eng, arm, pid, lv, srch, rep = key.split("|")
        if lv == "A_sistema": continue
        n[pid] += 1
        sec = P[pid]["sector"]
        for k in {canon(sec, b) for b in (r.get("brand") or [])} - {None}:
            out[pid][k] += 1
    return out, n

def kurl(u): return hashlib.sha256(u.encode()).hexdigest()[:16]
