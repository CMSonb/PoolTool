import json
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from sample_records import SAMPLE_DIR
from time_mapping import parse_time
from time_values import as_list, time_entries

DATA_DIR = Path(__file__).resolve().parent / "data"
OUTPUT_PATH = DATA_DIR / "time_api_check.csv"

API_URL = "https://api.kulturpool.at/v2/search"
BATCH = 100
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
TOLERANCE = 1  # Jahre


def epoch_year(seconds: int | None) -> int | None:
    """Unix-Sekunden (auch negativ) als Kalenderjahr."""
    if seconds is None:
        return None
    try:
        return (EPOCH + timedelta(seconds=seconds)).year
    except OverflowError:
        return None


def sample_dates() -> dict[str, list[dict]]:
    """kp_id -> Zeitangaben des Feldes `date` aus der Stichprobe."""
    dates = {}
    for path in sorted(SAMPLE_DIR.glob("*_first_records.json")):
        for record in json.loads(path.read_text(encoding="utf-8")):
            cho = (record.get("content") or {}).get("aggregatedCHO") or {}
            entries = time_entries("date", cho.get("date"))
            if entries:
                dates[record["kp_id"]] = entries
    return dates


def fetch_api_dates(ids: list[str]) -> dict[str, dict]:
    """dateMin/dateMax und date des Suchindex für eine Liste von Datensatz-IDs holen."""
    query = urllib.parse.urlencode(
        {
            "q": "*",
            "filter_by": "id:=[" + ",".join(ids) + "]",
            "per_page": len(ids),
            "include_fields": "id,date,dateMin,dateMax",
        }
    )
    with urllib.request.urlopen(f"{API_URL}?{query}", timeout=60) as response:
        hits = json.load(response)["hits"]
    return {hit["document"]["id"]: hit["document"] for hit in hits}


def main() -> None:
    dates = sample_dates()
    ids = list(dates)
    api = {}
    for start in range(0, len(ids), BATCH):
        api.update(fetch_api_dates(ids[start : start + BATCH]))
    print(f"{len(ids)} Datensätze mit date in der Stichprobe, {len(api)} im Suchindex gefunden")

    rows = []
    for kp_id, entries in dates.items():
        doc = api.get(kp_id)
        if not doc or doc.get("dateMin") is None:
            continue
        parsed = [parse_time(e["text"], e["begin"] or None, e["end"] or None) for e in entries]
        parsed = [p for p in parsed if p.begin_year is not None or p.end_year is not None]
        if not parsed:
            continue
        begins = [p.begin_year for p in parsed if p.begin_year is not None]
        ends = [p.end_year for p in parsed if p.end_year is not None]
        mine = (min(begins) if begins else None, max(ends) if ends else None)
        theirs = (epoch_year(doc.get("dateMin")), epoch_year(doc.get("dateMax")))
        agree = all(
            a is None or b is None or abs(a - b) <= TOLERANCE for a, b in zip(mine, theirs)
        )
        rows.append(
            {
                "kp_id": kp_id,
                "text": " | ".join(e["text"] for e in entries),
                "my_begin": mine[0],
                "my_end": mine[1],
                "api_begin": theirs[0],
                "api_end": theirs[1],
                "api_date": json.dumps(doc.get("date"), ensure_ascii=False),
                "agree": agree,
            }
        )
    table = pd.DataFrame(rows)
    table.to_csv(OUTPUT_PATH, index=False, encoding="utf-8")
    print(f"{len(table)} verglichen, {int(table['agree'].sum())} stimmen überein (±{TOLERANCE} Jahr)")
    print(table[~table["agree"]].head(25).to_string())


if __name__ == "__main__":
    main()
