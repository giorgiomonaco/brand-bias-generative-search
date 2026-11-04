#!/usr/bin/env python
"""Cycle 8 — engine test: which engines give the data the full L1 needs.

One run = one row of the test (a model, a tool, a call form). Every row gets the same
10 calls, in one tight window:

  A  search    3 pilot prompts (2 nike.com, 1 sweethome3d.com) x 2 replications,
               search forced (`tool_choice: "required"`)                          6
  B  no search the first prompt x 2 replications, no tool at all                   2
  C  persona   the first prompt with the L1c-attr persona in the user message
               x 2 replications, search forced                                    2

Prompts are the first two nike.com and the first sweethome3d.com prompt in config
order, and the persona is the Sneaker Collector of cycles 6-7: stated rules, not a
sample, so the rows are comparable call by call.

Rows (see the internal notes page "Operativo ciclo 8"):

  R1  gpt-5.5, effort low        R2  gpt-5.5, effort medium
  R9  gpt-5.6-luna, medium       R8  gpt-4.1 (positive control of the detector)
  R3  DeepSeek-V3.2              R5  Llama-4-Maverick
  R7  gemini-2.5-flash           R7b gemini-3.8-flash (newest flash on the API)

Cycle 8b (--cycle 8b): R13 gemini-3.5-flash, R14 gemini-2.5-pro, R15 grok-4-20-non-reasoning
(R10 Grok 4.20 reasoning and R12 Llama-3.3 never ran as rows: see results/cycle8b/).

Stop rules wired in: estimated spend of the whole cycle over $20 aborts; a row with
more than half of its calls failed is closed; a tool refused by a model closes the row
with the refusal recorded verbatim (for DeepSeek this is also co-author's explicit rule:
record and stop, no alternatives). A refused `tool_choice` is retried once with
"auto" and the row keeps "auto", flagged "forzatura non supportata".

Output: one JSONL per row in data/raw/, raw response included, one record per call,
appended and fsync'd (checkpoint: completed (block, prompt, replication) skipped on
resume). The per-call measures (searched, query_equals_prompt, persona_in_query,
site_queries, cost) are computed here and recomputed by the analysis from the raw.

    .venv/bin/python pipeline/cycle8_runner.py --row R1
    .venv/bin/python pipeline/cycle8_runner.py --smoke            # one call per row
    .venv/bin/python pipeline/cycle8_runner.py --row R1 --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "analysis"))

import adapter_azure  # noqa: E402
from thesis_env import require  # noqa: E402  (keys come only from .env)
from common import l1a_chunk_domain, normalize_domain, normalize_query  # noqa: E402

CONFIG_PATH = ROOT / "config" / "pilot_config_v1.yaml"
RAW_DIR = ROOT / "data" / "raw"
PREFIX = "cycle8"                     # file prefix; "cycle8b" with --cycle 8b
SMOKE_PATH = RAW_DIR / "cycle8_smoke_runs.jsonl"
STATUS_PATH = RAW_DIR / "cycle8_row_status.jsonl"
BATCH = "cycle8"


def configure(cycle: str) -> None:
    """Point files, batch tag and spend counter at one cycle (8 or 8b)."""
    global PREFIX, SMOKE_PATH, STATUS_PATH, BATCH
    PREFIX = "cycle8" if cycle == "8" else f"cycle{cycle}"
    BATCH = PREFIX
    SMOKE_PATH = RAW_DIR / f"{PREFIX}_smoke_runs.jsonl"
    STATUS_PATH = RAW_DIR / f"{PREFIX}_row_status.jsonl"

SPEND_CAP_USD = 20.0
MAX_ATTEMPTS = 4
BASE_BACKOFF_SEC = 10.0
MAX_BACKOFF_SEC = 120.0

PERSONA_ROLE = "Sneaker Collector"
QUERY_EQ_THRESHOLD = 0.9
PERSONA_NGRAM = 5

# --------------------------------------------------------------------------- rows

# Versions are those deployed on 2026-09-26 (setup/azure_setup.sh), NoAutoUpgrade on
# the GPTs. They are written here because the Azure response echoes the DEPLOYMENT
# name in `model`, not the dated version (verified on the raw of the first probe).
ROWS: dict[str, dict[str, Any]] = {
    "R1": {"engine": "azure", "deployment_env": "AZURE_DEPLOYMENT_GPT", "effort": "low",
           "version": "2026-04-24", "sku": "GlobalStandard", "price": "gpt-5.5"},
    "R2": {"engine": "azure", "deployment_env": "AZURE_DEPLOYMENT_GPT", "effort": "medium",
           "version": "2026-04-24", "sku": "GlobalStandard", "price": "gpt-5.5"},
    "R9": {"engine": "azure", "deployment_env": "AZURE_DEPLOYMENT_GPT_CANDIDATE", "effort": "medium",
           "version": "2026-07-09", "sku": "DataZoneStandard", "price": "gpt-5.6-luna-dz"},
    "R8": {"engine": "azure", "deployment_env": "AZURE_DEPLOYMENT_GPT_CONTROL", "effort": None,
           "version": "2025-04-14", "sku": "GlobalStandard", "price": "gpt-4.1"},
    "R3": {"engine": "azure", "deployment_env": "AZURE_DEPLOYMENT_DEEPSEEK", "effort": None,
           "version": "1", "sku": "GlobalStandard", "price": "deepseek-v3.2",
           # co-author, 2026-09-26: if DeepSeek refuses Web Search or tool calling, record the
           # error verbatim and stop on DeepSeek — no fallback, no alternative.
           "no_fallback": True},
    "R5": {"engine": "azure", "deployment_env": "AZURE_DEPLOYMENT_LLAMA", "effort": None,
           "version": "1", "sku": "GlobalStandard", "price": "llama-4-maverick"},
    "R7": {"engine": "gemini", "model": "gemini-2.5-flash", "effort": None,
           "version": None, "sku": None, "price": "gemini-2.5-flash"},
    "R7b": {"engine": "gemini", "model": "gemini-3.8-flash", "effort": None,
            "version": None, "sku": None, "price": "gemini-3.8-flash"},
    # --- cycle 8b (internal notes "Operativo ciclo 8b — Motori aggiuntivi", 2026-09-27) ---
    # Grok: effort NOT set, so the model runs at its own default. The Microsoft docs say
    # "high", but the API echoes reasoning.effort = "medium" (cycle-8b diagnostic); the
    # echoed effort is recorded per call.
    "R10": {"engine": "azure", "deployment_env": "AZURE_DEPLOYMENT_GROK", "effort": None,
            "version": "1", "sku": "GlobalStandard", "price": "grok-4.20"},
    "R12": {"engine": "azure", "deployment_env": "AZURE_DEPLOYMENT_LLAMA33", "effort": None,
            "version": "9", "sku": "GlobalStandard", "price": "llama-3.3-70b"},
    "R13": {"engine": "gemini", "model": "gemini-3.5-flash", "effort": None,
            "version": None, "sku": None, "price": "gemini-3.5-flash"},
    "R14": {"engine": "gemini", "model": "gemini-2.5-pro", "effort": None,
            "version": None, "sku": None, "price": "gemini-2.5-pro"},
    # co-author, 2026-09-28: grok-4-20-non-reasoning is the candidate third engine (the only
    # Grok that accepted web_search in the cycle-8b diagnostic): a full row like the others.
    "R15": {"engine": "azure", "deployment_env": "AZURE_DEPLOYMENT_GROK_NR", "effort": None,
            "version": "1", "sku": "GlobalStandard", "price": "grok-4.20"},
}

# Which rows belong to which cycle (R11, DeepSeek with bing_grounding, never ran: the
# subscription refused the Grounding with Bing resource, SkuNotEligible).
CYCLE_ROWS = {"8": ["R1", "R2", "R9", "R8", "R3", "R5", "R7", "R7b"],
              "8b": ["R10", "R12", "R13", "R14", "R15"]}

# --------------------------------------------------------------------------- prices

# USD list prices, consulted 2026-09-26. Azure: Retail Prices API, eastus2, standard
# short-context meters (Global unless the deployment is DataZone). Web Search on Azure
# is billed as "MS Bing Services / Grounding with Bing / Search Transactions",
# $14 per 1,000 (the ~12 EUR per 1,000 seen on the REDACTED MVP bill). Gemini: ai.google.dev
# paid tier, free allowances ignored (conservative).
PRICES: dict[str, dict[str, float | str]] = {
    "gpt-5.5": {"in": 5.00, "cached_in": 0.50, "out": 30.00, "search": 0.014,
                "source": "prices.azure.com 5.5 ShortCo inp/cd inp/opt Gl; Bing Search Transactions $14/1K"},
    "gpt-5.6-luna-dz": {"in": 0.22, "cached_in": 0.022, "out": 1.32, "search": 0.014,
                        "source": "prices.azure.com 5.6 luna ShortCo Inp/Cd Inp/Opt Std DZ; Bing $14/1K"},
    "gpt-4.1": {"in": 2.00, "cached_in": 0.50, "out": 8.00, "search": 0.014,
                "source": "prices.azure.com gpt 4.1 Inp/cached Inp/Outp glbl; Bing $14/1K"},
    "deepseek-v3.2": {"in": 0.58, "cached_in": 0.58, "out": 1.68, "search": 0.014,
                      "source": "prices.azure.com Azure Deepseek Models V3.2 Inp/Outp glbl; Bing $14/1K"},
    "llama-4-maverick": {"in": 0.25, "cached_in": 0.25, "out": 1.00, "search": 0.014,
                         "source": "prices.azure.com Llama 4 Maverick 17B Inp/Outp glbl; Bing $14/1K"},
    "gemini-2.5-flash": {"in": 0.30, "cached_in": 0.30, "out": 2.50, "grounded_prompt": 0.035,
                         "source": "ai.google.dev paid tier: $0.30/$2.50 per 1M; $35/1K grounded prompts"},
    "gemini-3.8-flash": {"in": 0.75, "cached_in": 0.75, "out": 3.75, "search": 0.014,
                         "source": "ai.google.dev paid tier (to 2026-12-31): $0.75/$3.75 per 1M; $14/1K search requests"},
    # cycle 8b, consulted 2026-09-27 (same sources)
    "grok-4.20": {"in": 1.25, "cached_in": 1.25, "out": 2.50, "search": 0.014,
                  "source": "prices.azure.com Azure Grok Models Grok 4.2 Inp/Outp glbl; Bing $14/1K"},
    "llama-3.3-70b": {"in": 0.71, "cached_in": 0.71, "out": 0.71, "search": 0.014,
                      "source": "prices.azure.com Azure Llama Models Llama 3.3 70B Inp/Outp glbl; Bing $14/1K"},
    "gemini-3.5-flash": {"in": 1.50, "cached_in": 1.50, "out": 9.00, "search": 0.014,
                         "source": "ai.google.dev paid tier: $1.50/$9.00 per 1M; $14/1K search requests"},
    "gemini-2.5-pro": {"in": 1.25, "cached_in": 1.25, "out": 10.00, "grounded_prompt": 0.035,
                       "source": "ai.google.dev paid tier (<=200k): $1.25/$10.00 per 1M; $35/1K grounded prompts"},
    # Grok models of the cycle-8b diagnostic (prices.azure.com, Azure Grok Models, Glbl meters)
    "grok-4.1-fast": {"in": 0.20, "cached_in": 0.20, "out": 0.50, "search": 0.014,
                      "source": "prices.azure.com Grok 4.1 Inp/Outp Glbl; Bing $14/1K"},
    "grok-4.3": {"in": 1.25, "cached_in": 1.25, "out": 2.50, "search": 0.014,
                 "source": "prices.azure.com 4.3 Inp/Outp Glbl; Bing $14/1K"},
    "grok-4.6": {"in": 2.00, "cached_in": 2.00, "out": 6.00, "search": 0.014,
                 "source": "prices.azure.com 4.6 Inp/Outp Glbl; Bing $14/1K"},
}


def estimate_cost(price_key: str, rec: dict[str, Any]) -> float | None:
    p = PRICES[price_key]
    tin = rec.get("input_tokens")
    tout = rec.get("output_tokens")
    if tin is None and tout is None:
        return None
    tin, tout = tin or 0, tout or 0
    cached = rec.get("cached_input_tokens") or 0
    cost = (tin - cached) / 1e6 * p["in"] + cached / 1e6 * p["cached_in"] + tout / 1e6 * p["out"]
    if "grounded_prompt" in p:
        cost += p["grounded_prompt"] if rec.get("searched") else 0.0
    else:
        n = rec.get("n_search_requests_billed")
        if n is None:
            n = rec.get("n_search_actions") or len(rec.get("web_search_queries") or [])
        cost += n * p["search"]
    return round(cost, 6)


# --------------------------------------------------------------------------- measures

_SITE_RE = re.compile(r"\bsite:\s*([^\s)\"']+)", re.I)


def query_similarity(queries: list[str], message: str) -> float | None:
    """Highest SequenceMatcher ratio between a query and the user message (normalised)."""
    m = normalize_query(message)
    scores = [SequenceMatcher(None, normalize_query(q), m).ratio() for q in queries if q]
    return max(scores) if scores else None


def persona_in_query(queries: list[str], persona_text: str | None, n: int = PERSONA_NGRAM) -> bool | None:
    """True if a query contains `n` consecutive words of the persona text."""
    if not persona_text or not queries:
        return None
    words = normalize_query(persona_text).split()
    grams = {" ".join(words[i:i + n]) for i in range(len(words) - n + 1)}
    for q in queries:
        qw = normalize_query(q).split()
        if any(" ".join(qw[i:i + n]) in grams for i in range(len(qw) - n + 1)):
            return True
    return False


def site_queries(queries: list[str]) -> list[dict[str, str]]:
    out = []
    for q in queries:
        for m in _SITE_RE.finditer(q or ""):
            out.append({"query": q, "domain": normalize_domain(m.group(1))})
    return out


def add_measures(rec: dict[str, Any]) -> None:
    """Per-call measures, from fields already in the record (recomputable offline).

    The detector of the internal notes page (SequenceMatcher >= 0.9 on normalised strings, 5
    consecutive persona words) runs on BOTH query levels. The primary one is the
    model's own query (`model_queries`, Azure `action.query`): "is the user message
    forwarded as it is?" is a question about what the model hands to the tool. The
    executed level (`web_search_queries`) says what actually reached the search engine.
    On Gemini there is one level: the model writes the executed queries itself.
    """
    msg, persona = rec["sent_prompt_text"], rec.get("persona_text")
    mq = rec.get("model_queries") or []
    eq = rec.get("web_search_queries") or []
    s_m, s_e = query_similarity(mq, msg), query_similarity(eq, msg)
    rec["max_query_similarity"] = None if s_m is None else round(s_m, 4)
    rec["query_equals_prompt"] = None if s_m is None else s_m >= QUERY_EQ_THRESHOLD
    rec["max_exec_query_similarity"] = None if s_e is None else round(s_e, 4)
    rec["query_equals_prompt_exec"] = None if s_e is None else s_e >= QUERY_EQ_THRESHOLD
    rec["persona_in_query"] = persona_in_query(mq, persona)
    rec["persona_in_exec_query"] = persona_in_query(eq, persona)
    rec["site_queries"] = site_queries(eq)
    rec["site_queries_model"] = site_queries(mq)
    rec["tool_choice_not_honored"] = (rec.get("tool_choice_sent") == "required"
                                      and rec.get("error") is None and not rec.get("searched"))
    rec["no_grounding"] = not rec.get("grounding_chunks")
    rec["arm"] = f"c8_{rec['row']}_{rec['block']}"
    rec["channel"] = "L1c" if rec["block"] == "C" else "control"
    rec["persona_slot"] = "query" if rec["block"] == "C" else "none"
    rec["cited_domains"] = sorted({l1a_chunk_domain(c) for c in rec.get("grounding_chunks") or []} - {""})
    rec["consulted_domains"] = sorted({normalize_domain(s.get("url")) for s in
                                       rec.get("consulted_sources") or []} - {""})


# --------------------------------------------------------------------------- record

@dataclass
class Record:
    row: str
    block: str                 # A | B | C
    engine: str                # azure | gemini
    tool: str | None           # web_search | google_search | None
    form: str | None           # form1_resource_key | form2_project_entra | gemini_api
    deployment: str | None
    model: str
    model_version: str | None  # pinned version (Azure) or response model_version (Gemini)
    sku: str | None
    effort: str | None
    tool_choice_sent: str | None
    batch: str
    cell_id: str
    domain: str
    generic_prompt_id: str
    generic_prompt_text: str
    persona_role: str | None
    persona_text: str | None
    replication: int
    timestamp: str
    sent_prompt_text: str
    sent_system_prompt: str | None = None
    # response
    http_status: int | None = None
    error: str | None = None
    attempts: int = 0
    attempt_errors: list[dict[str, Any]] = field(default_factory=list)
    tool_choice_fallback: bool = False     # "required" refused, re-sent with "auto"
    latency_s: float | None = None
    response_text: str | None = None
    preamble_text: str | None = None           # pre-search message (DeepSeek, Llama)
    n_output_messages: int | None = None
    model_version_response: str | None = None
    web_search_queries: list[str] = field(default_factory=list)   # executed queries
    model_queries: list[str] = field(default_factory=list)        # the model's own
    n_model_query_in_executed: int | None = None
    grounding_chunks: list[dict[str, Any]] = field(default_factory=list)
    grounding_supports: list[dict[str, Any]] = field(default_factory=list)
    consulted_sources: list[dict[str, Any]] = field(default_factory=list)
    opened_pages: list[str] = field(default_factory=list)
    searched: bool | None = None
    queries_available: bool | None = None
    consulted_available: bool | None = None
    n_search_calls: int | None = None
    n_search_actions: int | None = None
    search_action_types: list[str] = field(default_factory=list)
    n_search_requests_billed: int | None = None
    billed_field_path: str | None = None
    input_tokens: int | None = None
    cached_input_tokens: int | None = None
    output_tokens: int | None = None
    reasoning_tokens: int | None = None
    total_tokens: int | None = None
    reasoning_effort_echo: str | None = None
    tool_choice_echo: Any = None
    output_item_types: list[str] = field(default_factory=list)
    tool_choice_not_honored: bool | None = None  # "required" echoed, yet no search
    no_grounding: bool | None = None            # pilot field: no cited source
    # pilot-compatible provenance (common.* helpers expect them)
    arm: str | None = None                      # c8_<row>_<block>
    channel: str | None = None                  # control | L1c
    persona_slot: str | None = None             # none | query
    persona_id: str | None = None
    cost_usd_est: float | None = None
    price_source: str | None = None
    raw_response: dict[str, Any] | None = None


# --------------------------------------------------------------------------- plan

def pick_cells(cfg: dict) -> tuple[list[dict], dict]:
    """The 3 prompts of block A (control cells) and the persona cell of block C."""
    controls = [c for c in cfg["cells"] if c.get("system_prompt") is None]
    nike = [c for c in controls if c["domain"] == "nike.com"][:2]
    sh3d = [c for c in controls if c["domain"] == "sweethome3d.com"][:1]
    prompts = nike + sh3d
    first = prompts[0]
    persona = [c for c in cfg["cells"] if c["generic_prompt_id"] == first["generic_prompt_id"]
               and c.get("persona_role") == PERSONA_ROLE]
    if len(prompts) != 3 or len(persona) != 1:
        sys.exit(f"ERRORE: attesi 3 prompt e 1 cella persona, trovati {len(prompts)} e {len(persona)}")
    return prompts, persona[0]


def build_plan(cfg: dict) -> list[dict[str, Any]]:
    from pilot_runner_v2 import attr_prefix
    prompts, pcell = pick_cells(cfg)
    persona_text = attr_prefix(pcell["system_prompt"])
    plan: list[dict[str, Any]] = []
    for rep in (1, 2):
        for c in prompts:
            plan.append({"block": "A", "cell": c, "replication": rep, "search": True,
                         "sent_text": c["generic_prompt_text"], "persona_text": None,
                         "persona_role": None})
        plan.append({"block": "B", "cell": prompts[0], "replication": rep, "search": False,
                     "sent_text": prompts[0]["generic_prompt_text"], "persona_text": None,
                     "persona_role": None})
        plan.append({"block": "C", "cell": pcell, "replication": rep, "search": True,
                     "sent_text": f"{persona_text} {pcell['generic_prompt_text']}",
                     "persona_text": persona_text, "persona_role": PERSONA_ROLE})
    return plan


def slot_key(item: dict[str, Any]) -> tuple[str, str, int]:
    return (item["block"], item["cell"]["cell_id"], int(item["replication"]))


# --------------------------------------------------------------------------- io

def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def row_path(row: str) -> Path:
    return RAW_DIR / f"{PREFIX}_{row}_runs.jsonl"


def spent_so_far() -> float:
    """Estimated spend of the batch rows and the smoke test (the stop-rule counter).

    The out-of-matrix probes are priced separately by the analysis (a few cents)."""
    total = 0.0
    for p in RAW_DIR.glob(f"{PREFIX}_*_runs.jsonl"):
        if p.name == f"{PREFIX}_probes_runs.jsonl":
            continue
        total += sum(r.get("cost_usd_est") or 0.0 for r in read_jsonl(p))
    return total


def append(path: Path, rec: dict[str, Any]) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


# --------------------------------------------------------------------------- engines

class AzureEngine:
    def __init__(self, row: str, spec: dict[str, Any], form: str):
        self.deployment = require(spec["deployment_env"])
        self.form = form
        if form == "form1_resource_key":
            self.url = adapter_azure.responses_url(require("AZURE_OPENAI_ENDPOINT"))
            self.auth = {"api-key": require("AZURE_OPENAI_API_KEY")}
        elif form == "form2_project_entra":
            self.url = adapter_azure.responses_url(require("FOUNDRY_PROJECT_ENDPOINT"))
            self.auth = {"Authorization": f"Bearer {adapter_azure.entra_token()}"}
        else:
            raise SystemExit(f"forma non gestita: {form}")
        self.effort = spec["effort"]
        self.tool_choice = "required"

    def run(self, item: dict[str, Any]) -> tuple[dict | None, str | None, float, int | None, dict]:
        payload = adapter_azure.build_payload(
            self.deployment, item["sent_text"], search=item["search"],
            tool_choice=self.tool_choice if item["search"] else None, effort=self.effort)
        raw, err, lat, status = adapter_azure.call(self.url, self.auth, payload)
        return raw, err, lat, status, payload

    def parse(self, raw: dict) -> dict[str, Any]:
        p = adapter_azure.parse(raw)
        p["model_version_response"] = p.pop("model_version")
        p["searched"] = p.pop("search_performed")
        return {k: v for k, v in p.items() if k in Record.__dataclass_fields__}


class GeminiEngine:
    """The pilot's call and parse functions, unchanged, for the search blocks; block B drops
    the tool. Deliberate deviation from the pilot RUNNER: no retry when grounding is
    missing, because here whether Gemini grounds is the measurement, not a failure."""

    def __init__(self, spec: dict[str, Any]):
        from google import genai
        self.genai = genai
        # Timeout on the client (cycle 8b: one gemini-2.5-pro call hung >12 min with none).
        # The pilot's call/parse functions stay unchanged; only the client carries it.
        from google.genai import types as _types
        self.client = genai.Client(api_key=require("GEMINI_API_KEY"),
                                   http_options=_types.HttpOptions(timeout=180_000))
        self.model = spec["model"]
        self.form = "gemini_api"

    def run(self, item: dict[str, Any]) -> tuple[Any, str | None, float, int | None, dict]:
        from google.genai import types
        from pilot_runner_v2 import call_gemini
        t0 = time.monotonic()
        if item["search"]:
            resp, err = call_gemini(self.client, self.model, item["sent_text"], None)
            payload = {"model": self.model, "tools": ["google_search"]}
        else:
            try:
                resp = self.client.models.generate_content(
                    model=self.model, contents=item["sent_text"],
                    config=types.GenerateContentConfig())
                err = None
            except Exception as e:  # noqa: BLE001
                resp, err = None, f"{type(e).__name__}: {e}"
            payload = {"model": self.model, "tools": []}
        return resp, err, time.monotonic() - t0, (200 if err is None else None), payload

    def parse(self, resp: Any) -> dict[str, Any]:
        from pilot_runner_v2 import parse_grounding, response_to_dict
        queries, chunks, supports = parse_grounding(resp)
        raw = response_to_dict(resp)
        um = raw.get("usage_metadata") or {}
        tin = (um.get("prompt_token_count") or 0) + (um.get("tool_use_prompt_token_count") or 0)
        tout = (um.get("candidates_token_count") or 0) + (um.get("thoughts_token_count") or 0)
        return {
            "response_text": getattr(resp, "text", None),
            "model_version_response": raw.get("model_version"),
            "web_search_queries": queries,
            "model_queries": list(queries),      # one level on Gemini: the model writes them
            "grounding_chunks": chunks,
            "grounding_supports": supports,
            "searched": bool(queries or chunks),
            "queries_available": bool(queries),
            "consulted_available": False,
            "n_search_actions": len(queries),
            "input_tokens": tin,
            "cached_input_tokens": um.get("cached_content_token_count") or 0,
            "output_tokens": tout,
            "reasoning_tokens": um.get("thoughts_token_count"),
            "total_tokens": um.get("total_token_count"),
            "raw_response": raw,
        }


# --------------------------------------------------------------------------- run

def gemini_retryable(err: str) -> bool:
    from pilot_runner_v2 import is_retryable
    return is_retryable(err)


def is_tool_refusal(err: str | None) -> bool:
    """A non-retryable 4xx on a search call: the tool (or the model) is refused."""
    return bool(err) and err.startswith("HTTP 4") and not err.startswith("HTTP 429")


def run_row(row: str, plan: list[dict[str, Any]], out_path: Path, form: str,
            sleep_s: float, keep_raw: bool = True) -> dict[str, Any]:
    spec = ROWS[row]
    engine = GeminiEngine(spec) if spec["engine"] == "gemini" else AzureEngine(row, spec, form)
    model = spec.get("model") or engine.deployment
    done = {(r["block"], r["cell_id"], int(r["replication"])) for r in read_jsonl(out_path)
            if r.get("error") is None and r.get("row") == row}
    todo = [it for it in plan if slot_key(it) not in done]
    print(f"[{row}] {model} ({engine.form}) — {len(plan)} pianificate, {len(done)} fatte, "
          f"{len(todo)} da eseguire -> {out_path.name}", flush=True)

    n_done = n_err = 0
    closed: str | None = None
    for i, item in enumerate(todo, 1):
        spent = spent_so_far()
        if spent > SPEND_CAP_USD:
            closed = f"STOP: spesa stimata del ciclo ${spent:.2f} oltre ${SPEND_CAP_USD:.0f}"
            print(closed, flush=True)
            break
        cell = item["cell"]
        rec = Record(
            row=row, block=item["block"], engine=spec["engine"],
            tool=(("google_search" if spec["engine"] == "gemini" else "web_search")
                  if item["search"] else None),
            form=engine.form, deployment=None if spec["engine"] == "gemini" else engine.deployment,
            model=model, model_version=spec["version"], sku=spec["sku"], effort=spec["effort"],
            tool_choice_sent=(engine.tool_choice if (item["search"] and spec["engine"] == "azure")
                              else None),
            batch=BATCH, cell_id=cell["cell_id"], domain=cell["domain"],
            generic_prompt_id=cell["generic_prompt_id"],
            generic_prompt_text=cell["generic_prompt_text"],
            persona_role=item["persona_role"], persona_text=item["persona_text"],
            persona_id=cell.get("persona_id") if item["block"] == "C" else None,
            replication=item["replication"], timestamp=datetime.now(timezone.utc).isoformat(),
            sent_prompt_text=item["sent_text"],
        )
        raw = err = None
        lat = 0.0
        status = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            rec.attempts = attempt
            raw, err, lat, status, payload = engine.run(item)
            if err is None:
                break
            rec.attempt_errors.append({"attempt": attempt, "error": err, "http_status": status,
                                       "seconds": round(lat, 1), "tool_choice": payload.get("tool_choice"),
                                       "at": datetime.now(timezone.utc).isoformat()})
            if (spec["engine"] == "azure" and item["search"] and engine.tool_choice == "required"
                    and not spec.get("no_fallback") and adapter_azure.tool_choice_refused(err)):
                print(f"  [{i}] tool_choice=required rifiutato: riprovo con auto — {err[:160]}", flush=True)
                engine.tool_choice = "auto"
                rec.tool_choice_fallback = True
                rec.tool_choice_sent = "auto"
                continue
            retryable = (adapter_azure.is_retryable(err) if spec["engine"] == "azure"
                         else gemini_retryable(err))
            if not retryable or attempt == MAX_ATTEMPTS:
                break
            wait = min(BASE_BACKOFF_SEC * 2 ** (attempt - 1), MAX_BACKOFF_SEC) * (0.5 + random.random())
            print(f"  [{i}] retry {attempt} fra {wait:.0f}s — {err[:140]}", flush=True)
            time.sleep(wait)

        rec.http_status, rec.error, rec.latency_s = status, err, round(lat, 3)
        if err is None and raw is not None:
            parsed = engine.parse(raw)
            if spec["engine"] == "gemini":
                rec.model_version = parsed.get("model_version_response")
                raw_dict = parsed.pop("raw_response")
            else:
                raw_dict = raw
            for k, v in parsed.items():
                setattr(rec, k, v)
            if keep_raw:
                rec.raw_response = raw_dict
        elif isinstance(raw, dict) and keep_raw:
            rec.raw_response = raw          # failed/incomplete body with status 200

        d = asdict(rec)
        add_measures(d)
        d["cost_usd_est"] = estimate_cost(spec["price"], d) if err is None else None
        d["price_source"] = PRICES[spec["price"]]["source"]
        append(out_path, d)

        n_done += 1
        n_err += err is not None
        if err:
            print(f"  [{i}/{len(todo)}] ERR {item['block']} r{item['replication']} "
                  f"{cell['domain']:15} — {err[:300]}", flush=True)
        else:
            print(f"  [{i}/{len(todo)}] {item['block']} r{item['replication']} {cell['domain']:15} "
                  f"q={len(d['web_search_queries']):2} cit={len(d['cited_domains']):2} "
                  f"src={len(d.get('consulted_sources') or []):3} "
                  f"qeq={d['max_query_similarity']} ${d['cost_usd_est']} {lat:5.1f}s", flush=True)

        if err and item["search"] and is_tool_refusal(err):
            closed = f"STOP riga: strumento/forma rifiutati — {err[:2000]}"
            print(closed, flush=True)
            break
        if n_err > 5 or (n_done >= 4 and n_err / n_done > 0.5):
            closed = f"STOP riga: {n_err}/{n_done} errori (oltre il 50%)"
            print(closed, flush=True)
            break
        if i < len(todo):
            time.sleep(sleep_s)

    append(STATUS_PATH, {"row": row, "file": out_path.name, "at": datetime.now(timezone.utc).isoformat(),
                         "calls": n_done, "errors": n_err, "closed": closed})
    print(f"[{row}] fine: {n_done} chiamate, {n_err} errori, spesa ciclo ~${spent_so_far():.2f}"
          + (f" — {closed[:200]}" if closed else ""), flush=True)
    return {"row": row, "calls": n_done, "errors": n_err, "closed": closed}


_PERSONA_ID: dict[str, str | None] = {}


def _persona_id(cell_id: str) -> str | None:
    if not _PERSONA_ID:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            _PERSONA_ID.update({c["cell_id"]: c.get("persona_id") for c in yaml.safe_load(f)["cells"]})
    return _PERSONA_ID.get(cell_id)


def reparse_record(d: dict[str, Any]) -> dict[str, Any]:
    """Re-derive parsed fields and measures from the stored raw (Azure), measures only (Gemini)."""
    if d.get("block") == "C" and not d.get("persona_id"):
        d["persona_id"] = _persona_id(d["cell_id"])
    if d.get("error") is None and d.get("engine") == "azure" and d.get("raw_response"):
        p = adapter_azure.parse(d["raw_response"])
        p["model_version_response"] = p.pop("model_version")
        p["searched"] = p.pop("search_performed")
        d.update({k: v for k, v in p.items() if k in Record.__dataclass_fields__})
    elif d.get("engine") == "gemini":
        d["model_queries"] = list(d.get("web_search_queries") or [])
    if d.get("error") is None:
        add_measures(d)
        d["cost_usd_est"] = estimate_cost(ROWS[d["row"]]["price"], d)
    return d


def reparse_file(path: Path) -> int:
    recs = [reparse_record(r) for r in read_jsonl(path)]
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    tmp.replace(path)
    return len(recs)


def main() -> None:
    ap = argparse.ArgumentParser(description="Cycle 8 — engine test, one row per run")
    ap.add_argument("--reparse", default=None, help="re-derive parsed fields and measures of a JSONL from its raw")
    ap.add_argument("--cycle", default="8", choices=sorted(CYCLE_ROWS), help="8 (default) or 8b")
    ap.add_argument("--row", choices=sorted(ROWS))
    ap.add_argument("--smoke", action="store_true", help="one block-A call per row, to <prefix>_smoke_runs.jsonl")
    ap.add_argument("--rows", default=None, help="comma-separated rows for --smoke (default: all)")
    ap.add_argument("--form", default="form1_resource_key",
                    choices=("form1_resource_key", "form2_project_entra"))
    ap.add_argument("--sleep", type=float, default=1.0)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    configure(args.cycle)
    if args.row and args.row not in CYCLE_ROWS[args.cycle]:
        ap.error(f"la riga {args.row} non appartiene al ciclo {args.cycle}")
    if args.rows and any(r not in CYCLE_ROWS[args.cycle] for r in args.rows.split(",")):
        ap.error(f"--rows contiene righe fuori dal ciclo {args.cycle}: {args.rows}")

    if args.reparse:
        n = reparse_file(Path(args.reparse))
        print(f"riletti {n} record da {args.reparse}")
        return

    with open(CONFIG_PATH, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    plan = build_plan(cfg)

    if args.dry_run:
        for it in plan:
            print(f"{it['block']} r{it['replication']} {it['cell']['domain']:15} "
                  f"search={it['search']!s:5} | {it['sent_text'][:160]}")
        print(f"{len(plan)} chiamate per riga")
        return

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    if args.smoke:
        rows = args.rows.split(",") if args.rows else list(CYCLE_ROWS[args.cycle])
        first = plan[0]
        for row in rows:
            smoke_item = {**first, "block": "A"}
            # The smoke file holds one slot per row; the row tag keeps them apart.
            done_rows = {r["row"] for r in read_jsonl(SMOKE_PATH) if r.get("error") is None}
            if row in done_rows:
                print(f"[{row}] smoke già fatto")
                continue
            run_row(row, [smoke_item], SMOKE_PATH, args.form, 0)
        return

    if not args.row:
        ap.error("--row o --smoke")
    res = run_row(args.row, plan, row_path(args.row), args.form, args.sleep)
    sys.exit(1 if res["closed"] or res["errors"] else 0)


if __name__ == "__main__":
    main()
