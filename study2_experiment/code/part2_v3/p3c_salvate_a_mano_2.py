"""Secondo giro di pagine salvate a mano da co-author (24/10, Safari, Web Archive): pagine trovate dalle regole 2/3 ma non
leggibili in automatico (Trek, Adidas padel, Selected Homme, Drivalia) e pagine cercate da lui sul sito del marchio
(Bershka: primo risultato di «jeans mom»; Massimo Dutti: giubbotto in pelle). Stesso controllo GPT; l'esito si
aggiunge ai tentativi della regola 2/3 del marchio."""
import json, plistlib, hashlib, gzip
from datetime import datetime, timezone
from scarica import OUT, kurl, ok, testo
from comune_v3 import D
import p2_regola1 as r1
import p3_regola2 as r2
S = D / "salvate_a_mano"
FILE = {"Bici ibrida confortevole Verve EQ – Trek Bikes.webarchive": ("sport_09|Trek", "regola 2"),
        "racchetta da padel DRIVE 2026 - Blu adidas | adidas Italia.webarchive": ("sport_13|Adidas", "regola 2"),
        "GIACCA IN PELLE | Nero | Selected.webarchive": ("moda_beauty_06|Selected Homme", "regola 2"),
        "I nostri veicoli | Rent | DRIVALIA.webarchive": ("viaggi_17|Drivalia", "regola 2"),
        "Jeans barrel fit a vita bassa - Donna | Bershka.webarchive": ("moda_beauty_08|Bershka", "regola 3 (ricerca a mano)"),
        "City bike elettrica Verve+": ("sport_09|Trek", "regola 2"),
        "Jeans mom fit - Donna | Bershka.webarchive": ("moda_beauty_08|Bershka", "regola 3 (ricerca a mano)"),
        "Giacca combinata in pelle e pelle scamosciata · Tegola · Top E Altri Capi | Massimo Dutti.webarchive": ("moda_beauty_06|Massimo Dutti", "regola 2 (ricerca a mano)")}
tutti = {x.name: x for x in S.glob("*.webarchive")}
def trova(nome):
    pre = nome[:10]; c = [x for n, x in tutti.items() if n.startswith(pre)]
    if len(c) > 1: c = [x for x in c if x.name[:24] == nome[:24]] or c[:1]
    assert len(c) == 1, nome; return c[0].name
for f0, (j, regola) in FILE.items():
    f = trova(f0)
    if any(p.get("file") == f for p in r2.R[j].get("prove_url", [])) or (r2.R[j].get("scelta") and "salvata" not in f0 and any(p.get("metodo") == "safari_webarchive_a_mano" for p in r2.R[j].get("prove_url", []))): continue
    a = plistlib.load(open(S / f, "rb"))["WebMainResource"]; u = a.get("WebResourceURL")
    html = a["WebResourceData"].decode(a.get("WebResourceTextEncodingName") or "utf-8", errors="replace")
    t, txt, ld = testo(html); k = kurl(u)
    meta = dict(url=u, url_finale=u, stato="salvata a mano", metodo="safari_webarchive_a_mano", titolo=t, parole=len(txt.split()), ok=ok(t, txt), ld=ld,
                catturato=datetime.fromtimestamp((S / f).stat().st_mtime, timezone.utc).isoformat(), sha256_html=hashlib.sha256(html.encode()).hexdigest(), file_originale=f"salvate_a_mano/{f}")
    (OUT / f"{k}.html.gz").write_bytes(gzip.compress(html.encode())); (OUT / f"{k}.txt").write_text(txt); (OUT / f"{k}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    pid, b = j.split("|"); v, m = r2.controlla(pid, b, u) if meta["ok"] else ("non_leggibile", meta)
    st = r2.R[j]; st.setdefault("prove_url", []).append(dict(regola=regola, cosa="pagina salvata a mano", url=u, esito=v, metodo="safari_webarchive_a_mano", parole=meta["parole"], file=f))
    if v == "SI": st.update(scelta=u, regola=regola)
    print(j, meta["parole"], v, u[:90])
json.dump(r2.R, open(r2.F, "w"), ensure_ascii=False, indent=1)
