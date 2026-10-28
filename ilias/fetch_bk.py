import json
import re
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent / "data"
OUTPUT_PATH = DATA_DIR / "bk_terms.csv"

SCHEME_URI = "http://uri.gbv.de/terminology/bk/"
TOP_URL = "https://api.dante.gbv.de/voc/top?uri=" + urllib.parse.quote(SCHEME_URI, safe="")
CONCEPT_URL = "https://uri.gbv.de/terminology/bk/{notation}?format=jskos"

MAX_WORKERS = 8


def fetch_json(url: str):
    """JSON von einer URL laden."""
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def fetch_concept(uri: str) -> dict:
    """Einen BK-Begriff (JSKOS) über seine URI laden."""
    return fetch_json(CONCEPT_URL.format(notation=uri.removeprefix(SCHEME_URI)))


def crawl(top_uris: list[str]) -> dict[str, dict]:
    """Alle Begriffe ab den obersten Klassen ebenenweise über `narrower` einsammeln."""
    concepts: dict[str, dict] = {}
    level = list(dict.fromkeys(top_uris))
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        while level:
            next_level: list[str] = []
            for concept in pool.map(fetch_concept, level):
                concepts[concept["uri"]] = concept
                for child in concept.get("narrower") or []:
                    child_uri = child["uri"]
                    if child_uri not in concepts and child_uri not in next_level:
                        next_level.append(child_uri)
            print(f"{len(concepts)} Begriffe geladen, {len(next_level)} in der nächsten Ebene")
            level = next_level
    return concepts


def notation_key(uri: str) -> list:
    """Sortierschlüssel, der Notationen wie 5, 3-4, 81.64 natürlich ordnet."""
    notation = uri.removeprefix(SCHEME_URI)
    return [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", notation) if part]


def main() -> None:
    top_uris = [concept["uri"] for concept in fetch_json(TOP_URL)]
    print(f"{len(top_uris)} oberste Klassen")

    concepts = crawl(top_uris)

    rows = []
    skipped = 0
    for uri, concept in concepts.items():
        term = (concept.get("prefLabel") or {}).get("de")
        if not term:
            skipped += 1
            continue
        rows.append({"term": term, "uri": uri})
    print(f"{len(rows)} Begriffe mit deutscher Bezeichnung, {skipped} ohne übersprungen")

    rows.sort(key=lambda row: notation_key(row["uri"]))
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=["term", "uri"]).to_csv(OUTPUT_PATH, index=False, encoding="utf-8")
    print(f"Geschrieben: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
