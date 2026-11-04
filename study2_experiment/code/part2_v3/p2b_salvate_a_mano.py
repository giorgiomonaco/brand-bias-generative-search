"""Pagine della regola 1 che i siti non lasciano leggere in automatico: salvate a mano da co-author in Safari
(formato Web Archive, 23/10) in data/part2_v3/salvate_a_mano/. Si estrae l'HTML principale e si applica lo stesso
controllo GPT della regola 1. La pagina di Bershka era un 404 (link morto): quel marchio passa alla regola 2."""
import json, plistlib, hashlib, gzip, sys
from pathlib import Path
from datetime import datetime, timezone
from scarica import OUT, kurl, ok
from scarica import testo
from comune_v3 import D
import p2_regola1 as r1
from motori import motore
S = D / "salvate_a_mano"
FILE = {
 "https://www.larocheposay.it/retinolo-scopri-come-attenuare-le-rughe/redermic-retinol-occhi": ("moda_beauty_14|La Roche-Posay", "Redermic Retinol Occhi Crema Anti-Rughe | La Roche Posay.webarchive"),
 "https://www.larocheposay.it/retinolo-scopri-come-attenuare-le-rughe/retinol-b3-siero": ("moda_beauty_18|La Roche-Posay", "Retinol B3 Siero Anti-Rughe Concentrato |La Roche-Posay.webarchive"),
 "https://www.zara.com/it/it/jeans-z1975-mom-fit-vita-alta-p04083224.html": ("moda_beauty_08|Zara", "JEANS Z1975 MOM FIT A VITA ALTA - Azzurro medio | ZARA Italia : Italy.webarchive"),
 "https://www.massimodutti.com/it/uomo/giubbotti/pelle-n1375": ("moda_beauty_06|Massimo Dutti", "GIACCHE IN PELLE - Massimo Dutti - IT.webarchive"),
 "https://www.geniallife.it/soluzioni-per-te/geniallife-plan": ("assicurazioni_20|GenialLife", "GenialLife Plan: polizza vita pluriennale a premio costante.webarchive"),
 "https://www.coverwise.it/assicurazione-annullamento-viaggio.aspx": ("assicurazioni_02|Coverwise", "Assicurazione Annullamento Viaggio E Volo: La Polizza Cancellazione.webarchive"),
 "https://www.drivalia.com/it/ita/rent": ("viaggi_17|Drivalia", "Noleggio auto a Breve Termine | Drivalia.webarchive"),
}
eng = motore("gpt"); sel = r1.sel
for u, (j, f) in FILE.items():
    a = plistlib.load(open(S / f, "rb"))["WebMainResource"]
    html = a["WebResourceData"].decode(a.get("WebResourceTextEncodingName") or "utf-8", errors="replace")
    t, txt, ld = testo(html); k = kurl(u)
    meta = dict(url=u, url_finale=a.get("WebResourceURL", u), stato="salvata a mano", metodo="safari_webarchive_a_mano", titolo=t,
                parole=len(txt.split()), ok=ok(t, txt), ld=ld, catturato=datetime.fromtimestamp((S / f).stat().st_mtime, timezone.utc).isoformat(),
                sha256_html=hashlib.sha256(html.encode()).hexdigest(), file_originale=f"salvate_a_mano/{f}")
    (OUT / f"{k}.html.gz").write_bytes(gzip.compress(html.encode())); (OUT / f"{k}.txt").write_text(txt)
    (OUT / f"{k}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    pid, b = j.split("|"); v = None
    if meta["ok"]:
        r = eng.once(dict(call_id="p", user_message=r1.P.format(q=sel[pid]["domanda"], b=b, t=txt[:3500]), system_prompt=None, search=False))
        v = (r.get("response_text") or "").strip().upper()[:2]
    st = r1.R[j]
    for p in st["prove"]:
        if p["url"] == u: p.update(esito=v or "non_leggibile", metodo=meta["metodo"], parole=meta["parole"])
    if v == "SI": st["scelta"] = u
    print(j, meta["parole"], "OK" if meta["ok"] else "NO", v)
for p in r1.R["moda_beauty_08|Bershka"]["prove"]: p["esito"] = "404 (link morto, controllo a mano)"
json.dump(r1.R, open(r1.F, "w"), ensure_ascii=False, indent=1)
