#!/usr/bin/env python
"""Studio principale — embedding di risposte e query con BAAI/bge-m3 (scelto il 13/10).

    python analysis/main_embed.py [--batch 16] [--device mps|cpu]

Legge data/processed/main_calls.jsonl, calcola il vettore denso (normalizzato) di ogni testo distinto e lo salva in
data/processed/emb_bge_m3/ a blocchi da 2.000 (riprende da dove era). Le risposte entrano intere: bge-m3 accetta
fino a 8.192 token, quindi niente passaggi come nel pilot. Le query entrano una per una.
La revisione del modello scaricata si registra in models/bge-m3.lock.json.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CALLS = ROOT / "data" / "processed" / "main_calls.jsonl"
DIR = ROOT / "data" / "processed" / "emb_bge_m3"
LOCK = ROOT / "models" / "bge-m3.lock.json"
MODEL = "BAAI/bge-m3"
BLOCK = 2000


def h(t: str) -> str:
    return hashlib.sha1((t or "").encode()).hexdigest()


def gia_fatti() -> set[str]:
    import numpy as np
    out = set()
    for f in sorted(DIR.glob("blocco_*.npz")):
        out.update(np.load(f)["chiavi"].tolist())
    return out


def carica() -> dict:
    """chiave sha1 -> vettore float32 normalizzato (per l'analisi)."""
    import numpy as np
    out = {}
    for f in sorted(DIR.glob("blocco_*.npz")):
        z = np.load(f)
        for k, v in zip(z["chiavi"].tolist(), z["vettori"]):
            out[k] = v.astype("float32")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--device", default=None)
    a = ap.parse_args()
    import numpy as np
    import torch
    from sentence_transformers import SentenceTransformer
    DIR.mkdir(parents=True, exist_ok=True)
    testi = {}
    for line in CALLS.open():
        r = json.loads(line)
        for t in [r.get("response_text") or ""] + (r.get("queries") or []) + (r.get("queries_modello") or []):
            if t.strip():
                testi.setdefault(h(t), t)
    fatti = gia_fatti()
    todo = sorted(((k, t) for k, t in testi.items() if k not in fatti), key=lambda kt: len(kt[1]))
    print(f"{len(testi)} testi distinti, {len(fatti)} già fatti, {len(todo)} da fare", flush=True)
    if not todo:
        return
    dev = a.device or ("mps" if torch.backends.mps.is_available() else "cpu")
    m = SentenceTransformer(MODEL, device=dev)
    m.max_seq_length = 8192
    rev = None
    try:
        from huggingface_hub import model_info
        rev = model_info(MODEL).sha
    except Exception:  # noqa: BLE001
        pass
    LOCK.parent.mkdir(exist_ok=True)
    LOCK.write_text(json.dumps({"modello": MODEL, "revisione": rev, "dispositivo": dev,
                                "sentence_transformers": __import__("sentence_transformers").__version__},
                               indent=1))
    n0 = len(list(DIR.glob("blocco_*.npz")))
    t0 = time.monotonic()
    for i in range(0, len(todo), BLOCK):
        parte = todo[i:i + BLOCK]
        v = m.encode([t for _, t in parte], batch_size=a.batch, normalize_embeddings=True, show_progress_bar=False)
        np.savez(DIR / f"blocco_{n0 + i // BLOCK:04d}.npz", chiavi=np.array([k for k, _ in parte]),
                 vettori=np.asarray(v, dtype=np.float16))
        fatti_ora = i + len(parte)
        v_s = fatti_ora / (time.monotonic() - t0)
        print(f"{fatti_ora}/{len(todo)}  ~{(len(todo) - fatti_ora) / v_s / 60:.0f} min", flush=True)
    print("fine", flush=True)


if __name__ == "__main__":
    main()
