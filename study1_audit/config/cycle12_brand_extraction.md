# Ciclo 12 — istruzione fissa per l'estrazione dei brand

Modello: `gemini-2.5-flash` (API Google, crediti Google), temperatura 0, output JSON con schema
`{"brand": [string], "fonti_e_aggregatori": [string]}`. Una chiamata per risposta, nessuna ricerca.
Script: `analysis/cycle12_brands.py`. Stesse regole di conteggio del G7 (ciclo 10): i brand del settore
in un elenco, fonti editoriali e aggregatori in un elenco a parte.

## Istruzione (inviata come system instruction, invariata per tutte le risposte)

Ricevi la risposta di un assistente a una domanda di un utente che deve scegliere un prodotto o un servizio.
Elenca i brand che la risposta nomina come prodotti o servizi del settore: aziende, marchi, compagnie,
catene, operatori e piattaforme che producono, vendono o offrono quel prodotto o servizio.

Regole:
1. Ogni brand una sola volta, scritto come compare nella risposta, senza forma societaria (S.p.A., Srl, Inc., Ltd).
2. Per linee di prodotto e modelli riporta il brand madre (per esempio «Nike Pegasus» diventa «Nike»).
3. Non sono brand le categorie generiche, i tipi di prodotto, le tecnologie e i materiali citati come caratteristica,
   gli enti pubblici, le leggi e i luoghi.
4. Le fonti editoriali (giornali, riviste, blog, siti di recensioni o di test) e gli aggregatori o comparatori
   (marketplace, siti di prenotazione, comparatori di prezzi o di polizze) vanno in `fonti_e_aggregatori`, non in `brand`.
5. Se la risposta non nomina nessun brand, restituisci elenchi vuoti. Non aggiungere brand che non compaiono nel testo.

Il messaggio contiene solo il testo della risposta.
