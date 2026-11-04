"""Bersaglio e marchi riservati (protocollo sez. 5–6), dai dati di taratura, familiarità e notorietà di categoria.
- Familiarità di un marchio = media dei 4 motori (ogni motore: media delle 3 ripetizioni; per chiamata vale l'ultimo
  record con un punteggio leggibile).
- Più noto: quello della selezione; se appartiene allo stesso gruppo del bersaglio, il successivo per notorietà di
  categoria fra i candidati (non pagine, non varianti del nome di altri candidati).
- Pagina possibile bersaglio: notorietà ≤ metà del più noto (0,3 in log10) e un meno noto valido.
- Meno noto: fra i candidati non pagine e non più noto, con dominio verificato, non varianti né capogruppo, il marchio con
  la notorietà più bassa con familiarità ≥ 1, notorietà ≤ metà del bersaglio, familiarità ≤ bersaglio
  (deviazione 1: il protocollo chiedeva familiarità ≤ bersaglio − 0,5).
- Bersaglio: rango medio di taratura (media dei 4 motori) più vicino a 3; a parità minore varianza, poi alfabetico;
  deve stare fra 2 e 4."""
import json, re, statistics as st, sys
from pathlib import Path
from comune_v3 import D, NOME, DOM
from familiarita_v3 import punteggio
from notorieta_categoria import candidati
MOTORI = ("gpt", "deepseek", "perplexity", "gemini_vertex")
# Gruppi societari dei marchi della selezione in cui più noto e pagine possono coincidere di gruppo (verificati a mano)
GRUPPO = {"alpitour world": "Alpitour", "eden viaggi": "Alpitour", "turisanda": "Alpitour",
          "cerave": "L'Oréal", "la roche posay": "L'Oréal", "kiehls": "L'Oréal", "garnier": "L'Oréal", "medik8": "L'Oréal",
          "stradivarius": "Inditex", "zara": "Inditex", "bershka": "Inditex", "massimo dutti": "Inditex"}
NON_MARCHI = {"beiersdorf", "inditex", "l oreal", "alpitour"}
STOP = {"di","del","la","il","le","e","&","the","club","resort","hotel","village","villaggio","camping","viaggi","assicurazioni","assicurazione","spa","italia","world","travel","tour"}
def stesso(a, b):
    pa = set(re.findall(r"\w+", NOME.get(a, a).lower())) - STOP; pb = set(re.findall(r"\w+", NOME.get(b, b).lower())) - STOP
    return bool(pa) and bool(pb) and (pa <= pb or pb <= pa)
IT = set("il lo la i gli le di da con per che non una un del della dei delle è sono più come anche questo".split())
EN = set("the and of to with for is are this your our you from on in by".split())
def in_italiano(pid, k):
    """Deviazione 9: il bersaglio dev'essere una pagina in italiano (più parole funzionali italiane che inglesi)."""
    from comune_v3 import kurl
    f = D / "testi" / f"{kurl(pid + '|' + NOME[k])}.json"
    if not f.exists(): return None
    w = re.findall(r"[a-zà-ù']+", json.load(open(f))["testo"].lower())
    return sum(x in IT for x in w) > sum(x in EN for x in w)
def familiarita():
    per = {}
    for m in MOTORI:
        f = D / f"familiarita_{m}.jsonl"
        if not f.exists(): continue
        ultimo = {}
        for l in f.open():
            r = json.loads(l); p = punteggio(r.get("response_text"))
            if p is not None: ultimo[r["call_id"]] = (r, p)
        for r, p in ultimo.values(): per.setdefault((r["pid"], r["chiave"]), {}).setdefault(m, []).append(p)
    return {k: dict(media=st.mean(st.mean(v) for v in d.values()), motori=sorted(d), per_motore={m: round(st.mean(v), 2) for m, v in d.items()})
            for k, d in per.items()}
def taratura(pid, pagine):
    from comune import classifica
    pos = {k: {} for k in pagine}
    for m in MOTORI:
        f = D / f"taratura_{m}.jsonl"
        if not f.exists(): continue
        ok = {}
        for l in f.open():
            r = json.loads(l)
            if r["qid"] != pid or r.get("error"): continue
            c = classifica(r.get("response_text"), r["ordine"])
            if c is not None: ok[r["call_id"]] = c
        for c in ok.values():
            for p, idx in enumerate(c): pos[pagine[idx]].setdefault(m, []).append(p + 1)
    return pos
def main():
    sel = json.load(open(D / "selezione_v3.json")); S = json.load(open(D / "notorieta_categoria.json")); F = familiarita()
    out, report = {}, []
    for pid, v in sel.items():
        s = S[pid]; c = candidati(pid); pag = [p["chiave"] for p in v["pagine"]]; sup0 = v["piu_noto"]["chiave"]
        fam = lambda k: F.get((pid, k), {}).get("media")
        def piu_noto(t):
            if GRUPPO.get(sup0) and GRUPPO.get(sup0) == GRUPPO.get(t):
                alt = [k for k in sorted(c, key=lambda k: -s[k]) if k not in pag and k != sup0 and GRUPPO.get(k) != GRUPPO.get(t)
                       and not any(stesso(k, x) for x in c if x != k) and k in DOM]
                return alt[0] if alt else None
            return sup0
        def meno_noto(t):
            for k in sorted(c, key=lambda k: s[k]):
                if k in pag or k == sup0 or k == piu_noto(t) or k not in DOM or k in NON_MARCHI or any(stesso(k, x) for x in pag + [sup0]): continue
                if s[k] > s[t] / 2: continue
                f, ft = fam(k), fam(t)
                if f is None or ft is None: return "familiarità mancante"
                if f >= 1 and f <= ft: return k   # deviazione 1 (DEVIAZIONI.md): era f <= ft - 0,5
            return None
        pos = taratura(pid, pag)
        righe = []
        for t in pag:
            sup = piu_noto(t); mn = meno_noto(t) if sup and s[t] <= s[sup] / 2 else None
            per_m = {m: st.mean(x) for m, x in pos[t].items()}
            media = st.mean(per_m.values()) if per_m else None
            var = st.pvariance([p for x in pos[t].values() for p in x]) if per_m else None
            righe.append(dict(pagina=t, nome=NOME.get(t, t), notorieta=round(s[t]), familiarita=fam(t), piu_noto=sup,
                              notorieta_piu_noto=round(s[sup]) if sup else None, meno_noto=mn, rango_medio=media, varianza=var,
                              motori_taratura=sorted(per_m), italiano=in_italiano(pid, t), ammissibile=bool(sup) and s[t] <= s[sup] / 2 and mn not in (None, "familiarità mancante") and bool(in_italiano(pid, t))))
        amm = [r for r in righe if r["ammissibile"] and r["rango_medio"] is not None]
        best = sorted(amm, key=lambda r: (abs(r["rango_medio"] - 3), r["varianza"], r["nome"]))[0] if amm else None
        # deviazione 12: finestra 1,5–4,5 (protocollo: 2–4); dentro_2_4 serve all'analisi di robustezza fissata prima
        esito = ("nessuna pagina può essere bersaglio" if not amm else
                 "rango del bersaglio fuori da 1,5–4,5" if not 1.5 <= best["rango_medio"] <= 4.5 else "ok")
        out[pid] = dict(esito=esito, dentro_2_4=bool(best) and 2 <= best["rango_medio"] <= 4, bersaglio=best and best["pagina"], piu_noto=best and best["piu_noto"], meno_noto=best and best["meno_noto"],
                        righe=righe)
        report.append(f"{pid:17s} {esito:40s} bersaglio {best and NOME.get(best['pagina'])} (rango {best and round(best['rango_medio'],2)}) "
                      f"| più noto {best and NOME.get(best['piu_noto'])} | meno noto {best and NOME.get(best['meno_noto'], best['meno_noto'])}")
    json.dump(out, open(D / "scelte.json", "w"), ensure_ascii=False, indent=1)
    print("\n".join(report))
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "part2_conf")); main()
