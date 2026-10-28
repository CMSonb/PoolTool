"""Einlesen der Daten und Vokabulare sowie das Ändern der Feldwerte."""
from __future__ import annotations

import csv
import json
from pathlib import Path

import config

# --------------------------------------------------------------------------
# Daten einlesen
# --------------------------------------------------------------------------


def parse_json_lines_or_array(path: Path) -> list[dict]:
    """JSONL (eine JSON-Zeile je Datensatz) oder ein JSON-Array."""
    with open(path, "r", encoding="utf-8-sig") as fh:
        head = ""
        while True:
            ch = fh.read(1)
            if ch == "" or not ch.isspace():
                head = ch
                break
        fh.seek(0)
        if head == "[":
            try:
                data = json.load(fh)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Ungültiges JSON: {exc.msg} (Zeile {exc.lineno})") from exc
            if not all(isinstance(r, dict) for r in data):
                raise ValueError("Das JSON-Array darf nur Objekte (Datensätze) enthalten.")
            return data
        records = []
        for n, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Zeile {n}: keine gültige JSON-Zeile ({exc.msg}).") from exc
            if not isinstance(rec, dict):
                raise ValueError(f"Zeile {n}: erwartet wurde ein JSON-Objekt.")
            records.append(rec)
        return records


def parse_xml_or_rdf(path: Path) -> list[dict]:
    """PLATZHALTER: XML/RDF-Import ist noch nicht implementiert.

    Später hier einen Parser ergänzen, der eine Liste von Datensätzen im selben
    internen Format (dict mit src_id + content.aggregatedCHO.<Feld>) zurückgibt,
    und ihn in PARSERS unten eintragen. Der Rest der Anwendung muss nicht geändert werden.
    """
    raise NotImplementedError(
        "XML/RDF-Import ist noch nicht implementiert. Bitte JSONL hochladen "
        "(Parser ergänzen in data_utils.PARSERS)."
    )


# Dateiendung -> Parser-Funktion. Hier neue Formate registrieren.
PARSERS = {
    ".jsonl": parse_json_lines_or_array,
    ".ndjson": parse_json_lines_or_array,
    ".json": parse_json_lines_or_array,
    ".xml": parse_xml_or_rdf,
    ".rdf": parse_xml_or_rdf,
    ".ttl": parse_xml_or_rdf,
    ".nt": parse_xml_or_rdf,
}


def load_records(path: Path, filename: str) -> list[dict]:
    ext = Path(filename).suffix.lower()
    parser = PARSERS.get(ext)
    if parser is None:
        raise ValueError(
            f"Dateityp '{ext or '?'}' wird nicht unterstützt. Erlaubt: {', '.join(PARSERS)}."
        )
    return parser(path)


# --------------------------------------------------------------------------
# Vokabular einlesen
# --------------------------------------------------------------------------

_HEADER_TERM = {"term", "begriff", "preflabel", "vokabular", "label", "bezeichnung"}


def load_vocabulary(path: Path) -> list[dict]:
    """CSV mit einem Vorzugsbegriff je Zeile (erste Spalte).

    Optional: zweite Spalte mit Konzept-URI (beginnt mit http). Kopfzeile optional.
    Trennzeichen ',' oder ';' (automatisch erkannt). Begriffe mit Komma bitte in
    Anführungszeichen setzen.
    """
    if not Path(path).exists():
        raise FileNotFoundError(f"Vokabular-Datei nicht gefunden: {path}")
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        text = fh.read()
    first_line = text.splitlines()[0] if text.strip() else ""
    delimiter = ";" if ";" in first_line and "," not in first_line else ","
    rows = list(csv.reader(text.splitlines(), delimiter=delimiter))
    vocab, seen = [], set()
    for idx, row in enumerate(rows):
        if not row or not row[0].strip() or row[0].lstrip().startswith("#"):
            continue
        term = row[0].strip()
        if idx == 0 and term.lower() in _HEADER_TERM:
            continue
        uri = ""
        if len(row) > 1 and row[1].strip().lower().startswith("http"):
            uri = row[1].strip()
        if term in seen:
            continue
        seen.add(term)
        vocab.append({"term": term, "uri": uri})
    if not vocab:
        raise ValueError(f"Das Vokabular ist leer: {path}")
    return vocab


# --------------------------------------------------------------------------
# Zugriff auf Datensätze
# --------------------------------------------------------------------------


def _dig(node, dotted: str):
    for key in dotted.split("."):
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    return node


def get_record_id(record: dict, line_no: int) -> tuple[str, bool]:
    """Gibt (ID, gefunden?) zurück. Ohne ID: Ersatzbezeichnung 'Datensatz Nr. N'."""
    for key in config.ID_FIELDS:
        val = _dig(record, key)
        if isinstance(val, list):
            for item in val:
                candidate = item.get("@value") if isinstance(item, dict) else item
                if isinstance(candidate, (str, int)) and str(candidate).strip():
                    val = candidate
                    break
            else:
                val = None
        elif isinstance(val, dict):
            val = val.get("@value")
        if isinstance(val, (str, int)) and str(val).strip():
            return str(val), True
    return f"Datensatz Nr. {line_no}", False


def get_record_url(record: dict) -> str:
    """Link zum Original-Objekt (isShownAt) oder "" – nur http(s)-Links."""
    nodes = [_dig(record, ".".join(config.RECORD_PATH)), record.get("content"), record]
    for key in config.URL_FIELDS:
        for node in nodes:
            val = node.get(key) if isinstance(node, dict) else None
            if isinstance(val, list):
                val = val[0] if val else None
            if isinstance(val, dict):
                val = val.get("@value") or val.get("id")
            if isinstance(val, str) and val.strip().lower().startswith(("http://", "https://")):
                return val.strip()
    return ""


def get_cho(record: dict):
    node = record
    for key in config.RECORD_PATH:
        node = node.get(key) if isinstance(node, dict) else None
    return node if isinstance(node, dict) else None


class Slot:
    """Eine änderbare Textstelle innerhalb eines Feldes (Container + Schlüssel)."""

    __slots__ = ("container", "key", "owner")

    def __init__(self, container, key, owner=None):
        self.container = container
        self.key = key
        self.owner = owner  # dict-Eintrag (z. B. Konzept mit "id"), sonst None

    def get(self) -> str:
        return self.container[self.key]

    def set(self, value: str) -> None:
        self.container[self.key] = value


def _label_slots(container, key, owner):
    """Slots für ein Label, das String, Liste, {"@value"} oder Sprach-Map sein kann."""
    val = container[key]
    if isinstance(val, str):
        yield Slot(container, key, owner)
    elif isinstance(val, list):
        for i, x in enumerate(val):
            if isinstance(x, str):
                yield Slot(val, i, owner)
            elif isinstance(x, dict) and isinstance(x.get("@value"), str):
                yield Slot(x, "@value", owner)
    elif isinstance(val, dict):
        if isinstance(val.get("@value"), str):
            yield Slot(val, "@value", owner)
        else:  # Sprach-Map {"de": "..."} bzw. {"de": ["..."]}
            for lang in list(val):
                yield from _label_slots(val, lang, owner)


def _item_slots(container, key):
    item = container[key]
    if isinstance(item, str):
        yield Slot(container, key, None)
    elif isinstance(item, dict):
        if isinstance(item.get("@value"), str):
            yield Slot(item, "@value", item)
        if "prefLabel" in item:
            yield from _label_slots(item, "prefLabel", item)


def iter_slots(cho: dict, field: str):
    val = cho.get(field)
    if isinstance(val, list):
        for i in range(len(val)):
            yield from _item_slots(val, i)
    elif val is not None:
        yield from _item_slots(cho, field)


def split_value(text: str, split: bool) -> list[str]:
    if not split:
        t = text.strip()
        return [t] if t else []
    return [p.strip() for p in text.split(",") if p.strip()]


def collect_variants(records: list[dict], field: str, split: bool) -> dict[str, list[int]]:
    """Alle verschiedenen Werte -> Liste der Datensatz-Indizes, in denen sie vorkommen."""
    variants: dict[str, list[int]] = {}
    for idx, rec in enumerate(records):
        cho = get_cho(rec)
        if cho is None:
            continue
        for slot in iter_slots(cho, field):
            for part in split_value(slot.get(), split):
                lst = variants.setdefault(part, [])
                if not lst or lst[-1] != idx:
                    lst.append(idx)
    return variants


def apply_mapping(record: dict, field: str, split: bool, mapping: dict[str, tuple[str, str]]) -> list[dict]:
    """Ersetzt Werte gemäß mapping {Variante: (Zielbegriff, URI)}; gibt Änderungen zurück."""
    changes: list[dict] = []
    cho = get_cho(record)
    if cho is None:
        return changes
    for slot in list(iter_slots(cho, field)):
        old = slot.get()
        parts = split_value(old, split)
        matched = [p for p in parts if p in mapping]
        if not matched:
            continue
        new_parts = [mapping[p][0] if p in mapping else p for p in parts]
        if split:
            new_parts = list(dict.fromkeys(new_parts))  # Duplikate nach Ersetzung entfernen
        new = ", ".join(new_parts)
        if new == old:
            continue
        slot.set(new)

        old_uri = new_uri = ""
        owner = slot.owner
        if isinstance(owner, dict) and ("id" in owner or owner.get("type") == "Concept"):
            old_uri = owner.get("id", "") or ""
            uri = mapping[matched[0]][1]
            if uri:
                owner["id"] = uri
                new_uri = uri
            elif config.ON_CHANGE_WITHOUT_VOCAB_URI == "remove_id":
                owner.pop("id", None)
            else:
                new_uri = old_uri

        for p in dict.fromkeys(matched):
            changes.append(
                {
                    "field": field,
                    "old_value": old,
                    "new_value": new,
                    "variant": p,
                    "vocabulary_term": mapping[p][0],
                    "old_uri": old_uri,
                    "new_uri": new_uri,
                }
            )
    return changes