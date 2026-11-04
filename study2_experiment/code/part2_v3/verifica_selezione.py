"""Verifica: la selezione ricostruita riproduce la tabella del protocollo (sez. 3) e i valori del 22/10."""
import json, re
from pathlib import Path
from comune_v3 import D, NOME, norm
from tabella_protocollo import T
from notorieta_categoria import candidati
S = json.load(open(D / "notorieta_categoria.json"))
O = json.load(open(Path(__file__).parent / "origine_22_10/selezione_v3.json"))["selezione"]
STOP = {"di","del","la","il","le","e","&","the","club","resort","hotel","village","villaggio","camping","viaggi","assicurazioni","assicurazione","spa","italia","world","travel","tour"}
def stesso(a, b):
    pa = set(re.findall(r"\w+", NOME.get(a, a).lower())) - STOP; pb = set(re.findall(r"\w+", NOME.get(b, b).lower())) - STOP
    return bool(pa) and bool(pb) and (pa <= pb or pb <= pa)
diff = []
for pid, mis, sup, pag in T:
    c = candidati(pid); s = S[pid]; top = c[:12]
    validi = [x for x in top if not any(stesso(x, y) for y in top if y != x)] or top
    k_sup = max(validi, key=lambda x: (s[x], -c.index(x)))
    cinque = [x for x in c if x != k_sup and s[x] < s[k_sup] and not stesso(x, k_sup)][:5]
    zeri = sum(1 for k in top if s[k] == 0)
    inf = mis == "nome del marchio" or (zeri <= 3 and s[k_sup] >= 300)
    ok_tab = norm(NOME[k_sup]) == norm(sup) and [norm(NOME[k]) for k in cinque] == [norm(x) for x in pag]
    o = O.get(pid, {}); dv = [k for k in [o.get("sup")] + o.get("cinque", []) if k and abs(s.get(k, -1) - o["S"][k]) > 0.01]
    print(f"{pid:17s} tabella {'OK' if ok_tab else 'DIVERSA'} | misura informativa {'sì' if inf else 'NO'} (zeri {zeri}, più noto {s[k_sup]:.0f}) | valori 22/10 {'uguali' if not dv else 'diversi: ' + str(dv)}")
    if not ok_tab or not inf or dv: diff.append(pid)
print("\nDomande con differenze:", diff or "nessuna")
