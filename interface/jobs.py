"""Arbeitssitzungen (Jobs): Verarbeitung im Hintergrund, Schrittlogik, Export."""
from __future__ import annotations

import csv
import json
import re
import shutil
import threading
import time
import uuid
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from werkzeug.utils import secure_filename

import config
from data_utils import (
    apply_mapping,
    collect_variants,
    get_record_id,
    load_records,
    load_vocabulary,
)
from matching import get_matcher

JOBS: dict[str, "Job"] = {}

LOG_COLUMNS = [
    "record_id",
    "field",
    "old_value",
    "new_value",
    "vocabulary_term",
    "variant",
    "old_uri",
    "new_uri",
]

# Sprachprüfung der Eingabedatei: ganze Wörter, Groß-/Kleinschreibung egal
BOOK_RE = re.compile(r"\bbooks?\b", re.IGNORECASE)
BUCH_RE = re.compile(r"\b(?:buch|bücher)\b", re.IGNORECASE)
BOOK_THRESHOLD = 10  # mehr als so viele Treffer entscheiden über die Vokabularsprache

REPORT_FONT =config.BASE_DIR / "static" / "fonts" / "AtkinsonHyperlegibleNext.ttf"


class Job:
    def __init__(self, filename: str, threshold: float):
        self.id = uuid.uuid4().hex[:12]
        self.filename = filename
        self.stem = secure_filename(Path(filename).stem) or "daten"
        self.threshold = threshold
        self.created = time.time()
        self.lock = threading.RLock()

        self.field = config.FIELD
        self.split = config.field_cfg()["split_on_commas"]
        self.vocab_file = config.field_cfg()["vocab_file"]

        self.status = "processing"  # processing | ready | error
        self.message = "Wird gestartet …"
        self.progress = 0.0  # 0–1, nur während der Verarbeitung aussagekräftig
        self.warnings: list[str] = []

        self.records: list[dict] = []
        self.ids: list[str] = []
        self.steps: list[dict] = []  # {term, uri, candidates:[{variant,score,rec_idx}], state, applied}
        self.current: int | None = None
        self.log: list[dict] = []
        self.changed: set[int] = set()
        self.possible_records: set[int] = set()
        self.stats = {"records": 0, "distinct_values": 0, "conforming": 0, "candidates": 0}

    # ------------------------------------------------------------------ Verarbeitung
    def process(self, path: Path) -> None:
        try:
            self._set(message="Datei wird auf Sprache geprüft …", progress=0.01)
            self._choose_vocabulary(path)

            self._set(message="Vokabular wird geladen …", progress=0.03)
            vocab = load_vocabulary(config.VOCAB_DIR / self.vocab_file)
            vocab_terms = [v["term"] for v in vocab]
            vocab_set = set(vocab_terms)

            self._set(message="Datei wird gelesen …", progress=0.05)
            records = load_records(path, self.filename)
            if not records:
                raise ValueError("Die Datei enthält keine Datensätze.")

            self._set(message="Datensatz-IDs werden gelesen …", progress=0.15)
            ids, missing = [], 0
            for n, rec in enumerate(records, 1):
                rid, found = get_record_id(rec, n)
                ids.append(rid)
                missing += 0 if found else 1
            if missing:
                self.warnings.append(
                    f"{missing} Datensätze haben keine ID in {config.ID_FIELDS}; "
                    "stattdessen wird 'Datensatz Nr. N' verwendet."
                )

            self._set(message=f"Werte im Feld '{self.field}' werden gesammelt …", progress=0.2)
            variants = collect_variants(records, self.field, self.split)
            if not variants:
                raise ValueError(
                    f"Im Feld '{self.field}' wurden keine Werte gefunden "
                    f"(Pfad: {'.'.join(config.RECORD_PATH)}.{self.field}). Bitte config.py prüfen."
                )

            to_match = [v for v in variants if v not in vocab_set]
            matcher = get_matcher(config.MATCHER)

            self._set(message="Ähnlichkeitsanalyse wird vorbereitet (Modell wird geladen) …", progress=0.25)

            def progress(done, total):
                # Ähnlichkeitsanalyse nimmt den Bereich 25–95 % ein
                fraction = done / total if total else 1.0
                self._set(
                    message=f"Ähnlichkeitsanalyse … {done} / {total} Werte",
                    progress=0.25 + 0.7 * fraction,
                )

            by_term = matcher.match(to_match, vocab_terms, self.threshold, progress)

            self._set(message="Vorschläge werden zusammengestellt …", progress=0.96)
            steps = []
            n_cands = 0
            for entry in vocab:
                cands = [
                    {"variant": v, "score": round(float(s), 3), "rec_idx": variants[v]}
                    for v, s in by_term.get(entry["term"], [])
                ]
                cands.sort(key=lambda c: (-c["score"], -len(c["rec_idx"]), c["variant"].lower()))
                n_cands += len(cands)
                steps.append(
                    {
                        "term": entry["term"],
                        "uri": entry["uri"],
                        "candidates": cands,
                        "state": "pending" if cands else "skipped",
                        "applied": 0,
                    }
                )

            with self.lock:
                self.records = records
                self.ids = ids
                self.steps = steps
                self.possible_records = {
                    idx
                    for step in steps
                    for candidate in step["candidates"]
                    for idx in candidate["rec_idx"]
                }
                self.stats = {
                    "records": len(records),
                    "distinct_values": len(variants),
                    "conforming": len(variants) - len(to_match),
                    "candidates": n_cands,
                }
                self.current = self._next_pending(-1)
                self.status = "ready"
                self.progress = 1.0
                self.message = "Analyse abgeschlossen."
        except NotImplementedError as exc:
            self._set(status="error", message=str(exc))
        except (ValueError, FileNotFoundError) as exc:
            self._set(status="error", message=str(exc))
        except Exception as exc:  # noqa: BLE001 - dem Nutzer verständlich melden
            self._set(status="error", message=f"Unerwarteter Fehler: {exc}")
        finally:
            shutil.rmtree(path.parent, ignore_errors=True)

    def _choose_vocabulary(self, path: Path) -> None:
        """Sanity-Check: zählt "book" und "Buch" in der Eingabedatei und wählt ggf. das Vokabular."""
        if self.field != "dcType":
            return
        counts = {"book": 0, "buch": 0}
        with open(path, "r", encoding="utf-8-sig", errors="replace") as fh:
            for line in fh:
                counts["book"] += len(BOOK_RE.findall(line))
                counts["buch"] += len(BUCH_RE.findall(line))
        if max(counts.values()) > BOOK_THRESHOLD:
            lang = max(counts, key=counts.get)
            self.vocab_file = "dctype_en.csv" if lang == "book" else "dctype.csv"
            self.warnings.append(
                f"Sprachprüfung: \"{lang}\" kommt {counts[lang]}-mal in der Datei vor "
                f"(book: {counts['book']}, Buch: {counts['buch']}); Vokabular: {self.vocab_file}."
            )

    def _set(self, **kw) -> None:
        with self.lock:
            for k, v in kw.items():
                setattr(self, k, v)

    def _next_pending(self, after: int) -> int | None:
        for i in range(after + 1, len(self.steps)):
            if self.steps[i]["state"] == "pending":
                return i
        return None

    # ------------------------------------------------------------------ Schritte
    @property
    def finished(self) -> bool:
        return self.status == "ready" and self.current is None

    def go(self, selected: list[str]) -> dict:
        with self.lock:
            if self.status != "ready" or self.current is None:
                raise ValueError("Es gibt keinen aktiven Schritt.")
            step = self.steps[self.current]
            cmap = {c["variant"]: c for c in step["candidates"]}
            chosen = list(dict.fromkeys(v for v in selected if v in cmap))
            mapping = {v: (step["term"], step["uri"]) for v in chosen}
            rec_set = sorted({i for v in chosen for i in cmap[v]["rec_idx"]})

            step["accepted"] = [
                self._report_candidate(candidate)
                for candidate in step["candidates"]
                if candidate["variant"] in chosen
            ]
            step["declined"] = [
                self._report_candidate(candidate)
                for candidate in step["candidates"]
                if candidate["variant"] not in chosen
            ]
            n_changes = 0
            for i in rec_set:
                for ch in apply_mapping(self.records[i], self.field, self.split, mapping):
                    ch["record_id"] = self.ids[i]
                    self.log.append(ch)
                    self.changed.add(i)
                    n_changes += 1

            step["state"] = "done"
            step["applied"] = len(chosen)
            self.current = self._next_pending(self.current)
            return {"variants": len(chosen), "records": len(rec_set), "changes": n_changes}

    @staticmethod
    def _report_candidate(candidate: dict) -> dict:
        return {
            "variant": candidate["variant"],
            "score": candidate["score"],
            "records": len(candidate["rec_idx"]),
        }

    def all_ids(self, step_index: int, variant: str) -> list[str]:
        with self.lock:
            if not 0 <= step_index < len(self.steps):
                raise ValueError("Unbekannter Schritt.")
            for c in self.steps[step_index]["candidates"]:
                if c["variant"] == variant:
                    return [self.ids[i] for i in c["rec_idx"]]
        raise ValueError("Unbekannte Variante.")

    # ------------------------------------------------------------------ Zustand für das Interface
    def to_state(self) -> dict:
        with self.lock:
            cfg = config.field_cfg()
            state = {
                "job_id": self.id,
                "status": self.status,
                "message": self.message,
                "progress": self.progress,
                "warnings": self.warnings,
                "filename": self.filename,
                "field": self.field,
                "field_label": cfg["label"],
                "stats": dict(self.stats),
                "changes": len(self.log),
                "records_changed": len(self.changed),
                "finished": self.finished,
                "current": self.current,
                "steps": [],
                "current_step": None,
            }
            if self.status != "ready":
                return state
            state["steps"] = [
                {"term": s["term"], "n_candidates": len(s["candidates"]), "state": s["state"], "applied": s["applied"]}
                for s in self.steps
            ]
            if self.current is not None:
                s = self.steps[self.current]
                state["current_step"] = {
                    "index": self.current,
                    "term": s["term"],
                    "uri": s["uri"],
                    "candidates": [
                        {
                            "variant": c["variant"],
                            "score": c["score"],
                            "id_total": len(c["rec_idx"]),
                            "ids_preview": [self.ids[i] for i in c["rec_idx"][: config.IDS_PREVIEW]],
                        }
                        for c in s["candidates"]
                    ],
                }
            return state

    # ------------------------------------------------------------------ Export
    def export(self, data_format: str, log_format: str) -> dict[str, Path]:
        with self.lock:
            outdir = config.OUTPUT_DIR / self.id
            outdir.mkdir(parents=True, exist_ok=True)
            base = f"{self.stem}_{self.field}"

            ext = "jsonl" if data_format == "jsonl" else "json"
            data_path = outdir / f"{base}_normalisiert.{ext}"
            with open(data_path, "w", encoding="utf-8") as fh:
                if ext == "jsonl":
                    for rec in self.records:
                        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                else:
                    fh.write("[\n")
                    for i, rec in enumerate(self.records):
                        if i:
                            fh.write(",\n")
                        fh.write(json.dumps(rec, ensure_ascii=False))
                    fh.write("\n]\n")

            if log_format == "json":
                log_path = outdir / f"{base}_aenderungslog.json"
                payload = {
                    "quelle": self.filename,
                    "feld": self.field,
                    "vokabular": self.vocab_file,
                    "exportiert_am": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "anzahl_aenderungen": len(self.log),
                    "aenderungen": self.log,
                }
                log_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            else:
                log_path = outdir / f"{base}_aenderungslog.csv"
                with open(log_path, "w", encoding="utf-8-sig", newline="") as fh:
                    writer = csv.DictWriter(fh, fieldnames=LOG_COLUMNS, extrasaction="ignore")
                    writer.writeheader()
                    writer.writerows(self.log)

            zip_path = outdir / f"{base}_export.zip"
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.write(data_path, data_path.name)
                zf.write(log_path, log_path.name)
            return {"data": data_path, "log": log_path, "zip": zip_path}

    def export_report(self, report_format: str) -> Path:
        with self.lock:
            if not self.finished:
                raise ValueError("Der Bericht ist erst nach dem letzten Schritt verfügbar.")
            if report_format not in {"markdown", "pdf"}:
                raise ValueError("Unbekanntes Berichtsformat.")

            outdir = config.OUTPUT_DIR / self.id
            outdir.mkdir(parents=True, exist_ok=True)
            extension = "md" if report_format == "markdown" else "pdf"
            path = outdir / f"{self.stem}_{self.field}_verarbeitungsbericht.{extension}"
            report = self._report_data()
            if report_format == "markdown":
                path.write_text(self._markdown_report(report), encoding="utf-8")
            else:
                self._write_pdf_report(path, report)
            return path

    def _report_data(self) -> dict:
        accepted = [
            (step["term"], decision)
            for step in self.steps
            for decision in step.get("accepted", [])
        ]
        declined = [
            (step["term"], decision)
            for step in self.steps
            for decision in step.get("declined", [])
        ]
        return {
            "filename": self.filename,
            "field_label": config.field_cfg()["label"],
            "vocab_file": self.vocab_file,
            "threshold": self.threshold,
            "created": time.strftime("%Y-%m-%d %H:%M"),
            "total_records": len(self.records),
            "possible_records": len(self.possible_records),
            "changed_records": len(self.changed),
            "candidate_count": sum(len(step["candidates"]) for step in self.steps),
            "accepted_count": len(accepted),
            "declined_count": len(declined),
            "change_count": len(self.log),
            "accepted": accepted,
            "declined": declined,
        }

    @staticmethod
    def _markdown_report(report: dict) -> str:
        lines = [
            "# Verarbeitungsbericht",
            "",
            f"- **Quelldatei:** {report['filename']}",
            f"- **Metadatenfeld:** {report['field_label']}",
            f"- **Vokabular:** {report['vocab_file']}",
            f"- **Erstellt am:** {report['created']}",
            f"- **Eingestellte Ähnlichkeitsschwelle:** {report['threshold']:.2f}",
            "",
            "## Überblick",
            "",
            "| Kennzahl | Anzahl |",
            "| --- | ---: |",
            f"| Datensätze insgesamt | {report['total_records']} |",
            f"| Datensätze mit mindestens einem Vorschlag (hätten geändert werden können) | {report['possible_records']} |",
            f"| Tatsächlich geänderte Datensätze | {report['changed_records']} |",
            f"| Vorgeschlagene Varianten | {report['candidate_count']} |",
            f"| Angenommene Vorschläge | {report['accepted_count']} |",
            f"| Abgelehnte Vorschläge | {report['declined_count']} |",
            f"| Einzelne Änderungen an Feldwerten | {report['change_count']} |",
            "",
            "Ein Vorschlag ist ein vorhandener Wert, der dem jeweiligen Vorzugsbegriff "
            "zugeordnet wurde. Die Ähnlichkeit ist ein textbasierter Vergleichswert, "
            "keine Wahrscheinlichkeit für die fachliche Richtigkeit. Vorschläge wurden "
            "nur ab der eingestellten Schwelle angezeigt. Bei abgelehnten Vorschlägen "
            "blieben die ursprünglichen Werte unverändert.",
            "",
        ]
        for title, key in (("Angenommene Änderungen", "accepted"), ("Abgelehnte Vorschläge", "declined")):
            lines.extend(
                [
                    f"## {title}",
                    "",
                    "| Vorhandener Wert | Vorgeschlagener Vorzugsbegriff | Ähnlichkeit | Betroffene Datensätze |",
                    "| --- | --- | ---: | ---: |",
                ]
            )
            if report[key]:
                for term, decision in report[key]:
                    cells = (
                        decision["variant"],
                        term,
                        f"{decision['score']:.3f}",
                        str(decision["records"]),
                    )
                    lines.append("| " + " | ".join(cell.replace("|", "\\|").replace("\n", " ") for cell in cells) + " |")
            else:
                lines.append("| Keine | – | – | – |")
            lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _write_pdf_report(path: Path, report: dict) -> None:
        if not REPORT_FONT.is_file():
            raise FileNotFoundError(f"Die Schriftart für den PDF-Bericht fehlt: {REPORT_FONT}")
        if "AtkinsonHyperlegibleNext" not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont("AtkinsonHyperlegibleNext", str(REPORT_FONT)))

        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(
            name="ReportTitle",
            parent=styles["Title"],
            fontName="AtkinsonHyperlegibleNext",
            fontSize=20,
            leading=25,
            textColor=colors.HexColor("#173c36"),
            alignment=TA_LEFT,
            spaceAfter=12,
        ))
        styles.add(ParagraphStyle(
            name="ReportBody",
            parent=styles["BodyText"],
            fontName="AtkinsonHyperlegibleNext",
            fontSize=9,
            leading=13,
        ))
        styles.add(ParagraphStyle(
            name="ReportHeading",
            parent=styles["Heading2"],
            fontName="AtkinsonHyperlegibleNext",
            textColor=colors.HexColor("#173c36"),
            spaceBefore=10,
        ))
        styles.add(ParagraphStyle(
            name="ReportCell",
            parent=styles["BodyText"],
            fontName="AtkinsonHyperlegibleNext",
            fontSize=8,
            leading=10,
            splitLongWords=True,
        ))

        def paragraph(text: str, style: str = "ReportBody") -> Paragraph:
            return Paragraph(escape(str(text)), styles[style])

        story = [
            paragraph("Verarbeitungsbericht", "ReportTitle"),
            paragraph(f"Quelldatei: {report['filename']}"),
            paragraph(f"Metadatenfeld: {report['field_label']}"),
            paragraph(f"Vokabular: {report['vocab_file']}"),
            paragraph(f"Erstellt am: {report['created']}"),
            paragraph(f"Eingestellte Ähnlichkeitsschwelle: {report['threshold']:.2f}"),
            paragraph("Überblick", "ReportHeading"),
        ]
        stats = [
            ["Kennzahl", "Anzahl"],
            ["Datensätze insgesamt", str(report["total_records"])],
            ["Datensätze mit mindestens einem Vorschlag (hätten geändert werden können)", str(report["possible_records"])],
            ["Tatsächlich geänderte Datensätze", str(report["changed_records"])],
            ["Vorgeschlagene Varianten", str(report["candidate_count"])],
            ["Angenommene Vorschläge", str(report["accepted_count"])],
            ["Abgelehnte Vorschläge", str(report["declined_count"])],
            ["Einzelne Änderungen an Feldwerten", str(report["change_count"])],
        ]
        story.extend([
            Table(stats, colWidths=[125 * mm, 30 * mm], repeatRows=1, hAlign="LEFT"),
            Spacer(1, 7 * mm),
            paragraph(
                "Ein Vorschlag ist ein vorhandener Wert, der dem jeweiligen Vorzugsbegriff "
                "zugeordnet wurde. Die Ähnlichkeit ist ein textbasierter Vergleichswert, "
                "keine Wahrscheinlichkeit für die fachliche Richtigkeit. Vorschläge wurden "
                "nur ab der eingestellten Schwelle angezeigt. Bei abgelehnten Vorschlägen "
                "blieben die ursprünglichen Werte unverändert."
            ),
        ])
        for title, key in (("Angenommene Änderungen", "accepted"), ("Abgelehnte Vorschläge", "declined")):
            story.extend([
                paragraph(title, "ReportHeading"),
            ])
            rows = [[
                paragraph("Vorhandener Wert", "ReportCell"),
                paragraph("Vorzugsbegriff", "ReportCell"),
                paragraph("Ähnlichkeit", "ReportCell"),
                paragraph("Datensätze", "ReportCell"),
            ]]
            rows.extend(
                [
                    paragraph(decision["variant"], "ReportCell"),
                    paragraph(term, "ReportCell"),
                    paragraph(f"{decision['score']:.3f}", "ReportCell"),
                    paragraph(str(decision["records"]), "ReportCell"),
                ]
                for term, decision in report[key]
            )
            if len(rows) == 1:
                rows.append([paragraph("Keine", "ReportCell"), "", "", ""])
            story.append(Table(rows, colWidths=[48 * mm, 50 * mm, 28 * mm, 29 * mm], repeatRows=1, hAlign="LEFT"))

        def style_table(table: Table) -> None:
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e6f3ee")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#105544")),
                ("FONTNAME", (0, 0), (-1, -1), "AtkinsonHyperlegibleNext"),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#dce3e7")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]))

        for element in story:
            if isinstance(element, Table):
                style_table(element)

        doc = SimpleDocTemplate(
            str(path),
            pagesize=A4,
            rightMargin=18 * mm,
            leftMargin=18 * mm,
            topMargin=18 * mm,
            bottomMargin=18 * mm,
            title="Verarbeitungsbericht",
        )
        doc.build(story)


def create_job(filename: str, threshold: float) -> Job:
    job = Job(filename, threshold)
    JOBS[job.id] = job
    return job


def start_processing(job: Job, path: Path) -> None:
    threading.Thread(target=job.process, args=(path,), daemon=True).start()