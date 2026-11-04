"""Deviazione 9 (DEVIAZIONI.md): Fitfiu Fitness (sport_11) e Lalique (moda_beauty_03) non hanno una pagina sul sito
ufficiale italiano; al loro posto il marchio successivo per menzioni con la stessa regola della sez. 3 (notorietà di
categoria sotto il più noto, non variante del suo nome): Everfit e Davidoff. Decisa da co-author il 24/10."""
import json
from comune_v3 import D, NOME, DOM
from notorieta_categoria import candidati
SOST = {"viaggi_17": ("drivalia", "hertz")}   # sport_11 Fitfiu -> Everfit già applicata il 24/10 mattina   # Lalique: sostituzione annullata il 24/10 (vedi DEVIAZIONI.md, voce 9)
sel = json.load(open(D / "selezione_v3.json"))
for pid, (via, nuovo) in SOST.items():
    p = sel[pid]["pagine"]; i = [x["chiave"] for x in p].index(via)
    m = next(c for c in sel[pid]["candidati"] if c["chiave"] == nuovo)
    p[i] = dict(chiave=nuovo, nome=NOME[nuovo], dominio=DOM[nuovo], menzioni=m["menzioni"], sostituisce=NOME[via], deviazione=9)
    print(pid, NOME[via], "->", NOME[nuovo], DOM[nuovo])
json.dump(sel, open(D / "selezione_v3.json", "w"), ensure_ascii=False, indent=1)
