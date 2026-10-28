import csv
import re
from pathlib import Path

from time_mapping import NO_DATE, PERIODS_PATH, parse_time

DATA_DIR = Path(__file__).resolve().parent / "data"
LOOKUP_PATH = DATA_DIR / "time_lookup_final.csv"
OUTPUT_PATH = DATA_DIR / "time_terms_verbose.csv"

COLUMNS = [
    "term", "begin_year", "end_year", "iso", "confidence", "source", "source_uri",
    "records_seen", "datasets_seen", "note",
]


def seen_counts() -> dict[str, tuple[int, int]]:
    """Je Bezeichnung (ohne Groß-/Kleinschreibung) die Zahl der Datensätze und Datensets in den Stichproben."""
    counts: dict[str, list[int]] = {}
    with LOOKUP_PATH.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            for piece in row["value"].split(" | "):
                entry = counts.setdefault(piece.strip().casefold(), [0, 0])
                entry[0] += int(row["records"])
                entry[1] = max(entry[1], int(row["datasets"]))
    return {term: (records, datasets) for term, (records, datasets) in counts.items()}


def main() -> None:
    """Nur verbale Zeitangaben (ohne Ziffern) mit ihren Jahren in einer CSV zusammenfassen."""
    seen = seen_counts()
    rows = []
    with PERIODS_PATH.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            term = row["label"]
            if re.search(r"\d", term):  # Zahlenwerte mit manueller Entscheidung gehören nicht hierher
                continue
            result = parse_time(term)
            rows.append(
                {
                    "term": term,
                    "begin_year": row["begin_year"],
                    "end_year": row["end_year"],
                    "iso": result.iso,
                    "confidence": row["confidence"],
                    "source": row["source"],
                    "source_uri": row["source_uri"],
                    "records_seen": seen.get(term.casefold(), (0, 0))[0],
                    "datasets_seen": seen.get(term.casefold(), (0, 0))[1],
                    "note": "",
                }
            )
    for term in sorted(NO_DATE):
        if re.search(r"\d", term):
            continue
        rows.append(
            {
                "term": term, "begin_year": "", "end_year": "", "iso": "", "confidence": "", "source": "no-date word",
                "source_uri": "", "records_seen": seen.get(term.casefold(), (0, 0))[0], "datasets_seen": seen.get(term.casefold(), (0, 0))[1],
                "note": "no time information; treated as no date",
            }
        )
    rows.sort(key=lambda r: r["term"].casefold())
    with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    periods = sum(1 for r in rows if r["begin_year"] or r["end_year"])
    print(f"{len(rows)} verbale Angaben nach {OUTPUT_PATH} geschrieben ({periods} mit Jahren, {len(rows) - periods} ohne Datum)")


if __name__ == "__main__":
    main()
