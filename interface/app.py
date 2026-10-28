"""Flask-Anwendung: Normalisierung von Metadatenwerten (dcType / medium / subject)."""
from __future__ import annotations

import math
import os
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file
from werkzeug.exceptions import RequestEntityTooLarge

import config
import jobs

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = config.MAX_UPLOAD_MB * 1024 * 1024
config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


@app.errorhandler(RequestEntityTooLarge)
def file_too_large(_error):
    return jsonify(error=f"Die Datei überschreitet das Upload-Limit von {config.MAX_UPLOAD_MB} MB."), 413


def _job_or_404(job_id: str):
    job = jobs.JOBS.get(job_id)
    if job is None:
        return None, (
            jsonify(error="Sitzung nicht gefunden (wurde der Server neu gestartet?). Bitte Datei erneut hochladen."),
            404,
        )
    return job, None


@app.get("/")
def index():
    cfg = config.field_cfg()
    return render_template(
        "index.html",
        field=config.FIELD,
        field_label=cfg["label"],
        fields=config.FIELDS,
        vocab_file=cfg["vocab_file"],
        split=cfg["split_on_commas"],
        threshold=config.DEFAULT_THRESHOLD,
        accept=",".join(sorted(".jsonl .ndjson .json".split())),
    )


@app.post("/api/upload")
def upload():
    file = request.files.get("file")
    if file is None or not file.filename:
        return jsonify(error="Bitte eine Datei auswählen."), 400
    try:
        threshold = float(request.form.get("threshold", config.DEFAULT_THRESHOLD))
    except ValueError:
        return jsonify(error="Die Ähnlichkeitsschwelle muss eine Zahl sein."), 400
    if not math.isfinite(threshold):
        return jsonify(error="Die Ähnlichkeitsschwelle muss eine endliche Zahl sein."), 400
    threshold = min(max(threshold, 0.0), 1.0)
    field = request.form.get("field") or config.FIELD
    if field not in config.FIELDS:
        return jsonify(error="Unbekanntes Feld."), 400

    job = jobs.create_job(file.filename, threshold, field)
    folder = config.UPLOAD_DIR / job.id
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / ("upload" + Path(file.filename).suffix.lower())
    file.save(path)
    jobs.start_processing(job, path)
    return jsonify(job_id=job.id)


@app.get("/api/jobs/<job_id>")
def job_state(job_id):
    job, err = _job_or_404(job_id)
    return err if err else jsonify(job.to_state())


@app.post("/api/jobs/<job_id>/go")
def job_go(job_id):
    job, err = _job_or_404(job_id)
    if err:
        return err
    payload = request.get_json(silent=True) or {}
    selected = payload.get("selected", [])
    if not isinstance(selected, list) or not all(isinstance(x, str) for x in selected):
        return jsonify(error="Ungültige Auswahl."), 400
    try:
        applied = job.go(selected)
    except ValueError as exc:
        return jsonify(error=str(exc)), 409
    return jsonify(applied=applied, state=job.to_state())


@app.get("/api/jobs/<job_id>/ids")
def job_ids(job_id):
    job, err = _job_or_404(job_id)
    if err:
        return err
    try:
        step = int(request.args.get("step", ""))
        ids = job.all_ids(step, request.args.get("variant", ""))
    except ValueError as exc:
        return jsonify(error=str(exc) or "Ungültige Anfrage."), 400
    return jsonify(ids=ids)


@app.get("/api/jobs/<job_id>/export/<kind>")
def job_export(job_id, kind):
    job, err = _job_or_404(job_id)
    if err:
        return err
    if kind not in {"zip", "data", "log", "report"}:
        return jsonify(error="Unbekannter Export."), 404
    if not job.finished:
        return jsonify(error="Der Export ist erst nach dem letzten Schritt möglich."), 409
    if kind == "report":
        report_format = request.args.get("format", "markdown")
        try:
            path = job.export_report(report_format)
        except ValueError as exc:
            return jsonify(error=str(exc)), 400
        return send_file(path, as_attachment=True, download_name=path.name)
    data_format = "jsonl" if request.args.get("data_format") == "jsonl" else "json"
    log_format = "json" if request.args.get("log_format") == "json" else "csv"
    paths = job.export(data_format, log_format)
    path = paths[kind]
    return send_file(path, as_attachment=True, download_name=path.name)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)