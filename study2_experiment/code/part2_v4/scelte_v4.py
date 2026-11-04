"""Bersaglio e marchi riservati della raccolta rivista (protocollo v2.0 sez. 5-6, con le decisioni del 24-25/10).
Differenze dalla v3 (scelte_v3.py), decise da co-author:
- la notorietà è quella congelata di Study 1 (config/main_notorieta.csv) per tutti i confronti, non più la notorietà
  «marchio + prodotto» della categoria;
- il meno noto NON si sceglie con la familiarità dei modelli (25/10: nessuna scelta di marchi sui giudizi dei modelli).
  È il candidato con la notorietà più bassa, fra quelli non pagine e non più noto, con dominio verificato, non varianti
  del nome di una pagina o del più noto, non società capogruppo, con notorietà al massimo la metà del bersaglio.
  Familiarità e coerenza percepita restano misure secondarie (controllo e moderatori), non criteri.
Invariati: più noto della selezione (se è dello stesso gruppo del bersaglio, il successivo per notorietà); pagina
possibile bersaglio se notorietà <= metà del più noto, se esiste un meno noto e se il testo è in italiano (deviazione 9);
bersaglio = rango medio di taratura (media dei 4 motori) più vicino a 3, a parità minore varianza poi ordine alfabetico;
finestra 1,5-4,5 (deviazione 12) con dentro_2_4 per la robustezza fissata prima. Nessuna chiamata ai modelli."""
import json, re, statistics as st, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from comune_v4 import D, SRC24, NOME, DOM, V, MOTORI, kurl, read, write
from audit_v4 import stesso, lingua
from comune import classifica
GRUPPO = {"alpitour world": "Alpitour", "eden viaggi": "Alpitour", "turisanda": "Alpitour",
          "cerave": "L'Oréal", "la roche posay": "L'Oréal", "kiehls": "L'Oréal", "garnier": "L'Oréal", "medik8": "L'Oréal",
          "stradivarius": "Inditex", "zara": "Inditex", "bershka": "Inditex", "massimo dutti": "Inditex"}  # scelte_v3
G = {**GRUPPO, **read(SRC24 / 'gruppi_verificati.json')['additions']}
NON_MARCHI = {"beiersdorf", "inditex", "l oreal", "alpitour"}


def ranghi(pid, pagine):
    pos = {k: {} for k in pagine}
    for m in MOTORI:
        ok = {}
        for l in (D / f'taratura_{m}.jsonl').open():
            r = json.loads(l)
            if r['qid'] != pid or r.get('error'): continue
            c = classifica(r.get('response_text'), r['ordine'])
            if c is not None: ok[r['call_id']] = c
        for c in ok.values():
            for p, idx in enumerate(c): pos[pagine[idx]].setdefault(m, []).append(p + 1)
    return pos


def main():
    sel = read(D / 'selezione.json'); out, rep = {}, []
    for pid, v in sel.items():
        c = [x['chiave'] for x in v['candidati']]; pag = [p['chiave'] for p in v['pagine']]; sup0 = v['piu_noto']['chiave']
        def piu_noto(t):
            if G.get(sup0) and G.get(sup0) == G.get(t):
                alt = [k for k in sorted(c, key=lambda k: -V[k]) if k not in pag and k != sup0 and G.get(k) != G.get(t)
                       and not any(stesso(k, x) for x in c if x != k) and k in DOM]
                return alt[0] if alt else None
            return sup0
        def meno_noto(t, sup):
            for k in sorted(c, key=lambda k: (V[k], c.index(k))):
                if k in pag or k in (sup0, sup) or k not in DOM or k in NON_MARCHI or any(stesso(k, x) for x in pag + [sup0, sup]): continue
                if V[k] <= V[t] / 2: return k
            return None
        pos = ranghi(pid, pag); righe = []
        for t in pag:
            sup = piu_noto(t); mn = meno_noto(t, sup) if sup and V[t] <= V[sup] / 2 else None
            per_m = {m: st.mean(x) for m, x in pos[t].items()}
            media = st.mean(per_m.values()) if len(per_m) == len(MOTORI) else None
            var = st.pvariance([p for x in pos[t].values() for p in x]) if per_m else None
            it = lingua(read(D / 'testi' / f"{kurl(pid + '|' + NOME[t])}.json")['testo']) == 'it'
            righe.append(dict(pagina=t, nome=NOME[t], notorieta=V[t], piu_noto=sup, notorieta_piu_noto=V[sup] if sup else None,
                              meno_noto=mn, notorieta_meno_noto=V[mn] if mn else None, rango_medio=media, rango_per_motore=per_m,
                              n_taratura={m: len(x) for m, x in pos[t].items()}, varianza=var, italiano=it,
                              ammissibile=bool(sup) and V[t] <= V[sup] / 2 and bool(mn) and it))
        amm = [r for r in righe if r['ammissibile'] and r['rango_medio'] is not None]
        best = sorted(amm, key=lambda r: (abs(r['rango_medio'] - 3), r['varianza'], r['nome']))[0] if amm else None
        esito = ('taratura incompleta' if any(r['rango_medio'] is None for r in righe) else
                 'nessuna pagina può essere bersaglio' if not amm else
                 'rango del bersaglio fuori da 1,5-4,5' if not 1.5 <= best['rango_medio'] <= 4.5 else 'ok')
        out[pid] = dict(esito=esito, dentro_2_4=bool(best) and 2 <= best['rango_medio'] <= 4, bersaglio=best and best['pagina'],
                        piu_noto=best and best['piu_noto'], meno_noto=best and best['meno_noto'], righe=righe)
        rep.append(f"{pid:17s} {esito:38s} bersaglio {best and NOME[best['pagina']]} (rango {best and round(best['rango_medio'], 2)}) "
                   f"| più noto {best and NOME[best['piu_noto']]} | meno noto {best and NOME[best['meno_noto']]}")
    write(D / 'scelte.json', out); print('\n'.join(rep))


if __name__ == '__main__':
    main()
