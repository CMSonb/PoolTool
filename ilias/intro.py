import json
import tarfile
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent / "data"
FIRST_RECORDS_DIR = DATA_DIR / "first_records"
ARCHIVE_PATH = DATA_DIR / "full_records.tar.gz"

MEMBER_NAME = "akademie-der-bildenden-kuenste-core__2026-01-14T11-50-22Z.jsonl"


def iter_records(archive: Path):
    """Alle Datensätze aus allen .jsonl-Dateien im Archiv liefern."""
    with tarfile.open(archive, mode="r:gz") as tar:
        for member in tar:
            if not (member.isfile() and member.name.endswith(".jsonl")):
                continue

            print(f"\n--- Verarbeite Datei: {member.name} ---")
            handle = tar.extractfile(member)
            if handle is None:
                continue

            for line_number, raw_line in enumerate(handle, 1):
                line = raw_line.decode("utf-8").strip()
                if not line:
                    continue
                try:
                    yield member.name, json.loads(line)
                except json.JSONDecodeError:
                    print(f"Fehler beim Parsen von {member.name}:{line_number}")


def get_title(record: dict) -> str | None:
    """Titel extrahieren, bevorzugt auf Deutsch."""
    titles = record.get("content", {}).get("aggregatedCHO", {}).get("title") or []
    if not titles:
        return None

    # Titel sind entweder einfache Strings oder {"@value", "@language"}-Objekte
    def value(t) -> str | None:
        return t.get("@value") if isinstance(t, dict) else t

    german = next(
        (value(t) for t in titles if isinstance(t, dict) and t.get("@language") == "de"),
        None,
    )
    return german or value(titles[0])


def read_jsonl_member(archive: Path, member_name: str, limit: int | None = None) -> list[dict]:
    """Eine einzelne .jsonl-Datei direkt aus dem tar.gz lesen (ohne Entpacken)."""
    records = []
    with tarfile.open(archive, mode="r:gz") as tar:
        handle = tar.extractfile(member_name)
        if handle is None:
            raise FileNotFoundError(member_name)
        for raw_line in handle:
            line = raw_line.decode("utf-8").strip()
            if line:
                records.append(json.loads(line))
            if limit is not None and len(records) >= limit:
                break
    return records


def split_member_name(member_name: str) -> tuple[str, str]:
    """Dateiname <datenset>__<zeitstempel>.jsonl in (Datenset, Zeitstempel) zerlegen."""
    dataset, _, exported_at = Path(member_name).stem.partition("__")
    return dataset, exported_at


def write_first_records(archive: Path, member_name: str, limit: int = 3) -> Path:
    """Die ersten Datensätze eines beliebigen Datensets als {datenset}_first_records.json speichern."""
    dataset, _ = split_member_name(member_name)
    first_records = read_jsonl_member(archive, member_name, limit=limit)

    target = FIRST_RECORDS_DIR / f"{dataset}_first_records.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(first_records, indent=2, ensure_ascii=False), encoding="utf-8")
    return target


def write_all_first_records(archive: Path, limit: int = 3) -> list[Path]:
    """Die ersten Datensätze jedes Datensets in einem Durchlauf als {datenset}_first_records.json speichern."""
    FIRST_RECORDS_DIR.mkdir(parents=True, exist_ok=True)
    targets = []
    with tarfile.open(archive, mode="r:gz") as tar:
        for member in tar:
            if not (member.isfile() and member.name.endswith(".jsonl")):
                continue

            handle = tar.extractfile(member)
            if handle is None:
                continue

            first_records = []
            for raw_line in handle:
                line = raw_line.decode("utf-8").strip()
                if line:
                    first_records.append(json.loads(line))
                if len(first_records) >= limit:
                    break

            dataset, _ = split_member_name(member.name)
            target = FIRST_RECORDS_DIR / f"{dataset}_first_records.json"
            target.write_text(json.dumps(first_records, indent=2, ensure_ascii=False), encoding="utf-8")
            targets.append(target)
    return targets


def write_dataset_overview(per_dataset: dict[str, dict[str, int]], target: Path) -> Path:
    """Eine Zeile pro Datenset (.jsonl-Datei) als CSV schreiben."""
    rows = []
    for member_name, stats in per_dataset.items():
        dataset, exported_at = split_member_name(member_name)
        rows.append(
            {
                "dataset": dataset,
                "exported_at": exported_at,
                "file": member_name,
                **stats,
            }
        )

    target.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(target, index=False, encoding="utf-8")
    return target


def main():
    if not ARCHIVE_PATH.exists():
        raise FileNotFoundError(f"{ARCHIVE_PATH} nicht gefunden — Archiv zuerst nach ilias/data/ legen.")

    count = 0
    # pro .jsonl-Datei (= einzelnes Datenset im Pool): Datensätze gesamt / mit Titel
    per_dataset: dict[str, dict[str, int]] = {}
    for source_file, record in iter_records(ARCHIVE_PATH):
        stats = per_dataset.setdefault(source_file, {"records": 0, "records_with_title": 0})
        stats["records"] += 1
        if get_title(record):
            stats["records_with_title"] += 1
            count += 1

    print(f"\nVerarbeitung abgeschlossen. {count} Datensätze mit Titel gefunden.")

    # Übersicht aller geladenen Datensets als CSV speichern
    datasets_path = DATA_DIR / "datasets.csv"
    write_dataset_overview(per_dataset, datasets_path)
    print(f"{len(per_dataset)} Datensets gespeichert: {datasets_path}")

    # JSON-Ergebnis nicht im Terminal ausgeben, sondern in ilias/data/ speichern
    output_path = write_first_records(ARCHIVE_PATH, MEMBER_NAME)
    print(f"Datensätze gespeichert: {output_path}")


if __name__ == "__main__":
    main()
