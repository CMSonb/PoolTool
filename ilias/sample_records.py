from intro import ARCHIVE_PATH, DATA_DIR, write_all_first_records

SAMPLE_DIR = DATA_DIR / "first_records_100"
LIMIT = 100


def main() -> None:
    targets = write_all_first_records(ARCHIVE_PATH, limit=LIMIT, target_dir=SAMPLE_DIR)
    print(f"{len(targets)} Datensets nach {SAMPLE_DIR} geschrieben (je höchstens {LIMIT} Datensätze)")


if __name__ == "__main__":
    main()
