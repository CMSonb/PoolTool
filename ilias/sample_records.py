import sys

from intro import ARCHIVE_PATH, DATA_DIR, write_all_first_records

SAMPLE_DIR = DATA_DIR / "first_records_100"
SECOND_SAMPLE_DIR = DATA_DIR / "records_101_200"
LIMIT = 100


def main(second: bool = False) -> None:
    """Datensatz 1-100 (Standard) oder 101-200 (--second) jedes Datensets schreiben."""
    target_dir, skip = (SECOND_SAMPLE_DIR, LIMIT) if second else (SAMPLE_DIR, 0)
    targets = write_all_first_records(ARCHIVE_PATH, limit=LIMIT, target_dir=target_dir, skip=skip)
    print(f"{len(targets)} Datensets nach {target_dir} geschrieben (je höchstens {LIMIT} Datensätze)")


if __name__ == "__main__":
    main(second="--second" in sys.argv)
