"""Testo delle pagine (protocollo sez. 4): pagina intera senza menu, piè di pagina, cookie, newsletter, recensioni, prodotti
correlati, taglie e carrello, testi generici su spedizioni e resi. GPT copia parola per parola (istruzione della v2,
analysis/part2_v2/s6_estrai_intera.py); si tengono solo le righe che compaiono nella pagina originale. Testi congelati
con impronta in data/part2_v3/testi/."""
import sys, json, re, hashlib, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "part2_conf")); sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "part2_v2"))
from motori import motore, with_retries
from s6_estrai_intera import P, norm
from comune_v3 import D
from scarica import OUT, kurl
TD = D / "testi"; TD.mkdir(exist_ok=True)
sel = json.load(open(D / "selezione_v3.json"))
def pagine_scelte():
    r1 = json.load(open(D / "regola1.json")); f2 = D / "regola2.json"; r2 = json.load(open(f2)) if f2.exists() else {}
    out = {}
    for pid, v in sel.items():
        for p in v["pagine"]:
            j = f"{pid}|{p['nome']}"; u = r1.get(j, {}).get("scelta"); reg = "regola 1"
            if not u and r2.get(j, {}).get("scelta"): u, reg = r2[j]["scelta"], r2[j].get("regola")
            out[j] = dict(url=u, regola=reg if u else None)
    return out
def estrai(j, u):
    pid, b = j.split("|"); src = (OUT / f"{kurl(u)}.txt").read_text(); S = norm(src)
    r = with_retries(motore("gpt"), dict(call_id="e", user_message=P.format(brand=b, prod=sel[pid]["domanda"], testo=src[:120000]), system_prompt=None, search=False))
    kept, drop = [], []
    for l in (r.get("response_text") or "").split("\n"):
        l2 = norm(re.sub(r"^[-•*#>]+\s*", "", l))
        if l2: (kept if l2 in S else drop).append(l2)
    txt = "\n".join(kept)
    return j, dict(url=u, parole_grezze=len(src.split()), parole=len(txt.split()), righe_scartate=len(drop), testo=txt,
                   sha256=hashlib.sha256(txt.encode()).hexdigest())
if __name__ == "__main__":
    ps = pagine_scelte(); fatte = {f.stem for f in TD.glob("*.json")}
    jobs = [(j, v["url"]) for j, v in ps.items() if v["url"] and kurl(j) not in fatte]
    print("pagine scelte:", sum(bool(v["url"]) for v in ps.values()), "da estrarre:", len(jobs), flush=True)
    with ThreadPoolExecutor(20) as ex:
        for fu in as_completed([ex.submit(estrai, j, u) for j, u in jobs]):
            j, o = fu.result(); o["chiave"] = j; (TD / f"{kurl(j)}.json").write_text(json.dumps(o, ensure_ascii=False, indent=1))
