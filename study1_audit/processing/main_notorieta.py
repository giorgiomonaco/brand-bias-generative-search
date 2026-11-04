#!/usr/bin/env python
"""Studio principale — notorietà dei brand: ricerche mensili medie in Italia (DataForSEO, Google Ads).

    python analysis/main_notorieta.py elenco    # brand da misurare e query proposte -> results/main/notorieta_query.xlsx
    python analysis/main_notorieta.py volumi    # legge la revisione, chiama DataForSEO, scrive config/main_notorieta.csv

Universo: i brand (radici di tipo brand della tabella dei nomi) nominati in almeno MIN_RISPOSTE risposte di almeno
un motore e un settore, lo stesso universo di P1 in main_analysis.py.
Query: il nome del brand in minuscolo, senza accenti e punteggiatura (stessa regola del ciclo 10). Per i nomi che
sono anche parole comuni (Budget, Prima, Linear, Focus...) la query va disambiguata a mano nella revisione: la
colonna «query» del file Excel è quella che conta. Le disambiguazioni del ciclo 10 (volume_query in
config/cycle10_brand_domains.yaml) entrano già come proposta.
Notorietà = media degli ultimi 12 mesi disponibili (stessa funzione del ciclo 10), location 2380 (Italia), lingua it.
Permesso d'uso dei dati DataForSEO per la tesi: results/cycle10/dataforseo_permesso.md.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "analysis"))
sys.path.insert(0, str(ROOT / "pipeline"))
import main_analysis as M  # noqa: E402

REV = M.OUT / "notorieta_query.xlsx"
QUERY_CSV = ROOT / "config" / "main_notorieta_query.csv"
OUT_CSV = ROOT / "config" / "main_notorieta.csv"
CAP_USD = 5.0


def norm_q(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower().replace("'", "")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", s)).strip()


def universo() -> list[dict]:
    rows = M.load_calls()
    nomi = M.Nomi()
    info = M.attach_brands(rows, nomi, "estrattore")
    per = defaultdict(Counter)
    for r in rows:
        for k in r["B"]:
            per[k][(r["engine"], r["sector"])] += 1
    out = []
    for k, c in per.items():
        if max(c.values()) >= M.MIN_RISPOSTE:
            settori = sorted({s for (_, s) in c})
            out.append({"chiave": k, "nome": nomi.etichetta(k, info["varianti"]), "settori": " | ".join(settori),
                        "risposte": sum(c.values())})
    return sorted(out, key=lambda r: -r["risposte"])


def vq_ciclo10() -> dict[str, str]:
    f = ROOT / "config" / "cycle10_brand_domains.yaml"
    if not f.exists():
        return {}
    import yaml
    d = yaml.safe_load(f.read_text()) or {}
    out = {}
    for s, m in (d.get("volume_query") or {}).items():
        for name, q in (m or {}).items():
            out[M.canon(name)] = q
    return out


def cmd_elenco() -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    U = universo()
    vq = vq_ciclo10()
    wb = Workbook()
    ws = wb.active
    ws.title = "query"
    head = ["chiave", "nome", "settori", "risposte", "query_proposta", "da_controllare", "query"]
    ws.append(head)
    for r in U:
        prop = norm_q(vq.get(r["chiave"], r["nome"]))
        dubbio = "sì" if (len(prop.split()) == 1 and len(prop) <= 7) or r["chiave"] in vq else ""
        ws.append([r["chiave"], r["nome"], r["settori"], r["risposte"], prop, dubbio, prop])
    for c in ws[1]:
        c.font = Font(name="Arial", bold=True)
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.font = Font(name="Arial")
        row[6].fill = PatternFill("solid", fgColor="FFF2CC")
    ws2 = wb.create_sheet("istruzioni")
    for line in ("Colonna «query» (gialla): la ricerca da misurare su Google Italia. Modificala solo se il nome del brand "
                 "è anche una parola comune o un altro marchio (es. Budget -> «budget autonoleggio»).",
                 "«da_controllare» = sì per i nomi brevi di una parola o già disambiguati nel ciclo 10.",
                 "Lascia vuota la query per escludere un brand dalla notorietà (resta nelle altre misure)."):
        ws2.append([line])
    ws.column_dimensions["B"].width = 28
    ws.column_dimensions["E"].width = 34
    ws.column_dimensions["G"].width = 34
    M.OUT.mkdir(exist_ok=True)
    wb.save(REV)
    print(f"{len(U)} brand, {sum(1 for r in U if len(norm_q(r['nome']).split()) == 1)} di una parola -> {REV}")


def cmd_volumi() -> None:
    import cycle10_dataforseo as d
    from openpyxl import load_workbook
    ws = load_workbook(REV)["query"]
    righe = [dict(zip([c.value for c in ws[1]], [c.value for c in r])) for r in ws.iter_rows(min_row=2)]
    with QUERY_CSV.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["chiave", "nome", "query"])
        w.writeheader()
        for r in righe:
            w.writerow({"chiave": r["chiave"], "nome": r["nome"], "query": norm_q(r["query"] or "")})
    qs = sorted({norm_q(r["query"]) for r in righe if r.get("query")})
    print(f"{len(qs)} query; spesa DataForSEO cumulata {d.spent():.4f} $")
    vols, s0 = {}, d.spent()
    for i in range(0, len(qs), 1000):
        part = qs[i:i + 1000]
        if d.spent() - s0 + d.estimate("google_ads") > CAP_USD:
            raise SystemExit(f"tetto di spesa di questo passo ({CAP_USD} $) superato")
        data = d.call("keywords_data/google_ads/search_volume/live",
                      [dict(keywords=part, location_code=2380, language_code="it")],
                      f"main_brand_volume_{i // 1000}", est=d.estimate("google_ads"))
        for r in data["tasks"][0].get("result") or []:
            vols[r["keyword"]] = (r.get("search_volume"), mean_12m(r.get("monthly_searches")))
    with OUT_CSV.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["chiave", "nome", "query", "volume", "volume_api"])
        w.writeheader()
        for r in righe:
            q = norm_q(r["query"] or "")
            api, m12 = vols.get(q, (None, None))
            w.writerow({"chiave": r["chiave"], "nome": r["nome"], "query": q,
                        "volume": "" if m12 is None else m12, "volume_api": "" if api is None else api})
    print(f"scritto {OUT_CSV}: {sum(1 for q in qs if vols.get(q, (None, None))[1] is not None)} query con volume")


def mean_12m(ms):
    if not ms:
        return None
    ms = sorted(ms, key=lambda m: (m["year"], m["month"]), reverse=True)[:12]
    v = [m["search_volume"] for m in ms if m.get("search_volume") is not None]
    return round(sum(v) / len(v), 1) if v else None


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["elenco", "volumi"])
    {"elenco": cmd_elenco, "volumi": cmd_volumi}[ap.parse_args().cmd]()
