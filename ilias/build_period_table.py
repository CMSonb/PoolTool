import csv
import gzip
import json
import urllib.request
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
OUTPUT_PATH = DATA_DIR / "periodo_periods.csv"

PERIODO_URL = "https://n2t.net/ark:/99152/p0d.json"
PERIODO_BASE = "http://n2t.net/ark:/99152/"


def download_periodo() -> dict:
    """PeriodO-Datensatz laden; der Server liefert zstd-, gzip- oder unkomprimiertes JSON."""
    with urllib.request.urlopen(PERIODO_URL, timeout=120) as response:
        raw = response.read()
    if raw[:4] == b"\x28\xb5\x2f\xfd":
        from compression import zstd  # Python 3.14+

        raw = zstd.decompress(raw)
    elif raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return json.loads(raw.decode("utf-8"))


def historical_year(value) -> int | None:
    """PeriodO nutzt astronomische Jahre (-3499 = 3500 v. Chr.); in historische Zählung umrechnen."""
    try:
        year = int(value)
    except (TypeError, ValueError):
        return None
    return year - 1 if year <= 0 else year


def bound(period: dict, side: str) -> int | None:
    """Anfangs- oder Endjahr einer Periode: exaktes Jahr, sonst früheste/späteste Grenze."""
    data = period.get(side) or {}
    if "in" in data:
        return historical_year(data["in"].get("year"))
    fallback = data.get("earliestYear") if side == "start" else data.get("latestYear")
    return historical_year(fallback)


def main() -> None:
    dump = download_periodo()
    rows = []
    for authority_id, authority in dump["authorities"].items():
        for period_id, period in authority["periods"].items():
            begin, end = bound(period, "start"), bound(period, "stop")
            if begin is None or end is None:
                continue
            for language, labels in (period.get("localizedLabels") or {}).items():
                if language not in ("de", "en"):
                    continue
                for label in labels:
                    rows.append(
                        {
                            "label": label,
                            "language": language,
                            "begin_year": begin,
                            "end_year": end,
                            "source_uri": PERIODO_BASE + period_id,
                            "authority": authority_id,
                        }
                    )
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"{len(rows)} Bezeichnungen aus {len(dump['authorities'])} Autoritäten nach {OUTPUT_PATH} geschrieben")


if __name__ == "__main__":
    main()
