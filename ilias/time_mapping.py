import csv
import re
from dataclasses import asdict, dataclass
from functools import cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
PERIODS_PATH = DATA_DIR / "periods.csv"  # von Hand geprüfte Perioden (Vorrang)
PERIODO_PATH = DATA_DIR / "periodo_periods.csv"  # von build_period_table.py erzeugt

# Jahreszahlen: begin_year/end_year folgen der historischen Zählung (1 v. Chr. = -1, kein Jahr 0).
# Der ISO-8601-String verwendet die astronomische Zählung (1 v. Chr. = 0000, 2 v. Chr. = -0001).
# Unschärfe-Markierungen ("~" ungefähr, "?" unsicher) und offene Intervalle ("..") sind EDTF.

NO_DATE = {"ohne datierung", "ohne datum", "undatiert", "unbekannt", "unknown", "o. j.", "o.j.", "x", "geschichte", "sozialgeschichte", "div.", "9999"}

MONTHS = {
    "januar": 1, "februar": 2, "märz": 3, "maerz": 3, "april": 4, "mai": 5, "juni": 6,
    "juli": 7, "august": 8, "september": 9, "oktober": 10, "november": 11, "dezember": 12,
}

# Anteil eines Jahrhunderts (von-bis im Jahrhundert), benannt oder als k-tes Teil von n
CENTURY_PARTS = {
    "anfang": (1, 33), "früh": (1, 33), "frühes": (1, 33), "frühen": (1, 33),
    "mitte": (34, 66), "mittleres": (34, 66),
    "ende": (67, 100), "spät": (67, 100), "spätes": (67, 100), "späten": (67, 100),
}
PART_UNITS = {"hälfte": 2, "drittel": 3, "viertel": 4}
ORDINALS = {"erste": 1, "erstes": 1, "zweite": 2, "zweites": 2, "dritte": 3, "drittes": 3, "letztes": -1, "letzte": -1}

ERA_BCE = r"(?:v\.\s*Chr\.?|vor\s+Chr\.?|BCE|BC)"
ERA_CE = r"(?:n\.\s*Chr\.?|nach\s+Chr\.?|CE|AD)"
YEAR = rf"(?P<{{n}}>-?\d{{{{1,7}}}})(?:\.0)?(?:\s*(?P<{{n}}e>{ERA_BCE}|{ERA_CE}))?"


@dataclass
class TimeResult:
    begin_year: int | None
    end_year: int | None
    iso: str
    method: str
    score: float
    source_uri: str = ""
    qualifier: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


def unmapped() -> TimeResult:
    return TimeResult(None, None, "", "unmapped", 0.0)


def historical_year(number: str, era: str | None) -> int:
    """Jahreszahl mit optionaler Ära in die historische Zählung (BCE negativ) bringen."""
    year = int(number)
    if era and re.fullmatch(ERA_BCE, era):
        return -abs(year)
    return year


def iso_year(year: int) -> str:
    """Historisches Jahr als astronomisches ISO-Jahr (4 Stellen, BCE mit Vorzeichen)."""
    if abs(year) > 9999:
        return f"Y{year}"  # EDTF-Schreibweise für Jahre mit mehr als vier Stellen; Jahr-0-Verschiebung irrelevant
    astronomical = year + 1 if year < 0 else year
    return f"-{abs(astronomical):04d}" if astronomical < 0 else f"{astronomical:04d}"


def format_point(year: int, month: int | None = None, day: int | None = None) -> str:
    text = iso_year(year)
    if month:
        text += f"-{month:02d}"
        if day:
            text += f"-{day:02d}"
    return text


def mark(text: str, qualifier: str) -> str:
    """EDTF-Markierungen anhängen (~ ungefähr, ? unsicher, % beides)."""
    if not text or text == "..":
        return text
    return text + {"approx": "~", "uncertain": "?", "approx+uncertain": "%"}.get(qualifier, "")


def build(begin: tuple, end: tuple, qualifier: str, method: str = "rule") -> TimeResult:
    """TimeResult aus Anfangs-/Endpunkt (Jahr, Monat, Tag) bauen; None = offen."""
    begin = begin if begin and begin[0] is not None else None
    end = end if end and end[0] is not None and end[0] != 9999 else None  # 9999 = Platzhalter für "offen"
    begin_text = format_point(*begin) if begin else ".."
    end_text = format_point(*end) if end else ".."
    if begin and end and begin == end:
        iso = mark(begin_text, qualifier)
    else:
        iso = f"{mark(begin_text, qualifier)}/{mark(end_text, qualifier)}"
    return TimeResult(
        begin[0] if begin else None, end[0] if end else None, iso, method, 1.0, "", qualifier
    )


def clean(text: str) -> tuple[str, str]:
    """Text bereinigen und Qualifier (approx/uncertain) ermitteln."""
    text = text.replace("\n", " ").replace("–", "-").replace("—", "-").replace("©", " ").strip()
    qualifier = set()
    if "(?)" in text or text.endswith("?"):
        qualifier.add("uncertain")
        text = text.replace("(?)", " ").rstrip("?")
    if re.search(r"\b(?:ca|circa|um)\b|\bc\.", text, flags=re.IGNORECASE):
        qualifier.add("approx")
        # nachgestelltes ", ca." (hinter einer Zahl, vor Bindestrich/Schrägstrich/Ende) samt Komma entfernen
        text = re.sub(r"(?<=\d)\s*,\s*ca\.?(?=\s*(?:-|/|;|$))", " ", text, flags=re.IGNORECASE)
        text = re.sub(r"\b(?:ca|circa|um)\b\.?|\bc\.", " ", text, flags=re.IGNORECASE)
    if re.search(r"\b(?:vermutlich|wahrscheinlich|evtl|ev)\b", text, flags=re.IGNORECASE):
        qualifier.add("uncertain")
        text = re.sub(r"\b(?:vermutlich|wahrscheinlich|evtl|ev)\b\.?", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"(?<=\d)\s+bis\s+(?=\d)", " - ", text)
    text = re.sub(r"^\s*Geschichte\s+", "", text)
    text = text.strip()
    if text.startswith("[") and text.endswith("]"):
        text = text[1:-1].strip()
        if text.endswith("?"):  # "[1809?]": Fragezeichen steht innerhalb der Klammern
            qualifier.add("uncertain")
            text = text.rstrip("?").strip()
    # Nachträge ("Anfang 18. Jh. / Ergänzungen 20. Jh."): nur die ursprüngliche Datierung zählt
    text = re.split(r"\s*[/;,]?\s*Ergänzung(?:en)?\b", text, maxsplit=1)[0].strip()
    text = re.sub(r"\b(\d)\.?\s+Hälfte\s+des\b", r"\1. Hälfte", text)
    # Epochenname in Klammern am Ende (z. B. "(Flavisch)") verwerfen
    text = re.sub(r"\s*\([^\d()]*[A-Za-zÄÖÜäöüß][^\d()]*\)\s*$", "", text).strip()
    text = re.sub(r"\s+", " ", text)
    return text, "approx+uncertain" if len(qualifier) == 2 else "".join(qualifier)


def parse_endpoint(text: str):
    """Einzelnen Zeitpunkt (Jahr, Monat, Tag) mit optionaler Ära parsen, sonst None."""
    text = text.strip()
    m = re.fullmatch(rf"{YEAR.format(n='y')}", text)
    if m:
        return (historical_year(m.group("y"), m.group("ye")), None, None), m.group("ye")
    m = re.fullmatch(r"(\d{4})-(\d{2})(?:-(\d{2}))?", text)
    if m:
        return (int(m.group(1)), int(m.group(2)), int(m.group(3)) if m.group(3) else None), None
    m = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", text) or re.fullmatch(
        r"(\d{1,2})-(\d{1,2})-(\d{4})", text
    )
    if m:
        return (int(m.group(3)), int(m.group(2)), int(m.group(1))), None
    m = re.fullmatch(r"(\d{4})\.(\d{2})\.xx", text, flags=re.IGNORECASE)
    if m:
        return (int(m.group(1)), int(m.group(2)), None), None
    m = re.fullmatch(r"(\d{4})\.(\d{1,2})\.(\d{1,2})", text)
    if m:
        return (int(m.group(1)), int(m.group(2)), int(m.group(3))), None
    m = re.fullmatch(r"(\d{1,2})\.(\d{4})", text)
    if m:
        return (int(m.group(2)), int(m.group(1)), None), None
    m = re.fullmatch(r"([A-Za-zäöüÄÖÜ]+)\s+(\d{4})", text)
    if m and m.group(1).lower() in MONTHS:
        return (int(m.group(2)), MONTHS[m.group(1).lower()], None), None
    return None


def to_century_range(number: int, part: tuple[int, int] | None, era: str | None) -> tuple[int, int]:
    """Jahrhundert (mit optionalem Teil und Ära) als (von, bis) in historischen Jahren."""
    low, high = part or (1, 100)
    if era and re.fullmatch(ERA_BCE, era):
        # 2. Jh. v. Chr. = -200 bis -101; "Anfang" liegt bei den größeren Beträgen
        base = number * 100
        return -(base - low + 1), -(base - high + 1)
    base = (number - 1) * 100
    return base + low, base + high


def century_part(modifier: str) -> tuple[int, int] | None:
    """Teil eines Jahrhunderts aus "Anfang", "Mitte", "2. Hälfte", "1. Drittel", "Erste Hälfte" usw. ableiten."""
    modifier = re.sub(r"\s+", " ", modifier.lower().strip())
    if modifier in CENTURY_PARTS:
        return CENTURY_PARTS[modifier]
    m = re.fullmatch(r"(?:(\d)\.?|(" + "|".join(ORDINALS) + r"))\s+(hälfte|drittel|viertel)", modifier)
    if not m:
        return None
    units = PART_UNITS[m.group(3)]
    index = int(m.group(1)) if m.group(1) else ORDINALS[m.group(2)]
    index = units if index == -1 else index
    if not 1 <= index <= units:
        return None
    return (index - 1) * 100 // units + 1, index * 100 // units


CENTURY_WORD = r"(?:jh|jhdt|jahrhundert)"
CENTURY_CHUNK = (
    r"(?:(?P<mod>anfang|früh(?:es|en)?|mitte|mittleres|ende|spät(?:es|en)?|"
    r"(?:\d\.?|erste|erstes|zweite|zweites|dritte|drittes|letzte|letztes)\s+(?:hälfte|drittel|viertel))\s+)?"
    r"(?P<n>\d{1,2})\.?(?:\s*" + CENTURY_WORD + r"\.?)?"
)


def parse_centuries(text: str, qualifier: str) -> TimeResult | None:
    """Jahrhundertangaben wie "19. Jh.", "Ende 19. Jh.", "18. - 19. Jh." und "19./20. Jahrhundert"."""
    if not re.search(CENTURY_WORD, text, flags=re.IGNORECASE):
        return None
    era = re.search(rf"\s*({ERA_BCE}|{ERA_CE})\s*$", text)
    era_text = era.group(1) if era else None
    body = text[: era.start()] if era else text
    parts = re.split(r"\s*(?:-|/)\s*", body)
    if not 1 <= len(parts) <= 2:
        return None
    ranges = []
    for chunk in parts:
        m = re.fullmatch(CENTURY_CHUNK, chunk, flags=re.IGNORECASE)
        if not m:
            return None
        part = century_part(m.group("mod")) if m.group("mod") else None
        if m.group("mod") and not part:
            return None
        ranges.append(to_century_range(int(m.group("n")), part, era_text))
    begin = min(r[0] for r in ranges)
    end = max(r[1] for r in ranges)
    return build((begin, None, None), (end, None, None), qualifier)


def parse_decade(text: str, qualifier: str) -> TimeResult | None:
    """Jahrzehnte wie "1930er Jahre" oder "[1980er]"."""
    m = re.fullmatch(r"(\d{3})0er(?:\s+Jahre)?", text.strip("[] "))
    if not m:
        return None
    start = int(m.group(1)) * 10
    return build((start, None, None), (start + 9, None, None), qualifier)


def parse_range(text: str, qualifier: str) -> TimeResult | None:
    """Bereiche wie "1855-1861", "100 n. Chr. - 200 n. Chr.", "1470-", "1547-01-01/1547-12-31"."""
    # ISO-Intervall mit Schrägstrich
    if "/" in text:
        left, _, right = text.partition("/")
        a, b = parse_endpoint(left), parse_endpoint(right)
        if a and b:
            return build(a[0], b[0], qualifier)
        return None

    open_end = re.fullmatch(r"(.+?)\s*-\s*", text)
    if open_end:
        a = parse_endpoint(open_end.group(1))
        return build(a[0], None, qualifier) if a else None

    # jeden Bindestrich als Trenner probieren; Vorzeichen und Datumsstriche scheitern beim Parsen
    for position in (m.start() for m in re.finditer("-", text)):
        a, b = parse_endpoint(text[:position]), parse_endpoint(text[position + 1 :])
        if not (a and b):
            continue
        (begin, begin_era), (end, end_era) = a, b
        if begin_era and not end_era and re.fullmatch(ERA_BCE, begin_era):
            return None  # "75 v. Chr.-20": BCE oder CE nicht entscheidbar
        if end_era and not begin_era:
            # "100-200 n. Chr." / "500-400 v. Chr.": Ära des Endes gilt für beide Seiten
            begin = (historical_year(str(abs(begin[0])), end_era), begin[1], begin[2])
        if begin[0] > end[0]:
            return None
        return build(begin, end, qualifier)
    return None


def parse_list(text: str, qualifier: str) -> TimeResult | None:
    """Aufzählungen einzelner Daten ("24.01.1986, 25.01.1986") als Intervall vom frühesten zum spätesten."""
    parts = [p.strip() for p in re.split(r"[;,]\s*", text) if p.strip()]
    if len(parts) < 2:
        return None
    points = [parse_endpoint(p) for p in parts]
    if not all(points):
        return None
    points = sorted((p[0] for p in points), key=lambda t: (t[0], t[1] or 0, t[2] or 0))
    return build(points[0], points[-1], qualifier)


def parse_open(text: str, qualifier: str) -> TimeResult | None:
    """Einseitig offene Angaben: "nach 1945", "vor 1905", "vor oder im Jahr 1905"."""
    m = re.fullmatch(r"(?:nach|ab)\s+(\d{3,4})", text)
    if m:
        return build((int(m.group(1)), None, None), None, qualifier)
    m = re.fullmatch(r"vor(?: oder im Jahr)?\s+(\d{3,4})", text)
    if m:
        return build(None, (int(m.group(1)), None, None), qualifier)
    return None


def parse_with_inner_range(text: str, qualifier: str) -> TimeResult | None:
    """Benannte Epoche mit Zahlenbereich in Klammern: "Römische Kaiserzeit (-15-476)"."""
    m = re.fullmatch(r"(?P<label>[^()\d]*[A-Za-zÄÖÜäöüß][^()\d]*)\((?P<range>[^()]*\d[^()]*)\)", text)
    if not m:
        m = re.fullmatch(r"(?P<label>[^()]*[A-Za-zÄÖÜäöüß][^()]*)\((?P<range>-?\d[^()]*)\)", text)
    if not m:
        return None
    result = parse_range(m.group("range").strip(), qualifier)
    if result:
        result.method = "rule_label_range"
    return result


def parse_date_tokens(text: str, qualifier: str) -> TimeResult | None:
    """Datumslisten mit abgekürzten Tagen ("30.09.1987, 01., 03., 04.10.1987", "08.-18.08.1987")."""
    text = re.sub(r"\([^)]*\)", " ", text)
    if not re.fullmatch(r"[\d.,/\-\s]+", text) or not re.search(r"\d{1,2}\.\d{1,2}\.\d{4}", text):
        return None
    month = year = None
    dates = []
    for token in reversed(re.findall(r"\d{1,2}\.(?:\d{1,2}\.)?(?:\d{4})?", text)):
        parts = token.rstrip(".").split(".")
        day = int(parts[0])
        if len(parts) > 1:
            month = int(parts[1])
        if len(parts) > 2:
            year = int(parts[2])
        if month is None or year is None:
            return None
        dates.append((year, month, day))
    dates.sort()
    return build(dates[0], dates[-1], qualifier)


def parse_between(text: str, qualifier: str) -> TimeResult | None:
    """"zwischen 1950 und 1997", auch innerhalb von Text ("Aufgenommen in Sri Lanka zwischen 1950 und 1997")."""
    m = re.search(r"zwischen\s+(\S+)\s+und\s+(\S+)", text, flags=re.IGNORECASE)
    if not m:
        return None
    a, b = parse_endpoint(m.group(1)), parse_endpoint(m.group(2).rstrip(".,;"))
    if not (a and b) or a[0] > b[0]:
        return None
    result = build(a[0], b[0], qualifier, "rule" if text.lower().startswith("zwischen") else "rule_embedded")
    result.score = 1.0 if result.method == "rule" else 0.6
    return result


def parse_serial(text: str, qualifier: str) -> TimeResult | None:
    """Bandzählungen mit Jahr in Klammern ("1 (1914)-5 (1917)"): frühestes bis spätestes Jahr im Text."""
    if not re.search(r"\d+\s*\(\d{4}\)", text):
        return None
    years = [int(y) for y in re.findall(r"(?<![\d/])\d{4}(?![\d])", text)]
    if len(years) < 2:
        return None
    result = build((min(years), None, None), (max(years), None, None), qualifier, "rule_embedded")
    result.score = 0.6
    return result


def parse_embedded(text: str, qualifier: str) -> TimeResult | None:
    """Datum oder Jahr in umgebendem Text ("Poststempel: Augsburg, 13.03.1978"); bei mehreren Jahren das Intervall."""
    found = re.findall(r"(?<![\d.])(?:\d{1,2}\.\d{1,2}\.(\d{4})|(\d{4})-\d{2}-\d{2}|(\d{4}))(?![\d])", text)
    years = {int(a or b or c) for a, b, c in found}
    if not years or not all(1000 <= y <= 2100 for y in years):
        return None
    if len(years) > 1:  # mehrere Jahre im Text: Intervall vom frühesten bis zum spätesten
        result = build((min(years), None, None), (max(years), None, None), qualifier, "rule_embedded")
        result.score = 0.5
        return result
    single = parse_endpoint(re.search(r"\d{1,2}\.\d{1,2}\.\d{4}|\d{4}-\d{2}-\d{2}|\d{4}", text).group())
    point = single[0] if len(found) == 1 else (next(iter(years)), None, None)
    result = build(point, point, qualifier, "rule_embedded")
    result.score = 0.6
    return result


def period_key(label: str) -> str:
    """Bezeichnung für den Tabellenvergleich normalisieren."""
    return re.sub(r"\s+", " ", label.casefold().replace("\u00ad", "")).strip(" .")


@cache
def load_periods() -> tuple[dict, dict]:
    """Geprüfte Perioden (periods.csv) und PeriodO-Perioden je als {normierte Bezeichnung: [Einträge]} laden."""
    tables = []
    for path in (PERIODS_PATH, PERIODO_PATH):
        table: dict[str, list[dict]] = {}
        if path.exists():
            with path.open(newline="", encoding="utf-8") as handle:
                for row in csv.DictReader(handle):
                    for key in ("begin_year", "end_year"):
                        row[key] = int(row[key]) if row[key] != "" else None  # leer = offenes Ende
                    table.setdefault(period_key(row["label"]), []).append(row)
        tables.append(table)
    return tuple(tables)


def period_candidates(label: str) -> list[dict]:
    """Alle Tabelleneinträge zu einer Bezeichnung (geprüfte zuerst, dann PeriodO)."""
    checked, periodo = load_periods()
    key = period_key(label)
    return checked.get(key, []) + periodo.get(key, [])


def parse_period(label: str, qualifier: str) -> TimeResult | None:
    """Benannte Epoche über die geprüfte Tabelle (periods.csv) auflösen.

    PeriodO-Einträge werden bewusst nicht automatisch übernommen: dieselbe Epoche hat dort oft mehrere
    Definitionen, und ein einzelner Treffer ist kein Konsens (z. B. "Römisches Reich" 1 Eintrag,
    "Roman Empire" 5 verschiedene). Sie dienen nur als Kandidaten für die Prüfliste.
    """
    candidates = load_periods()[0].get(period_key(label), [])
    intervals = {(c["begin_year"], c["end_year"]) for c in candidates}
    if len(intervals) != 1:
        return None
    first = candidates[0]
    result = build((first["begin_year"], None, None), (first["end_year"], None, None), qualifier, "table")
    result.source_uri = first.get("source_uri", "")
    return result


def parse_text(text: str) -> TimeResult:
    """Eine Zeitangabe ohne Strukturfelder auf Jahre und ISO 8601/EDTF abbilden."""
    cleaned, qualifier = clean(text)
    if not cleaned or cleaned.lower() in NO_DATE:
        return TimeResult(None, None, "", "no_date", 1.0)

    # von Hand geprüfte Einträge gelten für den unveränderten Text und haben Vorrang vor den Regeln
    checked = parse_period(text, qualifier)
    if checked:
        return checked

    # Index-Präfix vor Werten ("01: 1952; 02: 1951")
    if re.match(r"^\d{1,2}:\s*\d{4}", cleaned):
        cleaned = re.sub(r"(^|[;\s])\d{1,2}:\s*", r"\1", cleaned).strip(" ;")

    single = parse_endpoint(cleaned)
    if single:
        return build(single[0], single[0], qualifier)

    for parser in (
        parse_range,
        parse_centuries,
        parse_decade,
        parse_with_inner_range,
        parse_open,
        parse_date_tokens,
        parse_list,
        parse_between,
        parse_period,
        parse_serial,
        parse_embedded,
    ):
        result = parser(cleaned, qualifier)
        if result:
            return result
    return unmapped()


def parse_time(text: str | None, begin: str | None = None, end: str | None = None) -> TimeResult:
    """Zeitangabe (optional mit begin/end eines TimeSpan-Objekts) auf Jahre und ISO 8601/EDTF abbilden."""
    if begin or end:
        a = parse_endpoint(str(begin)) if begin else None
        b = parse_endpoint(str(end)) if end else None
        if (not begin or a) and (not end or b):
            return build(a[0] if a else None, b[0] if b else None, "", method="timespan")

    # mehrere Beschriftungen ("Early Minoan | Frühminoisch"): erste auswertbare gewinnt
    for piece in (text or "").split(" | "):
        result = parse_text(piece)
        if result.method != "unmapped":
            return result
    return unmapped()
