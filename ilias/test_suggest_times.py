import json
import tarfile
import tempfile
import unittest
from pathlib import Path

from suggest_times import iter_records, suggest

RECORDS = [
    {"kp_id": "a", "pipeline_id": "ds", "content": {"aggregatedCHO": {"temporal": ["Spätbarock"], "date": ["1855-1861"]}}},
    {"kp_id": "b", "pipeline_id": "ds", "content": {"aggregatedCHO": {"date": [{"@value": "um 1100", "@language": "de"}]}}},
]


class SuggestTest(unittest.TestCase):
    def test_status_levels(self):
        self.assertEqual(suggest("1855-1861")["status"], "ok")
        self.assertEqual(suggest("Poststempel: Anger, 13.03.1978")["status"], "check")
        self.assertEqual(suggest("Lichtermeer")["status"], "unmapped")

    def test_fuzzy_suggestion_for_typo(self):
        result = suggest("Spaetbarock")
        self.assertEqual((result["begin_year"], result["end_year"], result["status"]), (1720, 1780, "check"))
        self.assertIn("Spätbarock", result["note"])

    def test_reads_jsonl_json_and_tar(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            (folder / "a.jsonl").write_text("\n".join(json.dumps(r) for r in RECORDS), encoding="utf-8")
            (folder / "b.json").write_text(json.dumps(RECORDS), encoding="utf-8")
            with tarfile.open(folder / "c.tar.gz", "w:gz") as tar:
                tar.add(folder / "a.jsonl", arcname="a.jsonl")
            for name in ("a.jsonl", "b.json", "c.tar.gz"):
                self.assertEqual([r["kp_id"] for r in iter_records(folder / name)], ["a", "b"], name)
            self.assertEqual(len(list(iter_records(folder))), 6)


if __name__ == "__main__":
    unittest.main()
