"""Tabella vincolante delle 24 domande (protocollo v2.0, sez. 3)."""
T = [
 ("sport_21","marchio+prodotto","Nike",["ASICS","Brooks","Saucony","Adidas","Kiprun"]),
 ("sport_20","marchio+prodotto","Wilson",["Babolat","Yonex","ProKennex","Prince","Dunlop"]),
 ("sport_11","marchio+prodotto","Diadora",["Toorx","NordicTrack","Fitfiu Fitness","Sportstech","Technogym"]),
 ("sport_09","marchio+prodotto","Cube",["Fiido","Trek","Tenways","Tern","Eleglide"]),
 ("sport_01","marchio+prodotto","Salomon",["Merrell","CMP","La Sportiva","Columbia","Lowa"]),
 ("sport_13","marchio+prodotto","Babolat",["Nox","Bullpadel","Adidas","Dunlop","Siux"]),
 ("moda_beauty_14","marchio+prodotto","CeraVe",["The Ordinary","La Roche-Posay","Avène","Filorga","Kiehl’s"]),
 ("moda_beauty_18","marchio+prodotto","CeraVe",["The Ordinary","La Roche-Posay","Paula’s Choice","Medik8","Garnier"]),
 ("moda_beauty_03","marchio+prodotto","Lattafa",["Zara","Elizabeth Arden","Tesori d'Oriente","Calvin Klein","Lalique"]),
 ("moda_beauty_23","marchio+prodotto","Versace",["Zara","Davidoff","Montblanc","Dior","Creed"]),
 ("moda_beauty_08","marchio+prodotto","Stradivarius",["Zara","Levi’s","Kiabi","OVS","Bershka"]),
 ("moda_beauty_06","marchio+prodotto","Zara",["Schott NYC","Massimo Dutti","AllSaints","Belstaff","Selected Homme"]),
 ("assicurazioni_17","marchio+prodotto","Unipol",["Genertel","ConTe.it","Allianz Direct","Prima Assicurazioni","Allianz"]),
 ("assicurazioni_08","marchio+prodotto","Unipol",["Genertel","Allianz Direct","Prima Assicurazioni","Verti","ConTe.it"]),
 ("assicurazioni_20","marchio+prodotto","Allianz",["MetLife","Genertel","AXA","GenialLife","Wopta"]),
 ("assicurazioni_19","marchio+prodotto","Unipol",["Santévet","Poste Italiane","ConTe.it","Barkibu","Allianz"]),
 ("assicurazioni_04","marchio+prodotto","Unipol",["Allianz Direct","Genertel","Allianz","AXA","Prima Assicurazioni"]),
 ("assicurazioni_02","marchio+prodotto","AXA",["Columbus","Heymondo","Allianz","Coverwise","Allianz Global Assistance"]),
 ("viaggi_18","nome del marchio","WeRoad",["Dimensione Sicilia","Go-Etna","Sicilia Incoming","Tour of Sicily","Sicily Activities"]),
 ("viaggi_15","nome del marchio","Alpitour World",["Eden Viaggi","Veratour","WeRoad","Turisanda","Avventure nel Mondo"]),
 ("viaggi_07","nome del marchio","Alpitour World",["Eden Viaggi","Veratour","Pickalbatros","Bluserena","Club Esse"]),
 ("viaggi_04","nome del marchio","Baia del Silenzio",["Villaggio Elea","Blue Marine","Arco Naturale Club","Villaggio Camping Odissea","Residence Trivento"]),
 ("viaggi_13","nome del marchio","Vivosa Apulia Resort",["Esperia Palace Hotel","ROBINSON","Cala Saracena Resort","Nicolaus Club La Giurlita","Poseidone Beach Resort"]),
 ("viaggi_17","marchio+prodotto","Sixt",["Centauro","Goldcar","Drivalia","Sicily by Car","Avis"]),
]
# Controllo «vende il prodotto con il proprio marchio» del 22/10 sui marchi persi dal vecchio abbinamento dei nomi:
# tutti SI in entrambi i voti (protocollo sez. 3). Il file originale non è stato salvato sul Mac.
CAT_AGGIUNTE_22_10 = ["La Roche-Posay","Avène","Kiehl’s","Paula’s Choice","Tesori d'Oriente","Levi’s","ConTe.it","Santévet"]
