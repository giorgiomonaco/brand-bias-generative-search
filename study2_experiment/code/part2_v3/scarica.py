"""Scaricamento a livelli (protocollo sez. 4): 1 richiesta semplice; 2 Bright Data Web Unlocker con uscita italiana
(proxy residenziale, sblocco e rendering gestiti dal servizio); 3 browser reale (Playwright, solo dal Mac) per le pagine
rimaste. Nessuna pagina si scarta perché il sito blocca l'accesso automatico. HTML grezzo, testo e metadati congelati."""
import sys, json, re, gzip, hashlib, os
from pathlib import Path
from datetime import datetime, timezone
import requests
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline")); sys.path.insert(0, str(ROOT / "analysis/part2_conf"))
from thesis_env import load_env
load_env()
from cattura import UA
from bs4 import BeautifulSoup
def testo(html):
    """Come analysis/part2_conf/cattura.py, ma senza togliere i <form>: nei siti ASP.NET il <form> contiene tutta la
    pagina (Coverwise). Menu, piè di pagina e moduli si tolgono comunque nell'estrazione del testo del prodotto."""
    s = BeautifulSoup(html, "html.parser"); ld = []
    for t in s.find_all("script", type="application/ld+json"):
        try: d = json.loads(t.string or "")
        except Exception: continue
        for x in (d if isinstance(d, list) else d.get("@graph", [d]) if isinstance(d, dict) else []):
            if isinstance(x, dict) and x.get("description"): ld.append(str(x.get("description")))
    for t in s(["script", "style", "noscript", "nav", "header", "footer", "aside", "svg", "iframe"]): t.decompose()
    title = (s.title.string or "").strip() if s.title and s.title.string else ""
    body = s.body or s
    lines = [re.sub(r"\s+", " ", l).strip() for l in body.get_text("\n").split("\n")]
    return title, "\n".join(l for l in lines if l), ld
OUT = ROOT / "data/part2_v3/pagine"; OUT.mkdir(parents=True, exist_ok=True)
BLOCCO = re.compile(r"access denied|just a moment|attention required|security page|captcha|are you a robot|verify you are human|pardon our interruption|enable javascript|dispositivi automatici|non possiamo permetterti di accedere|accesso negato|verifica di non essere un robot|attiva(re)? javascript", re.I)
def ok(title, txt): return len(txt.split()) >= 150 and not BLOCCO.search(title + " " + txt[:1500])
def kurl(u): return hashlib.sha256(u.encode()).hexdigest()[:16]
def _dec(r):
    enc = requests.utils.get_encodings_from_content(r.text[:3000]) if r.content else []
    return r.content.decode(enc[0] if enc else (r.encoding or "utf-8"), errors="replace")
def liv1(u):
    try:
        r = requests.get(u, headers=UA, timeout=25, allow_redirects=True); return r.status_code, _dec(r), r.url
    except Exception as e: return f"ERR {type(e).__name__}", "", u
def liv2(u):
    try:
        r = requests.post("https://api.brightdata.com/request", timeout=120,
                          headers={"Authorization": f"Bearer {os.environ['BRIGHTDATA_API_TOKEN']}", "Content-Type": "application/json"},
                          json={"zone": os.environ["BRIGHTDATA_UNLOCKER_ZONE"], "url": u, "format": "raw", "country": "it"})
        return r.status_code, _dec(r), u
    except Exception as e: return f"ERR {type(e).__name__}", "", u
def salva(u, st, html, fin, metodo):
    k = kurl(u); t, txt, ld = testo(html) if html else ("", "", [])
    meta = dict(url=u, url_finale=fin, stato=st, metodo=metodo, titolo=t, parole=len(txt.split()), ok=ok(t, txt), ld=ld,
                catturato=datetime.now(timezone.utc).isoformat(), sha256_html=hashlib.sha256(html.encode()).hexdigest())
    (OUT / f"{k}.html.gz").write_bytes(gzip.compress(html.encode())); (OUT / f"{k}.txt").write_text(txt)
    (OUT / f"{k}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1)); return meta
def scarica(u):
    """Restituisce i metadati della migliore cattura; non riscarica una pagina già catturata bene."""
    f = OUT / f"{kurl(u)}.json"
    if f.exists():
        m = json.loads(f.read_text())
        if m["ok"]: return m
    st, html, fin = liv1(u); m = salva(u, st, html, fin, "requests")
    if m["ok"]: return m
    st, html, fin = liv2(u); m2 = salva(u, st, html, fin, "brightdata_unlocker_it")
    return m2 if m2["ok"] else m2
if __name__ == "__main__":
    for u in sys.argv[1:]:
        m = scarica(u); print(m["metodo"], m["stato"], m["parole"], "OK" if m["ok"] else "NO", m["titolo"][:50], "|", u[:80])
