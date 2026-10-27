import json
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent / "data"

# Ebenen, aus denen jeweils die Schlüssel der ersten Ebene als Spalten übernommen werden
LEVELS = [
    (),
    ("content",),
    ("content", "isShownBy"),
    ("content", "aggregatedCHO"),
]


def node_at(record: dict, path: tuple[str, ...]) -> dict:
    """Dict entlang path aus einem Datensatz holen (leer, falls nicht vorhanden)."""
    node = record
    for key in path:
        node = node.get(key) if isinstance(node, dict) else None
    return node if isinstance(node, dict) else {}


def load_fields() -> pd.DataFrame:
    """Eine Zeile pro Datensatz, eine Spalte pro Feld, gruppiert nach LEVELS."""
    rows = {}
    columns: dict[tuple[str, ...], dict[str, None]] = {path: {} for path in LEVELS}

    for file in sorted(DATA_DIR.glob("*_first_records.json")):
        dataset = file.name.removesuffix("_first_records.json")
        for i, record in enumerate(json.loads(file.read_text(encoding="utf-8")), 1):
            row = {}
            for path in LEVELS:
                for key, value in node_at(record, path).items():
                    column = ".".join((*path, key))
                    row[column] = value
                    columns[path].setdefault(column)  # Reihenfolge des ersten Auftretens
            rows[f"{dataset} #{i}"] = row

    order = [column for path in LEVELS for column in columns[path]]
    return pd.DataFrame.from_dict(rows, orient="index")[order]


def main():
    fields = load_fields()

    # 1, wenn das Feld im Datensatz vorhanden ist, sonst 0
    present = fields.notna().astype(int)

    target = DATA_DIR / "compared_fields.csv"
    present.to_csv(target, index_label="record", encoding="utf-8")
    print(f"{len(present)} Datensätze, {len(present.columns)} Felder gespeichert: {target}")


if __name__ == "__main__":
    main()
