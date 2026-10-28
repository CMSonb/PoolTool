"""Zeitangaben neuer Kulturpool-Datensätze auf Jahre und ISO 8601 / EDTF abbilden und Vorschläge als CSV schreiben.

Aufruf:
    python3 ilias/suggest_times.py EINGABE [-o time_suggestions.csv] [--online]

EINGABE ist eine .jsonl- oder .json-Datei (Liste von Datensätzen), ein .tar.gz mit solchen Dateien oder ein Ordner.
Gelesen werden die Felder temporal, date, issued und coverage unter content.aggregatedCHO.

Die CSV hat eine Zeile je Datensatz und Zeitangabe. Spalte status:
    ok        Regel, geprüfte Tabelle, begin/end-Angabe oder "kein Datum" (Score 0.8 oder höher)
    check     schwächerer Vorschlag (Text um ein Datum, ähnlicher Epochenname) - bitte ansehen
    unmapped  kein Vorschlag; in candidates stehen ggf. PeriodO-Definitionen als Hilfe

Mit --online werden für nicht abgebildete Epochen zusätzlich Zeitspannen aus iDAI.chronontology vorgeschlagen.

Benötigt data/periods.csv (geprüfte Epochen) und optional data/periodo_periods.csv (Kandidaten für unbekannte Epochen).
"""

import argparse
import csv
import difflib
import json
import sys
import tarfile
import time
from collections import Counter
from pathlib import Path

from time_mapping import TimeResult, build, load_periods, parse_time, period_candidates, period_key
from time_values import TIME_FIELDS, time_entries

COLUMNS = [
    "record_id", "dataset", "field", "value", "begin_year", "end_year", "iso",
    "method", "score", "qualifier", "source_uri", "status", "note", "candidates",
]

FUZZY_CUTOFF = 0.85  # Ähnlichkeit für Schreibfehler in Epochennamen ("Realimus" -> "Realismus")
MAX_CANDIDATES = 6


def read_stream(handle, name: str):
    """Datensätze aus einem geöffneten Binärstrom lesen (.jsonl zeilenweise, .json als Liste)."""
    if name.endswith(".jsonl"):
        for raw_line in handle:
            line = raw_line.decode("utf-8").strip()
            if line:
                yield json.loads(line)
    else:
        data = json.load(handle)
        yield from data["records"] if isinstance(data, dict) else data


def iter_records(path: Path):
    """Datensätze aus Datei, .tar.gz oder Ordner liefern."""
    if path.is_dir():
        for child in sorted(path.rglob("*")):
            if child.is_file():
                yield from iter_records(child)
    elif path.name.endswith((".tar.gz", ".tgz")):
        with tarfile.open(path, mode="r:gz") as tar:
            for member in tar:
                if member.isfile() and member.name.endswith((".jsonl", ".json")):
                    handle = tar.extractfile(member)
                    if handle is not None:
                        yield from read_stream(handle, member.name)
    elif path.name.endswith((".jsonl", ".json")):
        with path.open("rb") as handle:
            yield from read_stream(handle, path.name)


def format_candidates(label: str) -> str:
    """PeriodO-Definitionen zu einer (ggf. mehrteiligen) Bezeichnung als "von/bis (URI)" aneinanderreihen."""
    seen, parts = set(), []
    for piece in label.split(" | "):
        for c in period_candidates(piece):
            interval = (c["begin_year"], c["end_year"])
            if interval not in seen:
                seen.add(interval)
                parts.append(f"{interval[0]}/{interval[1]} ({c['source_uri']})")
    return "; ".join(parts[:MAX_CANDIDATES])


def fuzzy_period(label: str) -> tuple[TimeResult, str] | None:
    """Ähnlichsten Namen in der geprüften Tabelle suchen (Schreibfehler); nur bei eindeutigem Intervall."""
    checked = load_periods()[0]
    for piece in label.split(" | "):
        key = period_key(piece)
        if not any(ch.isalpha() for ch in key):
            continue
        match = difflib.get_close_matches(key, checked, n=1, cutoff=FUZZY_CUTOFF)
        if not match:
            continue
        rows = checked[match[0]]
        if len({(r["begin_year"], r["end_year"]) for r in rows}) != 1:
            continue
        first = rows[0]
        result = build((first["begin_year"], None, None), (first["end_year"], None, None), "", "suggested_fuzzy")
        result.score = round(difflib.SequenceMatcher(None, key, match[0]).ratio(), 2)
        result.source_uri = first.get("source_uri", "")
        return result, first["label"]
    return None


def chronontology_candidates(label: str) -> str:
    """Zeitspannen aus iDAI.chronontology zu einer Bezeichnung (braucht Internet)."""
    from run_time_mapping import chronontology_candidates as lookup

    found = []
    for piece in label.split(" | "):
        if any(ch.isalpha() for ch in piece) and len(piece) < 40:
            found.append(lookup(piece))
            time.sleep(0.2)
    return "; ".join(filter(None, found))


def suggest(text: str, begin: str = "", end: str = "", online: bool = False) -> dict:
    """Vorschlag für eine Zeitangabe als Zeile der Ausgabe-CSV (ohne Datensatz-Spalten)."""
    result, note, candidates = parse_time(text, begin or None, end or None), "", ""
    if result.method == "unmapped":
        fuzzy = fuzzy_period(text)
        if fuzzy:
            result, label = fuzzy
            note = f"similar to known period '{label}'"
        else:
            candidates = format_candidates(text)
            if online:
                candidates = "; ".join(filter(None, [candidates, chronontology_candidates(text)]))
    if result.method == "unmapped":
        status = "unmapped"
    elif result.method in ("rule", "table", "timespan", "no_date") and result.score >= 0.8:
        status = "ok"
    else:
        status = "check"
    return {
        "begin_year": "" if result.begin_year is None else result.begin_year,
        "end_year": "" if result.end_year is None else result.end_year,
        "iso": result.iso,
        "method": result.method,
        "score": result.score,
        "qualifier": result.qualifier,
        "source_uri": result.source_uri,
        "status": status,
        "note": note,
        "candidates": candidates,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("input", type=Path, help=".jsonl/.json-Datei, .tar.gz oder Ordner mit Datensätzen")
    parser.add_argument("-o", "--output", type=Path, default=Path("time_suggestions.csv"))
    parser.add_argument(
        "--online", action="store_true", help="für nicht abgebildete Epochen auch iDAI.chronontology abfragen (Internet)"
    )
    args = parser.parse_args()
    if not args.input.exists():
        sys.exit(f"{args.input} nicht gefunden")

    cache: dict[tuple, dict] = {}
    status_counts: Counter = Counter()
    unmapped: Counter = Counter()
    records = rows = 0

    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        for record in iter_records(args.input):
            records += 1
            cho = (record.get("content") or {}).get("aggregatedCHO") or {}
            for field in TIME_FIELDS:
                for entry in time_entries(field, cho.get(field)):
                    key = (entry["text"], entry["begin"], entry["end"])
                    if key not in cache:
                        cache[key] = suggest(*key, online=args.online)
                    row = {
                        "record_id": record.get("kp_id") or record.get("id") or "",
                        "dataset": record.get("pipeline_id") or record.get("institution_id") or "",
                        "field": field,
                        "value": entry["text"],
                        **cache[key],
                    }
                    writer.writerow(row)
                    rows += 1
                    status_counts[row["status"]] += 1
                    if row["status"] == "unmapped":
                        unmapped[entry["text"]] += 1

    print(f"{records} Datensätze, {rows} Zeitangaben, {len(cache)} verschiedene -> {args.output}", file=sys.stderr)
    for status in ("ok", "check", "unmapped"):
        print(f"  {status:9} {status_counts[status]}", file=sys.stderr)
    if unmapped:
        print("häufigste nicht abgebildete Angaben:", file=sys.stderr)
        for text, count in unmapped.most_common(15):
            print(f"  {count:5}  {text!r}", file=sys.stderr)


if __name__ == "__main__":
    main()
