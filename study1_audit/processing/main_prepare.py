#!/usr/bin/env python
"""Studio principale — tabella snella delle chiamate riuscite (una riga per chiamata).

    python analysis/main_prepare.py

Legge data/raw/main_{gpt,gemini,perplexity}.jsonl, tiene per ogni call_id l'ultima risposta riuscita e scrive
data/processed/main_calls.jsonl senza i grezzi della risposta (raw_response, request_body), così l'analisi non
rilegge ogni volta centinaia di MB. Scrive anche data/processed/main_mancanti.csv con le chiamate del piano che
non hanno una risposta riuscita (per esempio i blocchi del filtro dei contenuti di Azure) e il motivo.

Fonti per motore (stessa convenzione del ciclo 12):
  - citate: GPT = url_citation della risposta (cited_urls); Gemini = grounding_chunks, dominio nel titolo;
    Perplexity = nessuna (senza istruzione non segna le fonti citate);
  - consultate: GPT = action.sources (consulted_urls); Perplexity = risultati recuperati; Gemini = non restituite;
  - fonti (misura primaria di P2 e P3): citate su GPT e Gemini, recuperate su Perplexity.
Query: le query eseguite (web_search_queries); su GPT anche quelle scritte dal modello (model_queries).
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "analysis"))
from common import l1a_chunk_domain, normalize_domain  # noqa: E402

RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"
ENGINES = ("gpt", "gemini", "perplexity")
KEEP = ("engine", "call_id", "sector", "prompt_id", "sottotema", "prompt", "level", "search", "rep", "timestamp",
        "model_version", "search_performed", "latency_s", "response_text")


def _loads(line: str):
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return None


def domains(urls) -> list[str]:
    out = []
    for u in urls or []:
        d = normalize_domain(u if isinstance(u, str) else (u.get("url") or u.get("uri") or ""))
        if d and d not in out:
            out.append(d)
    return out


def slim(r: dict) -> dict:
    e = r["engine"]
    s = {k: r.get(k) for k in KEEP}
    s["queries"] = [q for q in (r.get("web_search_queries") or []) if q]
    s["queries_modello"] = [q for q in (r.get("model_queries") or []) if q] if e == "gpt" else s["queries"]
    if e == "gpt":
        cit = domains(r.get("cited_urls"))
        cons = domains(r.get("consulted_urls"))
        s["urls_citate"] = list(dict.fromkeys(r.get("cited_urls") or []))
    elif e == "gemini":
        cit = []
        for c in r.get("grounding_chunks") or []:
            d = l1a_chunk_domain(c)
            if d and d not in cit:
                cit.append(d)
        cons = []
        s["urls_citate"] = []
    else:
        cit = []
        cons = []
        for x in r.get("retrieved_results") or []:
            d = normalize_domain(x.get("domain") or x.get("url") or "")
            if d and d not in cons:
                cons.append(d)
        s["urls_citate"] = []
    s["citate"] = cit
    s["consultate"] = cons
    s["fonti"] = cons if e == "perplexity" else cit
    return s


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--gemini", choices=["vertex", "api"], default=None,
                    help="quale run di Gemini entra nell'analisi come «gemini» (predefinito: vertex se esiste)")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    vertex = RAW / "main_gemini_vertex.jsonl"
    scelta = a.gemini or ("vertex" if vertex.exists() else "api")
    file_gemini = {"vertex": vertex, "api": RAW / "main_gemini.jsonl"}
    altro = "api" if scelta == "vertex" else "vertex"
    sorgenti = [("gpt", RAW / "main_gpt.jsonl", "main_calls.jsonl"),
                ("gemini", file_gemini[scelta], "main_calls.jsonl"),
                ("perplexity", RAW / "main_perplexity.jsonl", "main_calls.jsonl"),
                (f"gemini_{altro}", file_gemini[altro], "main_calls_gemini_altro.jsonl")]
    print(f"Gemini nell'analisi: {scelta} ({file_gemini[scelta].name}); l'altro run va in main_calls_gemini_altro.jsonl")
    per_file = {}
    mancanti = []
    for e, f, dest in sorgenti:
        rows = per_file.setdefault(dest, [])
        if not f.exists():
            continue
        ok, ultimo_errore = {}, {}
        for line in f.open():
            r = _loads(line)
            if r is None:
                continue
            if r.get("error"):
                ultimo_errore[r["call_id"]] = str(r["error"])[:200]
            elif not (r.get("response_text") or "").strip():   # risposta vuota: conta come chiamata fallita
                ultimo_errore[r["call_id"]] = "risposta vuota"
            else:
                ok[r["call_id"]] = r
        for cid, r in ok.items():
            r = {**r, "engine": "gemini" if e == "gemini" else r["engine"]}
            sl = slim({**r, "engine": "gemini" if e.startswith("gemini") else r["engine"]})
            sl["engine"] = e
            sl["endpoint"] = (r.get("request_body") or {}).get("endpoint", "api") if e.startswith("gemini") else None
            rows.append(sl)
        for cid, err in ultimo_errore.items():
            if cid not in ok:
                mancanti.append({"engine": e, "call_id": cid, "errore": err})
        print(f"{e} ({f.name}): {len(ok)} riuscite, {sum(1 for c in ultimo_errore if c not in ok)} senza risposta", flush=True)
    for dest, rows in per_file.items():
        with (OUT / dest).open("w") as fo:
            for s in rows:
                fo.write(json.dumps(s, ensure_ascii=False) + "\n")
    with (OUT / "main_mancanti.csv").open("w", newline="") as fo:
        w = csv.DictWriter(fo, fieldnames=["engine", "call_id", "errore"])
        w.writeheader()
        w.writerows(mancanti)
    print("scritte: " + ", ".join(f"{d} {len(r)} righe" for d, r in per_file.items()))


if __name__ == "__main__":
    main()
