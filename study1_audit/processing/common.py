"""Shared helpers for the Pilot L1 analyses (L1a fresh run + L1b historical extraction).

Raw run outputs live under ``data/raw/``; the frozen experimental design lives in
``config/pilot_config_v1.yaml``. Both are local copies inside this repository —
nothing here reads from outside ``the project folder/`` and nothing calls any external API.
"""

from __future__ import annotations

import csv
import itertools
import json
import math
import random
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.parse import urlparse

import tldextract
import yaml

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW = DATA / "raw"
CONFIG = ROOT / "config"
RESULTS = ROOT / "results"
L1A_PATH = RAW / "pilot_v1_runs.jsonl"
L1B_PATH = RAW / "l1b_analyses.jsonl"
CONFIG_PATH = CONFIG / "pilot_config_v1.yaml"

DOMAINS = ("nike.com", "sweethome3d.com")
CONTROL = "control"

# Textual brand mention (case-insensitive). "Sweet Home 3D" is written in many ways.
TARGET_TEXT_REGEX = {
    "nike.com": re.compile(r"\bnike\b", re.I),
    "sweethome3d.com": re.compile(r"sweet\s*home\s*3\s*d", re.I),
}

# Gemini grounding chunks carry a Vertex redirect as `uri`; the real site is in `title`.
REDIRECT_HOSTS = {"vertexaisearch.cloud.google.com"}
_DOMAIN_RE = re.compile(r"^[a-z0-9.-]+\.[a-z]{2,}$")
_PUNCT_RE = re.compile(r"[^\w\s]")

# Offline extractor: bundled public-suffix snapshot, no network, no cache writes.
_extract = tldextract.TLDExtract(suffix_list_urls=(), cache_dir=None)

NAN = float("nan")


# ----------------------------------------------------------------------------- normalisation

def normalize_domain(value: str | None) -> str:
    """`www.nike.com` -> `nike.com`, `https://m.reddit.com/r/x` -> `reddit.com`."""
    s = (value or "").strip().lower()
    if not s:
        return ""
    if "://" in s:
        s = urlparse(s).netloc
    s = s.split("/")[0].split("@")[-1].split(":")[0].strip(".")
    ext = _extract(s)
    if ext.domain and ext.suffix:
        return f"{ext.domain}.{ext.suffix}"
    return s


def l1a_chunk_domain(chunk: dict[str, Any]) -> str:
    title = (chunk.get("title") or "").strip().lower()
    if _DOMAIN_RE.match(title):
        return normalize_domain(title)
    host = urlparse(chunk.get("uri") or "").netloc.lower()
    if host and host not in REDIRECT_HOSTS:
        return normalize_domain(host)
    return normalize_domain(title)


def l1b_source_domain(source: dict[str, Any]) -> str:
    raw = source.get("domain") or urlparse(source.get("uri") or "").netloc
    return normalize_domain(raw)


def normalize_query(q: str | None) -> str:
    return re.sub(r"\s+", " ", _PUNCT_RE.sub(" ", (q or "").lower())).strip()


# ----------------------------------------------------------------------------- set metrics

def jaccard(a: Iterable[str], b: Iterable[str]) -> float:
    a, b = set(a), set(b)
    if not a and not b:
        return NAN
    return len(a & b) / len(a | b)


def within_pairs(sets: list[set[str]]) -> list[float]:
    return [jaccard(x, y) for x, y in itertools.combinations(sets, 2)]


def cross_pairs(sets_a: list[set[str]], sets_b: list[set[str]]) -> list[float]:
    return [jaccard(x, y) for x in sets_a for y in sets_b]


def consensus(sets: list[set[str]], k: int = 2) -> set[str]:
    """Domains present in at least `k` of the replicas."""
    counts = Counter(d for s in sets for d in s)
    return {d for d, c in counts.items() if c >= k}


def union(sets: list[set[str]]) -> set[str]:
    out: set[str] = set()
    for s in sets:
        out |= s
    return out


# ----------------------------------------------------------------------------- statistics

def _clean(xs: Iterable[float]) -> list[float]:
    return [x for x in xs if x is not None and not (isinstance(x, float) and math.isnan(x))]


def mean(xs: Iterable[float]) -> float:
    xs = _clean(xs)
    return sum(xs) / len(xs) if xs else NAN


def median(xs: Iterable[float]) -> float:
    xs = _clean(xs)
    return statistics.median(xs) if xs else NAN


def sd(xs: Iterable[float]) -> float:
    xs = _clean(xs)
    return statistics.stdev(xs) if len(xs) > 1 else NAN


def bootstrap_ci(
    clusters: list[Any],
    stat: Callable[[list[Any]], float],
    n_iter: int = 1000,
    seed: int = 42,
    alpha: float = 0.05,
) -> tuple[float, float]:
    """Percentile bootstrap CI, resampling whole clusters (cells or prompts) with replacement."""
    n = len(clusters)
    if n == 0:
        return NAN, NAN
    rng = random.Random(seed)
    vals: list[float] = []
    for _ in range(n_iter):
        sample = [clusters[rng.randrange(n)] for _ in range(n)]
        v = stat(sample)
        if v == v:  # skip NaN
            vals.append(v)
    if not vals:
        return NAN, NAN
    vals.sort()
    lo = vals[int((alpha / 2) * (len(vals) - 1))]
    hi = vals[int((1 - alpha / 2) * (len(vals) - 1))]
    return lo, hi


def r4(x: float) -> float | str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return ""
    return round(x, 4)


# ----------------------------------------------------------------------------- loading

def load_config() -> dict[str, Any]:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def load_l1a() -> list[dict[str, Any]]:
    """One row per fresh Gemini call (system-prompt persona operationalisation)."""
    rows = []
    for r in _read_jsonl(L1A_PATH):
        target = r["domain"]
        chunks = r.get("grounding_chunks") or []
        cited = sorted({l1a_chunk_domain(c) for c in chunks} - {""})
        queries_raw = list(r.get("web_search_queries") or [])
        text = r.get("response_text") or ""
        raw = r.get("raw_response") or {}
        rows.append({
            "channel": "L1a",
            "cell_id": r["cell_id"],
            "domain": target,
            "generic_prompt_id": r["generic_prompt_id"],
            "generic_prompt_text": r.get("generic_prompt_text"),
            "generic_prompt_intent": r.get("generic_prompt_intent"),
            "persona_id": r.get("persona_id") or CONTROL,
            "persona_role": r.get("persona_role") or CONTROL,
            "is_control": r.get("persona_id") is None,
            "replication": int(r["replication"]),
            "timestamp": r.get("timestamp"),
            "model": r.get("model"),
            "model_version": raw.get("model_version"),
            "n_sources": len(chunks),
            "n_queries": len(queries_raw),
            "cited_domains": cited,
            "queries_raw": queries_raw,
            "queries_norm": sorted({normalize_query(q) for q in queries_raw} - {""}),
            "query_tokens": query_tokens(queries_raw),
            "target_cited": target in cited,
            "target_text_mention": bool(TARGET_TEXT_REGEX[target].search(text)),
            "error": r.get("error"),
        })
    return rows


def load_l1b() -> list[dict[str, Any]]:
    """One row per historical REDACTED Gemini analysis (persona-in-query operationalisation)."""
    recs = _read_jsonl(L1B_PATH)
    by_cell: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in recs:
        by_cell[r["cell_id"]].append(r)
    rows = []
    for cell_id, group in by_cell.items():
        group.sort(key=lambda x: str(x.get("created_at") or ""))
        for i, r in enumerate(group, start=1):
            target = r["domain"]
            sources = r.get("sources") or []
            cited = sorted({l1b_source_domain(s) for s in sources} - {""})
            queries_raw = list(r.get("search_queries") or [])
            text = r.get("answer") or ""
            rows.append({
                "channel": "L1b",
                "cell_id": cell_id,
                "domain": target,
                "generic_prompt_id": r["generic_prompt_id"],
                "generic_prompt_text": r.get("persona_layer_question"),
                "generic_prompt_intent": None,
                "persona_id": r.get("persona_id") or CONTROL,
                "persona_role": r.get("persona_role") or CONTROL,
                "is_control": r.get("persona_id") is None,
                "replication": i,
                "timestamp": r.get("created_at"),
                "model": r.get("model"),
                "model_version": r.get("model"),
                "n_sources": len(sources),
                "n_queries": len(queries_raw),
                "cited_domains": cited,
                "queries_raw": queries_raw,
                "queries_norm": sorted({normalize_query(q) for q in queries_raw} - {""}),
                "query_tokens": query_tokens(queries_raw),
                "target_cited": target in cited,
                "target_text_mention": bool(TARGET_TEXT_REGEX[target].search(text)),
                "target_mentioned_REDACTED": r.get("target_mentioned"),
                "error": None,
            })
    return rows


def group_cells(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    cells: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        cells[r["cell_id"]].append(r)
    for recs in cells.values():
        recs.sort(key=lambda x: x["replication"])
    return dict(sorted(cells.items()))


def cell_sets(recs: list[dict[str, Any]], field: str = "cited_domains") -> list[set[str]]:
    return [set(r[field]) for r in recs]


# ----------------------------------------------------------------------------- output

def _csv_cell(v: Any) -> Any:
    if isinstance(v, (list, dict)):
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, float):
        return r4(v)
    return v


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("")
        return
    fieldnames = fieldnames or list(rows[0].keys())
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: _csv_cell(v) for k, v in r.items()})


def json_safe(obj: Any) -> Any:
    """Recursively round floats and turn NaN into null so metrics.json is strict JSON."""
    if isinstance(obj, float):
        return None if math.isnan(obj) else round(obj, 4)
    if isinstance(obj, dict):
        return {k: json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [json_safe(v) for v in obj]
    return obj


def query_tokens(queries: Iterable[str]) -> list[str]:
    """Bag-of-words view of a call's decomposed search queries (tokens of length > 2)."""
    toks: set[str] = set()
    for q in queries:
        toks |= {t for t in normalize_query(q).split() if len(t) > 2}
    return sorted(toks)


# ============================================================================
# Cycle 2 additions (L1c channel arms + N=10 replication boost).
# Nothing above this line changed: `run_all.py` still reproduces the June report.
# ============================================================================

L1C_VERBATIM_PATH = RAW / "pilot_l1c_verbatim_runs.jsonl"
L1C_ATTR_PATH = RAW / "pilot_l1c_attr_runs.jsonl"
L1A_BOOST_PATH = RAW / "pilot_l1a_boost_runs.jsonl"

L1C_ARMS = {"l1c_verbatim": L1C_VERBATIM_PATH, "l1c_attr": L1C_ATTR_PATH}


def load_v2(path: Path) -> list[dict[str, Any]]:
    """Rows from a cycle-2 runner output (`pilot_runner_v2.py`).

    Same row shape as `load_l1a`, plus the provenance fields that keep the two
    batches separable: `arm`, `batch`, `persona_slot`, `sent_prompt_text`.
    """
    if not path.exists():
        return []
    # A resumed run re-attempts a failed (cell, replication), so the file can hold an
    # error record and a later successful one for the same slot. Keep the last
    # success per slot and drop error records: a failed call is not an observation.
    best: dict[tuple[str, int], dict[str, Any]] = {}
    for r in _read_jsonl(path):
        if r.get("error") is not None:
            continue
        best[(r["cell_id"], int(r["replication"]))] = r
    rows = []
    for r in best.values():
        target = r["domain"]
        chunks = r.get("grounding_chunks") or []
        cited = sorted({l1a_chunk_domain(c) for c in chunks} - {""})
        queries_raw = list(r.get("web_search_queries") or [])
        text = r.get("response_text") or ""
        rows.append({
            "channel": r.get("channel", "L1c"),
            "arm": r.get("arm"),
            "batch": r.get("batch", "settembre"),
            "persona_slot": r.get("persona_slot"),
            "cell_id": r["cell_id"],
            "domain": target,
            "generic_prompt_id": r["generic_prompt_id"],
            "generic_prompt_text": r.get("generic_prompt_text"),
            "generic_prompt_intent": r.get("generic_prompt_intent"),
            "persona_id": r.get("persona_id") or CONTROL,
            "persona_role": r.get("persona_role") or CONTROL,
            "is_control": r.get("persona_id") is None,
            "replication": int(r["replication"]),
            "timestamp": r.get("timestamp"),
            "model": r.get("model"),
            "model_version": r.get("model_version"),
            "n_sources": len(chunks),
            "n_queries": len(queries_raw),
            "cited_domains": cited,
            "queries_raw": queries_raw,
            "queries_norm": sorted({normalize_query(q) for q in queries_raw} - {""}),
            "query_tokens": query_tokens(queries_raw),
            "target_cited": target in cited,
            "target_text_mention": bool(TARGET_TEXT_REGEX[target].search(text)),
            "sent_prompt_text": r.get("sent_prompt_text"),
            "no_grounding": bool(r.get("no_grounding")),
            "attempts": r.get("attempts"),
            "error": r.get("error"),
        })
    return rows


def count_failed_calls(path: Path) -> int:
    """Error records still sitting in a run file (each was retried on the next resume)."""
    if not path.exists():
        return 0
    return sum(1 for r in _read_jsonl(path) if r.get("error") is not None)


def tag_batch(rows: list[dict[str, Any]], batch: str, arm: str | None = None) -> list[dict[str, Any]]:
    """Stamp provenance onto rows that predate the cycle-2 fields (the June L1a run)."""
    for r in rows:
        r.setdefault("batch", batch)
        r.setdefault("arm", arm)
        r.setdefault("persona_slot", "none" if r["is_control"] else "system_prompt")
        r.setdefault("no_grounding", r["n_sources"] == 0)
    return rows


# ----------------------------------------------------------------------------- reusable estimators

def prompt_index(cells: dict[str, list[dict[str, Any]]]) -> dict[tuple[str, str], dict[str, list[dict]]]:
    """(domain, prompt_id) -> {persona_role: replicas}. Same grouping `run_all` uses."""
    idx: dict[tuple[str, str], dict[str, list[dict]]] = defaultdict(dict)
    for recs in cells.values():
        idx[(recs[0]["domain"], recs[0]["generic_prompt_id"])][recs[0]["persona_role"]] = recs
    return dict(idx)


def within_by_cell(rows: list[dict[str, Any]], field: str = "cited_domains") -> dict[str, float]:
    """Analysis ① estimator: mean pairwise Jaccard between a cell's replicas."""
    return {cid: mean(within_pairs(cell_sets(recs, field)))
            for cid, recs in group_cells(rows).items()}


def interpersona_delta(
    rows: list[dict[str, Any]],
    within: dict[str, float],
    domain: str,
    field: str = "cited_domains",
    n_iter: int = 1000,
    seed: int = 42,
) -> dict[str, float]:
    """Analysis ② estimator, replica-level only (the consensus variant is an artefact).

    Δ = mean cross-persona Jaccard − mean within-cell Jaccard, CI bootstrapped over
    prompt clusters. Also returns the persona-vs-control contrast on the same cells.
    """
    idx = prompt_index(group_cells(rows))
    prompts: list[dict[str, list[float]]] = []
    for (d, _prompt), by_role in idx.items():
        if d != domain:
            continue
        ctrl = by_role.get(CONTROL)
        personas = {r: v for r, v in by_role.items() if r != CONTROL}
        ps: dict[str, list[float]] = {
            "within": [within[v[0]["cell_id"]] for v in personas.values()],
            "cross": [], "ctrl": [],
        }
        for (_ra, A), (_rb, B) in itertools.combinations(sorted(personas.items()), 2):
            ps["cross"].append(mean(cross_pairs(cell_sets(A, field), cell_sets(B, field))))
        if ctrl:
            for recs in personas.values():
                ps["ctrl"].append(mean(cross_pairs(cell_sets(recs, field), cell_sets(ctrl, field))))
        prompts.append(ps)

    def flat(pl: list[dict], key: str) -> float:
        return mean(x for p in pl for x in p[key])

    def d_cross(pl: list[dict]) -> float:
        return flat(pl, "cross") - flat(pl, "within")

    def d_ctrl(pl: list[dict]) -> float:
        return flat(pl, "ctrl") - flat(pl, "within")

    lo, hi = bootstrap_ci(prompts, d_cross, n_iter, seed)
    clo, chi = bootstrap_ci(prompts, d_ctrl, n_iter, seed)
    return {
        "n_prompts": len(prompts),
        "n_cells": sum(len(p["within"]) for p in prompts),
        "n_pairs": sum(len(p["cross"]) for p in prompts),
        "within": flat(prompts, "within"),
        "cross_persona": flat(prompts, "cross"),
        "delta": d_cross(prompts), "delta_ci95_lo": lo, "delta_ci95_hi": hi,
        "vs_control": flat(prompts, "ctrl"),
        "delta_vs_control": d_ctrl(prompts),
        "delta_vs_control_ci95_lo": clo, "delta_vs_control_ci95_hi": chi,
    }


def ci_overlap(a_lo: float, a_hi: float, b_lo: float, b_hi: float) -> bool:
    """Do two percentile CIs overlap? Used to flag divergences worth reporting."""
    for v in (a_lo, a_hi, b_lo, b_hi):
        if v != v:
            return True
    return a_lo <= b_hi and b_lo <= a_hi


# ============================================================================
# Cycle 3 additions (within-market brand reanalysis).
# Needs the full response text, which the cycle-1/2 loaders drop: brand mention
# for non-target brands cannot be computed without it.
# ============================================================================

def load_all_calls_with_text() -> list[dict[str, Any]]:
    """Every usable call across all batches, carrying `response_text`.

    One row per call: L1a June (165), L1c verbatim/attr (330), L1a boost (259),
    L1b historical (68). `market` is the pilot's target domain for that cell, which
    is what defines the competitive market the call belongs to.
    """
    out: list[dict[str, Any]] = []
    raw_text: dict[tuple[str, str, int], str] = {}

    for path, arm in ((L1A_PATH, "L1a_giugno"), (L1C_VERBATIM_PATH, "L1c_verbatim"),
                      (L1C_ATTR_PATH, "L1c_attr"), (L1A_BOOST_PATH, "L1a_boost")):
        if not path.exists():
            continue
        for r in _read_jsonl(path):
            if r.get("error") is None:
                raw_text[(arm, r["cell_id"], int(r["replication"]))] = r.get("response_text") or ""

    def attach(rows: list[dict[str, Any]], arm: str) -> None:
        for r in rows:
            r = dict(r)
            r["arm"] = arm
            r["market"] = r["domain"]
            r["response_text"] = raw_text.get((arm, r["cell_id"], r["replication"]), "")
            out.append(r)

    attach(load_l1a(), "L1a_giugno")
    attach(load_v2(L1C_VERBATIM_PATH), "L1c_verbatim")
    attach(load_v2(L1C_ATTR_PATH), "L1c_attr")
    attach(load_v2(L1A_BOOST_PATH), "L1a_boost")

    # L1b keeps its answer text under a different key and never went through the runner.
    by_cell: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in _read_jsonl(L1B_PATH):
        by_cell[r["cell_id"]].append(r)
    texts: dict[tuple[str, int], str] = {}
    for cell_id, group in by_cell.items():
        group.sort(key=lambda x: str(x.get("created_at") or ""))
        for i, r in enumerate(group, start=1):
            texts[(cell_id, i)] = r.get("answer") or ""
    for r in load_l1b():
        r = dict(r)
        r["arm"] = "L1b"
        r["market"] = r["domain"]
        r["response_text"] = texts.get((r["cell_id"], r["replication"]), "")
        out.append(r)
    return out
