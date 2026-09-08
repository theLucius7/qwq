from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from qoj_import import normalize_capture


def submission(identifier, cid=7, pid=42, accepted=True):
    return {
        "id": f"#{identifier}", "problem": f"#{pid}. Example & Test",
        "problemUrl": f"/contest/{cid}/problem/{pid}" if cid else f"/problem/{pid}",
        "submitter": "Lucius7", "verdict": "AC ✓" if accepted else "Compile Error",
        "score": "100.000000" if accepted else None,
        "fullScore": "100.000000" if accepted else None,
        "submitTime": "2026-09-08 00:00:00",
    }


def capture_page(number, rows, final):
    pager = [
        {"active": False, "disabled": True, "text": "", "url": None},
        {"active": True, "disabled": False, "text": str(number), "url": "/submissions?submitter=Lucius7" + (f"&page={number}" if number != 1 else "")},
    ]
    if not final:
        pager.append({"active": False, "disabled": False, "text": str(number + 1), "url": f"/submissions?submitter=Lucius7&page={number + 1}"})
    pager.append({"active": False, "disabled": final, "text": "", "url": None if final else f"/submissions?submitter=Lucius7&page={number + 1}"})
    return {"page": number, "rows": rows, "pager": pager}


def contest(cid=7, pid=42, title="Example Contest"):
    return {"cid": cid, "headings": ["QOJ.ac", title, "Notice", "My Questions"], "table": f'<table><thead><tr><th>#</th><th>Problem</th></tr></thead><tbody><tr><td>A</td><td><a href="/contest/{cid}/problem/{pid}">Example &amp; Test</a></td></tr><tr><td>B</td><td><a href="/contest/{cid}/problem/{pid + 1}">Unattempted</a></td></tr></tbody></table>'}


def captures(two_pages=False):
    submissions = {"platform": "qoj", "handle": "Lucius7", "sourceUrl": "https://qoj.ac/submissions?submitter=Lucius7", "capturedAt": "2026-09-08T01:19:34.819Z", "pages": []}
    if two_pages:
        submissions["pages"] = [capture_page(1, [submission(identifier) for identifier in range(20, 10, -1)], False), capture_page(2, [submission(10, accepted=False)], True)]
    else:
        submissions["pages"] = [capture_page(1, [submission(20), submission(19, accepted=False)], True)]
    contests = {"platform": "qoj", "handle": "Lucius7", "capturedAt": "2026-09-08T01:22:00.000Z", "pages": [contest()]}
    return submissions, contests


class QojImportTests(unittest.TestCase):
    def test_capture_normalization_preserves_ac_times_attempts_and_complete_contest(self):
        submissions, contests = captures(two_pages=True)
        original = deepcopy((submissions, contests))
        with patch("urllib.request.OpenerDirector.open", side_effect=AssertionError("offline import attempted network")):
            result = normalize_capture(submissions, contests)
        self.assertEqual(result["submission_count"], 11)
        self.assertEqual(len(result["accepted"]), 10)
        self.assertEqual(result["accepted"][0]["epoch"], 1788796800)
        self.assertEqual(result["attempted"], {"qoj:42"})
        self.assertEqual(result["contests"]["qoj:7"]["problems"], ["qoj:42", "qoj:43"])
        self.assertTrue(result["contests"]["qoj:7"]["hasSubmissions"])
        self.assertEqual(result["profile"]["lastSuccess"], None)
        self.assertEqual(result["capturedAt"], submissions["capturedAt"])
        self.assertEqual((submissions, contests), original)

    def test_account_source_and_timestamp_must_be_verified(self):
        mutations = [
            ("handle", "AnotherUser"), ("sourceUrl", "https://example.com/submissions?submitter=Lucius7"),
            ("sourceUrl", "https://qoj.ac/submissions?submitter=AnotherUser"),
            ("sourceUrl", "https://qoj.ac/submissions?submitter=Lucius7&page=2"),
            ("sourceUrl", "https://qoj.ac:8443/submissions?submitter=Lucius7"),
            ("sourceUrl", "https://user@qoj.ac/submissions?submitter=Lucius7"),
            ("capturedAt", "2026-09-08"), ("capturedAt", "2026-02-30T01:00:00Z"),
            ("capturedAt", "2025-01-01T00:00:00Z"),
        ]
        for key, value in mutations:
            submissions, contests = captures()
            submissions[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                normalize_capture(submissions, contests)
        submissions, contests = captures()
        contests["capturedAt"] = "not a timestamp"
        with self.assertRaisesRegex(ValueError, "capturedAt"):
            normalize_capture(submissions, contests)

    def test_missing_pages_and_unverified_last_page_fail_without_network(self):
        submissions, contests = captures(two_pages=True)
        submissions["pages"].pop()
        with patch("urllib.request.OpenerDirector.open", side_effect=AssertionError("offline import attempted network")), self.assertRaisesRegex(ValueError, "missing pages"):
            normalize_capture(submissions, contests)
        submissions, contests = captures(two_pages=True)
        submissions["pages"][1]["page"] = 3
        with self.assertRaisesRegex(ValueError, "consecutive"):
            normalize_capture(submissions, contests)
        submissions, contests = captures(two_pages=True)
        submissions["pages"][0]["rows"].pop()
        with self.assertRaisesRegex(ValueError, "incomplete intermediate"):
            normalize_capture(submissions, contests)
        submissions, contests = captures()
        submissions["pages"][0]["pager"] = []
        with self.assertRaisesRegex(ValueError, "pagination controls"):
            normalize_capture(submissions, contests)

    def test_missing_contest_is_not_replaced_with_a_network_fetch(self):
        submissions, contests = captures()
        contests["pages"] = []
        with patch("urllib.request.OpenerDirector.open", side_effect=AssertionError("offline import attempted network")), self.assertRaisesRegex(ValueError, "missing a required page"):
            normalize_capture(submissions, contests)

    def test_extra_exported_contests_do_not_imply_participation(self):
        submissions, contests = captures()
        contests["pages"].append(contest(99, 42, "Reused Problem Contest"))
        result = normalize_capture(submissions, contests)
        self.assertEqual(set(result["contests"]), {"qoj:7"})
        self.assertEqual(result["problems"]["qoj:42"]["contestId"], "qoj:7")

    def test_previous_complete_catalogue_can_fill_missing_export_but_fresh_export_wins(self):
        submissions, contests = captures()
        initial = normalize_capture(submissions, contests)
        previous = {"schemaVersion": 1, "platform": "qoj", "handle": "Lucius7", "problems": list(initial["problems"].values()), "contests": list(initial["contests"].values())}
        missing = deepcopy(contests)
        missing["pages"] = []
        result = normalize_capture(submissions, missing, previous)
        self.assertEqual(result["contests"]["qoj:7"]["problems"], ["qoj:42", "qoj:43"])
        contests["pages"][0]["headings"][1] = "Fresh Contest Name"
        result = normalize_capture(submissions, contests, previous)
        self.assertEqual(result["contests"]["qoj:7"]["name"], "Fresh Contest Name")
        previous["contests"][0]["catalogComplete"] = False
        with self.assertRaisesRegex(ValueError, "missing a required page"):
            normalize_capture(submissions, missing, previous)

    def test_invalid_rows_and_pagination_are_not_silently_ignored(self):
        for field, value in [("id", "not an id"), ("submitter", "OtherUser"), ("problemUrl", "https://example.com/problem/42"), ("fullScore", "NaN"), ("submitTime", "missing")]:
            submissions, contests = captures()
            submissions["pages"][0]["rows"][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                normalize_capture(submissions, contests)
        submissions, contests = captures()
        submissions["pages"][0]["rows"][1]["id"] = "#20"
        with self.assertRaisesRegex(ValueError, "distinct"):
            normalize_capture(submissions, contests)
        submissions, contests = captures()
        submissions["pages"][0]["pager"][1]["url"] += "&page=2"
        with self.assertRaisesRegex(ValueError, "pagination"):
            normalize_capture(submissions, contests)
        submissions, contests = captures(two_pages=True)
        submissions["pages"][0]["pager"][-1]["url"] = "/submissions?submitter=Lucius7&page=3"
        with self.assertRaisesRegex(ValueError, "not consecutive"):
            normalize_capture(submissions, contests)

    def test_capture_values_are_escaped_before_rebuilding_html(self):
        submissions, contests = captures()
        submissions["pages"][0]["rows"][0]["problem"] = '#42. <a href="/contest/99/problem/100">Text & Tags</a>'
        result = normalize_capture(submissions, contests)
        self.assertEqual(result["problems"]["qoj:42"]["name"], '<a href="/contest/99/problem/100">Text & Tags</a>')
        self.assertEqual(set(result["contests"]), {"qoj:7"})

    def test_decorated_submitter_requires_the_matching_profile_url(self):
        submissions, contests = captures()
        row = submissions["pages"][0]["rows"][0]
        row["submitter"] = "Lucius7#"
        with self.assertRaisesRegex(ValueError, "another user"):
            normalize_capture(submissions, contests)
        row["submitterUrl"] = "//qoj.ac/user/profile/Lucius7"
        self.assertEqual(normalize_capture(submissions, contests)["submission_count"], 2)
        for url in ("//qoj.ac/user/profile/AnotherUser", "https://example.com/user/profile/Lucius7", "https://qoj.ac:8443/user/profile/Lucius7", "http://qoj.ac/user/profile/Lucius7"):
            row["submitterUrl"] = url
            with self.subTest(url=url), self.assertRaisesRegex(ValueError, "profile identifies another user or origin"):
                normalize_capture(submissions, contests)

    def test_only_normalized_public_fields_reach_the_result(self):
        submissions, contests = captures()
        marker = "not-a-real-private-value"
        submissions["cookie"] = marker
        submissions["pages"][0]["html"] = marker
        submissions["pages"][0]["rows"][0]["sourceCode"] = marker
        contests["authorization"] = marker
        contests["pages"][0]["hiddenState"] = marker
        result = normalize_capture(submissions, contests)
        self.assertNotIn(marker, repr(result))
        self.assertEqual(set(result["problems"]["qoj:42"]), {"id", "platform", "contestId", "index", "name", "url", "difficulty"})
        self.assertEqual(set(result["accepted"][0]), {"id", "platform", "problemId", "epoch", "url"})


if __name__ == "__main__":
    unittest.main()
