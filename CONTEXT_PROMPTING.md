# CONTEXT_PROMPTING.md – PoolTool orientation for Claude Sonnet 5.5

Paste this file into the chat before asking for changes. It tells you where everything is, so you can ask for only the files you need.

## Security rules (always enforced, no exceptions)
- NEVER read `.env` files or any log files (`logs/`, `*.log`)
- NEVER edit any file without explicitly asking the user first and receiving approval
- You need to ask every time before edition anything
- NEVER read any file without explicitly asking the user first and receiving approval
- Use as little tokens in the chat as needed for sufficient answers. Preferably show issues and changes in a table format.
- Functions that are commented out can be ignored.

---

## Project in one paragraph

PoolTool (Kulturpool Hackathon 2026) has two parts: (1) a Dockerised Flask app in `interface/` that matches values of one metadata field (`dcType`, `medium` or `subject`) in Kulturpool JSONL records to a CSV vocabulary, lets the user accept or decline each suggestion per vocabulary term, and exports the changed records, a change log and a processing report; (2) notebooks in `dataanalysis_notebooks/` analysing the full Kulturpool export. UI and user-facing messages are **German**; code identifiers and comments are mixed German/English – match the surrounding file.

## Repository map

| Path | Role |
|---|---|
| `README.md` | Public overview (interface usage, data analysis) |
| `interface/app.py` | Flask routes only; thin layer over `jobs.py` |
| `interface/config.py` | **All settings**: field choice, matcher, threshold, ID fields, paths, limits |
| `interface/jobs.py` | `Job` class: background analysis, step logic (`go`), state for UI, exports (data/log/zip/report MD+PDF) |
| `interface/data_utils.py` | Parsers, vocabulary loader, record/slot access, `collect_variants`, `apply_mapping` |
| `interface/matching.py` | Matchers: `StringMatcher` (rapidfuzz), `ClipMatcher` (CLIP text encoder), `get_matcher` |
| `interface/templates/index.html` | Single page (German) |
| `interface/static/app.js` | Frontend logic (vanilla JS, polls job state) |
| `interface/static/style.css`, `static/fonts/` | Styling; Atkinson Hyperlegible Next font (also used in PDF report) |
| `interface/data/vocabularies/` | `dctype.csv`, `dctype.txt`, `dctype_en.csv`, `medium.csv`, `subject.csv` |
| `interface/tests/test_workflow.py` | unittest suite (upload API, ID lookup, process→go→export, report) |
| `interface/Dockerfile`, `docker-compose.yml`, `.dockerignore`, `requirements.txt` | Docker setup |
| `interface/prompts.txt` | Original prompt/spec the interface was generated from (requirements + Q&A) |
| `interface/uploads/`, `interface/output/` | Runtime dirs (upload deleted after processing; exports per job id) |
| `dataanalysis_notebooks/` | `carla.ipynb`, `melissa.ipynb`, `make_dataset.ipynb`, `ilias.py`, `institution_stats.json`, `neither_ids.json` |

Ignore: `interface/.venv/`, `interface/.env/` (these are Python virtualenv folders, not env files), `.git/`.

## How the interface works (data flow)

1. `GET /` renders `index.html` with field label, vocab file and default threshold from `config.py`.
2. `POST /api/upload` (file + threshold, clamped 0–1) → `jobs.create_job` → file saved to `uploads/<job_id>/` → `jobs.start_processing` runs `Job.process` in a daemon thread.
3. `Job.process`:
   - `_choose_vocabulary`: only for `dcType`; counts "book" vs "Buch" in the file, if > `BOOK_THRESHOLD` (10) switches to `dctype_en.csv` / `dctype.csv` and adds a warning.
   - `load_vocabulary` → `load_records` (via `PARSERS` by extension) → `get_record_id` per record → `collect_variants` (value → record indices).
   - Values already in the vocabulary are skipped; the rest go to `matcher.match(...)`, which returns `{term: [(variant, score)]}`; each variant maps to at most one term (its best, if ≥ threshold).
   - Builds `steps` (one per vocabulary term; `pending` if it has candidates, else `skipped`), stats, `possible_records`. Status becomes `ready`. The upload folder is always removed.
4. Frontend polls `GET /api/jobs/<id>` (`Job.to_state`) until `ready`/`error`, then renders the progress list and the current step.
5. `GET /api/jobs/<id>/ids?step=&variant=` → all record IDs for one candidate (expandable list; only 3 are in the preview, `IDS_PREVIEW`).
6. `POST /api/jobs/<id>/go` with `{selected: [variants]}` → `Job.go`: records accepted/declined candidates for the report, calls `apply_mapping` on affected records, appends to `log`, advances to the next pending step.
7. When no pending step is left (`finished`), `GET /api/jobs/<id>/export/<zip|data|log|report>` is allowed. Query params: `data_format` (json|jsonl), `log_format` (csv|json), `format` (markdown|pdf, for report).

Jobs live only in memory (`jobs.JOBS`); a server restart gives 404 "Sitzung nicht gefunden".

## Where to change what

| I want to… | Edit | Notes |
|---|---|---|
| Switch field (dcType/medium/subject) | `NORM_FIELD` env var, or `FIELD` in `config.py` | Compose passes `NORM_FIELD`, default `dcType` |
| Add a new field | `FIELDS` in `config.py` + new vocabulary CSV | Set `split_on_commas`; `medium` splits on commas |
| Change vocabulary | CSV in `interface/data/vocabularies/` | Volume-mounted; no rebuild. Header `term,uri` optional; `,` or `;`; `#` comments; first-column terms, duplicates dropped |
| Change similarity method | `MATCHER` in `config.py` (`"clip"` or `"string"`) | `get_matcher` registry in `matching.py` |
| Add a new matcher | Subclass `BaseMatcher` in `matching.py`, register in `get_matcher` | Must return `{term: [(variant, score 0–1)]}`, each variant to ≤ 1 term, call `progress(done, total)` |
| Tune CLIP | `MODEL_NAME`, `TEMPLATE`, `BATCH` in `ClipMatcher` | Template is "a photo of a {}" |
| Default threshold / upload limit / ID preview | `DEFAULT_THRESHOLD`, `MAX_UPLOAD_MB` (2048), `IDS_PREVIEW` in `config.py` | |
| Original-ID fields | `ID_FIELDS` in `config.py` (priority order) | `kp_id` is deliberately excluded |
| Record JSON path | `RECORD_PATH` in `config.py` | Default `content.aggregatedCHO` |
| URI behaviour on replace without vocab URI | `ON_CHANGE_WITHOUT_VOCAB_URI` (`remove_id` / `keep_id`) | Logic in `data_utils.apply_mapping` |
| Support XML/RDF input | Implement `parse_xml_or_rdf` in `data_utils.py` (placeholder, raises `NotImplementedError`) and keep `PARSERS` | Must return records in the same dict format; rest of app unchanged |
| Change log columns | `LOG_COLUMNS` in `jobs.py` | Also `apply_mapping` change dict keys |
| Change report content/layout | `_report_data`, `_markdown_report`, `_write_pdf_report` in `jobs.py` | PDF via reportlab; font `static/fonts/AtkinsonHyperlegibleNext.ttf` |
| Change UI text/layout | `templates/index.html`, `static/app.js`, `static/style.css` | German |
| Add/change API route | `app.py` | Keep logic in `jobs.py` |
| Docker settings | `Dockerfile`, `docker-compose.yml` | Port 5000; mounts `data/vocabularies` and `output` |

## Key data structures

- **Record**: Kulturpool EDM JSON: `kp_id`, `src_id`, `content.aggregatedCHO.{dcType|medium|subject,…}`, `institution_id`, `pipeline_id`.
- **Field values** can be: plain strings, lists, `{"@value", "@language"}`, language maps, or concept objects `{id, type:"Concept", prefLabel:[…]}`. `data_utils.iter_slots` yields editable `Slot`s for all of these.
- **Step** (in `Job.steps`): `{term, uri, candidates:[{variant, score, rec_idx}], state: pending|skipped|done, applied, accepted, declined}`.
- **Log entry**: `record_id, field, old_value, new_value, vocabulary_term, variant, old_uri, new_uri`.

## Behaviours worth knowing before editing

- Replacement sets the label to the vocabulary term; for concept objects the `id` URI is replaced by the vocab URI, or removed if none (see config option).
- With `split_on_commas`, only matching parts are replaced and duplicates removed; the value is re-joined with `", "`.
- Selection is by variant string, not per record: choosing a variant changes it in all records where it occurs.
- `requirements.txt` has unpinned `torch` and `transformers`, so Docker builds are large and the CLIP model downloads on first analysis (not cached in a volume).
- Tests: `python -m unittest` from `interface/` (they patch `config.VOCAB_DIR` / `OUTPUT_DIR`; some use CSV files named `dctype.csv`).

## Data analysis notebooks (summary)

| File | Does |
|---|---|
| `carla.ipynb` | Downloads/extracts full export; counts records with dcType/medium/subject overall and per institution; writes `institution_stats.json` and `neither_ids.json` (kp_ids with neither field) |
| `melissa.ipynb` | Kulturpool search API (`api.kulturpool.at/v2/search`) exploration; contains unfinished/draft cells |
| `make_dataset.ipynb` | One institution's JSONL → DataFrame; value counts for dcType/medium; SentenceTransformers clustering; zero-shot and CLIP matching against EKT item-types vocabulary |
| `ilias.py` | Download + stream records from `records_export_full.tar.gz` |

Full export: `https://s3.kpool.at/nightly/records_export_full.tar.gz` (not in the repo).

## How to answer in this repo

1. Ask which files you may read; request only the ones in the table above that are relevant.
2. Propose changes as a table (file, location, change, reason) and wait for approval before editing.
3. Keep replies short.
