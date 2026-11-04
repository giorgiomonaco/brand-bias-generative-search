# Replication package (anonymous version for review)

Data and code for the two studies in the paper: an audit of three generative search engines on Italian
commercial prompts (Study 1) and a controlled ranking experiment on product pages (Study 2).

Every figure and table in the paper can be rebuilt from the files in this repository with no API calls and
no keys. The collection code is included for transparency; running it again requires your own API
credentials and will not return the same answers, since the engines change over time.

## Setup

Python 3.10 or later.

```
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

The analysis scripts were checked with Python 3.10 and 3.12; the rebuilt outputs match the numbers in the paper.

## Layout

```
study1_audit/
  config/        prompts, buyer personas, brand popularity, brand-to-domain table, brand-name table
  data/          per-answer table (calls.json.gz), brand table (P1_brand.csv), GPT search actions, source checks
  figures/       one folder per group of figures; each script writes to a fig/ folder next to it
  stats/         numbers reported in the text of the Study 1 results
  processing/    brand extraction and source matching on the raw answers
  collection/    API calls (requires credentials)
study2_experiment/
  materials/     questions, target pages, signatures, invented names, page texts (pagine/), stimuli (stimoli/)
  data/raw/      every ranking returned by the four models (JSONL, gzip)
  data/scores_main/   per-ranking scores of the main collection and the resulting contrasts
  data/recognition/   answers to the brand-recognition check on the neutralised pages
  analysis/      Figure 7, contrasts of the real-product arms, recognition check
  code/          stimulus construction, collection and main analysis (part2_conf, part2_v3, part2_v4, recognition)
appendix_tables/ prompt, persona and Study 2 tables of the appendix
```

## Figures and tables

Run each command from the folder of the script, unless a path is given. Figure numbers refer to the submitted PDF.

| Paper | Script | Input |
|---|---|---|
| Fig. 1 | `study1_audit/figures/fig1/pipeline.py` | none (diagram) |
| Fig. 2, Fig. D.3, Fig. D.4, Tab. D.2 | `study1_audit/figures/search_on_off/slope_on_off.py`, then `fig_search.py` | `data/P1_brand.csv` |
| Fig. 3, Tab. D.3 | `study1_audit/figures/fig_core/mention_citation_norm.py` | `data/P1_brand.csv` |
| Fig. D.1, Fig. D.2 | `study1_audit/figures/fig_core/mention_citation.py` | `data/P1_brand.csv` |
| Fig. 4 | `study1_audit/figures/fig_extra/fig_h2.py` | `data/h2/` |
| Fig. 5 | `study1_audit/figures/fig_core/first_query.py` | `data/gpt_azioni.json`, `data/alias_lookup.json` |
| Fig. 6, Fig. D.7 to D.10 | `study1_audit/figures/fig_extra/persona_quintiles.py` | `data/calls.json.gz`, `data/P1_brand.csv` |
| Fig. D.5 | `study1_audit/figures/fig_extra/fig_source_match.py` | `data/mention_source_classification_v6.csv.gz` |
| Fig. D.6 | `study1_audit/figures/persona_pooled/persona_pooled.py`, then `fig_persona_slopes.py` | `data/calls.json.gz`, `data/persona_pendenze_seed1014.json` |
| Study 1 numbers in the text | `study1_audit/stats/*.py` (see the header of each script) | `data/`, `config/domini_v2B.csv` |
| Tab. 2, Tab. E.1, robustness subsets | `python study2_experiment/code/part2_v4/analisi_v4.py study2_experiment/data/scores_main` (writes `risultati/risultati_v4.json`) | `data/scores_main/` |
| Real-product arms (contrasts in the text and appendix) | `study2_experiment/analysis/analisi_bracci_15q.py` | `data/raw/` |
| Fig. 7 | `study2_experiment/analysis/carica.py` (writes `data/rankings.csv`), then `fig_study2.py` | `data/raw/` |
| Neutralisation check, Tab. B.2 (popularity distances, recognition) | `study2_experiment/analysis/misure_identita.py` | `data/recognition/`, `data/raw/main/`, `materials/` |
| Neutralisation check (Spearman with the true-brand effect, effects by recognition) | `study2_experiment/analysis/recognition_vs_effects.py`, after `misure_identita.py` | `data/scores_main/`, `analysis/misure_identita.json` |
| Tab. A.1, A.2, B.1 | `appendix_tables/make_tables.py` | `study1_audit/config/`, `study2_experiment/materials/` |

`study1_audit/stats/build_p1.py` rebuilds `data/P1_brand.csv` from `data/calls.json.gz` and
`config/domini_v2B.csv` (same values; row order may differ).

## Data

Most code, file and field names are in Italian, because the study runs on the Italian market. The glossary below
covers the names used in the data.

**Sectors** (`settore`, `sector`): `assicurazioni` insurance, `moda_beauty` fashion and beauty, `sport` sport,
`viaggi` travel.

**Engines** (`motore`, `engine`): `gpt` gpt-5.5, `gemini` / `gemini_vertex` gemini-3.6-flash, `perplexity`
perplexity/sonar, `deepseek` deepseek-v3.2 (Study 2 only).

### Study 1

`data/calls.json.gz` holds one record per answer (19,200: 80 prompts × 4 persona levels × search on/off × 10
repetitions × 3 engines) under `rows`, and the brand-to-official-domain table under `dominio`. List fields are
stored as Python literals in strings.

| field | meaning |
|---|---|
| `engine`, `sector`, `prompt_id` | engine, sector and prompt (prompt text in `config/main_study_prompts.csv`) |
| `level` | persona: `nessuna` no persona context, `A` Baseline persona (A), `B` Price variant (B), `C` Profile variant (C); texts in `config/cycle11_personas.yaml` |
| `search` | search on (`True`) or off (`False`) |
| `search_performed` | whether the engine actually searched |
| `queries` | search queries executed by the engine |
| `fonti_s` | domains of the sources returned with the answer |
| `B`, `brand_ord` | brands mentioned in the answer (normalised keys), and the same in order of first appearance |
| `ha_estrazione` | brand extraction available for the answer |
| `chars` | length of the answer in characters |

`data/P1_brand.csv`: one row per brand × engine × sector × search setting. `notorieta_log10` is brand popularity
(log10 of mean monthly search volume in Italy, DataForSEO, from `config/main_notorieta.csv`); `risposte` answers,
`menzioni` answers that mention the brand, `tasso_menzione` mention rate, `tasso_citazione` citation rate (the
brand's official site is among the sources), `citazioni_su_menzioni` citation rate among answers that mention it.
The brand set is one per sector: brands mentioned in at least 5 answers by at least one engine.

Also in `data/`: `gpt_azioni.json` (ordered search actions of GPT), `alias_lookup.json` (brand aliases),
`mention_source_classification_v6.csv.gz` (for each mention with search on, whether the brand name appears in the
returned sources), `h2/` (search-query and answer similarity by popularity band, precomputed from the answers
with the embedding model `bge-m3`), `persona_pendenze_seed1014.json` (per-cell popularity slopes by persona).

The full text of the Study 1 answers is not included in this version because of its size (about 550 MB); it will
be deposited in a public archive with the final version.

### Study 2

`data/raw/<arm>/studio_<engine>.jsonl.gz`: one record per call, with the order of the pages (`ordine`), the target
page (`bersaglio`), the signature (`firma`), the text version (`testo`), the order index (`j`, one of 10 Williams
orders), the repetition (`rip`) and the full model response (`response_text`). `main` holds the five signatures
crossed with the four texts; `real_product_arms` and `real_product_arms_extra` hold the better-known and
less-known brands with their own real product.

| `firma` | label in the paper |
|---|---|
| `REALE` | Original brand with real product |
| `PIU_NOTO_REALE` | Better known with real product |
| `MENO_NOTO_REALE` | Less known with real product |
| `BRAND` | Original brand with invented product |
| `PIU_NOTO` | Better known with invented product |
| `MENO_NOTO` | Less known with invented product |
| `INVENTATO` | Invented brand |

`testo`: `ORIGINALE` original, `STRUTTURA` structure, `FLUENCY` fluency, `AUTHORITATIVE` authoritative.

The contrasts in `risultati_v4.json` keep the names of the preregistered protocol. Correspondence with Table 2:
`H1` = H4a, `H2a` = H4b, `H2b` = H4c (the paper reports the full difference, twice `H2b`; the p-value is the same),
`H2b'` = H4d, `H2c` = H4e, `H3` = H5a, `H4` = H5b. Scores are 6 minus the position of the target page, so a
positive contrast means the page moves up.

`materials/`: `selezione.json` (questions, the five pages per question and candidate brands), `scelte.json`
(target and signature brands per question), `inventati.json` (invented names), `prodotti_extra.json` (real
products of the added arm), `pagine/` (extracted text and metadata of each product page; the raw HTML is not
redistributed), `stimoli/` (the neutralised target page and its rewrites, per question), `testi/` (page texts as
sent to the models).

## License

To be added with the final version.
