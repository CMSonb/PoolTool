import json
import tarfile
from pathlib import Path

import pandas as pd
import requests

DATASET_URL = "https://s3.kpool.at/nightly/records_export_full.tar.gz"
DATA_DIR = Path("ilias_data")
ARCHIVE_PATH = DATA_DIR / "full_records.tar.gz"

MEMBER_NAME = "akademie-der-bildenden-kuenste-core__2026-01-14T11-50-22Z.jsonl"


def download(url: str, target: Path) -> Path:
    """Archiv streamend herunterladen (mehrere hundert MB)."""
    if target.exists():
        print(f"{target} existiert bereits — Download übersprungen.")
        return target

    target.parent.mkdir(parents=True, exist_ok=True)

    print(f"Lade Datenset von {url} herunter ...")
    with requests.get(url, stream=True, timeout=60) as response:
        response.raise_for_status()
        with target.open("wb") as fh:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                fh.write(chunk)

    print(f"Fertig: {target} ({target.stat().st_size / 1024**2:.0f} MB)")
    return target


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


def main():
    download(DATASET_URL, ARCHIVE_PATH)

    count = 0
    for source_file, record in iter_records(ARCHIVE_PATH):
        title = get_title(record)
        if title:
            count += 1
            if count <= 10:
                print(f"Gefundener Titel: {title}")

    print(f"\nVerarbeitung abgeschlossen. {count} Datensätze mit Titel gefunden.")

    first_records = read_jsonl_member(ARCHIVE_PATH, MEMBER_NAME, limit=3)
    print(f"{len(first_records)} Datensätze geladen")
    print(json.dumps(first_records[0], indent=2, ensure_ascii=False)[:4000])

    # Alle Datensätze der Datei laden und die Struktur als Tabelle anschauen
    records = read_jsonl_member(ARCHIVE_PATH, MEMBER_NAME)
    df = pd.json_normalize(records)
    print(f"{len(df)} Zeilen, {len(df.columns)} Spalten")
    print(df.columns.tolist())
    print(df.head())


if __name__ == "__main__":
    main()
