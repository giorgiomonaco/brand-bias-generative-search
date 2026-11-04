# Ciclo 12 — tabella dei nomi: istruzioni fisse per le proposte

Modello: `gemini-2.5-flash` (API Google), temperatura 0, output JSON con schema. Script: `analysis/cycle12_names.py`.
Le risposte del modello sono **proposte**: i casi segnalati si decidono a mano in `results/cycle12/revisione_nomi.xlsx`,
e la tabella finale è `config/tabella_nomi_v1.csv`.

Regole decise l'11 ottobre 2026, dopo il controllo a mano dell'estrazione:
1. Le compagnie aeree sono brand del settore viaggi, come nella lista dei brand del ciclo 10.
2. Marchi dello stesso gruppo venduti ciascuno con il proprio nome (Allianz e Allianz Direct) restano separati;
   si uniscono solo le varianti di scrittura e le linee di prodotto.
3. I rivenditori che vendono soprattutto marche di altri (Decathlon, Douglas) sono una categoria a parte.
   Marketplace, siti di prenotazione e comparatori restano aggregatori.
4. I marchi di componenti, materiali o tecnologie citati come caratteristica di un altro prodotto (motori Bosch o
   Bafang, cambi Shimano, freni Tektro, suole Vibram) sono una categoria a parte, come i rivenditori: se contarli tra
   i brand si decide in analisi.
5. L'indirizzo di un sito citato come fonte (per esempio adidas.it tra le fonti) resta una fonte e non si unisce al
   brand: la citazione di un sito non è una menzione del brand nel testo. Vale solo per gli indirizzi usati come
   fonte, non per i brand che si chiamano così (Prima.it, Lastminute.com).

## Istruzione: tipo del nome

Ricevi un elenco di nomi citati nelle risposte di un assistente a domande di acquisto. Per ogni nome hai il settore
della domanda e un estratto della risposta in cui compare. Assegna a ogni nome una sola categoria:

- brand: azienda o marchio che produce od offre il prodotto o il servizio con il proprio nome. Comprende i marchi
  propri delle catene (Zara, H&M, Kipsta), i tour operator, le compagnie aeree e di navigazione, le società di
  noleggio, le compagnie assicurative e gli intermediari che vendono polizze con il proprio nome.
- componente: marchio di un componente, di un materiale o di una tecnologia che nella risposta compare come
  caratteristica di un altro prodotto (motori Bosch o Bafang, cambi Shimano, freni Tektro, suole Vibram, membrane
  Gore-Tex).
- rivenditore: negozio, catena o negozio online che vende soprattutto prodotti di altre marche, anche se ha qualche
  marchio proprio (Decathlon, Douglas, Sephora, Notino, MediaWorld, Cisalfa, supermercati e catene di drogherie).
- aggregatore_o_fonte: marketplace con venditori terzi (Amazon, eBay, Subito, Vinted), siti di prenotazione e
  agenzie online che vendono offerte di altri (Booking, Lastminute, eDreams, Expedia, Logitravel), comparatori di
  prezzi o di polizze (Facile, Segugio, Skyscanner, Kayak), giornali, riviste, siti di recensioni o di test, blog, forum.
  Anche l'indirizzo di un sito citato come fonte (adidas.it, aci.gov.it) è aggregatore_o_fonte, se nell'estratto
  compare come link o fonte e non come nome di chi vende.
- altro: non è un'azienda né un marchio: categoria o tipo di prodotto, caratteristica generica, ente pubblico,
  legge, luogo, persona.

Restituisci per ogni nome l'id ricevuto, la categoria e un motivo di al massimo 15 parole.

## Istruzione: coppie di nomi

Ricevi coppie di nomi citati nelle risposte di un assistente, con il settore e un estratto per ciascun nome.
Per ogni coppia decidi se i due nomi vanno contati come lo stesso brand:

- unisci_in_A o unisci_in_B: sono varianti di scrittura dello stesso nome, oppure uno dei due è una linea di
  prodotto, un modello, una polizza o un piano dell'altro, oppure è lo stesso nome con una parola in più
  (assicurazioni, viaggi, tour operator, airlines). Indica in quale nome unire: quello del brand, non del prodotto.
- separa: sono marchi diversi, anche se dello stesso gruppo, ciascuno venduto con il proprio nome (Allianz e
  Allianz Direct), oppure sono nomi che non c'entrano tra loro (Ford e Tom Ford), oppure uno dei due è l'indirizzo
  di un sito citato come fonte e l'altro il nome del brand (adidas.it come link e Adidas nel testo).

Restituisci per ogni coppia l'id ricevuto, la decisione e un motivo di al massimo 15 parole.
