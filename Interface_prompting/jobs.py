"""Arbeitssitzungen (Jobs): Verarbeitung im Hintergrund, Schrittlogik, Export."""
from __future__ import annotations

import csv
import json
import shutil
import threading
import time
import uuid
import zipfile
from pathlib import Path

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

        self.status = "processing"  # processing | ready | error
        self.message = "Wird gestartet …"
        self.warnings: list[str] = []

        self.records: list[dict] = []
        self.ids: list[str] = []
        self.steps: list[dict] = []  # {term, uri, candidates:[{variant,score,rec_idx}], state, applied}
        self.current: int | None = None
        self.log: list[dict] = []
        self.changed: set[int] = set()
        self.stats = {"records": 0, "distinct_values": 0, "conforming": 0, "candidates": 0}

    # ------------------------------------------------------------------ Verarbeitung
    def process(self, path: Path) -> None:
        try:
            self._set(message="Vokabular wird geladen …")
            vocab = load_vocabulary(config.vocab_path())
            vocab_terms = [v["term"] for v in vocab]
            vocab_set = set(vocab_terms)

            self._set(message="Datei wird gelesen …")
            records = load_records(path, self.filename)
            if not records:
                raise ValueError("Die Datei enthält keine Datensätze.")

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

            self._set(message=f"Werte im Feld '{self.field}' werden gesammelt …")
            variants = collect_variants(records, self.field, self.split)
            if not variants:
                raise ValueError(
                    f"Im Feld '{self.field}' wurden keine Werte gefunden "
                    f"(Pfad: {'.'.join(config.RECORD_PATH)}.{self.field}). Bitte config.py prüfen."
                )

            to_match = [v for v in variants if v not in vocab_set]
            matcher = get_matcher(config.MATCHER)

            def progress(done, total):
                self._set(message=f"Ähnlichkeitsanalyse … {done} / {total} Werte")

            by_term = matcher.match(to_match, vocab_terms, self.threshold, progress)

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
                self.stats = {
                    "records": len(records),
                    "distinct_values": len(variants),
                    "conforming": len(variants) - len(to_match),
                    "candidates": n_cands,
                }
                self.current = self._next_pending(-1)
                self.status = "ready"
                self.message = "Analyse abgeschlossen."
        except NotImplementedError as exc:
            self._set(status="error", message=str(exc))
        except (ValueError, FileNotFoundError) as exc:
            self._set(status="error", message=str(exc))
        except Exception as exc:  # noqa: BLE001 - dem Nutzer verständlich melden
            self._set(status="error", message=f"Unerwarteter Fehler: {exc}")
        finally:
            shutil.rmtree(path.parent, ignore_errors=True)

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
                    "vokabular": config.field_cfg()["vocab_file"],
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


def create_job(filename: str, threshold: float) -> Job:
    job = Job(filename, threshold)
    JOBS[job.id] = job
    return job


def start_processing(job: Job, path: Path) -> None:
    threading.Thread(target=job.process, args=(path,), daemon=True).start()