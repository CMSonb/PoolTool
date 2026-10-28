import sys
from pathlib import Path

import pandas as pd

from sample_records import SECOND_SAMPLE_DIR, THIRD_SAMPLE_DIR
from time_mapping import parse_time
from time_values import collect

DATA_DIR = Path(__file__).resolve().parent / "data"

FIELDS = ["temporal", "date", "issued"]
KEY = ["text", "begin", "end"]

# Stichprobe -> (Ordner, Ausgabedatei, frühere Stichproben als Vergleich)
SAMPLES = {
    "second": (SECOND_SAMPLE_DIR, DATA_DIR / "time_values_sample2.csv", ["time_values.csv"]),
    "third": (
        THIRD_SAMPLE_DIR,
        DATA_DIR / "time_values_sample3.csv",
        ["time_values.csv", "time_values_sample2.csv"],
    ),
}


def main(sample: str) -> None:
    """Weitere Stichprobe abbilden und die Angaben zeigen, die in den früheren Stichproben fehlten."""
    sample_dir, output_path, earlier = SAMPLES[sample]
    table = collect(sample_dir)
    table = table[table["field"].isin(FIELDS)]

    known = set()
    for name in earlier:
        previous = pd.read_csv(DATA_DIR / name, keep_default_na=False)
        previous = previous[previous["field"].isin(FIELDS)]
        known |= set(map(tuple, previous[KEY].drop_duplicates().itertuples(index=False)))
    table["new"] = [tuple(row) not in known for row in table[KEY].itertuples(index=False)]
    results = [parse_time(r.text, r.begin or None, r.end or None).as_dict() for r in table.itertuples()]
    table = pd.concat([table.reset_index(drop=True), pd.DataFrame(results)], axis=1)
    table.to_csv(output_path, index=False, encoding="utf-8")

    print(f"{len(table)} Angaben (Feld x Wert), davon {int(table['new'].sum())} neu gegenüber früheren Stichproben")
    print(table.groupby(["new", "method"]).agg(distinct=("text", "size"), records=("records", "sum")))

    unmapped = (
        table[table["method"] == "unmapped"]
        .groupby("text")
        .agg(records=("records", "sum"), datasets=("datasets", "max"), fields=("field", lambda f: ",".join(sorted(set(f)))))
        .reset_index()
        .sort_values("records", ascending=False)
    )
    print(f"\n{len(unmapped)} nicht abgebildete Angaben:")
    print(unmapped.to_string(index=False))


if __name__ == "__main__":
    main("third" if "--third" in sys.argv else "second")
