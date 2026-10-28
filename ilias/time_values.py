import json
import re
from collections import defaultdict
from pathlib import Path

import pandas as pd

from sample_records import SAMPLE_DIR

DATA_DIR = Path(__file__).resolve().parent / "data"
OUTPUT_PATH = DATA_DIR / "time_values.csv"

TIME_FIELDS = ("temporal", "date", "issued", "coverage")


def as_list(value) -> list:
    """Einzelwert oder Liste einheitlich als Liste liefern."""
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def label_text(label) -> str | None:
    """Text aus String oder {"@value", "@language"}-Objekt holen."""
    if isinstance(label, dict):
        label = label.get("@value")
    return label.strip() if isinstance(label, str) and label.strip() else None


def time_entries(field: str, value) -> list[dict]:
    """Zeitangaben eines Feldes als Zeilen mit text, begin, end und shape liefern."""
    entries = []
    for item in as_list(value):
        if isinstance(item, dict) and item.get("type") == "TimeSpan":
            labels = [text for text in map(label_text, as_list(item.get("prefLabel"))) if text]
            entries.append(
                {
                    "text": " | ".join(labels),
                    "begin": label_text(item.get("begin")) or "",
                    "end": label_text(item.get("end")) or "",
                    "shape": "timespan",
                }
            )
        elif isinstance(item, dict) and "@value" in item:
            text = label_text(item)
            if text:
                entries.append({"text": text, "begin": "", "end": "", "shape": "language_value"})
        elif isinstance(item, str) and item.strip():
            entries.append({"text": item.strip(), "begin": "", "end": "", "shape": "string"})
        # andere Objekte (z. B. Place-Objekte in coverage) sind keine Zeitangaben

    if field == "coverage":
        # coverage enthält auch Personen und Orte; nur Werte mit Ziffer oder TimeSpan behalten
        entries = [e for e in entries if e["shape"] == "timespan" or re.search(r"\d", e["text"])]
    return entries


def collect(sample_dir: Path) -> pd.DataFrame:
    """Alle Zeitangaben der Stichprobe einsammeln und je (Feld, Angabe) zählen."""
    records_count: dict[tuple, int] = defaultdict(int)
    datasets: dict[tuple, set] = defaultdict(set)

    for path in sorted(sample_dir.glob("*_first_records.json")):
        dataset = path.name.removesuffix("_first_records.json")
        for record in json.loads(path.read_text(encoding="utf-8")):
            cho = (record.get("content") or {}).get("aggregatedCHO") or {}
            seen = set()
            for field in TIME_FIELDS:
                for entry in time_entries(field, cho.get(field)):
                    key = (field, entry["shape"], entry["text"], entry["begin"], entry["end"])
                    if key in seen:
                        continue
                    seen.add(key)
                    records_count[key] += 1
                    datasets[key].add(dataset)

    rows = [
        {
            "field": field,
            "shape": shape,
            "text": text,
            "begin": begin,
            "end": end,
            "records": records_count[key],
            "datasets": len(datasets[key]),
        }
        for key in records_count
        for field, shape, text, begin, end in [key]
    ]
    return pd.DataFrame(rows).sort_values(["field", "records"], ascending=[True, False])


def main() -> None:
    table = collect(SAMPLE_DIR)
    table.to_csv(OUTPUT_PATH, index=False, encoding="utf-8")
    print(f"{len(table)} verschiedene Zeitangaben nach {OUTPUT_PATH} geschrieben")
    print(table.groupby(["field", "shape"]).agg(distinct=("text", "size"), records=("records", "sum")))


if __name__ == "__main__":
    main()
