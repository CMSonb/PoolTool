from pathlib import Path

import pandas as pd

from sample_records import SECOND_SAMPLE_DIR
from time_mapping import parse_time
from time_values import collect

DATA_DIR = Path(__file__).resolve().parent / "data"
OUTPUT_PATH = DATA_DIR / "time_values_sample2.csv"

FIELDS = ["temporal", "date", "issued"]
KEY = ["text", "begin", "end"]


def main() -> None:
    """Zweite Stichprobe (Datensatz 101-200) abbilden und die Angaben zeigen, die in der ersten fehlten."""
    second = collect(SECOND_SAMPLE_DIR)
    second = second[second["field"].isin(FIELDS)]
    first = pd.read_csv(DATA_DIR / "time_values.csv", keep_default_na=False)
    first = first[first["field"].isin(FIELDS)]

    known = set(map(tuple, first[KEY].drop_duplicates().itertuples(index=False)))
    second["new"] = [tuple(row) not in known for row in second[KEY].itertuples(index=False)]
    results = [parse_time(r.text, r.begin or None, r.end or None).as_dict() for r in second.itertuples()]
    second = pd.concat([second.reset_index(drop=True), pd.DataFrame(results)], axis=1)
    second.to_csv(OUTPUT_PATH, index=False, encoding="utf-8")

    print(f"{len(second)} Angaben (Feld x Wert), davon {int(second['new'].sum())} neu gegenüber Stichprobe 1")
    summary = second.groupby(["new", "method"]).agg(distinct=("text", "size"), records=("records", "sum"))
    print(summary)

    unmapped = (
        second[second["method"] == "unmapped"]
        .groupby("text")
        .agg(records=("records", "sum"), datasets=("datasets", "max"), fields=("field", lambda f: ",".join(sorted(set(f)))))
        .reset_index()
        .sort_values("records", ascending=False)
    )
    print(f"\n{len(unmapped)} nicht abgebildete Angaben:")
    print(unmapped.to_string(index=False))


if __name__ == "__main__":
    main()
