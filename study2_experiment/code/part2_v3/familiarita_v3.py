"""Familiarità dei modelli con i marchi (protocollo sez. 8), scala 0–3, 3 ripetizioni per motore, i 4 motori dello studio.
Si misurano i marchi che servono alle regole della sez. 5–6: le pagine che possono essere bersaglio (notorietà di
categoria al massimo la metà del più noto) e i candidati che possono fare da «meno noto» (al massimo la metà della
pagina possibile bersaglio più nota). Uso: python familiarita_v3.py MOTORE [secondi]   (gemini_vertex solo dal Mac)."""
import sys, json, re, time, threading
from pathlib import Path
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "part2_conf"))
from comune_v3 import D, NOME
PRODOTTO = {  # fissato prima delle chiamate: il tipo di prodotto della domanda
 "sport_21": "scarpe da corsa", "sport_20": "racchette da tennis", "sport_11": "tapis roulant", "sport_09": "bici elettriche",
 "sport_01": "scarpe da trekking", "sport_13": "racchette da padel", "moda_beauty_14": "creme contorno occhi",
 "moda_beauty_18": "sieri e creme al retinolo", "moda_beauty_03": "profumi", "moda_beauty_23": "profumi da uomo",
 "moda_beauty_08": "jeans", "moda_beauty_06": "giubbotti in pelle", "assicurazioni_17": "assicurazioni auto RCA",
 "assicurazioni_08": "assicurazioni moto", "assicurazioni_20": "assicurazioni vita", "assicurazioni_19": "assicurazioni per animali domestici",
 "assicurazioni_04": "assicurazioni casa", "assicurazioni_02": "assicurazioni annullamento viaggio",
 "viaggi_18": "tour e viaggi organizzati in Sicilia", "viaggi_15": "viaggi organizzati e villaggi a Zanzibar",
 "viaggi_07": "villaggi turistici all inclusive", "viaggi_04": "villaggi e resort in Cilento", "viaggi_13": "villaggi e resort in Salento",
 "viaggi_17": "noleggio auto"}
P = ("Conosci il marchio «{b}» per {p}? Rispondi solo con due righe:\n"
     "PUNTEGGIO: un numero da 0 (mai sentito, o non credo che esista) a 3 (lo conosco bene)\nDESCRIZIONE: una riga su cosa vende")
def punteggio(t):
    """Il numero dopo PUNTEGGIO; se il modello scrive solo il numero nella prima riga (succede con DeepSeek), quello."""
    t = re.sub(r"[*_]", "", t or "")
    m = re.search(r"PUNTEGGIO\W*([0-3])", t, re.I) or re.match(r"\s*([0-3])\s*(?:\n|$)", t)
    return int(m.group(1)) if m else None
def marchi():
    S = json.load(open(D / "notorieta_categoria.json")); sel = json.load(open(D / "selezione_v3.json")); out = []
    for pid, v in sel.items():
        s = S[pid]; sup = v["piu_noto"]["chiave"]; pag = [p["chiave"] for p in v["pagine"]]
        tgt = [p for p in pag if s[p] <= s[sup] / 2]
        if not tgt: continue
        soglia = max(s[p] for p in tgt) / 2
        out += [(pid, k, "pagina") for k in tgt] + [(pid, k, "candidato") for k in s if k not in pag and k != sup and s[k] <= soglia]
    return out
def piano(m):
    return [dict(call_id=f"F|{pid}|{k}|{m}|{r}", pid=pid, chiave=k, marchio=NOME.get(k, k), ruolo=ru, motore=m, rip=r,
                 user_message=P.format(b=NOME.get(k, k), p=PRODOTTO[pid]), system_prompt=None, search=False)
            for pid, k, ru in marchi() for r in range(3)]
def esegui(m, budget):
    from motori import motore
    OUT = D / f"familiarita_{m}.jsonl"
    done = set()
    if OUT.exists():
        for l in OUT.open():
            r = json.loads(l)
            if punteggio(r.get("response_text")) is not None: done.add(r["call_id"])
    todo = [i for i in piano(m) if i["call_id"] not in done]; print(m, "da fare:", len(todo), flush=True)
    t0 = time.monotonic(); lock = threading.Lock(); eng = motore(m)
    def run(it):
        if time.monotonic() - t0 > budget: return
        for _ in range(6):
            rec = eng.once(it)
            if not (rec.get("error") and "429" in str(rec.get("error"))[:40]): break
            time.sleep(8)
        out = {k: it[k] for k in ("call_id", "pid", "chiave", "marchio", "ruolo", "motore", "rip", "user_message")}
        out.update(response_text=rec.get("response_text"), error=rec.get("error"), model_version=rec.get("model_version"),
                   punteggio=punteggio(rec.get("response_text")), timestamp=datetime.now(timezone.utc).isoformat())
        with lock:
            with OUT.open("a") as f: f.write(json.dumps(out, ensure_ascii=False) + "\n")
    with ThreadPoolExecutor(16 if m != "deepseek" else 8) as ex: list(ex.map(run, todo))
if __name__ == "__main__":
    esegui(sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else 1e9)
