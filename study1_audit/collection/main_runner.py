#!/usr/bin/env python
"""Studio principale (L1 completo) — tutte le chiamate di GPT, Gemini e Perplexity.

Uso, dal terminale del Mac (non dalla sandbox, che chiude i processi):

    cd the project folder/
    .venv/bin/python pipeline/main_runner.py --prova                      # 2 chiamate per motore, in file a parte
    .venv/bin/python pipeline/main_runner.py --dry-run [--ramo-system-prompt]
    caffeinate -i nohup .venv/bin/python pipeline/main_runner.py [--ramo-system-prompt] > data/raw/main_run.log 2>&1 &

Disegno (deciso il 6/10): 80 prompt (config/main_study_prompts.csv) x livello di persona x ricerca spenta/accesa
x 10 ripetizioni, su GPT, Gemini e Perplexity, location Roma.
  - nessuna: messaggio utente = prompt;
  - A, B, C: messaggio utente = "{persona} {prompt}" (config/cycle11_template.md), nessun system prompt;
  - A_sistema (solo con --ramo-system-prompt, proposta del 13/10): system prompt = persona A, messaggio = prompt.
Impostazioni dei motori identiche al test del ciclo 12 (classi riusate da pipeline/cycle12_runner.py).

Ordine: casuale con seme 20261013, uguale per i tre motori; prima tutte le chiamate a ricerca accesa (servono
anche come pagine per la Parte 2), poi quelle a ricerca spenta. I tre motori girano in parallelo, ognuno con i
suoi worker. Ogni chiamata è appesa a data/raw/main_{motore}.jsonl appena finisce: se il programma si ferma,
rilanciandolo riprende saltando le chiamate già riuscite (quelle fallite si ripetono).
Un motore si ferma da solo se la spesa proiettata supera il suo tetto o se più del 20% delle chiamate fallisce;
gli altri continuano. Lo stato è in data/raw/main_stato.json, aggiornato ogni 25 chiamate.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))
sys.path.insert(0, str(ROOT / "analysis"))

import os  # noqa: E402

from cycle12_runner import ENGINES as _ENGINES, EXP_S, GEM_LATLNG, Gemini, _loads, estimate_cost, with_retries  # noqa: E402

PROMPTS = ROOT / "config" / "main_study_prompts.csv"
PERSONAS = ROOT / "config" / "cycle11_personas.yaml"
TEMPLATE = ROOT / "config" / "cycle11_template.md"
RAW = ROOT / "data" / "raw"
STATO = RAW / "main_stato.json"
SEED = 20261013
LIVELLI = ["nessuna", "A", "B", "C"]
WORKERS = {"gpt": 16, "gemini": 10, "perplexity": 4, "gemini_vertex": 10}
TETTO = {"gpt": 1350.0, "gemini": 260.0, "perplexity": None, "gemini_vertex": 320.0}  # dollari; None = nessun tetto
COSTO_ATTESO = {("gpt", True): 0.278, ("gpt", False): 0.025,          # medie del test del ciclo 12
                ("gemini", True): 0.0325, ("gemini", False): 0.0196,
                ("gemini_vertex", True): 0.0373, ("gemini_vertex", False): 0.0196,   # on: media dello studio, 14/10
                ("perplexity", True): 0.0046, ("perplexity", False): 0.0007}


class GeminiVertex(Gemini):
    """Gemini tramite Vertex AI (aggiunto il 14/10, dopo il blocco della Gemini API per il tetto di spesa del Tier 1).

    Stesse impostazioni della classe Gemini del ciclo 12 (ricerca Google, lat_lng del Colosseo, nessun altro
    parametro), ma il client è Vertex AI: credenziali predefinite dell'applicazione (gcloud auth
    application-default login), progetto e location da VERTEX_PROJECT / VERTEX_LOCATION in .env (predefiniti
    REDACTED / global). Modello fissato per nome: VERTEX_MODEL, predefinito gemini-3.6-flash, cioè la versione che la
    Gemini API ha servito per tutte le chiamate del ciclo 12 e dello studio principale chiedendo gemini-3.5-flash.
    """
    name = "gemini_vertex"

    def __init__(self):
        from google import genai
        from google.genai import types
        from thesis_env import load_env
        load_env()
        self.t = types
        self.project = os.environ.get("VERTEX_PROJECT", "YOUR_GCP_PROJECT")
        self.location = os.environ.get("VERTEX_LOCATION", "global")
        self.model = os.environ.get("VERTEX_MODEL", "gemini-3.6-flash")
        self.client = genai.Client(vertexai=True, project=self.project, location=self.location,
                                   http_options=types.HttpOptions(timeout=180_000))

    def once(self, it: dict) -> dict:
        from pilot_runner_v2 import parse_grounding, response_to_dict
        t = self.t
        cfg: dict = {}
        sent: dict = {"model": self.model, "endpoint": "vertex", "project": self.project, "location": self.location,
                      "tools": [], "tool_config": None, "system_instruction": it["system_prompt"]}
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
            resp = self.client.models.generate_content(model=self.model, contents=it["user_message"],
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
            rec["billing"] = "Vertex AI (Cloud Billing, crediti Google for Startups se applicati)"
        return rec


ENGINES = {**_ENGINES, "gemini_vertex": GeminiVertex}
EXP_S.update({("gemini_vertex", True): 22, ("gemini_vertex", False): 12})


def riuscita(r: dict) -> bool:
    """Una chiamata conta come fatta se non ha errori e ha un testo. Le risposte vuote (5 di Gemini con la ricerca il
    14/10: MALFORMED_FUNCTION_CALL o STOP senza testo) contano come fallite e si ripetono; la prima resta nel file."""
    return not r.get("error") and bool((r.get("response_text") or "").strip())


def motivo_vuota(rec: dict) -> str:
    try:
        fr = (rec.get("raw_response") or {}).get("candidates")[0].get("finish_reason")
    except Exception:  # noqa: BLE001
        fr = None
    return f"risposta vuota (finish_reason {fr})"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def commit() -> str | None:
    try:
        return subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"], capture_output=True,
                              text=True, timeout=10).stdout.strip() or None
    except Exception:  # noqa: BLE001
        return None


def piano(ripetizioni: int, ramo_sistema: bool) -> list[dict]:
    prompts = list(csv.DictReader(PROMPTS.open()))
    assert len(prompts) == 80, len(prompts)
    pers = {(p["settore"], p["ruolo"]): p["it"] for p in yaml.safe_load(PERSONAS.read_text())["personas"]}
    livelli = LIVELLI + (["A_sistema"] if ramo_sistema else [])
    items = []
    for p in prompts:
        for liv in livelli:
            if liv == "nessuna":
                um, sp = p["prompt"], None
            elif liv == "A_sistema":
                um, sp = p["prompt"], pers[(p["sector"], "A")]
            else:
                um, sp = f"{pers[(p['sector'], liv)]} {p['prompt']}", None
            for search in (True, False):
                for rep in range(1, ripetizioni + 1):
                    items.append(dict(call_id=f"{p['prompt_id']}|{liv}|{'on' if search else 'off'}|{rep}",
                                      sector=p["sector"], prompt_id=p["prompt_id"], ordine=int(p["ordine"]),
                                      sottotema=p["sottotema"], prompt=p["prompt"], level=liv, system_prompt=sp,
                                      search=search, rep=rep, user_message=um))
    random.Random(SEED).shuffle(items)
    return [it for it in items if it["search"]] + [it for it in items if not it["search"]]


def coppie(s: str | None, tipo=str) -> dict:
    out = {}
    for x in (s or "").split(","):
        if "=" in x:
            k, v = x.split("=", 1)
            out[k.strip()] = tipo(v)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--motori", default="gpt,gemini,perplexity",
                    help="gpt, gemini, perplexity; gemini_vertex = Gemini tramite Vertex AI (file main_gemini_vertex.jsonl)")
    ap.add_argument("--ripetizioni", type=int, default=10)
    ap.add_argument("--ramo-system-prompt", action="store_true", help="aggiunge il ramo A_sistema (+4.800 chiamate)")
    ap.add_argument("--workers", default=None, help="es. gpt=16,gemini=10,perplexity=4")
    ap.add_argument("--tetto", default=None, help="dollari per motore, es. gpt=1350,gemini=260 (Perplexity senza tetto)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--prova", action="store_true", help="una chiamata a ricerca accesa e una spenta per motore, "
                                                         "in data/raw/main_prova_{motore}.jsonl")
    ap.add_argument("--deadline", type=float, default=None, help="secondi; solo per la sandbox")
    a = ap.parse_args()
    motori = [m.strip() for m in a.motori.split(",") if m.strip()]
    workers = {**WORKERS, **coppie(a.workers, int)}
    tetto = {**TETTO, **coppie(a.tetto, float)}
    items = piano(a.ripetizioni, a.ramo_system_prompt)
    meta = {"study": "main", "prompts_sha256": sha(PROMPTS), "personas_sha256": sha(PERSONAS),
            "template_sha256": sha(TEMPLATE), "seed_order": SEED, "ripetizioni": a.ripetizioni,
            "ramo_system_prompt": a.ramo_system_prompt, "commit": commit()}
    per_motore = len(items)
    print(f"piano: {per_motore} chiamate per motore, {per_motore * len(motori)} in tutto "
          f"({len(LIVELLI) + a.ramo_system_prompt} livelli x 80 prompt x 2 x {a.ripetizioni})", flush=True)
    proiez = {m: sum(COSTO_ATTESO[(m, it['search'])] for it in items) for m in motori}
    print("costo atteso (medie del ciclo 12): " + ", ".join(f"{m} ${v:,.0f}" for m, v in proiez.items()), flush=True)
    if a.dry_run:
        for m in motori:
            eng = ENGINES[m]()
            for it in (items[0], items[-1]):
                body = eng.payload(it) if hasattr(eng, "payload") else {"system": it["system_prompt"], "user": it["user_message"]}
                print(m, it["call_id"], json.dumps(body, ensure_ascii=False)[:400], flush=True)
        return

    if a.prova:
        items = [next(it for it in items if it["search"]), next(it for it in items if not it["search"])]
    # un processo con un sottoinsieme diverso di motori scrive il suo stato a parte, per non sovrascrivere l'altro
    stato_file = STATO if set(motori) == {"gpt", "gemini", "perplexity"} else RAW / f"main_stato_{'_'.join(motori)}.json"
    stato: dict = {"avvio": datetime.now(timezone.utc).isoformat(), "motori": {}}
    lock_stato = threading.Lock()
    t0 = time.monotonic()

    def scrivi_stato():
        if a.prova:
            return
        with lock_stato:
            stato["aggiornato"] = datetime.now(timezone.utc).isoformat()
            stato_file.write_text(json.dumps(stato, ensure_ascii=False, indent=1))

    def gira(m: str) -> None:
        eng = ENGINES[m]()
        out = RAW / (f"main_prova_{m}.jsonl" if a.prova else f"main_{m}.jsonl")
        done, spent = set(), 0.0
        if out.exists():
            for line in out.open():
                r = _loads(line)
                if r is None:
                    continue
                spent += r.get("cost_usd_est") or 0.0
                if riuscita(r):
                    done.add(r["call_id"])
        todo = [it for it in items if it["call_id"] not in done]
        st = {"piano": len(items), "fatte": len(done), "da_fare": len(todo), "errori": 0, "spesa": round(spent, 2),
              "tetto": tetto.get(m), "stop": None}
        stato["motori"][m] = st
        print(f"[{m}] {len(done)}/{len(items)} già fatte, {len(todo)} da fare, spesa registrata ${spent:.2f}", flush=True)
        lock = threading.Lock()
        costi = {True: [], False: []}
        nuove = {"ok": 0, "err": 0}

        def work(it: dict) -> None:
            if st["stop"]:
                return
            if a.deadline and time.monotonic() - t0 + EXP_S[(m, it["search"])] > a.deadline:
                return
            rec = with_retries(eng, it, single=bool(a.deadline))
            if not rec.get("error") and not (rec.get("response_text") or "").strip():
                rec["error"] = motivo_vuota(rec)
            rec = {"engine": m, **it, **meta, "timestamp": datetime.now(timezone.utc).isoformat(), **rec}
            with lock:
                with out.open("a") as f:
                    f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
                c = rec.get("cost_usd_est") or 0.0
                st["spesa"] = round(st["spesa"] + c, 4)
                if rec.get("error"):
                    nuove["err"] += 1
                    st["errori"] += 1
                else:
                    nuove["ok"] += 1
                    st["fatte"] += 1
                    costi[it["search"]].append(c)
                st["da_fare"] -= 1
                tentate = nuove["ok"] + nuove["err"]
                if tentate >= 50 and nuove["err"] / tentate > 0.20:
                    st["stop"] = f"errori {nuove['err']}/{tentate} oltre il 20%"
                if tentate % 25 == 0 or a.prova:
                    resto = {s: sum(1 for x in todo if x["search"] == s) for s in (True, False)}
                    media = {s: (sum(costi[s]) / len(costi[s]) if len(costi[s]) >= 20 else COSTO_ATTESO[(m, s)])
                             for s in (True, False)}
                    fatte_per_tipo = {s: len(costi[s]) for s in (True, False)}
                    proj = st["spesa"] + sum(media[s] * max(resto[s] - fatte_per_tipo[s], 0) for s in (True, False))
                    st["spesa_proiettata"] = round(proj, 2)
                    eta = (time.monotonic() - t0) / max(tentate, 1) * st["da_fare"]
                    st["ore_al_termine"] = round(eta / 3600, 2)
                    print(f"[{m}] fatte {st['fatte']}/{st['piano']}  errori {st['errori']}  spesa ${st['spesa']:.2f}  "
                          f"proiezione ${proj:,.0f}  mancano ~{eta / 3600:.1f} h", flush=True)
                    if tetto.get(m) is not None and proj > tetto[m]:
                        st["stop"] = f"spesa proiettata ${proj:,.0f} oltre il tetto ${tetto[m]:,.0f}"
                    scrivi_stato()
                if a.prova:
                    print(f"[{m}] {it['call_id']}: errore={str(rec.get('error'))[:200]} cerca={rec.get('search_performed')} "
                          f"testo={(rec.get('response_text') or '')[:120]!r}", flush=True)

        with ThreadPoolExecutor(max_workers=workers[m]) as ex:
            for _ in as_completed([ex.submit(work, it) for it in todo]):
                pass
        st["fine"] = datetime.now(timezone.utc).isoformat()
        scrivi_stato()
        print(f"[{m}] FINE: {st['fatte']}/{st['piano']} riuscite, {st['errori']} errori, spesa ${st['spesa']:.2f}"
              + (f" — STOP: {st['stop']}" if st["stop"] else ""), flush=True)

    threads = [threading.Thread(target=gira, args=(m,), daemon=False) for m in motori]
    for t in threads:
        t.start()
    for t in threads:
        t.join()


if __name__ == "__main__":
    main()
