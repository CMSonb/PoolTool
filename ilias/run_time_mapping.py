import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

from time_mapping import parse_time, period_candidates

DATA_DIR = Path(__file__).resolve().parent / "data"
VALUES_PATH = DATA_DIR / "time_values.csv"
MAPPING_PATH = DATA_DIR / "time_mapping.csv"
REVIEW_PATH = DATA_DIR / "time_review.csv"

CHRONONTOLOGY_URL = "https://chronontology.dainst.org/data/period?size=10&q="
MAX_CANDIDATES = 6


def format_candidates(candidates: list[dict]) -> str:
    """PeriodO-Kandidaten als "von/bis (URI)" aneinanderreihen, verschiedene Intervalle zuerst."""
    seen, parts = set(), []
    for c in candidates:
        interval = (c["begin_year"], c["end_year"])
        if interval in seen:
            continue
        seen.add(interval)
        parts.append(f"{interval[0]}/{interval[1]} ({c['source_uri']})")
    return "; ".join(parts[:MAX_CANDIDATES])


def chronontology_candidates(label: str) -> str:
    """Zeitspannen aus iDAI.chronontology für Perioden, deren deutscher oder englischer Name passt."""
    url = CHRONONTOLOGY_URL + urllib.parse.quote(label)
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            results = json.load(response)["results"]
    except OSError:
        return ""
    wanted = label.casefold()
    found = []
    for item in results:
        resource = item["resource"]
        names = [n.casefold() for values in resource.get("names", {}).values() for n in values]
        if wanted not in names:
            continue
        for span in resource.get("hasTimespan", []):
            begin = (span.get("begin") or {}).get("at") or (span.get("begin") or {}).get("notBefore")
            end = (span.get("end") or {}).get("at") or (span.get("end") or {}).get("notAfter")
            if begin and end:
                found.append(f"{begin}/{end} (https://chronontology.dainst.org/period/{resource['id']})")
    return "; ".join(dict.fromkeys(found))[:600]


def main() -> None:
    values = pd.read_csv(VALUES_PATH, keep_default_na=False)
    values = values[values["field"].isin(["temporal", "date", "issued"])]

    results = [parse_time(r.text, r.begin or None, r.end or None).as_dict() for r in values.itertuples()]
    mapping = pd.concat([values.reset_index(drop=True), pd.DataFrame(results)], axis=1)
    mapping.to_csv(MAPPING_PATH, index=False, encoding="utf-8")

    summary = mapping.groupby("method").agg(distinct=("text", "size"), records=("records", "sum"))
    print(summary)

    unmapped = (
        mapping[mapping["method"] == "unmapped"]
        .groupby("text")
        .agg(records=("records", "sum"), datasets=("datasets", "max"), fields=("field", lambda f: ",".join(sorted(set(f)))))
        .reset_index()
        .sort_values("records", ascending=False)
    )
    labels = []
    for text in unmapped["text"]:
        pieces = text.split(" | ")
        labels.append(pieces)
    unmapped["periodo_candidates"] = [
        "; ".join(filter(None, (format_candidates(period_candidates(p)) for p in pieces))) for pieces in labels
    ]
    chrono = []
    for pieces in labels:
        found = []
        for piece in pieces:
            if any(ch.isalpha() for ch in piece) and len(piece) < 40:
                found.append(chronontology_candidates(piece))
                time.sleep(0.2)
        chrono.append("; ".join(filter(None, found)))
    unmapped["chronontology_candidates"] = chrono
    unmapped["begin_year"], unmapped["end_year"], unmapped["decision"] = "", "", ""
    unmapped.to_csv(REVIEW_PATH, index=False, encoding="utf-8")
    print(f"{len(unmapped)} nicht abgebildete Angaben nach {REVIEW_PATH} geschrieben")


if __name__ == "__main__":
    main()
