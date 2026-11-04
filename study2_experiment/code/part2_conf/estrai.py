"""Estrazione verbatim del testo prodotto (procedura fissa, documentata nel protocollo).
GPT copia le parti descrittive della pagina; ogni riga restituita viene tenuta solo se compare identica
(spazi normalizzati) nel testo catturato o nelle descrizioni JSON-LD. Limite 450 parole."""
import json, re, hashlib, sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from motori import motore, with_retries
D = Path(__file__).resolve().parents[2] / "data" / "part2_conf"
DOM = json.load(open(Path(__file__).with_name("domande.json")))
PROMPT = ("Qui sotto c'è il testo estratto da una pagina web ufficiale del prodotto «{prod}» di {brand}.\n"
 "Copia PAROLA PER PAROLA solo le parti che descrivono questo prodotto: descrizione, caratteristiche, specifiche, "
 "cosa include o copre, prezzo se presente. Escludi menu, cookie, recensioni, altri prodotti, newsletter, note legali, "
 "footer, testi generici su spedizioni, resi, pagamenti o assistenza clienti. Non riscrivere, non riassumere, non "
 "aggiungere nulla, non correggere. Mantieni l'ordine originale e copia righe intere. Massimo 450 parole in totale: se "
 "le parti pertinenti sono di più, tieni quelle che descrivono meglio il prodotto. Restituisci solo il testo copiato, "
 "una riga per paragrafo o voce, senza commenti.\n\n=== TESTO DELLA PAGINA ===\n{testo}")
norm = lambda s: re.sub(r"\s+", " ", s).strip()
def k(url): return hashlib.sha256(url.encode()).hexdigest()[:16]
def lavora(arg):
    qid, i, (brand, prod, url) = arg
    meta = json.load(open(D / "pagine" / f"{k(url)}.json"))
    src = (D / "pagine" / f"{k(url)}.txt").read_text() + "\n" + "\n".join(meta.get("ld") or [])
    S = norm(src)
    it = dict(call_id=f"estr|{qid}|{i}", user_message=PROMPT.format(prod=prod, brand=brand, testo=src[:60000]), system_prompt=None, search=False)
    rec = with_retries(eng, it)
    out = rec.get("response_text") or ""
    kept, dropped = [], []
    for l in out.split("\n"):
        l2 = norm(re.sub(r"^[-•*]\s+", "", l))
        if not l2: continue
        (kept if l2 in S else dropped).append(l2)
    txt = "\n".join(kept)
    w = txt.split()
    if len(w) > 480:  # taglio di sicurezza a fine riga
        acc, n = [], 0
        for l in kept:
            if n + len(l.split()) > 480: break
            acc.append(l); n += len(l.split())
        txt = "\n".join(acc)
    (D / "testi" / f"{qid}__{i}.txt").write_text(txt)
    return dict(qid=qid, i=i, brand=brand, prodotto=prod, url=url, parole=len(txt.split()), righe_tenute=len(kept),
                righe_scartate=len(dropped), scartate=dropped[:5], errore=rec.get("error"), sha256=hashlib.sha256(txt.encode()).hexdigest())
eng = motore("gpt")
if __name__ == "__main__":
    jobs = [(q, i, p) for q, v in DOM.items() for i, p in enumerate(v["pagine"])]
    with ThreadPoolExecutor(16) as ex:
        res = list(ex.map(lavora, jobs))
    json.dump(res, open(D / "estrazione_report.json", "w"), ensure_ascii=False, indent=1)
    for r in res: print(r["qid"], r["i"], r["brand"], r["parole"], r["righe_scartate"], r["errore"] and r["errore"][:60])
