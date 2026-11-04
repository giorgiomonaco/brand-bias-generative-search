"""Azure Foundry adapter — Responses API with the web_search tool (cycle 8).

Same shape as `adapter_openai.py` (cycle 6), with the endpoint and the authentication
changed: the call goes to the Foundry resource, `model` is the DEPLOYMENT name, and the
key travels in the `api-key` header. Field names follow the pilot records; note that
`common.load_v2` keys rows by (cell, replication), so it would merge blocks A and B of
cycle 8 — the cycle-8 analysis reads the runner output with its own loader.
One module serves every Azure row of the test:

  form 1   resource endpoint + key          `AZURE_OPENAI_ENDPOINT/openai/v1/responses`
           GPT rows, and the first try for DeepSeek and Llama (same tool as the GPTs).
  form 2   project endpoint + Entra token   `FOUNDRY_PROJECT_ENDPOINT/openai/v1/responses`
           only if form 1 is refused. The token comes from `az account get-access-token`
           and is never written anywhere; it needs the Foundry User role (step C1).

What the Responses API exposes, and where it goes in the record (field names as in the
pilot, so `common.load_v2` reads the output unchanged):

  model queries `action.query` of each `search` action: what the model asked the tool
  queries       `action.queries`: what the tool executed (see the note in `parse`)
  opened pages  `action.url` of the `open_page` (and `find_in_page`) actions
  consulted     `action.sources`, requested via `include` — the retrieval set, kept apart
                from the citations exactly as in cycle 6
  citations     `url_citation` annotations on the message -> `grounding_chunks`
  billed        the web-search request count in the usage block, when the API returns it

Everything here is checked against the raw JSON, not assumed from the documentation:
`parse` also reports which of these structures were actually present in the response.
"""

from __future__ import annotations

import json
import re
import subprocess
import time
from typing import Any

import requests

TIMEOUT = 300
USER_COUNTRY = "US"
SEARCH_INCLUDE = ["web_search_call.action.sources"]


# ----------------------------------------------------------------------------- auth

def entra_token() -> str:
    """Entra token for the project endpoint (form 2). Held in memory only, never saved."""
    out = subprocess.run(
        ["az", "account", "get-access-token", "--scope", "https://ai.azure.com/.default",
         "--query", "accessToken", "-o", "tsv"],
        capture_output=True, text=True, timeout=60,
    )
    if out.returncode != 0 or not out.stdout.strip():
        # az's stderr can carry the subscription path or the user name: never into a log.
        err = re.sub(r"/subscriptions/[0-9a-fA-F-]{36}", "/subscriptions/<subscription-id>", out.stderr)
        err = re.sub(r"[\w.+-]+@[\w-]+\.[\w.]+", "<utente>", err)
        raise RuntimeError(f"az account get-access-token failed: {err.strip()[:300]}")
    return out.stdout.strip()


def responses_url(base: str) -> str:
    """`base` is AZURE_OPENAI_ENDPOINT (form 1) or FOUNDRY_PROJECT_ENDPOINT (form 2)."""
    return base.rstrip("/") + "/openai/v1/responses"


# ----------------------------------------------------------------------------- call

def build_payload(deployment: str, prompt_text: str, *, search: bool,
                  tool_choice: str | None = "required", effort: str | None = None,
                  system_prompt: str | None = None) -> dict[str, Any]:
    """Request body. `search=False` sends no tool at all: the "search off" condition."""
    payload: dict[str, Any] = {"model": deployment, "input": prompt_text}
    if system_prompt:
        payload["instructions"] = system_prompt
    if search:
        payload["tools"] = [{
            "type": "web_search",
            "user_location": {"type": "approximate", "country": USER_COUNTRY},
        }]
        payload["include"] = list(SEARCH_INCLUDE)
        if tool_choice:
            payload["tool_choice"] = tool_choice
    if effort:
        payload["reasoning"] = {"effort": effort}
    return payload


def call(url: str, auth_headers: dict[str, str], payload: dict[str, Any]
         ) -> tuple[dict[str, Any] | None, str | None, float, int | None]:
    """One call. Returns (raw response, error string, latency s, HTTP status).

    The error string keeps the API message verbatim (first 2000 chars): when a tool is
    refused, the refusal is itself the result the cycle has to record.
    """
    t0 = time.monotonic()
    try:
        r = requests.post(url, headers={**auth_headers, "Content-Type": "application/json"},
                          json=payload, timeout=TIMEOUT)
        latency = time.monotonic() - t0
        if r.status_code != 200:
            return None, f"HTTP {r.status_code}: {r.text[:2000]}", latency, r.status_code
        body = r.json()
        # A 200 can still carry a failed or incomplete response.
        if body.get("status") not in (None, "completed"):
            detail = body.get("error") or body.get("incomplete_details")
            return body, f"status={body.get('status')}: {json.dumps(detail)[:1000]}", latency, 200
        return body, None, latency, 200
    except Exception as e:  # noqa: BLE001 — every failure mode is recorded, none is fatal
        return None, f"{type(e).__name__}: {e}", time.monotonic() - t0, None


def is_retryable(err: str) -> bool:
    low = err.lower()
    return any(t in low for t in ("http 429", "rate limit", "http 500", "http 502", "http 503",
                                 "http 504", "overloaded", "timeout", "timed out",
                                 "connectionerror", "server_error", "unavailable"))


def tool_choice_refused(err: str | None) -> bool:
    """A 400 that names `tool_choice`: the forcing is not supported, the tool may be."""
    return bool(err) and err.startswith("HTTP 400") and "tool_choice" in err


# ----------------------------------------------------------------------------- parse

def _usage_search_requests(response: dict[str, Any]) -> tuple[int | None, str | None]:
    """Billed web-search requests, wherever this API version puts them.

    Returns (count, JSON path it came from). The cycle-6 OpenAI response carried it in
    `tool_usage.web_search.num_requests`; the path is recorded so the SUMMARY can say
    where the number really came from on Azure.
    """
    tu = response.get("tool_usage")
    if isinstance(tu, dict):
        ws = tu.get("web_search")
        if isinstance(ws, dict) and ws.get("num_requests") is not None:
            return int(ws["num_requests"]), "tool_usage.web_search.num_requests"
    usage = response.get("usage") or {}
    for key in ("tool_usage", "server_tool_use", "web_search"):
        block = usage.get(key)
        if isinstance(block, dict):
            for inner in (block.get("web_search"), block):
                if isinstance(inner, dict):
                    for k in ("num_requests", "web_search_requests", "requests"):
                        if inner.get(k) is not None:
                            return int(inner[k]), f"usage.{key}.{k}"
    return None, None


def parse(response: dict[str, Any]) -> dict[str, Any]:
    """Queries, opened pages, consulted sources, citations, text, usage."""
    output = response.get("output") or []

    # Two query levels, verified on the cycle-8 raw (2026-09-26):
    #   action.query    the argument the MODEL passed to the tool, one per search action.
    #   action.queries  the queries the tool actually EXECUTED. With reasoning (gpt-5.x)
    #                   the list starts with action.query; that the rest are the model's
    #                   own too is plausible but NOT verifiable (the reasoning summaries
    #                   are empty). Without reasoning (gpt-4.1, DeepSeek, Llama) it is
    #                   always three queries generated by the tool from the conversation,
    #                   independently of action.query, which is never among them (0/22).
    # The cycle-6 adapter kept only `queries`, which hides who wrote the query: here the
    # two levels stay apart, and `web_search_queries` holds the executed ones (what hits
    # the search engine, the same meaning as Gemini's web_search_queries).
    model_queries: list[str] = []
    queries: list[str] = []
    opened: list[str] = []
    consulted: list[dict[str, str]] = []
    action_types: list[str] = []
    n_search_calls = n_search_actions = 0
    n_model_query_in_executed = 0
    any_query_field = any_sources_field = False

    for item in output:
        if item.get("type") != "web_search_call":
            continue
        n_search_calls += 1
        action = item.get("action") or {}
        atype = action.get("type") or ""
        action_types.append(atype)
        if atype == "search" or (not atype and (action.get("query") or action.get("queries"))):
            n_search_actions += 1
        mq = str(action["query"]) if action.get("query") else None
        if mq:
            any_query_field = True
            model_queries.append(mq)
        qs = action.get("queries")
        if isinstance(qs, list) and qs:
            any_query_field = True
            queries.extend(str(q) for q in qs if q)
            n_model_query_in_executed += bool(mq and mq in qs)
        elif mq:
            queries.append(mq)
            n_model_query_in_executed += 1
        if atype in ("open_page", "find_in_page") and action.get("url"):
            opened.append(str(action["url"]))
        if "sources" in action:
            any_sources_field = True
        for s in action.get("sources") or []:
            url = (s or {}).get("url") or ""
            if url:
                consulted.append({"url": url})

    # The answer is the FINAL message: the one flagged phase == "final_answer" when the
    # API sets it (gpt-5.x), otherwise the last message. DeepSeek and Llama emit a
    # pre-search message ("I'll search for ...") before the web_search_call: it goes to
    # `preamble_text`, not into the answer, so the citation offsets stay aligned.
    msg_idx = [i for i, it in enumerate(output) if it.get("type") == "message"]
    final_idx = next((i for i in msg_idx if output[i].get("phase") == "final_answer"),
                     msg_idx[-1] if msg_idx else None)

    chunks: list[dict[str, str]] = []
    text_parts: list[str] = []
    preamble_parts: list[str] = []
    n_messages = len(msg_idx)
    for i in msg_idx:
        item = output[i]
        for c in item.get("content") or []:
            if c.get("text"):
                (text_parts if i == final_idx else preamble_parts).append(c["text"])
            for a in c.get("annotations") or []:
                if a.get("type") == "url_citation" and a.get("url"):
                    # `uri` + `title` are the names common.l1a_chunk_domain expects.
                    chunks.append({"uri": a["url"], "title": a.get("title") or "", "domain": ""})

    def dedup(xs: list, key) -> list:
        seen: set[str] = set()
        return [x for x in xs if not (key(x) in seen or seen.add(key(x)))]

    chunks = dedup(chunks, lambda c: c["uri"])
    consulted = dedup(consulted, lambda s: s["url"])
    opened = dedup(opened, lambda u: u)
    # A query can be issued twice in one call; keep order, keep duplicates out.
    queries = dedup(queries, lambda q: q)
    model_queries = dedup(model_queries, lambda q: q)

    usage = response.get("usage") or {}
    billed, billed_path = _usage_search_requests(response)

    return {
        "response_text": "\n".join(text_parts),
        "preamble_text": "\n".join(preamble_parts) or None,
        "model_version": response.get("model"),
        "web_search_queries": queries,
        "model_queries": model_queries,
        "n_model_query_in_executed": n_model_query_in_executed,
        "grounding_chunks": chunks,
        "grounding_supports": [],
        "consulted_sources": consulted,
        "opened_pages": opened,
        "search_performed": n_search_calls > 0,
        "queries_available": any_query_field,
        "consulted_available": any_sources_field,
        "n_search_calls": n_search_calls,
        "n_search_actions": n_search_actions,
        "search_action_types": action_types,
        "n_search_requests_billed": billed,
        "billed_field_path": billed_path,
        "input_tokens": usage.get("input_tokens"),
        "cached_input_tokens": (usage.get("input_tokens_details") or {}).get("cached_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "total_tokens": usage.get("total_tokens"),
        "reasoning_tokens": (usage.get("output_tokens_details") or {}).get("reasoning_tokens"),
        "n_output_messages": n_messages,
        "output_item_types": [it.get("type") for it in output],
        "temperature": response.get("temperature"),
        "service_tier": response.get("service_tier"),
        "reasoning_effort_echo": (response.get("reasoning") or {}).get("effort"),
        "tool_choice_echo": response.get("tool_choice"),
    }
