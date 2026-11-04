"""Emendamento 2: prova verso l'alto (marchio più noto sullo stesso testo) + controlli di riconoscimento e coerenza.
Celle (solo testo ORIG): SUPERIORE, BRAND, MINORE, rieseguite insieme nella stessa sessione."""
import json, sys
from comune import DOM, D, williams, testo_orig, messaggio, esegui
import studio
OUT = D / "estensione"
SUPERIORI = {"sport_01": "Salomon", "sport_07": "Decathlon", "sport_13": "Adidas", "moda_beauty_05": "La Roche-Posay",
 "moda_beauty_19": "KIKO Milano", "assicurazioni_02": "Unipol", "assicurazioni_05": "Unipol", "assicurazioni_10": "AXA",
 "assicurazioni_13": "Prima", "assicurazioni_19": "Unipol", "viaggi_10": "Alpitour", "viaggi_15": "Alpitour"}
def piano(motori):
    sc = json.load(open(D / "scelte_finali.json")); sc["superiore"] = SUPERIORI
    items = []
    for q, v in DOM.items():
        b = sc["bersaglio"][q]
        altre = [(testo_orig(q, i), p[2]) for i, p in enumerate(v["pagine"])]
        for ident in ("SUPERIORE", "BRAND", "MINORE"):
            pag = list(altre); pag[b] = studio.pagina_bersaglio(q, ident, "ORIG", sc)
            for m in motori:
                ordini, rip = studio.PIANO[m]
                for j in ordini:
                    o = williams()[j]
                    for r in rip:
                        items.append(dict(call_id=f"E|{q}|{ident}|ORIG|{m}|{j}|{r}", fase="estensione", qid=q, ident=ident,
                                          testo="ORIG", motore=m, j=j, rip=r, ordine=o, bersaglio=b,
                                          user_message=messaggio(v["domanda"], pag, o), system_prompt=None, search=False))
    return items
if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    a = sys.argv[1:]; m = a[0]; bud = float(a[1]) if len(a) > 1 else 100
    it = piano((m,))
    if "--dry" in a:
        x = [i for i in it if i["ident"] == "SUPERIORE"][0]; print(len(it)); print(x["user_message"][:200]); 
        import re; blk = re.split(r"\n\n(?=\[\d\] Fonte:)", x["user_message"]); k = x["ordine"].index(x["bersaglio"]); print(blk[k+1][:500]); sys.exit()
    esegui(it, OUT / f"est_{m}.jsonl", budget_s=bud, workers={"gpt": 28, "deepseek": 5, "perplexity": 8, "gemini_vertex": 10})
