"""Cattura delle pagine: GET con UA browser, HTML grezzo salvato, testo estratto (script/style/nav/header/footer/form/aside
rimossi) e descrizioni JSON-LD. Uso: python3 cattura.py URL [URL...]  -> stampa stato, parole, titolo."""
import sys, json, hashlib, re, gzip
from pathlib import Path
from datetime import datetime, timezone
import requests
from bs4 import BeautifulSoup
OUT = Path(__file__).resolve().parents[2] / "data" / "part2_conf" / "pagine"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36",
      "Accept-Language": "it-IT,it;q=0.9", "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}

def testo(html):
    s = BeautifulSoup(html, "html.parser")
    ld = []
    for t in s.find_all("script", type="application/ld+json"):
        try:
            d = json.loads(t.string or "")
        except Exception:
            continue
        for x in (d if isinstance(d, list) else d.get("@graph", [d]) if isinstance(d, dict) else []):
            if isinstance(x, dict) and x.get("description"):
                ld.append(str(x.get("description")))
    for t in s(["script", "style", "noscript", "nav", "header", "footer", "form", "aside", "svg", "iframe"]):
        t.decompose()
    title = (s.title.string or "").strip() if s.title and s.title.string else ""
    body = s.body or s
    lines = [re.sub(r"\s+", " ", l).strip() for l in body.get_text("\n").split("\n")]
    lines = [l for l in lines if l]
    return title, "\n".join(lines), ld

def cattura(url):
    k = hashlib.sha256(url.encode()).hexdigest()[:16]
    try:
        r = requests.get(url, headers=UA, timeout=25, allow_redirects=True)
        st, fin = r.status_code, r.url
        enc = requests.utils.get_encodings_from_content(r.text[:3000]) if r.content else []
        html = r.content.decode(enc[0] if enc else "utf-8", errors="replace")
    except Exception as e:
        st, html, fin = f"ERR {type(e).__name__}", "", url
    title, txt, ld = testo(html) if html else ("", "", [])
    meta = dict(url=url, url_finale=fin, stato=st, titolo=title, parole=len(txt.split()), ld=ld,
                catturato=datetime.now(timezone.utc).isoformat(), sha256_html=hashlib.sha256(html.encode()).hexdigest(), metodo="requests")
    (OUT / f"{k}.html.gz").write_bytes(gzip.compress(html.encode()))
    (OUT / f"{k}.txt").write_text(txt)
    (OUT / f"{k}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    return k, meta

if __name__ == "__main__":
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(12) as ex:
        for k, m in ex.map(cattura, sys.argv[1:]):
            print(k, m["stato"], m["parole"], m["titolo"][:70], "|", m["url"][:90], "->", m["url_finale"][:60] if m["url_finale"] != m["url"] else "")
