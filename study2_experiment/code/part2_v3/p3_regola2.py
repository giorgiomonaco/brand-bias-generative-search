"""Pagine, regola 2 (protocollo sez. 4): per i marchi senza pagina dalla regola 1, il prodotto di quel marchio più
nominato nelle risposte principali di Study 1 alla domanda, e la sua pagina sul sito ufficiale.
A. prodotti: per ogni risposta che nomina il marchio, le righe che lo contengono; GPT (istruzione fissa) scrive per ogni
   riga il nome del prodotto di quel marchio, o NESSUNO; si conta una volta per risposta.
B. URL: GPT-5.5 con ricerca web trova la pagina di quel prodotto sul sito ufficiale italiano del marchio (istruzione fissa,
   fino a 2 tentativi); la pagina deve stare sul sito del marchio e passare lo stesso controllo GPT della regola 1.
   Se il prodotto non ha una pagina valida si applica la regola 3: il primo prodotto della categoria sul sito del marchio.
   (Una prima versione cercava con Google «site:dominio prodotto» via DataForSEO: falliva quando il dominio del marchio
   in config/main_brand_domini.csv non è quello del negozio, es. zinodavidoff.com; i grezzi restano in data/raw.)"""
import sys, json, re, time, collections
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "part2_conf"))
from motori import motore
from comune_v3 import ROOT, D, P, NOME, canon, norm
from scarica import scarica, OUT, kurl
import p2_regola1 as r1helper  # solo per l'istruzione P del controllo
R1 = json.load(open(D / "regola1.json")); sel = json.load(open(D / "selezione_v3.json"))
F = D / "regola2.json"; R = json.load(open(F)) if F.exists() else {}
DA_FARE = [k for k, v in R1.items() if v["scelta"] is None]
PA = ("Qui sotto ci sono righe tratte da risposte a una domanda di un utente: «{q}». Ogni riga nomina il marchio {b}.\n"
      "Per ogni riga scrivi il numero della riga, due punti e il nome del prodotto o servizio di {b} che la riga nomina "
      "(modello, linea o polizza, senza taglie, colori o prezzi), oppure NESSUNO se la riga nomina solo il marchio. Una riga "
      "per numero, niente altro.\n\n{righe}")
def righe_marchio(pid, b, k):
    ultimo = {}
    for l in open(ROOT / "data/raw/main_brands.jsonl"):
        r = json.loads(l); e, arm, p, lv, s, rep = r["key"].split("|")
        if p == pid and lv != "A_sistema": ultimo[r["key"]] = r
    keys = {kk for kk, r in ultimo.items() if k in {canon(P[pid]["sector"], x) for x in (r.get("brand") or [])}}
    testi = {}
    for l in open(ROOT / "data/processed/main_calls.jsonl"):
        r = json.loads(l)
        if r["prompt_id"] != pid: continue
        kk = f"{r['engine']}|main|{r['call_id']}"
        if kk in keys: testi[kk] = r["response_text"] or ""
    nb = norm(b).split()[0]
    out = []
    for kk, t in testi.items():
        ls = [x.strip() for x in t.split("\n") if nb in norm(x)]
        if ls: out.append((kk, " / ".join(ls)[:600]))
    return out
def prodotti(j):
    pid, b = j.split("|"); k = sel[pid]["pagine"][[p["nome"] for p in sel[pid]["pagine"]].index(b)]["chiave"]
    rr = righe_marchio(pid, b, k); eng = motore("gpt"); conta = collections.Counter(); grezzi = {}
    blocchi = [rr[i:i + 40] for i in range(0, len(rr), 40)]
    def chiedi(blocco):
        txt = "\n".join(f"{n + 1}. {t}" for n, (_, t) in enumerate(blocco))
        return blocco, eng.once(dict(call_id="p", user_message=PA.format(q=sel[pid]["domanda"], b=b, righe=txt), system_prompt=None, search=False))
    with ThreadPoolExecutor(6) as ex2: risposte = list(ex2.map(chiedi, blocchi))
    for blocco, x in risposte:
        for l in (x.get("response_text") or "").split("\n"):
            m = re.match(r"\s*(\d+)\s*[:.)-]\s*(.+)", l)
            if not m or int(m.group(1)) > len(blocco): continue
            prod = m.group(2).strip().strip("*")
            grezzi[blocco[int(m.group(1)) - 1][0]] = prod
            if prod.upper() != "NESSUNO": conta[norm(prod)] += 1
    return j, dict(risposte=len(rr), prodotti=conta.most_common(10), grezzi=grezzi)
if __name__ == "__main__" and sys.argv[1:2] == ["A"]:
    jobs = [j for j in DA_FARE if "prodotti" not in R.get(j, {})]
    with ThreadPoolExecutor(12) as ex:
        for fu in as_completed([ex.submit(prodotti, j) for j in jobs]):
            j, v = fu.result()
            R.setdefault(j, {})["prodotti"] = v; json.dump(R, open(F, "w"), ensure_ascii=False, indent=1)
    for j in DA_FARE: print(j, R.get(j, {}).get("prodotti", {}).get("risposte"), R.get(j, {}).get("prodotti", {}).get("prodotti", [])[:3])

# ---- B: URL del prodotto più nominato (regola 2); se non c'è una pagina valida, regola 3 ----
sys.path.insert(0, str(Path(__file__).parent / "origine_22_10"))
from termini import TERM
from urllib.parse import urlsplit
ALTRI = {norm(n) for n in NOME.values()}
PU2 = ("Trova la pagina del prodotto «{p}» sul sito ufficiale italiano del marchio {b}: la scheda di quel singolo prodotto "
       "(o polizza, tour, struttura, servizio), non una categoria, un negozio terzo o un articolo. Rispondi solo con l'URL completo.")
PU3 = ("Sul sito ufficiale italiano del marchio {b}, apri la sezione dei prodotti «{c}» e prendi il primo prodotto elencato. "
       "Rispondi solo con l'URL completo della scheda di quel singolo prodotto (o polizza, tour, struttura, servizio).")
def sito_ok(u, b, dom, cit):
    h = (urlsplit(u).hostname or "").lower().removeprefix("www.")
    hosts = {dom} | {(urlsplit(x).hostname or "").lower().removeprefix("www.") for x, _ in cit}
    return any(h == x or h.endswith("." + x) for x in hosts if x) or norm(b).replace(" ", "") in h.replace("-", "")
def controlla(pid, b, u):
    m = scarica(u)
    if not m["ok"]: return "non_leggibile", m
    r = motore("gpt").once(dict(call_id="p", user_message=r1helper.P.format(q=sel[pid]["domanda"], b=b, t=r1helper.estratto(u)), system_prompt=None, search=False))
    return (r.get("response_text") or "").strip().upper()[:2], m
import threading
LOCK = threading.Lock()
def salva():
    with LOCK: json.dump(R, open(F, "w"), ensure_ascii=False, indent=1)
def url_per(j):
    pid, b = j.split("|"); st = R[j]; dom = next(p["dominio"] for p in sel[pid]["pagine"] if p["nome"] == b)
    cit = json.load(open(D / "pagine_candidate.json"))[pid][b]["citazioni"]
    prods = [p for p, n in st["prodotti"]["prodotti"] if p not in ALTRI and p != norm(b)]
    passi = ([("regola 2", PU2.format(p=prods[0], b=b), prods[0])] if prods else []) + [("regola 3", PU3.format(b=b, c=TERM[pid][0]), TERM[pid][0])]
    st.setdefault("prove_url", [])
    if any(p.get("esito") == "SI" for p in st["prove_url"]):
        u = next(p for p in st["prove_url"] if p.get("esito") == "SI"); st.update(scelta=u["url"], regola=u["regola"], prodotto=u["cosa"], versione_B=2); salva(); return j, st
    fatti = collections.Counter((p["regola"]) for p in st["prove_url"])
    for regola, msg, cosa in passi:
        for tent in range(fatti.get(regola, 0), 2):
            salva()
            x = motore("gpt").once(dict(call_id="u", user_message=msg, system_prompt=None, search=True))
            mm = re.search(r"https?://\S+", x.get("response_text") or "")
            if not mm: st["prove_url"].append(dict(regola=regola, cosa=cosa, url=None, esito="nessun URL")); continue
            u = mm.group(0).rstrip(").,>]*")
            if not sito_ok(u, b, dom, cit): st["prove_url"].append(dict(regola=regola, cosa=cosa, url=u, esito="fuori dal sito del marchio")); continue
            v, m = controlla(pid, b, u)
            st["prove_url"].append(dict(regola=regola, cosa=cosa, url=u, esito=v, metodo=m["metodo"], parole=m["parole"]))
            if v == "SI": st.update(scelta=u, regola=regola, prodotto=cosa, versione_B=2); salva(); return j, st
    st.update(scelta=None, regola=None, versione_B=2); salva(); return j, st
if __name__ == "__main__" and sys.argv[1:2] == ["B"]:
    for j in DA_FARE:
        if R.get(j, {}).get("versione_B") != 2 and any("query" in p for p in R.get(j, {}).get("prove_url", [])): R[j]["prove_url"] = []
    jobs = [j for j in DA_FARE if R.get(j, {}).get("versione_B") != 2]
    with ThreadPoolExecutor(16) as ex:
        for fu in as_completed([ex.submit(url_per, j) for j in jobs]):
            j, v = fu.result()
            v["versione_B"] = 2; R[j] = v; json.dump(R, open(F, "w"), ensure_ascii=False, indent=1)
    for j in DA_FARE:
        v = R.get(j, {}); print(f"{j:38s} {v.get('regola')} | {v.get('prodotto')} | {(v.get('scelta') or '-')[-60:]}")
