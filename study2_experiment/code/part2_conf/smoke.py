import sys, json, time
from motori import motore, with_retries
for n in sys.argv[1:]:
    e = motore(n)
    r = e.once(dict(call_id="smoke", user_message="Elenca tre città italiane, una per riga, senza altro.", system_prompt=None, search=False))
    print(n, r.get("error"), repr((r.get("response_text") or "")[:120]), r.get("model_version") or r.get("model_version_response"), r.get("input_tokens"), r.get("output_tokens"), r.get("cost_usd_est"))
