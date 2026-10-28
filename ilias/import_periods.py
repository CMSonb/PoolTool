import csv
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
PROPOSAL_PATH = DATA_DIR / "periods_proposal.csv"
PERIODS_PATH = DATA_DIR / "periods.csv"

FIELDNAMES = ["label", "language", "begin_year", "end_year", "source", "source_uri", "confidence"]

SOURCES = {
    "period": "periods_proposal.csv (reviewed)",
    "needs_decision": "periods_proposal.csv (manual decision)",
}


def main() -> None:
    """Geprüfte Perioden und manuelle Entscheidungen aus dem Vorschlag in periods.csv übernehmen."""
    rows = []
    with PROPOSAL_PATH.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["kind"] not in SOURCES or not (row["begin_year"] or row["end_year"]):
                continue
            # "Minoan | Minoisch": jede Bezeichnung bekommt einen eigenen Eintrag
            for label in (part.strip() for part in row["text"].split(" | ")):
                rows.append(
                    {
                        "label": label,
                        "language": "",
                        "begin_year": row["begin_year"],
                        "end_year": row["end_year"],
                        "source": SOURCES[row["kind"]],
                        "source_uri": row["source_uri"],
                        "confidence": row["confidence"],
                    }
                )
    with PERIODS_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    print(f"{len(rows)} Einträge nach {PERIODS_PATH} geschrieben")


if __name__ == "__main__":
    main()
