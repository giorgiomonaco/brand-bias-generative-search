#!/usr/bin/env python
"""Ciclo 12, Fase 4 — estrazione dei brand da ogni risposta (istruzione in config/cycle12_brand_extraction.md).

    python analysis/cycle12_brands.py [--workers 8]

Legge data/raw/cycle12_{gpt,gemini,perplexity}.jsonl e data/raw/cycle12_3b_perplexity.jsonl (solo risposte riuscite),
chiama gemini-2.5-flash una volta per risposta e appende a data/raw/cycle12_brands.jsonl (riprende da dove era).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))
from thesis_env import require  # noqa: E402

RAW = ROOT / "data" / "raw"
OUT = RAW / "cycle12_brands.jsonl"
INSTR_FILE = ROOT / "config" / "cycle12_brand_extraction.md"
MODEL = "gemini-2.5-flash"
FILES = ["cycle12_gpt.jsonl", "cycle12_gemini.jsonl", "cycle12_perplexity.jsonl", "cycle12_3b_perplexity.jsonl"]



def _loads(line: str):
    """Una riga troncata (processo chiuso a metà scrittura nella sandbox) si salta."""
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return None

def instruction() -> str:
    txt = INSTR_FILE.read_text()
    block = txt.split("## Istruzione", 1)[1].split("\n", 1)[1]
    return block.strip()


def key(r: dict) -> str:
    return f"{r['engine']}|{r['part']}|{r['call_id']}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=require("GEMINI_API_KEY"), http_options=types.HttpOptions(timeout=120_000))
    instr = instruction()
    schema = types.Schema(type="OBJECT", properties={
        "brand": types.Schema(type="ARRAY", items=types.Schema(type="STRING")),
        "fonti_e_aggregatori": types.Schema(type="ARRAY", items=types.Schema(type="STRING"))},
        required=["brand", "fonti_e_aggregatori"])
    cfg = types.GenerateContentConfig(system_instruction=instr, temperature=0, response_mime_type="application/json",
                                      response_schema=schema)
    done = set()
    if OUT.exists():
        for line in OUT.open():
            r = _loads(line)
            if r is None:
                continue
            if not r.get("error"):
                done.add(r["key"])
    todo = []
    for fn in FILES:
        p = RAW / fn
        if not p.exists():
            continue
        latest = {}
        for line in p.open():
            r = _loads(line)
            if r is None:
                continue
            if not r.get("error") and r.get("response_text") is not None:
                latest[key(r)] = r
        todo += [r for k, r in latest.items() if k not in done]
    print(f"{len(done)} già estratte, {len(todo)} da estrarre", flush=True)
    lock = threading.Lock()

    def work(r: dict) -> None:
        text = r.get("response_text") or ""
        rec = {"key": key(r), "model": MODEL}
        for attempt in range(4):
            try:
                resp = client.models.generate_content(model=MODEL, contents=text or "(risposta vuota)", config=cfg)
                d = json.loads(resp.text)
                rec.update({"brand": d.get("brand") or [], "fonti_e_aggregatori": d.get("fonti_e_aggregatori") or [],
                            "model_version": getattr(resp, "model_version", None), "error": None})
                um = resp.usage_metadata
                rec["tokens"] = {"in": getattr(um, "prompt_token_count", None), "out": getattr(um, "candidates_token_count", None),
                                 "thoughts": getattr(um, "thoughts_token_count", None)}
                break
            except Exception as e:  # noqa: BLE001
                rec["error"] = f"{type(e).__name__}: {e}"[:500]
                time.sleep(15 * (attempt + 1))
        with lock:
            with OUT.open("a") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        list(ex.map(work, todo))
    print("fine", flush=True)


if __name__ == "__main__":
    main()
