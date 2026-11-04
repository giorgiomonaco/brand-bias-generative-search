"""Regola 2/3: rifà il controllo GPT (titolo + indirizzo + 12.000 caratteri) sugli URL già trovati, nell'ordine dei
tentativi. Le ricerche non si rifanno: stessi URL, stesso numero di tentativi."""
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import p3_regola2 as r2
R = r2.R
def uno(j):
    st = R[j]; st["scelta"] = None; st["regola"] = None
    for p in st.get("prove_url", []):
        if not p.get("url") or p["esito"] in ("nessun URL", "fuori dal sito del marchio"): continue
        pid, b = j.split("|"); v, m = r2.controlla(pid, b, p["url"]); p["esito_3500"] = p["esito"]; p["esito"] = v
        if v == "SI": st.update(scelta=p["url"], regola=p["regola"], prodotto=p["cosa"]); break
    return j, st
todo = [j for j in r2.DA_FARE if R.get(j, {}).get("versione_B") == 2]
with ThreadPoolExecutor(16) as ex:
    for fu in as_completed([ex.submit(uno, j) for j in todo]):
        j, st = fu.result(); R[j] = st
json.dump(R, open(r2.F, "w"), ensure_ascii=False, indent=1)
print(len(todo), "con pagina", sum(bool(R[j]["scelta"]) for j in todo))
