"""Nomi inventati (protocollo sez. 6): uno per domanda, fissato prima delle chiamate, con dominio .it inesistente al
controllo DNS (risposta NXDOMAIN alla richiesta SOA, DNS pubblico di Google). Nomi scelti per non somigliare ai marchi
della domanda e per non essere parole o luoghi noti."""
import json, requests
from datetime import datetime, timezone
from comune_v3 import D, NOME, norm
INV = {"sport_21": "Kervino", "sport_20": "Zelvar", "sport_11": "Varenzo", "sport_09": "Brivano", "sport_01": "Dravio", "sport_13": "Zorvane",
       "moda_beauty_14": "Aurelys", "moda_beauty_18": "Ondarys", "moda_beauty_03": "Fiorvale", "moda_beauty_23": "Nevrola",
       "moda_beauty_08": "Velmora", "moda_beauty_06": "Darvento", "assicurazioni_17": "Corvalia", "assicurazioni_08": "Marvento",
       "assicurazioni_20": "Pelora", "assicurazioni_19": "Nidrava", "assicurazioni_04": "Solvane", "assicurazioni_02": "Quilvane",
       "viaggi_18": "Brezzaria", "viaggi_15": "Calimbra", "viaggi_07": "Ombrevia", "viaggi_04": "Ruvalia", "viaggi_13": "Lunerio", "viaggi_17": "Orbisa"}
if __name__ == "__main__":
    reali = {norm(n) for n in NOME.values()}; out = {}
    for pid, n in INV.items():
        r = requests.get("https://dns.google/resolve", params=dict(name=n.lower() + ".it", type="SOA"), timeout=15).json()
        out[pid] = dict(nome=n, dominio=n.lower() + ".it", dns_status=r.get("Status"), nxdomain=r.get("Status") == 3,
                        uguale_a_marchio_noto=norm(n) in reali, controllato=datetime.now(timezone.utc).isoformat())
        assert out[pid]["nxdomain"] and not out[pid]["uguale_a_marchio_noto"], (pid, n)
    json.dump(out, open(D / "inventati.json", "w"), ensure_ascii=False, indent=1); print("ok", len(out))
