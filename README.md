# PoolTool

Kulturpool Hackathon 2026 – tools for analysing and normalising metadata in [Kulturpool](https://kulturpool.at) records.

Team: 2townBefore, CarlaMariS, ikyriazi, MelissaSheena

| Part | Folder | What it is |
|---|---|---|
| **CONTEXT_PROMPTING.md** |---| This prompt was added to Claude. Using reusable context prompts saves tokens and  can increase consistency and transparency|
| **README.md** |---|This file explains the project for documentation and future use| 
| **Normalisation interface** | [`interface/`](interface/) | Dockerised Flask web app (German UI) that matches messy metadata values to a controlled vocabulary and lets a person approve each change |
| **Data analysis** | [`dataanalysis_notebooks/`](dataanalysis_notebooks/) | Notebooks and scripts exploring the full Kulturpool export (`dcType`, `medium`, `subject`) |



## The interface

Cultural-heritage records contain many spellings of the same thing (`Foto`, `Fotos`, `Photographie` → `Fotografie`). The interface finds these variants and lets you decide, term by term, which ones to replace. Nothing is changed without your selection.

The interface is in German. It works on one metadata field at a time: `dcType` (object type), `medium` (material/technique) or `subject` (topic).

### Run it with Docker

Requirements: [Docker](https://docs.docker.com/get-docker/) with Compose.

```powershell
cd interface
docker compose up --build
```

Open <http://localhost:5000>.

Choose the field to normalise (default `dcType`):

```powershell
$env:NORM_FIELD = "medium"      # or "subject"
docker compose up --build
```

Notes:
- The image installs `torch` and `transformers` for the CLIP matcher, so the first build is large. The CLIP model is downloaded on the first analysis.
- `interface/data/vocabularies/` and `interface/output/` are mounted as volumes: edit vocabularies without rebuilding, and find exports in `output/`.

### Without Docker

Python 3.10+:

```powershell
cd interface
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:NORM_FIELD = "dcType"
python app.py
```

Notes: The interface may look plain, because the visual elements/the CSS files/ are in docker. You may have to add an extra filepath. 

### How to use it

1. **Upload** a JSONL / NDJSON file or a JSON array (up to 2 GB) and set the **similarity threshold** (0–1). Click *Datei analysieren*.
2. **Wait for the analysis.** Each distinct value is compared with the vocabulary. Values already in the vocabulary are left alone.
3. **Review the suggestions, one vocabulary term at a time.**
   - Left: variants found in your data that resemble the term, with similarity score, number of hits and the first three record IDs (expandable to all IDs).
   - Right: the preferred term (and its URI, if the vocabulary has one).
   - Tick the variants to replace, then click *Auswahl übernehmen und weiter*. Unticked variants stay as they are.
   - The progress list on the left shows which terms are done. Terms without candidates are skipped.
4. **Export** after the last term:
   - normalised records (JSON array or JSONL),
   - change log (CSV or JSON): record ID, field, old/new value, vocabulary term, old/new URI,
   - processing report for the institution (Markdown or PDF) with accepted and declined suggestions and summary statistics,
   - or all of it as a ZIP.

### Vocabularies

CSV files in `interface/data/vocabularies/`, one preferred term per row, optional URI in the second column:

```csv
term,uri
Fotografie,
Druckgraphik,https://example.org/concept/123
```

| Field | File |
|---|---|
| `dcType` | `dctype.csv` (German) or `dctype_en.csv` (English, chosen automatically if the data contains many "book" and few "Buch") |
| `medium` | `medium.csv` (comma-separated values are matched individually) |
| `subject` | `subject.csv` |

### Good to know

- Input must follow the Kulturpool JSON structure: values live under `content.aggregatedCHO.<field>`.
- Record IDs shown and logged are the institution's original IDs (`src_id`, …), never `kp_id`.
- Sessions are kept in memory and are lost when the server restarts. Uploads are deleted after processing.
- XML/RDF import is a placeholder and not implemented yet.
- Similarity is a text-based score, not a probability that a match is correct.

More detail for developers: [`interface/README.md`](interface/README.md) and [`CONTEXT_PROMPTING.md`](CONTEXT_PROMPTING.md).

---

## Data analysis

Everything lives in [`dataanalysis_notebooks/`](dataanalysis_notebooks/):

| File | Content |
|---|---|
| `carla.ipynb` | Downloads the full Kulturpool export and computes how many records have `dcType`, `medium`, `subject` – overall and per institution. Writes the two JSON files below. |
| `institution_stats.json` | Output: per-institution counts and percentages of `dcType` / `medium` / `subject` |
| `neither_ids.json` | Output: `kp_id`s of records with neither `dcType` nor `medium` |
| `melissa.ipynb` | Uses the Kulturpool search API to explore the data |
| `make_dataset.ipynb` | Turns one institution's JSONL into a DataFrame, counts `dcType` / `medium` values, and tests clustering (SentenceTransformers) and CLIP matching against an external vocabulary (EKT item types) |
| `ilias.py` | Script to download the full export (`records_export_full.tar.gz`) and read records straight from the archive |

Headline numbers from the full export (2,636,673 records):

| Field | Records | Share |
|---|---:|---:|
| `dcType` | 2,444,252 | 92.70 % |
| `medium` | 809,780 | 30.71 % |
| `subject` | 1,360,391 | 51.59 % |
| neither `dcType` nor `medium` | 105,506 | 4.00 % |

Dataset: <https://s3.kpool.at/nightly/records_export_full.tar.gz> (several hundred MB; not stored in the repo).

---

## Ideas and next steps

### for the current 86 datasets
- Analyze the 86 datasets for structural differences and identifiy challenges 
- Dashboard and visualisation of value distributions per category
- Agreeing on umbrella terms (e.g. GND)
- Reporting per institution with concrete improvement suggestions
- Discuss  and reevaluate the changes with domainexperts and stackholders 
- XML/RDF input for the interface
- add failsaves
- streamline the design of the interface

### future datasets
- Analyze the dataset before ingestion into kulturpool
  
