"""Zentrale Konfiguration der Anwendung.

Zum Wechseln des zu normalisierenden Metadatenfelds genügt es, ``FIELD`` zu ändern
(oder die Umgebungsvariable ``NORM_FIELD`` zu setzen, z. B. in docker-compose.yml).
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# --------------------------------------------------------------------------
# >>> HIER das Feld wählen: "dcType", "medium" oder "subject" <<<
# --------------------------------------------------------------------------
FIELD = os.environ.get("NORM_FIELD", "dcType")

# Je Feld: Anzeigename, Vokabular-Datei (in VOCAB_DIR) und ob Werte an Kommas
# getrennt werden sollen (z. B. "Holzschnitt, koloriert" -> "Holzschnitt" + "koloriert").
FIELDS = {
    "dcType": {
        "label": "Objekttyp (dcType)",
        "vocab_file": "dctype.csv",
        "split_on_commas": False,
    },
    "medium": {
        "label": "Material / Technik (medium)",
        "vocab_file": "medium.csv",
        "split_on_commas": True,
    },
    "subject": {
        "label": "Thema (subject)",
        "vocab_file": "subject.csv",
        "split_on_commas": False,
    },
}

if FIELD not in FIELDS:
    raise RuntimeError(
        f"Unbekanntes Feld '{FIELD}'. Erlaubt: {', '.join(FIELDS)} (siehe config.py)."
    )

# Pfad zum Knoten, der die Felder dcType/medium/subject enthält (Kulturpool-EDM-JSON).
RECORD_PATH = ("content", "aggregatedCHO")

# Mögliche Felder mit der ORIGINALEN Objekt-ID, in Prioritätsreihenfolge.
# Institutionelle IDs haben je nach Quelle unterschiedliche Feldnamen. kp_id
# wird bewusst nicht verwendet.
ID_FIELDS = [
    "src_id",
    "source_id",
    "original_id",
    "institution_record_id",
    "record_id",
    "identifier",
    "content.aggregatedCHO.identifier",
]

# Was passiert mit der Konzept-URI (z. B. Getty AAT in "id"), wenn ein Label ersetzt
# wird und im Vokabular KEINE URI hinterlegt ist?
#   "remove_id" -> alte URI entfernen (sie gehörte zum alten Begriff); im Log vermerkt
#   "keep_id"   -> alte URI behalten
ON_CHANGE_WITHOUT_VOCAB_URI = "remove_id"

# Ähnlichkeitsanalyse
MATCHER = "string"          # "string" (Standard) oder "clip" (Hook, siehe matching.py)
DEFAULT_THRESHOLD = 0.75    # Mindestähnlichkeit 0–1; im Interface einstellbar

# Ordner
VOCAB_DIR = BASE_DIR / "data" / "vocabularies"
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "output"

MAX_UPLOAD_MB = 2048
IDS_PREVIEW = 3             # Anzahl der direkt angezeigten IDs je Kandidat


def field_cfg():
    return FIELDS[FIELD]


def vocab_path():
    return VOCAB_DIR / field_cfg()["vocab_file"]