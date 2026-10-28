import sys

from intro import ARCHIVE_PATH, DATA_DIR, write_all_first_records

SAMPLE_DIR = DATA_DIR / "first_records_100"
SECOND_SAMPLE_DIR = DATA_DIR / "records_101_200"
THIRD_SAMPLE_DIR = DATA_DIR / "records_201_300"
LIMIT = 100

# Stichprobe -> (Zielordner, übersprungene Datensätze je Datenset)
SAMPLES = {
    "first": (SAMPLE_DIR, 0),
    "second": (SECOND_SAMPLE_DIR, LIMIT),
    "third": (THIRD_SAMPLE_DIR, 2 * LIMIT),
}


def main(sample: str = "first") -> None:
    """Datensatz 1-100 (Standard), 101-200 (--second) oder 201-300 (--third) jedes Datensets schreiben."""
    target_dir, skip = SAMPLES[sample]
    targets = write_all_first_records(ARCHIVE_PATH, limit=LIMIT, target_dir=target_dir, skip=skip)
    print(f"{len(targets)} Datensets nach {target_dir} geschrieben (je höchstens {LIMIT} Datensätze)")


if __name__ == "__main__":
    main(next((name for name in SAMPLES if f"--{name}" in sys.argv), "first"))
