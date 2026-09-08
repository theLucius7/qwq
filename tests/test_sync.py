import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("sync", Path(__file__).resolve().parents[1] / "scripts" / "sync.py")
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)


class FakeClient:
    def __init__(self, pages):
        self.pages = iter(pages)
        self.urls = []

    def get(self, url):
        self.urls.append(url)
        return next(self.pages)


class SyncTests(unittest.TestCase):
    def test_atcoder_inclusive_timestamp_overlap_does_not_lose_equal_second_ac(self):
        first = [{"id": i, "epoch_second": i + 10} for i in range(499)]
        first.append({"id": 499, "epoch_second": 509})
        second = [{"id": 499, "epoch_second": 509}, {"id": 500, "epoch_second": 509}, {"id": 501, "epoch_second": 510}]
        client = FakeClient([first, second])
        records = sync.atcoder_submissions(client)
        self.assertEqual(len(records), 502)
        self.assertIn("from_second=509", client.urls[1])
        self.assertEqual(len({item["id"] for item in records}), 502)

    def test_atcoder_impossible_timestamp_page_fails_instead_of_silently_truncating(self):
        client = FakeClient([[{"id": i, "epoch_second": 42} for i in range(500)]] * 2)
        with self.assertRaisesRegex(ValueError, "did not advance"):
            sync.atcoder_submissions(client)

    def test_cf_pagination_overlaps_and_deduplicates(self):
        client = FakeClient([[{"id": i} for i in range(1000)], [{"id": i} for i in range(990, 1010)]])
        result = sync.codeforces_submissions(client)
        self.assertEqual(len(result), 1010)
        self.assertIn("from=1&count=1000", client.urls[0])
        self.assertIn("from=991&count=1000", client.urls[1])

    def test_gym_parser_only_accepts_official_problem_table_and_decodes_names(self):
        parsed = sync.parse_gym('''<a href="/gym/100001/problem/Z">unrelated</a>
          <table class="problems"><tr><td><a href="/gym/100001/problem/A">A</a></td>
          <td><a href="/gym/100001/problem/A">A &amp; B</a></td></tr>
          <tr><td><a href="/gym/100001/problem/B">B</a></td><td><a href="/gym/100001/problem/B"><span>Second</span></a></td></tr></table>''', 100001)
        self.assertEqual([problem["index"] for problem in parsed], ["A", "B"])
        self.assertEqual(parsed[0]["name"], "A & B")
        self.assertEqual(parsed[1]["url"], "https://codeforces.com/gym/100001/problem/B")

    def test_problem_identity_preserves_gym_and_missing_rating(self):
        problem = sync.cf_problem({"contestId": 100001, "index": "C", "name": "Test"})
        self.assertEqual(problem["id"], "codeforces:100001:C")
        self.assertIsNone(problem["difficulty"])
        self.assertEqual(sync.codeforces_kind({"id": 1234, "name": "Round (Div. 1 + Div. 2)"}), "Div. 1 + 2")

    def test_failed_source_preserves_previous_success_and_fails_without_cache(self):
        problem = sync.cf_problem({"contestId": 100001, "index": "A", "name": "First"})
        previous = {"schemaVersion": 1, "handle": sync.HANDLE, "lastSuccess": "2026-09-01T00:00:00Z", "submissionCount": 1, "problems": [problem], "contests": [{"id": "codeforces:100001", "problems": [problem["id"]]}], "accepted": [{"id": 1, "problemId": problem["id"], "epoch": 123}], "attempted": [problem["id"]]}
        before = copy.deepcopy(previous)

        def failing(*args):
            raise RuntimeError("upstream unavailable")

        snapshot, error = sync.refresh_source("codeforces", failing, None, previous)
        self.assertEqual(snapshot, before)
        self.assertEqual(previous, before)
        self.assertIn("upstream unavailable", error)
        self.assertIsNot(snapshot, previous)
        with self.assertRaisesRegex(RuntimeError, "first sync failed"):
            sync.refresh_source("codeforces", failing, None, None)

    def test_atomic_json_preserves_unicode(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nested" / "data.json"
            sync.atomic_json(path, {"title": "解题日志"})
            self.assertEqual(sync.read_json(path), {"title": "解题日志"})
            self.assertFalse(path.with_suffix(".json.tmp").exists())

    def test_missing_cf_catalogue_cannot_turn_one_known_ac_into_a_full_clear(self):
        class MissingCatalogue:
            def get(self, url, as_json=True):
                if "/user.status" in url:
                    return [{"id": 9, "contestId": 1234, "problem": {"contestId": 1234, "index": "A", "name": "A test"}, "verdict": "OK", "creationTimeSeconds": 123}]
                if "/problemset.problems" in url:
                    return {"problems": []}
                if "gym=true" in url:
                    return []
                if "/contest.list" in url:
                    return [{"id": 1234, "name": "Test Round", "phase": "FINISHED", "startTimeSeconds": 100}]
                if "/user.info" in url:
                    return [{"handle": "Lucius7"}]
                raise AssertionError(url)

        snapshot = sync.collect_codeforces(MissingCatalogue(), None)
        contest = snapshot["contests"][0]
        self.assertEqual(contest["problems"], ["codeforces:1234:A"])
        self.assertTrue(contest["hasSubmissions"])
        self.assertFalse(contest["catalogComplete"])


if __name__ == "__main__":
    unittest.main()
