import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import import_browser
from test_luogu import capture


class BrowserImportTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source_dir = self.root / "sources"
        self.capture_path = self.root / "luogu-practice.json"
        network = patch("socket.socket.connect", side_effect=AssertionError("Browser import must stay offline"))
        self.connect = network.start()
        self.addCleanup(network.stop)

    def write_capture(self, value):
        self.capture_path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")

    def import_capture(self):
        return import_browser.import_records(
            luogu_practice=self.capture_path, source_dir=self.source_dir)

    def test_saved_snapshot_preserves_capture_time_without_inventing_ac_events(self):
        value = capture()
        self.write_capture(value)
        with patch.object(import_browser.sync, "now", return_value="2030-01-01T00:00:00Z"):
            result = self.import_capture()
        stored = json.loads((self.source_dir / "luogu.json").read_text(encoding="utf-8"))
        self.assertEqual(stored, result["luogu"])
        self.assertEqual(stored["lastSuccess"], value["capturedAt"])
        self.assertEqual(stored["collectionMethod"], "browser_import")
        self.assertEqual(stored["coverage"], "solved_only")
        self.assertEqual(stored["undatedSolved"], ["luogu:CF1A", "luogu:P1001"])
        self.assertEqual(set(stored["attempted"]), {"luogu:CF1A", "luogu:P1001", "luogu:P1014"})
        self.assertEqual(stored["accepted"], [])
        self.assertEqual(stored["contests"], [])
        self.assertIsNone(stored["submissionCount"])
        self.assertIsNone(stored["profile"]["lastSuccess"])
        self.assertEqual(stored["reportedCounts"], {"solved": 2, "submitted": 585})
        self.connect.assert_not_called()

    def test_wrong_account_truncated_capture_and_invalid_json_preserve_existing_source(self):
        self.write_capture(capture())
        self.import_capture()
        output = self.source_dir / "luogu.json"
        original = output.read_bytes()
        wrong_account = capture()
        wrong_account["uid"] = 571083
        missing_problem = capture()
        missing_problem["solvedGroups"][0]["problems"].pop()
        invalid_inputs = [json.dumps(wrong_account), json.dumps(missing_problem), "{invalid json"]
        for raw in invalid_inputs:
            with self.subTest(raw=raw[:80]):
                self.capture_path.write_text(raw, encoding="utf-8")
                with self.assertRaises(ValueError):
                    self.import_capture()
                self.assertEqual(output.read_bytes(), original)
                self.assertFalse(output.with_suffix(".json.tmp").exists())
        self.connect.assert_not_called()

    def test_valid_empty_page_cannot_erase_established_passed_problems(self):
        self.write_capture(capture())
        self.import_capture()
        output = self.source_dir / "luogu.json"
        original = output.read_bytes()
        empty = capture()
        empty.update(solvedGroups=[], attempted=[], reportedSolved="通过0")
        self.write_capture(empty)
        with self.assertRaisesRegex(ValueError, "empty import would erase"):
            self.import_capture()
        self.assertEqual(output.read_bytes(), original)
        self.connect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
