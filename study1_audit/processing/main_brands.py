#!/usr/bin/env python
"""Studio principale — estrazione dei brand da ogni risposta, con l'istruzione fissa del ciclo 12.

    python analysis/main_brands.py [--workers 16] [--vertex] [--file main_calls_gemini_altro.jsonl]

Istruzione, modello e schema identici al ciclo 12 (config/cycle12_brand_extraction.md, gemini-2.5-flash,
temperatura 0), validati a mano l'11/10 (precisione 96,2%, richiamo 98,7%). Legge data/processed/main_calls.jsonl
(prima: python analysis/main_prepare.py), una chiamata per risposta, appende a data/raw/main_brands.jsonl e
riprende da dove era. Le risposte vuote non vanno al modello: brand e fonti vuoti.
Con --vertex lo stesso modello gira su Vertex AI (credenziali predefinite, VERTEX_PROJECT / VERTEX_LOCATION in .env,
predefiniti REDACTED / global): aggiunto il 14/10, dopo il blocco della Gemini API per il tetto di spesa. Prima di
usarlo sul run completo, analysis/main_brands_controllo_vertex.py ripete l'estrazione sul campione validato a mano.
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))
sys.path.insert(0, str(ROOT / "analysis"))
from cycle12_brands import MODEL, instruction  # noqa: E402
from thesis_env import require  # noqa: E402

OUT = ROOT / "data" / "raw" / "main_brands.jsonl"


def _loads(line: str):
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return None


def client_gemini(vertex: bool):
    import os
    from google import genai
    from google.genai import types
    if vertex:
        from thesis_env import load_env
        load_env()
        c = genai.Client(vertexai=True, project=os.environ.get("VERTEX_PROJECT", "YOUR_GCP_PROJECT"),
                         location=os.environ.get("VERTEX_LOCATION", "global"),
                         http_options=types.HttpOptions(timeout=120_000))
        return c, types, "vertex"
    return genai.Client(api_key=require("GEMINI_API_KEY"), http_options=types.HttpOptions(timeout=120_000)), types, "api"


def config(types):
    schema = types.Schema(type="OBJECT", properties={
        "brand": types.Schema(type="ARRAY", items=types.Schema(type="STRING")),
        "fonti_e_aggregatori": types.Schema(type="ARRAY", items=types.Schema(type="STRING"))},
        required=["brand", "fonti_e_aggregatori"])
    return types.GenerateContentConfig(system_instruction=instruction(), temperature=0,
                                       response_mime_type="application/json", response_schema=schema)


def key(r: dict) -> str:
    return f"{r['engine']}|main|{r['call_id']}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--vertex", action="store_true", help="estrazione su Vertex AI invece che sulla Gemini API")
    ap.add_argument("--file", default="main_calls.jsonl", help="tabella in data/processed/ da cui leggere le risposte")
    ap.add_argument("--central-only", action="store_true", help="exclude the set-aside system-prompt arm")
    ap.add_argument("--dry-run", action="store_true", help="count pending extractions without a client or API calls")
    a = ap.parse_args()
    calls = ROOT / "data" / "processed" / a.file
    done, vuote = set(), set()
    if OUT.exists():
        for line in OUT.open():
            r = _loads(line)
            if r is not None and not r.get("error"):
                done.add(r["key"])
                if r.get("vuota"):
                    vuote.add(r["key"])
                else:
                    vuote.discard(r["key"])
    # una risposta vuota ripetuta il 15/10 ha ora un testo: si estrae di nuovo (l'ultima estrazione vale nell'analisi)
    todo = [r for r in map(_loads, calls.open()) if r is not None
            and (key(r) not in done or (key(r) in vuote and (r.get("response_text") or "").strip()))]
    if a.central_only:
        todo = [r for r in todo if r["level"] != "A_sistema"]
    print(f"{len(done)} già estratte, {len(todo)} da estrarre", flush=True)
    if a.dry_run or not todo:
        return
    client, types, endpoint = client_gemini(a.vertex)
    cfg = config(types)
    lock = threading.Lock()
    stato = {"fatte": 0, "errori": 0, "t0": time.monotonic()}

    def work(r: dict) -> None:
        text = (r.get("response_text") or "").strip()
        rec = {"key": key(r), "model": MODEL, "endpoint": endpoint}
        if not text:
            rec.update({"brand": [], "fonti_e_aggregatori": [], "error": None, "vuota": True})
        else:
            for attempt in range(5):
                try:
                    resp = client.models.generate_content(model=MODEL, contents=text, config=cfg)
                    d = json.loads(resp.text)
                    rec.update({"brand": d.get("brand") or [], "fonti_e_aggregatori": d.get("fonti_e_aggregatori") or [],
                                "model_version": getattr(resp, "model_version", None), "error": None})
                    um = resp.usage_metadata
                    rec["tokens"] = {"in": getattr(um, "prompt_token_count", None),
                                     "out": getattr(um, "candidates_token_count", None),
                                     "thoughts": getattr(um, "thoughts_token_count", None)}
                    break
                except Exception as e:  # noqa: BLE001
                    rec["error"] = f"{type(e).__name__}: {e}"[:500]
                    time.sleep(15 * (attempt + 1))
        with lock:
            with OUT.open("a") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            stato["fatte"] += 1
            stato["errori"] += bool(rec.get("error"))
            if stato["fatte"] % 200 == 0:
                v = stato["fatte"] / (time.monotonic() - stato["t0"])
                print(f"{stato['fatte']}/{len(todo)}  errori {stato['errori']}  ~{(len(todo) - stato['fatte']) / v / 60:.0f} min",
                      flush=True)

    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        list(ex.map(work, todo))
    print(f"fine: {stato['fatte']} estratte, {stato['errori']} errori (si ritentano rilanciando)", flush=True)


if __name__ == "__main__":
    main()
