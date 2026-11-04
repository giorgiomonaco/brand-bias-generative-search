"""Deposito del codice e degli stimoli prima delle chiamate dello studio (protocollo, intestazione): impronte SHA-256 di
codice, scelte, testi delle pagine, stimoli e registro delle deviazioni. Scrive DEPOSITO_CODICE.md."""
import hashlib, json
from pathlib import Path
from datetime import datetime, timezone
H = Path(__file__).parent; ROOT = H.parents[1]; D = ROOT / "data/part2_v3"
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
righe = [f"{sha(p)}  {p.relative_to(ROOT)}" for p in sorted(H.glob("*.py")) + [H / "DEVIAZIONI.md", H / "PROTOCOLLO_STUDIO2.md"]]
righe += [f"{sha(p)}  {p.relative_to(ROOT)}" for p in [D / "selezione_v3.json", D / "scelte.json", D / "inventati.json", D / "notorieta_categoria.json"]]
righe += [f"{sha(p)}  {p.relative_to(ROOT)}" for p in sorted((D / "stimoli").glob("*.json"))]
testi = hashlib.sha256("".join(json.load(open(p))["sha256"] for p in sorted((D / "testi").glob("*.json"))).encode()).hexdigest()
righe.append(f"{testi}  data/part2_v3/testi/ (impronte dei testi concatenate in ordine di nome)")
ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
(H / "DEPOSITO_CODICE.md").write_text(f"# Deposito del codice e degli stimoli — Study 2, studio completo\n\nData del deposito: {ts} (UTC). "
    "Nessuna chiamata dello studio eseguita a questa data.\n\n```\n" + "\n".join(righe) + "\n```\n")
print(ts, len(righe), "impronte")
