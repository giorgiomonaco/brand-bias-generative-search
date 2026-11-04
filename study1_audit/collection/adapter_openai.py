"""OpenAI adapter — Responses API with the web search tool.

Produces the same record shape as the Gemini pipeline (`pilot_runner_v2.py`), so the
analysis code of cycles 1-5 reads it through `common.load_v2` without a single change.

Model pinned to a dated snapshot: the platform ships undated aliases that move without
notice, and every cross-batch comparison in this thesis assumes a fixed model.

What this engine exposes, and how it maps onto the pilot's schema:

  citations        `url_citation` annotations on the message. This is a SELECTIVE set:
                   the answer cites a handful of the pages it read. It is the analogue
                   of Gemini's grounding chunks, so it goes into `grounding_chunks` and
                   becomes `cited_domains` downstream.
  consulted        `action.sources` of each web_search_call, requested via `include`.
                   The full retrieval set, an order of magnitude larger. Kept SEPARATE
                   in `consulted_sources`: mixing it with the citations would silently
                   redefine what "cited" means halfway through the thesis.
  queries          `action.query` / `action.queries` of each web_search_call. The
                   documentation guarantees them "usually but not always", so the
                   runner records whether they were actually present.

Tool choice is left on automatic, as the brief requires: a call where the model chose
not to search is an observation, not a failure, and is flagged `search_performed=False`.
"""

from __future__ import annotations

import time
from typing import Any

import requests

MODEL = "gpt-5.5-2026-04-23"
ENDPOINT = "https://api.openai.com/v1/responses"
TIMEOUT = 300


def call(api_key: str, prompt_text: str, system_prompt: str | None,
         model: str = MODEL) -> tuple[dict[str, Any] | None, str | None, float]:
    """One call. Returns (raw response, error string, latency in seconds)."""
    payload: dict[str, Any] = {
        "model": model,
        "input": prompt_text,
        "tools": [{"type": "web_search"}],
        "include": ["web_search_call.action.sources"],
    }
    if system_prompt:
        payload["instructions"] = system_prompt
    t0 = time.monotonic()
    try:
        r = requests.post(
            ENDPOINT,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=TIMEOUT,
        )
        latency = time.monotonic() - t0
        if r.status_code != 200:
            return None, f"HTTP {r.status_code}: {r.text[:300]}", latency
        return r.json(), None, latency
    except Exception as e:  # noqa: BLE001 — every failure mode is recorded, none is fatal
        return None, f"{type(e).__name__}: {e}", time.monotonic() - t0


def parse(response: dict[str, Any]) -> dict[str, Any]:
    """Pull out citations, consulted sources, queries and the answer text."""
    output = response.get("output") or []

    queries: list[str] = []
    consulted: list[dict[str, str]] = []
    n_search_calls = 0
    any_query_field = False

    for item in output:
        if item.get("type") != "web_search_call":
            continue
        n_search_calls += 1
        action = item.get("action") or {}
        qs = action.get("queries")
        if isinstance(qs, list) and qs:
            any_query_field = True
            queries.extend(str(q) for q in qs if q)
        elif action.get("query"):
            any_query_field = True
            queries.append(str(action["query"]))
        for s in action.get("sources") or []:
            url = s.get("url") or ""
            if url:
                consulted.append({"url": url})

    chunks: list[dict[str, str]] = []
    text_parts: list[str] = []
    for item in output:
        if item.get("type") != "message":
            continue
        for c in item.get("content") or []:
            if c.get("text"):
                text_parts.append(c["text"])
            for a in c.get("annotations") or []:
                if a.get("type") == "url_citation" and a.get("url"):
                    # `uri` + `title` are the field names common.l1a_chunk_domain expects.
                    chunks.append({"uri": a["url"], "title": a.get("title") or "", "domain": ""})

    # De-duplicate while preserving order: the same page can be cited several times.
    seen: set[str] = set()
    chunks = [c for c in chunks if not (c["uri"] in seen or seen.add(c["uri"]))]
    seen = set()
    consulted = [s for s in consulted if not (s["url"] in seen or seen.add(s["url"]))]

    usage = response.get("usage") or {}
    tool_usage = (response.get("tool_usage") or {}).get("web_search") or {}

    return {
        "response_text": "\n".join(text_parts),
        "model_version": response.get("model"),
        "web_search_queries": queries,
        "grounding_chunks": chunks,
        "grounding_supports": [],
        "consulted_sources": consulted,
        "search_performed": n_search_calls > 0,
        "queries_available": any_query_field,
        "n_search_calls": n_search_calls,
        "n_search_requests_billed": tool_usage.get("num_requests"),
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "total_tokens": usage.get("total_tokens"),
        "reasoning_tokens": (usage.get("output_tokens_details") or {}).get("reasoning_tokens"),
        "cost_usd": None,          # OpenAI does not return cost; computed in analysis
        "temperature": response.get("temperature"),
        "service_tier": response.get("service_tier"),
    }


def is_retryable(err: str) -> bool:
    low = err.lower()
    return any(t in low for t in ("429", "rate limit", "500", "502", "503", "504",
                                 "overloaded", "timeout", "timed out", "connection",
                                 "server_error", "unavailable"))
