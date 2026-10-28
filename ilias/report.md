# Findings report

Running log of findings about the Kulturpool datasets and the scripts in `ilias/`. New findings are appended to the log; the summary sections are kept current.

## Scope of the analysis

- 86 datasets in `data/full_records.tar.gz` (not tracked in git), 2,636,673 records in total (`data/datasets.csv`).
- Field-usage analysis only looks at the **first 3 records of each dataset** (`data/first_records/`), 255 records in total. `erdstallzentrum-tollet-unterstetten-core` has 1 record and `kunstuni-linz-twinit` has 2 in the sample.
- `compare_fields.py` only reads the keys on four levels: record root, `content`, `content.isShownBy`, `content.aggregatedCHO`. Deeper nesting (for example inside `creator` objects) is not analysed.
- Consequence: a field that first appears after record 3 of a dataset is missed, so "used by N datasets" counts are lower bounds.

## Files

| File | Content |
|---|---|
| `data/first_records/*_first_records.json` | First 3 records of every dataset (written by `intro.py`) |
| `data/compared_fields.csv` | One row per sampled record, one column per field path, `1` = field filled, `0` = missing or empty |
| `data/mapping_main_classes.csv` | Feldbezeichnung, EDM Feld, JSON Key and JSON Key Path for the Hauptklassen of the mapping template |
| `data/bk_terms.csv` | Flat list of all Basisklassifikation terms: `term` (German label), `uri` (written by `fetch_bk.py`) |
| `data/first_records_100/*_first_records.json` | First 100 records of every dataset (written by `sample_records.py`, 93 MB, 8,600 records) |
| `data/time_values.csv` | Distinct time strings of the 100-record sample per field and shape, with record and dataset counts (`time_values.py`) |
| `data/time_mapping.csv` | Each distinct time string with `begin_year`, `end_year`, `iso`, `method`, `score`, `source_uri`, `qualifier` (`run_time_mapping.py`) |
| `data/time_review.csv` | Time strings the tool could not map, with PeriodO and ChronOntology candidates and empty `begin_year`/`end_year`/`decision` columns to fill in |
| `data/periodo_periods.csv` | German and English labels of PeriodO periods with start/stop year (`build_period_table.py`) |
| `data/periods.csv` | Reviewed periods and manual decisions (52 labels), written by `import_periods.py` from `periods_proposal.csv`; applied before the rules |
| `data/periods_proposal.csv` | Proposed dates for the 86 unmapped time strings, to be reviewed before they go into `periods.csv` |
| `data/time_api_check.csv` | Comparison of the mapped years with `dateMin`/`dateMax` of the Kulturpool search index (`check_dates_against_api.py`) |

## Field usage of the main-class fields (sample of 255 records)

Fields from `mapping_main_classes.csv` that were not present in the first two datasets and are now confirmed in the data:

| Path | Records | Datasets |
|---|---|---|
| `content.aggregatedCHO.subject` | 141 | 52 |
| `content.aggregatedCHO.spatial` | 110 | 43 |
| `content.aggregatedCHO.temporal` | 82 | 30 |
| `content.aggregatedCHO.date` | 66 | 27 |
| `content.aggregatedCHO.coverage` | 10 | 4 |
| `content.aggregatedCHO.alternative` | 6 | 2 |

All 25 JSON Key Paths in `mapping_main_classes.csv` exist as columns in `compared_fields.csv`.

## Findings log

### 2026-10-27

1. **`boku-larchiv-core` duplicates the record structure.** The CHO-level fields (`title`, `subject`, `spatial`, `creator`, `extent`, `format`, `medium`, `isPartOf`, `identifier`, `edmType`) appear both directly under `content` and inside `content.aggregatedCHO`. In addition, `content.aggregatedCHO` itself contains the aggregation-level keys (`aggregatedCHO`, `dataProvider`, `edmRights`, `isShownAt`, `isShownBy`, `provider`, `id`, `type`), i.e. a nested copy of the aggregation. This is where the odd paths `content.aggregatedCHO.aggregatedCHO`, `content.title`, `content.spatial` etc. in `compared_fields.csv` come from (3 records, this dataset only). The mapping paths stay valid for this dataset because `content.aggregatedCHO.<key>` exists too.
Check: 
   - https://api.kulturpool.at/v2/object?id=8ca72eb4-c312-4b60-a22b-369f6b876930
   - https://api.kulturpool.at/v2/search?q=*&filter_by=dataProvider:=Archiv%20%C3%96sterreichischer%20Landschaftsarchitektur%20an%20der%20BOKU%20University&per_page=250&page=1
   - https://kulturpool.at/objekte/8ca72eb4-c312-4b60-a22b-369f6b876930
1. **`ars-electronica` fills `content.isShownBy.title`** (a file name such as `Synth Cycles Poster (SynthCycles_Poster.png)`) and in one record `content.isShownBy.description`. The web resource carries titles and descriptions, which the mapping template (Digitale Ressource: only `dc:type`, `dc:creator`, `dc:rights`, `edm:rights`, `dcterms:extent`) does not list.
2. **Empty values were counted as present.** In the sample, `content.hasView` is an empty list in 166 records and `src_id` an empty string in 15. `compare_fields.py` used `notna()`, so these counted as used (`hasView` 251 instead of 85, `src_id` 255 instead of 240). The script now treats `[]`, `{}` and `""` as not filled. Only these two fields have empty values in the sample.
3. **Fields outside the main-class mapping that datasets use** (records in the sample): `content.aggregatedCHO.contributor` 37, `content.intermediateProvider` 27, `content.aggregatedCHO.format` 15, `content.aggregatedCHO.issued` 10, `content.aggregatedCHO.hasType` 9, `content.aggregatedCHO.isReferencedBy` 9, `content.aggregatedCHO.sameAs` 6, `content.aggregatedCHO.source` 6, `content.aggregatedCHO.relation` 3, `content.aggregatedCHO.isRelatedTo` 3, `content.dcRights` 32, `content.object` 109, `content.isShownBy.hasService` 77, `content.isShownBy.isReferencedBy` 65, `content.isShownBy.edmRights` 54, `content.isShownBy.format` 51, `content.isShownBy.dcType` 30.
4. **Only 2 datasets in the sample are short**: `erdstallzentrum-tollet-unterstetten-core` (1 record) and `kunstuni-linz-twinit` (2 records); all others contribute 3 records.
5. **Full scan abandoned.** A scan of all 2.6M records was started and stopped on request; no results from it are used anywhere in this report.

## Subject vocabularies with a URI for each term

Links to the vocabularies only.

- GND (subject terms): https://www.dnb.de/gnd
- LCSH: https://id.loc.gov/authorities/subjects.html
- LCGFT: https://id.loc.gov/authorities/genreForms.html
- FAST: https://www.oclc.org/research/areas/data-science/fast.html
- RAMEAU: https://rameau.bnf.fr/
- BNE subject headings: https://datos.bne.es/
- CERL Thesaurus: https://thesaurus.cerl.org/
- DDC: http://dewey.info/
- UDC: https://udcdata.info/
- RVK: https://rvk.uni-regensburg.de/
- Basisklassifikation (BK): https://uri.gbv.de/terminology/bk/
- Thema: https://www.editeur.org/151/Thema/
- Iconclass: https://iconclass.org/
- MeSH: https://www.nlm.nih.gov/mesh/
- Getty AAT: https://www.getty.edu/research/tools/vocabularies/aat/
- Getty TGN: https://www.getty.edu/research/tools/vocabularies/tgn/
- Getty ULAN: https://www.getty.edu/research/tools/vocabularies/ulan/
- STW: https://zbw.eu/stw/
- TheSoz: https://www.gesis.org/en/services/research/thesauri-and-classifications/social-science-thesaurus
- AGROVOC: https://www.fao.org/agrovoc/
- NALT: https://lod.nal.usda.gov/
- UNESCO Thesaurus: https://vocabularies.unesco.org/browser/thesaurus/en/
- EuroVoc: https://eurovoc.europa.eu/

## Subject vocabularies with German terminology and a URI for each term

Links to the vocabularies only.

- GND (subject terms): https://www.dnb.de/gnd
- RVK: https://rvk.uni-regensburg.de/
- Basisklassifikation (BK): https://uri.gbv.de/terminology/bk/
- STW: https://zbw.eu/stw/
- TheSoz: https://www.gesis.org/en/services/research/thesauri-and-classifications/social-science-thesaurus
- EuroVoc: https://eurovoc.europa.eu/
- AGROVOC: https://www.fao.org/agrovoc/
- GEMET: https://www.eionet.europa.eu/gemet/
- Getty AAT: https://www.getty.edu/research/tools/vocabularies/aat/
- DDC: http://dewey.info/
- UDC: https://udcdata.info/
- Thema: https://www.editeur.org/151/Thema/
- Iconclass: https://iconclass.org/

## Basisklassifikation term list (`fetch_bk.py`)

- `fetch_bk.py` crawls the BK from `https://uri.gbv.de/terminology/bk/<notation>?format=jskos`, starting at the 5 top classes (DANTE `voc/top`) and following `narrower`. It writes `data/bk_terms.csv` (columns `term`, `uri`, sorted by notation, relations dropped).
- Result: 2140 terms, all with a German `prefLabel`, URIs unique. The TIB terminology service lists 2142 individuals; the 2 extra are the scheme URI itself and `bk/Not_153`, which is not a class.
- The bulk JSKOS downloads that BARTOC lists for BK (`api.dante.gbv.de/voc/concepts?...&download=json`) return an empty list, hence the crawl.
- No `term_en` column, by decision. English labels do exist for at least some classes (`bk/81.64`: "Teaching process: other"), but not for all (`bk/5` has German only). Coverage was not measured. BARTOC still lists `languages: de` only.

## Time mapping (`time_mapping.py`)

Tool that maps time descriptions to years and ISO 8601 / EDTF. Sample: first 100 records per dataset (86 datasets, 8,600 records), by explicit decision a larger sample than the first-3 sample above; no full scan.

- **Conventions.** `begin_year`/`end_year` use historical counting (1 BCE = -1, no year 0). The `iso` string uses astronomical years (1 BCE = `0000`, 2 BCE = `-0001`). `~` (approximate), `?` (uncertain) and `..` (open end) are EDTF, not base ISO 8601. Source values with a minus sign (`-0015 - 0230`, `(-15-476)`) are read as historical years, not as astronomical years; this is an assumption. Parts of a century: Anfang = years 1-33, Mitte = 34-66, Ende = 67-100, halves 1-50/51-100, thirds and quarters analogous.
- **Time strings in the sample.** 2,272 distinct values in `temporal`, `date` and `issued` (2,472 with `coverage`, where only values with a digit or a TimeSpan are kept). Values appear as plain strings, `{"@value","@language"}` objects and TimeSpan objects.
- **Result by method** (distinct strings / records): rule 2,114 / 5,056; timespan 60 / 86; no_date 7 / 201 ("ohne Datierung", "undatiert", "Unbekannt"); unmapped 87 / 430 (7.4% of the records). 121 results are marked approximate, 20 uncertain. The rules cover ISO dates and intervals, `dd.mm.yyyy`, month dates, ranges with `n. Chr.`/`v. Chr.`, centuries and parts of centuries, decades, open ends (`nach`, `ab`, `vor`), date lists and named periods with a range in brackets (`Römische Kaiserzeit (-15-476)`).
- **Unmapped strings** (`time_review.csv`, 86 rows): almost all are named periods or styles (Late Middle Ages, Neolithikum, antik, Spätbarock, Hochbarock, Realismus, Römisches Reich, ...), plus a few odd date lists. Not implemented yet: the embedding step for spelling and language variants of table entries, and the LLM step.
- **Named periods have conflicting definitions in the gazetteers.** PeriodO has 11,355 German/English labels. "Römisches Reich" has one entry (-28/499), but "Roman Empire" has five different intervals (-28/499, -27/395, -27/476, -25/395 and others); ChronOntology gives -753/476 for "Römisches Reich". "Late Middle Ages" has 8 different intervals between 1001 and 1565, "Neolithikum" ranges from -10000 to -2000 in ChronOntology. A single PeriodO hit is therefore not treated as consensus: only rows in `periods.csv` are applied automatically, PeriodO and ChronOntology only appear as candidates in the review file.
- **Check against the search index.** The Kulturpool search index stores `dateMin`/`dateMax` (Unix seconds). For 2,169 sample records with a parsable `date`, 2,059 agree within one year (95%). Of the 110 differences, 33 are ranges like `1900, ca- 1930, ca` where the index keeps only the first year; most others are different conventions: the index maps "Mitte 19. Jh." or "2. Hälfte 19. Jh." to the whole century (1800-1899) and gives `um 1900` as a single year, while the tool returns the stated part or the stated range. The index's `date` field was not used as ground truth.
- **Not done yet:** hand-labelled gold set with precision per method; rows in `periods.csv`. The tests (`test_time_mapping.py`, `python3 -m unittest test_time_mapping`) use `unittest` because `pytest` is not installed.

### Proposal for the unmapped time strings (`data/periods_proposal.csv`)

All 86 rows of `time_review.csv` have a `kind`: 35 `period` (proposed `begin_year`/`end_year`, `confidence`, `basis`, `source_uri`), 35 `rule_gap` (the parser should be extended, no decision needed), 15 `needs_decision`, 1 `no_date`.

- Confidence of the 35 period rows: 1 high (Antoninisch 138-192, both gazetteers agree), 16 medium (taken from or close to PeriodO/ChronOntology), 17 low (no gazetteer entry: Spätgotik, the Baroque phases, Klassizismus, Romantik, Realismus, Historismus, Jugendstil, Expressionismus and similar; proposed from common art-historical dating, not from a cited source), 1 without a proposal (`Modern`, six conflicting PeriodO definitions).
- Choices that differ from the gazetteers: Biedermeier 1815-1848 (Austrian convention; ChronOntology has 1820-1859), `Römisches Reich` set to -27/476 like `Roman Empire` for consistency (PeriodO -28/499, ChronOntology -753/476), Eisenzeit -800/0 (ChronOntology majority).
- None of these rows is in `periods.csv` yet; the proposal has not been reviewed.

### After the review of the proposal

- `import_periods.py` copied the 35 period rows and the 15 manual decisions of `periods_proposal.csv` into `periods.csv` (52 labels; "Minoan | Minoisch" became two entries). `Modern` was set to 1900 and onward (open end) by decision; the only evidence is the `nhm-wien-divina` dataset (6 records, objects like matchboxes and cigarette cases).
- The parser now handles the 35 gap rows: `X bis Y`, date lists with abbreviated days (`01., 03., 04.10.1987`, `08.-18.08.1987`), masked days (`1933.03.xx`), hedging words (`vermutlich`, `ev.`), index prefixes (`01: 1952; 02: 1951`) and a date or year inside other text (`Poststempel: Augsburg, 13.03.1978`, method `rule_embedded`, score 0.6, only if all numbers in the text are the same year). Reviewed entries in `periods.csv` match the unchanged text and win over the rules.
- Result on the 100-record sample (distinct strings / records): rule 2,143 / 5,088; table 50 / 385; timespan 60 / 86; rule_embedded 6 / 6; no_date 8 / 202; unmapped 0 / 0 (before `Modern` was decided: 1 / 6).
- Notes on the decisions: `-60000000` now has begin and end -60000000 (a single year in EDTF long-year form, `Y-60000000`); this is probably a geological age and was entered as a point. `um 1720 und Ende 18. Jh.` ends in 1800, like the century rules. "1924 bzw. 1927" is the interval 1924/1927 as decided.
