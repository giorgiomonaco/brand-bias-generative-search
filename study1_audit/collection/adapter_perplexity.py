"""Perplexity adapter — Sonar chat completions.

Produces the same record shape as the Gemini pipeline (`pilot_runner_v2.py`), so the
analysis code of cycles 1-5 reads it through `common.load_v2` without a single change.

Model: `sonar`, pinned. Chosen over `sonar-pro` for two reasons. It is the default
Sonar tier, so the audit stays deployment-like — the condition Khan et al. argue for
and the one the pilot adopted with `gemini-2.5-flash`. And it costs less than half
per call ($0.0054 vs $0.0120 measured on an identical probe), which matters at the
~8.600 calls of the full L1. Neither tier is "equivalent" to gemini-2.5-flash in any
principled sense: tier equivalence across vendors is not established, and the
cross-engine comparison is therefore descriptive.

A finding that changes how this engine must be read, measured on real responses:

  `citations` is IDENTICAL to `search_results` — 20 of 20 on every probe. Perplexity
  returns the whole retrieval set under the name "citations"; it is NOT a selective
  set the way Gemini's grounding chunks and OpenAI's `url_citation` annotations are.
  Taking that field as "the cited sources" would compare a retrieval set on this
  engine against a citation set on the other two, and would inflate every Jaccard.

  The genuinely cited subset is recoverable: the answer text carries `[n]` markers
  indexing into `search_results`. Those, and only those, go into `grounding_chunks`
  and become `cited_domains` downstream. The full set is kept in `consulted_sources`,
  exactly as OpenAI's consulted sources are.

Search queries are not exposed — neither their text nor, in this API version, their
count. The retrieval result of the thesis therefore extends to OpenAI, not to
Perplexity. This is declared, not discovered in analysis.
"""

from __future__ import annotations

import re
import time
from typing import Any

import requests

MODEL = "sonar"
ENDPOINT = "https://api.perplexity.ai/chat/completions"
TIMEOUT = 300

_MARKER_RE = re.compile(r"\[(\d{1,3})\]")


def call(api_key: str, prompt_text: str, system_prompt: str | None,
         model: str = MODEL) -> tuple[dict[str, Any] | None, str | None, float]:
    """One call. Returns (raw response, error string, latency in seconds)."""
    messages: list[dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt_text})

    t0 = time.monotonic()
    try:
        r = requests.post(
            ENDPOINT,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": model, "messages": messages},
            timeout=TIMEOUT,
        )
        latency = time.monotonic() - t0
        if r.status_code != 200:
            return None, f"HTTP {r.status_code}: {r.text[:300]}", latency
        return r.json(), None, latency
    except Exception as e:  # noqa: BLE001
        return None, f"{type(e).__name__}: {e}", time.monotonic() - t0


def parse(response: dict[str, Any]) -> dict[str, Any]:
    """Split the retrieval set from the subset the answer actually cites."""
    choices = response.get("choices") or []
    text = ""
    if choices:
        text = (choices[0].get("message") or {}).get("content") or ""

    results = response.get("search_results") or []
    consulted = [{"url": s.get("url") or "", "title": s.get("title") or ""}
                 for s in results if s.get("url")]

    # `[n]` is 1-based into search_results. Out-of-range markers are ignored rather
    # than guessed at: a wrong index would invent a citation.
    cited_idx = sorted({int(m) for m in _MARKER_RE.findall(text)})
    chunks: list[dict[str, str]] = []
    for i in cited_idx:
        if 1 <= i <= len(results):
            s = results[i - 1]
            url = s.get("url") or ""
            if url:
                chunks.append({"uri": url, "title": s.get("title") or "", "domain": ""})

    usage = response.get("usage") or {}
    cost = usage.get("cost") or {}

    return {
        "response_text": text,
        "model_version": response.get("model"),
        "web_search_queries": [],           # not exposed by this engine
        "grounding_chunks": chunks,
        "grounding_supports": [],
        "consulted_sources": consulted,
        "search_performed": bool(results),
        "queries_available": False,
        "n_search_calls": None,             # not exposed
        "n_search_requests_billed": None,
        "n_citation_markers": len(cited_idx),
        "n_markers_out_of_range": sum(1 for i in cited_idx if i > len(results)),
        "input_tokens": usage.get("prompt_tokens"),
        "output_tokens": usage.get("completion_tokens"),
        "total_tokens": usage.get("total_tokens"),
        "reasoning_tokens": None,
        "cost_usd": cost.get("total_cost"),  # this engine returns the real cost
        "search_context_size": usage.get("search_context_size"),
        "temperature": None,
        "service_tier": None,
    }


def is_retryable(err: str) -> bool:
    low = err.lower()
    return any(t in low for t in ("429", "rate limit", "500", "502", "503", "504",
                                 "overloaded", "timeout", "timed out", "connection",
                                 "unavailable"))
