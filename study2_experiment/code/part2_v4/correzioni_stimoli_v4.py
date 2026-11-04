"""Correzioni deterministiche dei modelli neutralizzati, prima delle riscritture (stesso criterio delle correzioni
offline del 24/10, deviazione 15): si inventa solo l'identità commerciale (marchio, nomi di prodotto e di linee, codici,
recapiti, persone testimonial); restano reali i fatti del prodotto (materiali, ingredienti, categorie generiche, cifre).
Lette a mano il 25/10 sulle mappe di data/part2_v4/stimoli. Nessuna chiamata ai modelli. Idempotente."""
import hashlib, json, sys
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from comune_v4 import D, read, write
REALE = 'reale'  # il valore inventato torna uguale al reale
INV = {
 'sport_17': {'PRODOTTO': 'N2'},                                           # T2: si conserva la cifra del modello
 'sport_09': {'TECH_2': REALE, 'PRODOTTO_4': 'QF4 Expert'},                # batteria integrata rimovibile: caratteristica
 'sport_13': {'PRODOTTO': 'ZR12 Velora Kinetic 18K Alum 2026', 'PRODOTTO_2': 'ZR12 Kinetic 18K Alum', 'PRODOTTO_3': 'Cresta Line 2026',
              'TECH_2': REALE, 'TECH_4': REALE, 'TECH_5': REALE, 'TECH_6': REALE, 'TECH_7': REALE, 'TECH_9': REALE,
              'TECH_19': REALE, 'TECH_20': REALE},                          # carbonio 18K, EVA nera, vernice fotocromatica
 'moda_beauty_05': {'PRODOTTO': 'Velun Alpha Arbutin 2% + HA'},            # ingredienti e concentrazione conservati
 'assicurazioni_17': {'PRODOTTO': REALE, 'PRODOTTO_2': REALE, 'PRODOTTO_3': REALE},   # RC Auto / RCA: categoria generica
 'assicurazioni_03': {'TECH_2': REALE, 'TECH_8': REALE, 'TECH_10': REALE}, # Portale/Area/Card Salute: nomi generici
 'assicurazioni_19': {'TECH_1': REALE, 'TECH_2': REALE},                   # teleconsulto, area personale: termini generici
}
MOTIVI = {
 'sport_17': 'Cifra del nome del modello conservata.', 'sport_09': 'Batteria integrata rimovibile è una caratteristica, non un nome; cifra del modello conservata.',
 'sport_13': 'Carbonio 18K, EVA nera e vernice fotocromatica sono materiali e proprietà; cifre e anno conservati nei nomi inventati.',
 'moda_beauty_05': 'Alpha arbutina 2% e acido ialuronico sono ingredienti: si conserva il nome descrittivo con un prefisso inventato (come moda_beauty_18).',
 'assicurazioni_17': 'RC Auto e RCA sono la categoria di polizza, non un nome commerciale.',
 'assicurazioni_03': 'Portale/Area/Card Salute sono nomi generici; i servizi con il marchio nel nome (My AXA, AXA Caring, AXA Health Talk, '
                     'Card Salute AXA, Salute AXA) seguono la firma tramite {BRAND}, così non compare un quarto marchio inventato.',
 'assicurazioni_19': 'Teleconsulto e area personale sono termini generici. «Siamo con te» è una frase italiana usata come gioco di parole '
                     'sul marchio: resta letterale, perché sostituita con la firma diventerebbe «siamo UniSalute»; il residuo è un indizio '
                     'debole del marchio vero, registrato.'}
MODELLO = {'assicurazioni_03': {'{TECH_1}': 'My {BRAND}', '{TECH_3}': '{BRAND} Caring', '{TECH_4}': 'Card Salute {BRAND}',
                                '{TECH_5}': 'card salute {BRAND}', '{TECH_6}': 'Salute {BRAND}', '{TECH_7}': '{BRAND} Health Talk'},
           'assicurazioni_19': {'{BRAND_2}': 'Con Te', '{BRAND_3}': 'con te'}}
h = lambda s: hashlib.sha256(s.encode()).hexdigest()


def main():
    for q in sorted(set(INV) | set(MODELLO)):
        f = D / 'stimoli' / f'{q}.json'; s = read(f)
        if any(c.get('id') == 'v4-25/10' for c in s.get('log_correzioni_offline', [])): print(q, 'già corretto'); continue
        assert not s.get('riscritture'), f'{q}: correggere prima delle riscritture'
        prima = dict(modello=h(s['modello']), mappa_inventata=dict(s['mappa_inventata']))
        for k, v in INV.get(q, {}).items():
            assert k in s['mappa_reale'], (q, k)
            s['mappa_inventata'][k] = s['mappa_reale'][k] if v == REALE else v
        for ph, nuovo in MODELLO.get(q, {}).items():
            assert ph in s['modello'], (q, ph)
            s['modello'] = s['modello'].replace(ph, nuovo); k = ph.strip('{}')
            s['mappa_reale'].pop(k); s['mappa_inventata'].pop(k, None)
        s.setdefault('log_correzioni_offline', []).append(dict(id='v4-25/10', date='2026-10-25', method='deterministic_offline',
            reasons=[MOTIVI[q]], before=prima, after_modello=h(s['modello']), new_llm_judgment=False,
            timestamp=datetime.now(timezone.utc).isoformat()))
        write(f, s); print(q, 'corretto')


if __name__ == '__main__':
    main()
