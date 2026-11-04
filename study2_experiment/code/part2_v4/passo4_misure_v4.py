"""Passo 4: misure secondarie del protocollo (sez. 8) sugli stimoli definitivi, con i 4 motori, 3 ripetizioni.
Servono come controllo della manipolazione e come moderatori dichiarati prima della raccolta: nessuna scelta di
marchi, domande o condizioni dipende da queste misure (decisione di co-author del 25/10).
  fam MOTORE  familiarità (0-3) dei sette marchi usati per domanda: cinque pagine, più noto, meno noto
  sec MOTORE  notorietà secondo i modelli (0-10), riconoscimento del marchio vero, coerenza percepita (0-3) per firma
Le istruzioni sono quelle della v3 (familiarita_v3.P, misure_secondarie_v3)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from comune_v4 import D, NOME, read, usa_v4


def piano_fam(m):
    import familiarita_v3 as f
    sel, sc = read(D / 'selezione.json'), read(D / 'scelte.json'); out = []
    for pid, v in sel.items():
        s = sc[pid]; ks = [(p['chiave'], 'pagina') for p in v['pagine']] + [(s['piu_noto'], 'piu_noto'), (s['meno_noto'], 'meno_noto')]
        for k, ru in ks:
            for r in range(3):
                out.append(dict(call_id=f'F|{pid}|{k}|{m}|{r}', pid=pid, chiave=k, marchio=NOME[k], ruolo=ru, motore=m, rip=r,
                                user_message=f.P.format(b=NOME[k], p=f.PRODOTTO[pid]), system_prompt=None, search=False))
    return out


if __name__ == '__main__':
    usa_v4(); cosa, m = sys.argv[1], sys.argv[2]
    if cosa == 'fam':
        import familiarita_v3 as f
        f.piano = piano_fam; f.esegui(m, 1e9)
    else:
        import misure_secondarie_v3 as ms
        ms.esegui(m, 1e9)
