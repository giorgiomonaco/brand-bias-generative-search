#!/usr/bin/env python
"""Ciclo 12 — test sul system prompt (brief: internal notes «Operativo ciclo 12 — Test sul system prompt»).

    python pipeline/cycle12_runner.py --engine gpt|gemini|perplexity [--part test|3b] [--workers N]
                                      [--dry-run] [--smoke]

Parte `test` (disegno A, 240 chiamate per motore): prompt del test (config/cycle12_prompts.csv, 2 per settore)
x livello del system prompt (vuoto | rumore | persona) x ricerca (spenta | accesa) x 5 repliche.
  - vuoto: campo del system prompt omesso (non stringa vuota);
  - rumore: config/cycle12_noise.yaml, un testo per prompt, uguale in tutte le repliche e in tutti i motori;
  - persona: persona A del settore, campo `it` di config/cycle11_personas.yaml, così com'è;
  - messaggio utente: solo il prompt.
Parte `3b` (solo Perplexity, ricerca accesa): "{persona A} {prompt}" nel messaggio utente
(config/cycle11_template.md), stessi prompt, 5 repliche = 40 chiamate.

Motori, come nello studio principale:
  - gpt: gpt-5.5 (AZURE_DEPLOYMENT_GPT), Responses API, `web_search` NON forzato, user_location IT/Rome/Lazio,
    effort predefinito (medium, nessun parametro di reasoning); ricerca spenta = nessuno strumento.
  - gemini: gemini-3.5-flash, Google Search + retrieval_config.lat_lng = Colosseo (41.8902, 12.4922);
    ricerca spenta = nessuno strumento e nessuna location.
  - perplexity: Agent API, perplexity/sonar, `web_search` (search_context_size medium) con user_location
    IT/Lazio/Rome; ricerca spenta = nessuno strumento (cancello del ciclo 12, Fase 0.1). Nessuna istruzione di citare.
Ordine casuale per motore (seed 20261014; 3b: 20261015). Ogni chiamata è appesa al JSONL appena finisce:
una run interrotta riprende saltando i call_id già riusciti.
Tetti: gpt 60 $ (crediti Azure), gemini 20 $ (crediti Google), perplexity 5 $. Dopo 20 risposte si proietta
il costo sul totale; oltre il tetto ci si ferma.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import requests
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))
sys.path.insert(0, str(ROOT / "analysis"))

import adapter_azure  # noqa: E402
from cycle8_runner import estimate_cost  # noqa: E402
from thesis_env import require  # noqa: E402

PROMPTS = ROOT / "config" / "cycle12_prompts.csv"
NOISE = ROOT / "config" / "cycle12_noise.yaml"
PERSONAS = ROOT / "config" / "cycle11_personas.yaml"
RAW = ROOT / "data" / "raw"
SEED = {"test": 20261014, "3b": 20261015}
REPS = 5
CAPS = {"gpt": 60.0, "gemini": 20.0, "perplexity": 5.0}
GPT_LOC = {"type": "approximate", "country": "IT", "city": "Rome", "region": "Lazio"}
GEM_LATLNG = (41.8902, 12.4922)
GEMINI_MODEL = "gemini-3.5-flash"
PPLX_URL = "https://api.perplexity.ai/v1/agent"
PPLX_MODEL = "perplexity/sonar"
PPLX_LOC = {"country": "IT", "region": "Lazio", "city": "Rome"}
SMOKE_SYS = "Rispondi solo con la parola BANANA, senza nessun altro testo."



def _loads(line: str):
    """Una riga troncata (processo chiuso a metà scrittura nella sandbox) si salta."""
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return None

def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def rawfile(engine: str, part: str) -> Path:
    return RAW / (f"cycle12_{engine}.jsonl" if part == "test" else f"cycle12_3b_{engine}.jsonl")


def plan(part: str) -> list[dict]:
    prompts = list(csv.DictReader(PROMPTS.open()))
    personas = {p["settore"]: p["it"] for p in yaml.safe_load(PERSONAS.read_text())["personas"] if p["ruolo"] == "A"}
    items: list[dict] = []
    if part == "test":
        noise = yaml.safe_load(NOISE.read_text())["rumore"]
        for p in prompts:
            for level in ("vuoto", "rumore", "persona"):
                sp = None if level == "vuoto" else (noise[p["prompt_id"]]["testo"] if level == "rumore" else personas[p["sector"]])
                for search in (False, True):
                    for rep in range(1, REPS + 1):
                        items.append(dict(call_id=f"{p['prompt_id']}|{level}|{'on' if search else 'off'}|{rep}",
                                          sector=p["sector"], prompt_id=p["prompt_id"], ordine=int(p["ordine"]),
                                          sottotema=p["sottotema"], prompt=p["prompt"], level=level, system_prompt=sp,
                                          search=search, rep=rep, user_message=p["prompt"]))
    else:
        for p in prompts:
            for rep in range(1, REPS + 1):
                items.append(dict(call_id=f"{p['prompt_id']}|persona_utente|on|{rep}", sector=p["sector"],
                                  prompt_id=p["prompt_id"], ordine=int(p["ordine"]), sottotema=p["sottotema"],
                                  prompt=p["prompt"], level="persona_utente", system_prompt=None, search=True, rep=rep,
                                  user_message=f"{personas[p['sector']]} {p['prompt']}"))
    random.Random(SEED[part]).shuffle(items)
    return items


def retryable(err: str | None) -> bool:
    low = str(err or "").lower()
    return any(s in low for s in ("429", "rate", "503", "500", "502", "504", "unavailable", "overloaded",
                                  "resource_exhausted", "timeout", "timed out", "connection"))


# ----------------------------------------------------------------------------- engines

class GPT:
    name = "gpt"

    def __init__(self):
        self.deployment = require("AZURE_DEPLOYMENT_GPT")
        self.url = adapter_azure.responses_url(require("AZURE_OPENAI_ENDPOINT"))
        self.auth = {"api-key": require("AZURE_OPENAI_API_KEY")}

    def payload(self, it: dict) -> dict:
        p = adapter_azure.build_payload(self.deployment, it["user_message"], search=it["search"], tool_choice=None,
                                        effort=None, system_prompt=it["system_prompt"])
        if it["search"]:
            p["tools"][0]["user_location"] = dict(GPT_LOC)
        return p

    def once(self, it: dict) -> dict:
        body = self.payload(it)
        raw, err, lat, status = adapter_azure.call(self.url, self.auth, body)
        rec = {"request_body": body, "http_status": status, "error": err, "latency_s": round(lat, 3), "raw_response": raw}
        if raw and not err:
            p = adapter_azure.parse(raw)
            rec.update(p)
            rec["cited_urls"] = [c.get("uri") for c in p.get("grounding_chunks") or []]
            rec["consulted_urls"] = [c.get("url") for c in p.get("consulted_sources") or []]
            rec["cost_usd_est"] = estimate_cost("gpt-5.5", {**p, "searched": p.get("search_performed")})
            rec["billing"] = "crediti Azure"
        return rec


class Gemini:
    name = "gemini"

    def __init__(self):
        from google import genai
        from google.genai import types
        self.t = types
        self.client = genai.Client(api_key=require("GEMINI_API_KEY"), http_options=types.HttpOptions(timeout=180_000))

    def once(self, it: dict) -> dict:
        from pilot_runner_v2 import parse_grounding, response_to_dict
        t = self.t
        cfg: dict = {}
        sent: dict = {"model": GEMINI_MODEL, "tools": [], "tool_config": None, "system_instruction": it["system_prompt"]}
        if it["search"]:
            lat, lng = GEM_LATLNG
            cfg["tools"] = [t.Tool(google_search=t.GoogleSearch())]
            cfg["tool_config"] = t.ToolConfig(retrieval_config=t.RetrievalConfig(lat_lng=t.LatLng(latitude=lat, longitude=lng)))
            sent["tools"] = ["google_search"]
            sent["tool_config"] = {"lat_lng": {"latitude": lat, "longitude": lng}}
        if it["system_prompt"]:
            cfg["system_instruction"] = it["system_prompt"]
        t0 = time.monotonic()
        try:
            resp = self.client.models.generate_content(model=GEMINI_MODEL, contents=it["user_message"],
                                                       config=t.GenerateContentConfig(**cfg))
            err = None
        except Exception as e:  # noqa: BLE001
            resp, err = None, f"{type(e).__name__}: {e}"
        rec = {"request_body": sent, "error": err, "latency_s": round(time.monotonic() - t0, 3)}
        if resp is not None:
            queries, chunks, supports = parse_grounding(resp)
            raw = response_to_dict(resp)
            um = raw.get("usage_metadata") or {}
            tin = (um.get("prompt_token_count") or 0) + (um.get("tool_use_prompt_token_count") or 0)
            tout = (um.get("candidates_token_count") or 0) + (um.get("thoughts_token_count") or 0)
            p = {"response_text": getattr(resp, "text", None), "model_version": raw.get("model_version"),
                 "web_search_queries": queries, "model_queries": list(queries), "grounding_chunks": chunks,
                 "grounding_supports": supports, "search_performed": bool(queries or chunks),
                 "n_search_actions": len(queries), "input_tokens": tin,
                 "cached_input_tokens": um.get("cached_content_token_count") or 0, "output_tokens": tout,
                 "reasoning_tokens": um.get("thoughts_token_count"), "total_tokens": um.get("total_token_count")}
            rec.update(p)
            rec["cited_domains"] = [c.get("domain") or c.get("title") for c in chunks]
            rec["raw_response"] = raw
            rec["cost_usd_est"] = estimate_cost("gemini-3.5-flash", {**p, "searched": p["search_performed"]})
            rec["billing"] = "crediti Google"
        return rec


class Perplexity:
    name = "perplexity"

    def __init__(self):
        from cycle8c_runner import PerplexityAgentEngine
        self.parse = PerplexityAgentEngine.parse
        self.key = require("PERPLEXITY_API_KEY")

    def payload(self, it: dict) -> dict:
        body: dict = {"model": PPLX_MODEL, "input": it["user_message"]}
        if it["system_prompt"]:
            body["instructions"] = it["system_prompt"]
        if it["search"]:
            body["tools"] = [{"type": "web_search", "search_context_size": "medium", "user_location": dict(PPLX_LOC)}]
        return body

    def once(self, it: dict) -> dict:
        from common import normalize_domain
        body = self.payload(it)
        t0 = time.monotonic()
        raw, err, status = None, None, None
        try:
            r = requests.post(PPLX_URL, headers={"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"},
                              json=body, timeout=300)
            status = r.status_code
            if status != 200:
                err = f"HTTP {status}: {r.text[:2000]}"
            else:
                raw = r.json()
                if raw.get("status") not in (None, "completed"):
                    err = f"status={raw.get('status')}: {json.dumps(raw.get('error') or raw.get('incomplete_details'))[:1000]}"
        except Exception as e:  # noqa: BLE001
            err = f"{type(e).__name__}: {e}"
        rec = {"request_body": body, "http_status": status, "error": err, "latency_s": round(time.monotonic() - t0, 3),
               "raw_response": raw}
        if raw and not err:
            p = self.parse(raw)
            results = [x for o in raw.get("output") or [] if o.get("type") == "search_results" for x in o.get("results") or []]
            p["retrieved_results"] = [{"id": x.get("id"), "url": x.get("url"), "title": x.get("title"),
                                       "domain": normalize_domain(urlsplit(x.get("url") or "").netloc)} for x in results]
            rec.update(p)
            rec["cost_usd_est"] = (p.get("cost_perplexity") or {}).get("total_cost")
            rec["billing"] = "fuori dai crediti (Perplexity)"
        return rec


ENGINES = {"gpt": GPT, "gemini": Gemini, "perplexity": Perplexity}


EXP_S = {("gpt", True): 34, ("gpt", False): 14, ("gemini", True): 22, ("gemini", False): 12,
         ("perplexity", True): 12, ("perplexity", False): 8}   # durata attesa di una chiamata, per --deadline


def with_retries(eng, it: dict, single: bool = False) -> dict:
    waits = []
    base = 60 if eng.name == "gpt" else 20
    for attempt in range(5):
        rec = eng.once(it)
        if single or not rec.get("error") or not retryable(rec["error"]) or attempt == 4:
            break
        w = base * (attempt + 1)
        waits.append({"attempt": attempt + 1, "error": str(rec["error"])[:300], "wait_s": w})
        time.sleep(w)
    rec["retries"] = waits
    return rec


# ----------------------------------------------------------------------------- main

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", choices=tuple(ENGINES), required=True)
    ap.add_argument("--part", choices=("test", "3b"), default="test")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--smoke", action="store_true", help="una chiamata a ricerca spenta: il system prompt viene seguito?")
    ap.add_argument("--solo", choices=("on", "off"), default=None, help="solo le chiamate a ricerca accesa o spenta")
    ap.add_argument("--deadline", type=float, default=None,
                    help="secondi: non inizia una chiamata che non finirebbe entro la scadenza; nessuna attesa sui 429 "
                         "(la chiamata fallita si ripete al giro dopo). Per la sandbox, che chiude i processi a ogni comando.")
    a = ap.parse_args()
    if a.part == "3b" and a.engine != "perplexity":
        raise SystemExit("la parte 3b è solo per Perplexity")
    eng = ENGINES[a.engine]()

    if a.smoke:
        it = dict(call_id="smoke", user_message="Ciao, come stai?", system_prompt=SMOKE_SYS, search=False)
        rec = with_retries(eng, it)
        rec.update({"cycle": "12", "engine": a.engine, "call_id": "smoke",
                    "timestamp": datetime.now(timezone.utc).isoformat()})
        with (RAW / "cycle12_smoke.jsonl").open("a") as f:
            f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
        print(a.engine, "errore:", rec.get("error"), "| testo:", (rec.get("response_text") or "")[:200],
              "| costo:", rec.get("cost_usd_est"))
        return

    items = plan(a.part)
    meta = {"prompts_sha256": sha(PROMPTS), "personas_sha256": sha(PERSONAS),
            "noise_sha256": sha(NOISE) if a.part == "test" else None, "seed_order": SEED[a.part]}
    if a.dry_run:
        print(len(items), "chiamate;", meta)
        for it in items[:3]:
            print(json.dumps(eng.payload(it) if hasattr(eng, "payload") else it, ensure_ascii=False)[:600])
        return

    out = rawfile(a.engine, a.part)
    done, spent = set(), 0.0
    if out.exists():
        for line in out.open():
            r = _loads(line)
            if r is None:
                continue
            spent += r.get("cost_usd_est") or 0.0
            if not r.get("error"):
                done.add(r["call_id"])
    todo = [it for it in items if it["call_id"] not in done]
    if a.solo:
        todo = [it for it in todo if it["search"] == (a.solo == "on")]
    if a.deadline:   # sandbox: prima le chiamate lunghe (ricerca accesa), ordine casuale invariato dentro i due gruppi
        todo = [it for it in todo if it["search"]] + [it for it in todo if not it["search"]]
    cap = CAPS[a.engine]
    lock = threading.Lock()
    state = {"spent": spent, "ok": len(done), "err": 0, "stop": None, "n_new": 0}
    if a.deadline:
        print(f"{a.engine}/{a.part}: {len(done)}/{len(items)} fatte, spesa ${spent:.2f}", flush=True)
    else:
      print(f"{a.engine}/{a.part}: {len(items)} nel piano, {len(done)} già fatte, {len(todo)} da fare, "
          f"spesa già registrata ${spent:.3f}, tetto ${cap:.0f}", flush=True)

    t_start = time.monotonic()

    def work(it: dict) -> None:
        if state["stop"]:
            return
        if a.deadline and time.monotonic() - t_start + EXP_S[(a.engine, it["search"])] > a.deadline:
            return
        rec = with_retries(eng, it, single=bool(a.deadline))
        rec = {"cycle": "12", "part": a.part, "engine": a.engine, **it, **meta,
               "timestamp": datetime.now(timezone.utc).isoformat(), **rec}
        with lock:
            with out.open("a") as f:
                f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
            state["spent"] += rec.get("cost_usd_est") or 0.0
            if rec.get("error"):
                state["err"] += 1
                if a.deadline and "429" in str(rec["error"]):
                    state["stop"] = "429: quota di token al minuto esaurita, si riprende al giro dopo"
            else:
                state["ok"] += 1
                state["n_new"] += 1
            n = state["ok"]
            print(f"{n:3d} {it['call_id']:<40} err={str(rec.get('error'))[:80]} cerca={rec.get('search_performed')} "
                  f"costo={rec.get('cost_usd_est')} tot=${state['spent']:.3f}", flush=True)
            if state["n_new"] == 20:
                proj = state["spent"] / n * len(items)
                print(f"  proiezione su {len(items)} chiamate: ${proj:.2f}", flush=True)
                if proj > cap:
                    state["stop"] = f"proiezione ${proj:.2f} oltre il tetto ${cap:.0f}"
            if state["spent"] > cap:
                state["stop"] = f"spesa ${state['spent']:.2f} oltre il tetto ${cap:.0f}"
            tried = state["ok"] + state["err"] - len(done)
            if tried >= 30 and state["err"] / tried > 0.20:
                state["stop"] = f"errori {state['err']}/{tried} oltre il 20%"

    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = [ex.submit(work, it) for it in todo]
        for _ in as_completed(futs):
            pass
    print(f"FINE {a.engine}/{a.part}: {state['ok']} risposte, {state['err']} errori, spesa ${state['spent']:.3f}"
          + (f" — STOP: {state['stop']}" if state["stop"] else ""), flush=True)


if __name__ == "__main__":
    main()
