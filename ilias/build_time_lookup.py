import csv
import json
from collections import defaultdict
from pathlib import Path

from sample_records import SAMPLE_DIR, SECOND_SAMPLE_DIR, THIRD_SAMPLE_DIR
from suggest_times import suggest
from time_values import TIME_FIELDS, time_entries

DATA_DIR = Path(__file__).resolve().parent / "data"
OUTPUT_PATH = DATA_DIR / "time_lookup_final.csv"

SAMPLE_DIRS = [SAMPLE_DIR, SECOND_SAMPLE_DIR, THIRD_SAMPLE_DIR]
STATUS_ORDER = {"unmapped": 0, "check": 1, "ok": 2}

COLUMNS = [
    "value", "begin", "end", "begin_year", "end_year", "iso", "method", "score", "qualifier",
    "source_uri", "status", "note", "candidates", "fields", "records", "datasets",
]


def main() -> None:
    """Alle verschiedenen Zeitangaben der drei Stichproben mit Vorschlag in einer Nachschlagetabelle zusammenfassen."""
    records: dict[tuple, int] = defaultdict(int)
    datasets: dict[tuple, set] = defaultdict(set)
    fields: dict[tuple, set] = defaultdict(set)

    for sample_dir in SAMPLE_DIRS:
        for path in sorted(sample_dir.glob("*_first_records.json")):
            dataset = path.name.removesuffix("_first_records.json")
            for record in json.loads(path.read_text(encoding="utf-8")):
                cho = (record.get("content") or {}).get("aggregatedCHO") or {}
                seen = set()
                for field in TIME_FIELDS:
                    for entry in time_entries(field, cho.get(field)):
                        key = (entry["text"], entry["begin"], entry["end"])
                        fields[key].add(field)
                        datasets[key].add(dataset)
                        if key not in seen:  # ein Datensatz zählt je Angabe nur einmal
                            seen.add(key)
                            records[key] += 1

    rows = []
    for key in records:
        value, begin, end = key
        rows.append(
            {
                "value": value, "begin": begin, "end": end,
                **suggest(value, begin, end),
                "fields": ",".join(sorted(fields[key])),
                "records": records[key],
                "datasets": len(datasets[key]),
            }
        )
    rows.sort(key=lambda r: (STATUS_ORDER[r["status"]], r["value"].casefold()))

    with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    counts = {s: sum(r["status"] == s for r in rows) for s in STATUS_ORDER}
    print(f"{len(rows)} verschiedene Zeitangaben nach {OUTPUT_PATH} geschrieben: {counts}")


if __name__ == "__main__":
    main()
