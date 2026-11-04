# Ciclo 11 — Buyer personas dello Studio 1: regole scritte prima dei dati

Data: 2026-10-05. Scritte prima di aprire le keyword dei 4 settori. L'hash SHA-256 di questo
file è in `results/cycle11/regole_hash.txt`, calcolato subito dopo la scrittura e prima di
leggere i dati. Ogni modifica successiva è una deviazione e va registrata nel SUMMARY.

Contesto: Piano L1 completo, §5 Studio 1. Le personas sono profili identity-only, scritti prima
della domanda nello stesso messaggio utente. Settori: assicurazioni, viaggi, moda e beauty,
sport. Prompt: i 20 per settore del ciclo 10 (1–10 in `prompt_g7_revisione.csv`, 11–20 in
`prompt_studio1_revisione.csv`), che non si toccano.

## 0. Decisioni già prese (non in discussione)

1. Tre personas per settore, a un fattore per volta: A = base; B = come A con il budget
   diverso; C = come A con un altro elemento diverso.
2. Ogni persona ha tre elementi, sempre nello stesso ordine: (1) fase di vita o famiglia,
   (2) esperienza con la categoria, (3) atteggiamento verso il budget.
3. Esclusi: genere, età, regione e ogni altro attributo protetto o non legato al bisogno
   d'acquisto; brand; località; possesso di prodotti; pain point.
4. Gli attributi vengono dai dati (keyword) e dalle statistiche pubbliche. Nessun LLM inventa
   attributi. Nessun dato di REDACTED.
5. Nessuna persona si sceglie, si tiene o si scarta in base a risultati su citazioni, query o
   brand.
6. Validazione: controlli automatici, prova tecnica su GPT, lettura finale dell'autore. Un solo
   valutatore, dichiarato come limite.
7. Spesa: nessuna spesa DataForSEO; GPT su crediti Azure con tetto di 8 dollari.

## 1. Dati (Fase 1)

- Keyword italiane già estratte nel ciclo 10 (Google Ads, Italia, location 2380, lingua `it`),
  unione completa di tutte le idee restituite dai seed del settore.
- Filtri, in quest'ordine: senza brand secondo il lessico rivisto (`cycle10_brand_lexicon.yaml`
  più `cycle10_brand_lexicon_aggiunte.yaml`, a frasi intere, come nel ciclo 10); intento diverso
  da navigational (etichetta principale dell'endpoint `search_intent` del ciclo 10); volume
  mensile (media delle ultime 12 mensilità) almeno 20. Nessun altro filtro.
- Robustezza: tutto ripetuto sul sottoinsieme con intento commercial e volume almeno 100. La
  robustezza si riporta e non cambia le scelte.
- Volume limitato (winsorizzato) al 95esimo percentile del settore, calcolato sull'insieme
  filtrato di quel settore (e, per la robustezza, sul sottoinsieme di robustezza). Ogni quota
  usa il volume limitato. Quota di un livello = somma del volume limitato delle keyword che
  portano il livello ÷ somma del volume limitato di tutte le keyword del settore.

## 2. Dizionario dei modificatori

- Frasi intere, corrispondenza a parola intera dopo la normalizzazione del ciclo 10 (minuscolo,
  senza accenti, punteggiatura → spazio). Un solo dizionario per i 4 settori. Se due voci si
  sovrappongono nella stessa keyword vince la più lunga (per esempio «qualità prezzo» prima di
  «qualità»). Una keyword può portare più livelli, anche di famiglie diverse.
- Tre famiglie. Ogni voce appartiene a un livello; un livello è un gruppo di sinonimi che
  descrive la stessa condizione o lo stesso atteggiamento.
  - Fase di vita o famiglia: per esempio famiglie, bambini, neopatentati, giovani, anziani,
    coppie, single, pensionati, studenti.
  - Esperienza con la categoria: per esempio principianti, esperti, professionisti, alle prime
    armi.
  - Budget: per esempio economico, low cost, scontato, offerte (atteggiamento «attento al
    prezzo»); premium, lusso, di qualità («disposto a spendere di più per la qualità»); rapporto
    qualità prezzo come livello a sé.
- Non sono modificatori di budget le parole che chiedono un prezzo senza esprimere un
  atteggiamento (prezzo, prezzi, costo, quanto costa, preventivo): si contano a parte, solo
  come diagnostica.
- Livelli contati ma non utilizzabili in una persona: quelli che si esprimono solo con l'età
  (giovani, anziani, ragazzi, over, under) o che implicano il genere (donna, uomo, mamma, papà,
  gravidanza, sposa). Si contano, compaiono nelle tabelle con la marca «non utilizzabile», e al
  loro posto si usa il livello successivo. La marca dipende dal significato della voce, non dal
  volume, e si decide nel dizionario prima di calcolare le quote.
- Usi di categoria che non sono modificatori si escludono a frase intera (per esempio «rc
  professionale» nelle assicurazioni è un tipo di polizza, non l'esperienza dell'acquirente).
- Estensione: dopo il dizionario iniziale si leggono, per ogni settore, i 100 uni- e bigrammi più
  frequenti (per numero di keyword) che non sono coperti dal dizionario, dalle parole di
  categoria (token dei seed del settore) e dalle stopword. Si aggiungono solo voci che descrivono
  una fase di vita, un'esperienza o un atteggiamento verso il budget. Le aggiunte si elencano.
  Il dizionario finale si salva in `config/cycle11_modificatori.yaml` prima di calcolare le quote.
- Incompatibilità per il controllo persona-prompt, dichiarate nel dizionario prima del controllo:
  - budget: «attento al prezzo» contro «spendere di più per la qualità», in entrambi i versi;
    «rapporto qualità prezzo» non contraddice nessuno dei due;
  - esperienza: principiante contro esperto, in entrambi i versi;
  - fase di vita: i livelli della composizione del nucleo (famiglia con figli, coppia, single)
    si escludono a vicenda; le altre incompatibilità si dichiarano voce per voce.

## 3. Soglie e scelta dei livelli (Fase 1.4 e Fase 3)

- Un livello è utilizzabile se ha almeno il 2% del volume del settore; il secondo livello di un
  elemento basta con almeno l'1%.
- Per ogni elemento si prendono i due livelli utilizzabili con più volume. Parità: più keyword,
  poi ordine alfabetico.
- Se per il budget esiste un solo livello utilizzabile, il secondo è il polo opposto («attento
  al prezzo» contro «disposto a spendere di più per la qualità») con la marca «da sintesi, non
  dalla domanda».
- Se un elemento non ha nessun livello al 2%: si usa il livello con più volume purché abbia
  almeno una keyword, con la marca «sotto soglia»; se non ne ha nessuno, la persona porta una
  frase neutra per quell'elemento con la marca «da sintesi, non dalla domanda».
- A = il livello più frequente in ogni elemento. B = A con il budget al secondo livello.
  C = A con il secondo livello nel primo, fra esperienza e fase di vita (in quest'ordine), che
  ne ha uno utilizzabile. Se nessuno dei due ne ha uno, C cambia la fase di vita con il secondo
  livello per volume, con la marca «sotto soglia».

## 4. Frasi (Fase 3)

- Italiano, cornice fissa e uguale per tutti: «Sono {fase di vita}. {esperienza con la
  categoria}. {atteggiamento verso il budget}.»
- Le frasi sono una tabella per livello (`config/cycle11_frasi.yaml`): la stessa formulazione
  per lo stesso livello in tutte le personas di un settore. L'esperienza nomina la categoria del
  settore in modo generico, senza prodotti posseduti.
- Forme neutre rispetto al genere: nessun aggettivo o participio che concordi con chi parla
  (niente «esperto/esperta», «disposto/disposta»); niente articoli che marchino il genere della
  persona.
- Lunghezza in token (tokenizer o200k_base di GPT) entro ±10% della media delle tre personas del
  settore. Per rispettarla si cambia la formulazione, non il livello.
- Traduzione inglese solo per la pagina; agli studi va solo l'italiano.
- Unione con il prompt (`config/cycle11_template.md`): «{persona} {prompt}», persona prima, uno
  spazio, poi il prompt, tutto nel messaggio utente; system prompt vuoto.

## 5. Controlli automatici (Fase 4)

a) Struttura identica (tre frasi, la prima comincia con «Sono»), lunghezza in token, assenza di
   brand (lessico del settore), di località (toponimi del ciclo 10) e di parole di genere o
   età. Se una persona fallisce, si riscrive una sola volta usando il livello successivo della
   tabella nell'elemento che fallisce.
b) Differenza: un diff a livello di frase fra le personas dello stesso settore. A e B devono
   differire solo nella terza frase; A e C solo nella frase dell'elemento previsto.
c) Compatibilità: per ognuno dei 20 prompt del settore si individuano con lo stesso dizionario
   i livelli presenti nel prompt; una coppia persona-prompt è in contraddizione se un livello del
   prompt è incompatibile (§2) con un livello della persona. Matrice in
   `results/cycle11/compatibilita_<settore>.csv`. Se una persona contraddice più del 10% dei
   prompt del suo settore (più di 2 su 20), si riscrive una sola volta con i livelli successivi
   nell'elemento in contraddizione; se resta oltre soglia si tiene e si segnala. Le coppie in
   contraddizione si segnano e non si escludono: l'analisi dello Studio 1 avrà anche una
   versione senza di esse.
d) Prova tecnica su GPT: stesso deployment del ciclo 10 (gpt-5.5, Responses API, strumento
   web_search, user_location Italia come nel ciclo 10, effort predefinito: nessun parametro di
   reasoning; ricerca non forzata). 12 personas × 2 prompt (i primi due approvati del settore),
   una chiamata ciascuna, 24 chiamate, ordine casuale con seed fisso. Tetto 8 dollari: stop se
   dopo 5 chiamate la proiezione supera 8 dollari, e comunque a 8 dollari spesi. Si registrano
   solo: rifiuti o risposte troncate (status diverso da completed o testo di rifiuto), cambi di
   lingua (risposta non in italiano, dalla quota di parole funzione italiane e inglesi), risposta
   che ripete la persona (una sequenza di 5 parole della persona nel testo) o la commenta
   (formule come «hai detto che», «visto che sei», «come mi hai detto», da rileggere a mano),
   errori. Nessuna misura di citazioni, query o brand. Grezzi in
   `data/raw/cycle11_personas_prova.jsonl`. Una persona si riscrive (stessa scelta di livelli,
   solo formulazione) solo se dà rifiuto o cambio di lingua in entrambe le chiamate.

## 6. Blocco (Fase 5)

SHA-256 di `config/cycle11_personas.yaml`, `config/cycle11_frasi.yaml` e
`config/cycle11_template.md` in `results/cycle11/personas_hash.txt`. Il blocco è provvisorio
fino alla lettura dell'autore; dopo, ogni modifica è una deviazione registrata.

## 7. Statistiche pubbliche (Fase 2)

Per ogni settore una fonte pubblica italiana o europea (ISTAT, Eurostat, IVASS o associazioni di
settore) sulla composizione degli acquirenti, con link, anno e dato rilevante, verificando che la
tabella esista. Tempo limitato: se una fonte non si trova in poco tempo, si scrive e si va
avanti. Nessun numero inventato. Serve solo come controllo di plausibilità, non sceglie livelli.

## 8. Pagina condivisa

Sezione «Buyer personas» dopo «Brands named in GPT answers» e prima di «Limits», in inglese, senza
toccare il testo esistente; cinque punti in fondo a «Limits». Nel testo: nessun nome di cancello,
«screening», ciclo, percorso di file, «Claude» o REDACTED; nessuna scadenza né costo; nessun
trattino lungo; nessun grassetto; frasi brevi; niente riassunto finale. Ogni numero della sezione
deve essere rintracciabile in un file di `results/cycle11`.
