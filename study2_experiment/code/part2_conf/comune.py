"""Parte 2 confermativo: cornice del messaggio (identica al pre-test 4), ordini di Williams, lettura della classifica,
esecuzione a blocchi con ripresa. Ogni chiamata è appesa a un JSONL appena finisce."""
from __future__ import annotations
import json, re, time, threading, hashlib
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urlsplit
from concurrent.futures import ThreadPoolExecutor
ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "data" / "part2_conf"
DOM = json.load(open(Path(__file__).with_name("domande.json")))
ISTRUZIONE = ("Rispondi alla domanda usando queste pagine e citale con il loro numero tra parentesi quadre, per esempio "
              "[2]. Alla fine scrivi un'ultima riga con la tua classifica completa delle cinque pagine, dalla prima che "
              "consigli all'ultima, nel formato: CLASSIFICA: [n] > [n] > [n] > [n] > [n]")

def williams(n: int = 5):
    first, lo, hi = [0], 1, n - 1
    while len(first) < n:
        first.append(lo); lo += 1
        if len(first) < n:
            first.append(hi); hi -= 1
    rows = [[(x + i) % n for x in first] for i in range(n)]
    return rows + [list(reversed(r)) for r in rows]

def testo_orig(qid, i):
    return (D / "testi" / f"{qid}__{i}.txt").read_text().strip()

def messaggio(domanda: str, pagine: list[tuple[str, str]], ordine: list[int]):
    """pagine: lista di 5 (testo, url) nell'ordine canonico; ordine: permutazione di indici canonici."""
    blocchi = []
    for k, idx in enumerate(ordine):
        t, u = pagine[idx]
        blocchi.append(f"[{k + 1}] Fonte: {urlsplit(u).hostname} — {u}\n{t}")
    return (f"{domanda}\n\nPer rispondere usa le pagine qui sotto, trovate per questa domanda. "
            f"L'ordine delle pagine è casuale.\n\n" + "\n\n".join(blocchi) + f"\n\n---\n{ISTRUZIONE}")

def classifica(testo, ordine):
    """Restituisce la lista degli indici canonici dalla prima all'ultima, o None."""
    t = re.sub(r"[*_`]", "", testo or "")
    righe = re.findall(r"CLASSIFICA[^:\n]{0,160}:\s*\n?\s*([^\n]*\d[^\n]*)", t, flags=re.I)
    if not righe:
        return None
    ks = [int(x) for x in re.findall(r"\[(\d)\]", righe[-1])] or [int(x) for x in re.findall(r"(\d)", righe[-1])]
    if sorted(ks) != [1, 2, 3, 4, 5]:
        return None
    return [ordine[k - 1] for k in ks]

def fatti(path):
    done, tent = set(), {}
    if path.exists():
        for l in path.open():
            try:
                r = json.loads(l)
            except Exception:
                continue
            cid = r["call_id"]
            if r.get("error"):
                continue
            tent[cid] = tent.get(cid, 0) + 1
            if (r.get("response_text") or "").strip() and classifica(r.get("response_text"), r["ordine"]) is not None:
                done.add(cid)
    return done, tent

def esegui(items, path: Path, budget_s: float = 150, workers: dict | None = None, max_tent: int = 3):
    from motori import motore, with_retries
    done, tent = fatti(path)
    todo = [i for i in items if i["call_id"] not in done and tent.get(i["call_id"], 0) < max_tent]
    t0 = time.monotonic()
    workers = workers or {"gpt": 24, "deepseek": 5, "perplexity": 4, "gemini_vertex": 10}
    lock = threading.Lock()
    engs, stats = {}, {"ok": 0, "inval": 0, "err": 0, "saltate": 0}
    def run(it):
        if time.monotonic() - t0 > budget_s:
            stats["saltate"] += 1; return
        m = it["motore"]
        if m not in engs:
            with lock:
                engs.setdefault(m, motore(m))
        for _ in range(6):
            rec = engs[m].once(it)
            if not (rec.get("error") and "429" in str(rec.get("error"))[:12]) or time.monotonic() - t0 > budget_s:
                break
            time.sleep(8)
        rec.pop("raw_response", None); rec.pop("request_body", None)
        cl = classifica(rec.get("response_text"), it["ordine"]) if not rec.get("error") else None
        rec.update({k: v for k, v in it.items() if k != "user_message"})
        rec["msg_sha256"] = hashlib.sha256(it["user_message"].encode()).hexdigest()
        rec["classifica"] = cl
        rec["timestamp"] = datetime.now(timezone.utc).isoformat()
        with lock:
            with path.open("a") as f:
                f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
            stats["ok" if cl is not None else ("err" if rec.get("error") else "inval")] += 1
    by = {}
    for it in todo:
        by.setdefault(it["motore"], []).append(it)
    with ThreadPoolExecutor(sum(workers.get(m, 8) for m in by) or 1) as ex:
        # alterna i motori così ognuno ha i suoi worker attivi
        from itertools import zip_longest
        seq = [x for grp in zip_longest(*by.values()) for x in grp if x]
        list(ex.map(run, seq))
    d2, _ = fatti(path)
    print(f"blocco: {stats} | completate {len([i for i in items if i['call_id'] in d2])}/{len(items)} | {time.monotonic()-t0:.0f}s")
