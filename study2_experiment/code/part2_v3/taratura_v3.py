"""Taratura (protocollo sez. 5): le 5 pagine originali con identità reale, 10 ordini di Williams, 1 ripetizione, 4 motori.
Cornice del messaggio identica al pilota (analysis/part2_conf/comune.py). I dati di taratura non entrano nell'analisi.
Uso: python taratura_v3.py MOTORE [secondi]   (gemini_vertex solo dal Mac)"""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "part2_conf"))
from comune import williams, messaggio, esegui
from comune_v3 import D
from comune_v3 import kurl
OUT = D / "taratura.jsonl"
sel = json.load(open(D / "selezione_v3.json"))
def pagine(pid):
    """Le 5 pagine nell'ordine canonico della tabella: (testo, url). None se manca un testo."""
    out = []
    for p in sel[pid]["pagine"]:
        f = D / "testi" / f"{kurl(pid + '|' + p['nome'])}.json"
        if not f.exists(): return None
        x = json.load(open(f)); out.append((x["testo"], x["url"]))
    return out
def piano(motori):
    items = []
    for pid, v in sel.items():
        pag = pagine(pid)
        if pag is None: continue
        for m in motori:
            for j, o in enumerate(williams()):
                items.append(dict(call_id=f"T|{pid}|{m}|{j}", fase="taratura", qid=pid, motore=m, ordine=o, j=j,
                                  user_message=messaggio(v["domanda"], pag, o), system_prompt=None, search=False))
    return items
if __name__ == "__main__":
    m = sys.argv[1]; bud = float(sys.argv[2]) if len(sys.argv) > 2 else 1e9
    it = piano((m,)); print(m, "chiamate nel piano:", len(it), flush=True)
    esegui(it, D / f"taratura_{m}.jsonl", budget_s=bud,
           workers={"gpt": 24, "deepseek": 6, "perplexity": 8, "gemini_vertex": 10})
