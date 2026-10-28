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
| `data/periods.csv` | Reviewed periods and manual decisions (86 labels), written by `import_periods.py` from `periods_proposal.csv`; applied before the rules |
| `data/periods_proposal.csv` | Proposed dates for the 86 unmapped time strings, to be reviewed before they go into `periods.csv` |
| `data/time_api_check.csv` | Comparison of the mapped years with `dateMin`/`dateMax` of the Kulturpool search index (`check_dates_against_api.py`) |
| `suggest_times.py` | End tool: reads new records and writes a CSV with suggested years and ISO 8601 / EDTF for every time value |
| `data/time_lookup_final.csv` | Final lookup table: every distinct time value of the three samples (records 1-300 per dataset) with the suggested years and ISO value, status, record and dataset counts (`build_time_lookup.py`) |
| `data/time_terms_verbose.csv` | Only the verbal time terms (no digits) with their years and ISO value, plus the words treated as no date (`build_verbose_terms.py`) |
| `data/records_101_200/*_first_records.json` | Records 101-200 of every dataset (second sample, 99 MB, `sample_records.py --second`) |
| `data/time_values_sample2.csv` | Distinct time strings of the second sample with the mapping result and a `new` flag (not in sample 1) (`check_sample.py`) |
| `data/records_201_300/*_first_records.json` | Records 201-300 of every dataset (third sample, 82 MB, `sample_records.py --third`, ignored by git) |
| `data/time_values_sample3.csv` | Distinct time strings of the third sample with the mapping result and a `new` flag (not in samples 1 and 2) (`check_sample.py --third`) |

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

### Second sample (records 101-200 per dataset)

Test of how well the rules and `periods.csv` (tuned on records 1-100) generalise. 86 datasets, about 8,600 records; 2,166 distinct field/value pairs, of which 1,483 are new compared with sample 1.

- Result for the new values (distinct / records): rule 1,400 / 1,969; timespan 50 / 52; rule_embedded 7 / 8; unmapped 26 / 109. So 1.8% of the new distinct values and 1.9% of all records in this sample are unmapped. 65 of the 109 unmapped records are one geological string from one dataset.
- The 25 distinct unmapped strings fall into four groups:
  - Named periods missing from `periods.csv` (13): Severisch, Hadrianisch, Constantinisch, Soldatenkaiser, Roman Provincial | Provinzialrömisch, Neuromantik, Jahrhundertwende, Early Middle Ages, Late Neolithic | Spätneolithisch, and the Greek pottery periods Geometric, Middle Geometric, Cretan, Attic.
  - Not a time value: `Geschichte` (16 records, 2 datasets), `Sozialgeschichte` (2), `div.`; these are subject words in the `temporal` field.
  - Geological time: `Phanerozoic | Cenozoic | Neogene | Miocene (Karpatium bis Unter-Badenium)` (65 records), same kind of value as `-60000000`.
  - Rule gaps: `2 Hälfte des 19. Jhdt.`, `-125000 - -19650` (years with six digits), `zwischen 1950 und 1997`, serial volumes (`1 (1914)-5 (1917)`, `1867/70(1872) - ...`), two years in one text (`1967\nAngabe laut Verpackung: 1972`, `1906, ca. 1970 (Eintragungen)`), `Anfang 18. Jh. / Ergänzungen 20. Jh.`.
- Silent errors found by checking the mapped values (not unmapped): `1809-9999` is mapped to 1809/9999 although 9999 is a placeholder for an unknown end; `[1809?]` loses its uncertainty marker (`1809` instead of `1809?`) because the `?` sits inside the brackets. Not fixed yet.
- Compared with sample 1 the share of unmapped strings is lower (1.8% of new distinct values, against 3.8% before the review), but only because the review covered the sample 1 period names; new period names still appear in every new sample.

### Proposal for the period names of the second sample

`periods_proposal.csv` has 13 more `period` rows (appended, not yet in `periods.csv`): Severisch 193/235 and Hadrianisch 117/138 (high: both gazetteers agree), Geometric -900/-700 (high: Getty AAT, PeriodO and ChronOntology agree), 6 medium (Soldatenkaiser 235/284, Constantinisch 306/337, Early Middle Ages 500/1050, Late Neolithic -4000/-3000, Cretan -3500/-1050, Middle Geometric -850/-750) and 4 low without a dated source (Roman Provincial, Attic, Neuromantik, Jahrhundertwende).
- Nine of the names (Minoan, Early/Middle Minoan, Cretan, Late Neolithic, Attic, Geometric, Middle Geometric, Roman Provincial) are Getty AAT TimeSpans in the data (`content.aggregatedCHO.temporal[].id`, `http://vocab.getty.edu/aat/...`). The AAT scope notes confirm several dates (Minoan 3500-1050 BCE, Geometric 900-700 BCE) but give none for Attic and Roman Provincial.
- The 13 proposals were accepted as they are and imported (`periods.csv` now has 72 labels). Second sample after the import: unmapped 13 distinct values / 93 records (before 26 / 109); 12 distinct strings remain: the geological string (65 records), `Geschichte` and `Sozialgeschichte` (18), `div.`, and 8 parser gaps (`2 Hälfte des 19. Jhdt.`, `-125000 - -19650`, `zwischen 1950 und 1997`, serial volumes, texts with two years, `Anfang 18. Jh. / Ergänzungen 20. Jh.`).

### Fixes after the second sample

- No date: `Geschichte`, `Sozialgeschichte`, `div.` and a plain `9999` are treated as "no date".
- Parser: `2 Hälfte des 19. Jhdt.`, six-digit years (`-125000 - -19650` gives `Y-125000/Y-19650`), `zwischen X und Y` (also inside text), serial volumes with years in brackets (`1 (1914)-5 (1917)`, earliest to latest year, method `rule_embedded`), texts with two different years (interval from the earliest to the latest year, `rule_embedded`, score 0.5), `, ca.` after a number no longer removes the comma (`1906, ca. 1970`), and additions are ignored (`Anfang 18. Jh. / Ergänzungen 20. Jh.` gives 1701/1733).
- Silent errors: an end year of `9999` is an open end (`1809-9999` gives `1809/..`); `[1809?]` keeps its uncertainty marker. Side effect: `[1.]1856 - 2.1858[?]` now also gets `?` markers (`1856?/1858?`).
- Assumptions made without a decision from you: for two years in one text and for serial volumes the interval runs from the earliest to the latest year; `ca.` in `1906, ca. 1970` marks both ends as approximate.
- Second sample after the fixes: new values unmapped 1 distinct / 65 records (only the geological string `Phanerozoic | Cenozoic | Neogene | Miocene (...)`); sample 1 is unchanged except the one `?` marker above.

### Geological string

`Phanerozoic | Cenozoic | Neogene | Miocene (Karpatium bis Unter-Badenium)` (65 records, `nhm-wien-divina`, fossil specimens) is mapped to -17,200,000/-15,032,000 (`Y-17200000/Y-15032000`). Only the most specific label (`Miocene (Karpatium bis Unter-Badenium)`) is in `periods.csv`; the broader labels (Phanerozoic, Cenozoic, Neogene) are deliberately not, because they would get the same interval.
- End 15.032 Ma is the end of the Early (Unter-) Badenian (Hohenegger, Ćorić, Wagreich 2014, Geologica Carpathica 65(1), 55-66). The Karpatian/Badenian boundary in the same paper is 16.303 Ma.
- The begin, about 17.2 Ma (start of the Karpatian), is from memory and **not verified**: the paper and the searches did not give a start date for the Karpatian. Confidence low until checked.
- Years are counted from the year 0, not from the present; the difference of about 2,000 years does not matter at this scale.
- With this row nothing is unmapped any more in either sample.

### Third sample (records 201-300 per dataset)

2,132 distinct field/value pairs, 1,367 new compared with samples 1 and 2 (`check_sample.py --third`; this script replaces `check_second_sample.py`).

- New values (distinct / records): rule 1,301 / 1,558; timespan 36 / 40; rule_embedded 14 / 14; unmapped 16 / 20 (1.2% of the new distinct values).
- Trend of new period names that were missing from the table: about 35 (sample 1, reviewed), 13 (sample 2), 9 (sample 3): Late Minoan | Spätminoisch, Spätklassizismus, African | Afrikanisch, Cypriote | Zyprisch, Frühchristlich, Frühmittelalterlich, Neolithic | Neolithisch, Roman Imperial | Römische Kaiserzeit, and `Realimus` (typo of Realismus, record from Belvedere). The number is falling but not zero.
- Other unmapped strings: two-digit years (`09.09.01` and `28.06.01`, Wien Museum postcards of an actor who lived 1858-1910, so 1901; `Poststempel: Anger, 6.2.69` is 1969), masked months (`18##-02`, `18##-10`, `18##-11`) and `-195000000` (an ammonite, geological like `-60000000`).
- Wrong or imprecise results among the mapped values (checked by hand, not fixed yet): `um 1730/40` is mapped to `1730~/0040~` (abbreviated end year, begin after end); `Jänner 1909` becomes `1909` because `Jänner` is missing in the month list; `1. Juni 1995` becomes `1995`; `1927-01-xx` becomes `1927`; `23.09.1980, 24.09.1980; 02.-26.09.1980` becomes `1980` because `;` is not accepted in date lists; `1920-1960 ca..` (double dot) gets score 0.5 as embedded text.

### Fixes and proposals after the third sample

- Fixed (all checked against the three samples, nothing else changed): abbreviated end years (`um 1730/40` gives `1730~/1740~`, `1927-28`, `[1915/18]`, `1660/70`, `1996-06-08/09` gives `1996-06-08/1996-06-09`), `Jänner`, `1. Juni 1995`, `1927-01-xx`, `;` in date lists, double dot after `ca.`.
- Found while checking the old results: before the fix `[1915/18]` and `1660/70` were mapped to `1915/0018` and `1660/0070`, and dates with placeholder parts such as `1430-99-99` or `1907-94-21` were accepted as ISO dates. Months above 12 and days above 31 are now rejected; the placeholder dates are mapped to the year (`rule_embedded`).
- 9 proposals appended to `periods_proposal.csv` (not yet imported): Late Minoan -1600/-1050, Spätklassizismus 1810/1850 (low), Cypriote -2300/-1050 (Getty AAT), Frühchristlich 175/625, Frühmittelalterlich 500/1050, Neolithic -5500/-2200, Roman Imperial -27/476, Realimus 1840/1880 (typo of Realismus, low), and `African | Afrikanisch` as `no_date` (a cultural origin, not a date).
- Masked years (`18##-02`, `18##-10`, `18##-11`, `19??`) now map to the whole century (1800/1899), month and day ignored, as decided before for `18##-4`. `clean()` no longer reads the `??` of `19??` as an uncertainty marker.
- Two-digit years (`09.09.01`, `28.06.01`, `Poststempel: Anger, 6.2.69`) are still unmapped. Example `09.09.01`: Wien Museum postcard (record `37f590fe-90f0-4288-a634-552a32acacda`, `date` = `["09.09.01", "1893"]`, dcType "gelaufen" = circulated, title "Josef Kainz (1858-1910) als König Astolf"). The record has two dates with different meanings: `1893` is probably the date of the role or photo, `09.09.01` the date the card was sent (1901). A rule "two-digit year below 26 is the 2000s" would give 2001 here, which is impossible (Kainz died in 1910).
- Two-digit years (`dd.mm.yy`, `d.m.yy`) are read as 19yy, by decision (`09.09.01` gives `1901-09-09`, `28.06.01` gives `1901-06-28`, `Poststempel: Anger, 6.2.69` gives `1969-02-06`). This is an assumption about the collections seen (Wien Museum postcards, Jägerstätter letters); it would be wrong for two-digit years in the 2000s. No change in samples 1 and 2.
- Third sample after all fixes: 10 distinct unmapped strings, nine of them the period names waiting for review (`Late Minoan`, `Spätklassizismus`, `African`, `Cypriote`, `Frühchristlich`, `Frühmittelalterlich`, `Neolithic`, `Realimus`, `Roman Imperial`) and `-195000000`.
- The 9 proposals of the third sample were accepted and imported (`periods.csv` now has 86 labels); `African | Afrikanisch` is treated as no date (`african`, `afrikanisch` added to the no-date words). `-195000000` (ammonite) is the single year -195,000,000 by decision (`Y-195000000`).
- After this all three samples (about 25,800 records) map completely: no unmapped string in sample 1, 2 or 3. Third sample, new values: rule 1,306 distinct, rule_embedded 15, table 9, timespan 36, no_date 1.

## Tool for new records (`suggest_times.py`)

Usage: `python3 ilias/suggest_times.py INPUT [-o time_suggestions.csv] [--online]`. INPUT is a `.jsonl` or `.json` file (list of records), a `.tar.gz` with such files, or a folder. It reads `temporal`, `date`, `issued` and `coverage` under `content.aggregatedCHO` (record format of `full_records.tar.gz`). Needs `data/periods.csv` (reviewed periods, 86 labels) and optionally `data/periodo_periods.csv`; `--online` also asks iDAI.chronontology for periods it cannot map.

- **Output**: one row per record and time value, with `record_id`, `dataset`, `field`, `value`, `begin_year`, `end_year` (historical years, BCE negative), `iso` (ISO 8601 / EDTF, astronomical years), `method`, `score`, `qualifier`, `source_uri`, `status`, `note`, `candidates`.
- **status**: `ok` (rule, reviewed table, existing begin/end of a TimeSpan, or "no date", score 0.8 or higher), `check` (weaker suggestion: a date inside other text, or a similar known period name such as `Spaetbarock` for `Spätbarock`), `unmapped` (no suggestion; `candidates` lists PeriodO definitions, with `--online` also ChronOntology).
- **Test on records the rules had never seen** (records 301-400 of every dataset, 7,105 records, 5,381 time values, 2,110 distinct): ok 5,315 (98.8%), check 21 (0.4%), unmapped 45 (0.8%). The unmapped strings are mostly period names missing from the table (`Hallstattzeit` 12 records, `Spätromantik`, `Manierismus`, `Domitianisch`, `Archaic | Archaisch`, `HA C`), the event name `Lichtermeer` (16 records), geological ranges (`-358000000 - -66000000`, `-201000000`) and a few malformed values (`1. Häfte 18. Jh. (?)`, `Wende 15./16. Jahrhundert`, a serial number). `--online` finds candidate dates for `Hallstattzeit` (-800/-450, -750/-450), `HA C`, `Domitianisch` (81/96) and `Archaic`.
- **Checked rows to look at**: `Moderne vor 1945` and a few other texts with `vor` are read as the year 1945 (`rule_embedded`, direction lost), `1941 bis 1939` is swapped to 1939/1941, `15. Jh. (1451)` gives 1451 instead of the century.
- **Assumptions built in** (all decided earlier or marked in the output): historical years in the integer columns, astronomical years in `iso`; `Anfang/Mitte/Ende` = years 1-33/34-66/67-100 of a century; two-digit years are 19yy; two years in one text become the interval between them (`rule_embedded`, score 0.5); `ca.` marks both ends approximate; an end year of 9999 means open end; `Geschichte`, `Sozialgeschichte`, `div.`, `nicht datiert`, `African` and similar are "no date"; the 86 labels of `periods.csv` are decisions made on the Austrian collections seen (Roman terms from the Roman monument and ceramics datasets, art styles from Belvedere, geology from the Natural History Museum).
- Tests: `python3 -m unittest test_time_mapping test_suggest_times` (run inside `ilias/`).

### Final lookup table (`data/time_lookup_final.csv`)

`build_time_lookup.py` collects every distinct time value (`temporal`, `date`, `issued`, `coverage`) of samples 1-3 (records 1-300 per dataset, about 25,800 records) and runs the same suggestion logic as `suggest_times.py`. Result: 5,226 distinct values, one row each, sorted by status and then alphabetically: ok 5,183, check 43, unmapped 0. Methods: rule 4,702, timespan 398, table 73, rule_embedded 42, no_date 10, rule_label_range 1. Columns: `value`, `begin`, `end` (from TimeSpan objects), `begin_year`, `end_year`, `iso`, `method`, `score`, `qualifier`, `source_uri`, `status`, `note`, `candidates`, `fields` (where the value occurs), `records`, `datasets`.
- The 43 `check` rows are dates inside other text (`Poststempel: Anger, 6.2.69`), placeholder dates (`1430-99-99`, read as the year) and the serial notations decided earlier; they have a lower score and are worth a quick look.
- No values from outside the three samples are in the file; new values go through `suggest_times.py`. Nothing in it was verified by hand beyond the decisions recorded above.

### Verbal terms only (`data/time_terms_verbose.csv`)

`time_lookup_final.csv` is mostly numeric values (years, dates, ranges), which the rules handle in general, so a lookup of them cannot cover new data. `build_verbose_terms.py` therefore writes only the verbal terms: the 69 period names and styles of `periods.csv` that contain no digit (German and English labels separately, e.g. `Minoan` and `Minoisch`), plus 14 words that are treated as no date (`undatiert`, `ohne Datierung`, `Geschichte`, ...). Columns: `term`, `begin_year`, `end_year` (historical years), `iso`, `confidence` (reviewed: high/medium/low), `source`, `source_uri`, `records_seen`, `datasets_seen` (in samples 1-3), `note`. Numeric values that were decided by hand (`ca. 50 v. Chr.-50`, `-60000000`, `18##-4`, ...) stay in `periods.csv` but are not in this file. Confidence of the 69 terms: 5 high, 39 medium, 25 low (art-historical periods and style labels without a gazetteer source, the German and English labels of one period count separately).

