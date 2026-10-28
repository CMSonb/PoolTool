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
