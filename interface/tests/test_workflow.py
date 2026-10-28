import csv
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import config
import jobs
from app import app
from data_utils import get_record_id
from jobs import Job


class WorkflowTests(unittest.TestCase):
    def test_upload_api_rejects_non_finite_threshold_and_oversized_file(self):
        client = app.test_client()
        page = client.get("/")
        self.assertEqual(page.status_code, 200)
        self.assertIn('id="report-format"', page.get_data(as_text=True))
        self.assertIn('id="download-report"', page.get_data(as_text=True))

        invalid_threshold = client.post(
            "/api/upload",
            data={"threshold": "nan", "file": (io.BytesIO(b"{}"), "records.jsonl")},
        )
        self.assertEqual(invalid_threshold.status_code, 400)
        self.assertIn("endliche Zahl", invalid_threshold.get_json()["error"])

        original_limit = app.config["MAX_CONTENT_LENGTH"]
        app.config["MAX_CONTENT_LENGTH"] = 10
        try:
            oversized = client.post(
                "/api/upload",
                data={"file": (io.BytesIO(b"x" * 100), "records.jsonl")},
            )
        finally:
            app.config["MAX_CONTENT_LENGTH"] = original_limit
        self.assertEqual(oversized.status_code, 413)
        self.assertIn("Upload-Limit", oversized.get_json()["error"])

    def test_original_identifier_falls_back_to_nested_identifier_not_kp_id(self):
        record = {
            "kp_id": "kulturpool-id",
            "content": {"aggregatedCHO": {"identifier": ["source-record-42"]}},
        }

        self.assertEqual(get_record_id(record, 1), ("source-record-42", True))

    def test_processing_selection_and_export(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            vocab_dir = root / "vocabularies"
            vocab_dir.mkdir()
            (vocab_dir / "dctype.csv").write_text("term,uri\nFotografie,\n", encoding="utf-8")

            upload_dir = root / "uploads" / "job"
            upload_dir.mkdir(parents=True)
            input_path = upload_dir / "upload.jsonl"
            record = {
                "kp_id": "not-the-original-id",
                "src_id": "institution-17",
                "content": {
                    "aggregatedCHO": {
                        "dcType": [{"type": "Concept", "id": "https://old.example/concept", "prefLabel": ["Photographie"]}]
                    }
                },
            }
            input_path.write_text(json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")

            with (
                patch.object(config, "VOCAB_DIR", vocab_dir),
                patch.object(config, "OUTPUT_DIR", root / "output"),
            ):
                job = Job("records.jsonl", 0.7)
                job.process(input_path)

                self.assertEqual(job.status, "ready", job.message)
                self.assertEqual(job.current, 0)
                result = job.go(["Photographie"])
                self.assertEqual(result["changes"], 1)
                self.assertTrue(job.finished)

                paths = job.export("jsonl", "csv")
                exported = json.loads(paths["data"].read_text(encoding="utf-8"))
                concept = exported["content"]["aggregatedCHO"]["dcType"][0]
                self.assertEqual(concept["prefLabel"], ["Fotografie"])
                self.assertNotIn("id", concept)
                with paths["log"].open(encoding="utf-8-sig", newline="") as log_file:
                    log = next(csv.DictReader(log_file))
                self.assertEqual(log["record_id"], "institution-17")
                self.assertEqual(log["old_value"], "Photographie")
                self.assertEqual(log["new_value"], "Fotografie")

                json_paths = job.export("json", "json")
                self.assertEqual(json.loads(json_paths["data"].read_text(encoding="utf-8")), job.records)
                json_log = json.loads(json_paths["log"].read_text(encoding="utf-8"))
                self.assertEqual(json_log["anzahl_aenderungen"], 1)
                self.assertEqual(json_log["aenderungen"][0]["record_id"], "institution-17")
                report = job.export_report("markdown").read_text(encoding="utf-8")
                self.assertIn("Angenommene Vorschläge | 1", report)
                self.assertIn("Tatsächlich geänderte Datensätze | 1", report)
                self.assertIn("Einzelne Änderungen an Feldwerten | 1", report)

    def test_unselected_candidate_can_be_left_unchanged(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            vocab_dir = root / "vocabularies"
            vocab_dir.mkdir()
            (vocab_dir / "dctype.csv").write_text("term\nFotografie\n", encoding="utf-8")
            upload_dir = root / "uploads" / "job"
            upload_dir.mkdir(parents=True)
            input_path = upload_dir / "upload.jsonl"
            record = {
                "src_id": "institution-18",
                "content": {"aggregatedCHO": {"dcType": ["Photographie"]}},
            }
            input_path.write_text(json.dumps(record) + "\n", encoding="utf-8")

            with (
                patch.object(config, "VOCAB_DIR", vocab_dir),
                patch.object(config, "OUTPUT_DIR", root / "output"),
            ):
                job = Job("records.jsonl", 0.7)
                job.process(input_path)
                result = job.go([])

            self.assertTrue(job.finished)
            self.assertEqual(result["changes"], 0)
            self.assertEqual(job.records[0]["content"]["aggregatedCHO"]["dcType"], ["Photographie"])
            self.assertEqual(job.steps[0]["accepted"], [])
            self.assertEqual(job.steps[0]["declined"], [
                {"variant": "Photographie", "score": job.steps[0]["candidates"][0]["score"], "records": 1}
            ])

            with patch.object(config, "OUTPUT_DIR", root / "output"):
                markdown_path = job.export_report("markdown")
                markdown = markdown_path.read_text(encoding="utf-8")
                self.assertIn("Datensätze insgesamt | 1", markdown)
                self.assertIn("Datensätze mit mindestens einem Vorschlag (hätten geändert werden können) | 1", markdown)
                self.assertIn("Tatsächlich geänderte Datensätze | 0", markdown)
                self.assertIn("Abgelehnte Vorschläge | 1", markdown)
                self.assertIn("Photographie", markdown)
                self.assertIn("Fotografie", markdown)

                pdf_path = job.export_report("pdf")
                pdf_content = pdf_path.read_bytes()
                self.assertTrue(pdf_content.startswith(b"%PDF-"))
                self.assertIn(b"AtkinsonHyperlegibleNext", pdf_content)

                jobs.JOBS[job.id] = job
                self.addCleanup(jobs.JOBS.pop, job.id, None)
                response = app.test_client().get(
                    f"/api/jobs/{job.id}/export/report?format=markdown"
                )
                self.assertEqual(response.status_code, 200)
                self.assertIn("Photographie", response.get_data(as_text=True))
                response.close()
                pdf_response = app.test_client().get(
                    f"/api/jobs/{job.id}/export/report?format=pdf"
                )
                self.assertEqual(pdf_response.status_code, 200)
                self.assertEqual(pdf_response.mimetype, "application/pdf")
                self.assertTrue(pdf_response.get_data().startswith(b"%PDF-"))
                pdf_response.close()
                invalid_format = app.test_client().get(
                    f"/api/jobs/{job.id}/export/report?format=html"
                )
                self.assertEqual(invalid_format.status_code, 400)


if __name__ == "__main__":
    unittest.main()
