from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import luogu


def problem(pid="P1001", title="A+B Problem"):
    return {"id": pid, "title": title, "url": f"https://www.luogu.com.cn/problem/{pid}"}


def capture():
    return {
        "platform": "luogu",
        "uid": 571082,
        "handle": "Lucius7",
        "sourceUrl": "https://www.luogu.com.cn/user/571082/practice",
        "capturedAt": "2026-09-08T01:21:21.942Z",
        "reportedSolved": "通过2",
        "reportedSubmitted": "提交585",
        "solvedGroups": [
            {"difficulty": "入门", "problems": [problem(), problem("CF1A", "Theatre Square")]},
        ],
        "attempted": [problem("P1014", "Cantor 表")],
    }


class LuoguTests(unittest.TestCase):
    def test_passed_problems_remain_undated_and_no_submission_total_is_invented(self):
        result = luogu.normalize_capture(capture())
        self.assertEqual(result["undatedSolved"], ["luogu:CF1A", "luogu:P1001"])
        self.assertEqual(result["attempted"], {"luogu:CF1A", "luogu:P1001", "luogu:P1014"})
        self.assertEqual(result["accepted"], [])
        self.assertEqual(result["contests"], {})
        self.assertEqual(result["capturedAt"], "2026-09-08T01:21:21.942Z")
        self.assertIsNone(result["submission_count"])
        self.assertEqual(result["reportedCounts"], {"solved": 2, "submitted": 585})
        for field in ("rating", "maxRating", "rank", "lastSuccess"):
            self.assertIsNone(result["profile"][field])
        self.assertTrue(result["warnings"])

    def test_problem_metadata_preserves_luogu_namespace_and_difficulty_label(self):
        result = luogu.normalize_capture(capture())
        self.assertEqual(result["problems"]["luogu:CF1A"], {
            "id": "luogu:CF1A", "platform": "luogu", "contestId": None,
            "index": "CF1A", "name": "Theatre Square",
            "url": "https://www.luogu.com.cn/problem/CF1A",
            "difficulty": None, "difficultyLabel": "入门",
        })
        self.assertIsNone(result["problems"]["luogu:P1014"]["difficultyLabel"])
        self.assertFalse(any(key.startswith("codeforces:") for key in result["problems"]))

    def test_matching_duplicates_are_deduplicated_without_losing_solved_status(self):
        value = capture()
        value["solvedGroups"][0]["problems"].append(problem())
        value["attempted"] += [problem(), problem("P1014", "Cantor 表")]
        result = luogu.normalize_capture(value)
        self.assertEqual(len(result["problems"]), 3)
        self.assertEqual(len(result["undatedSolved"]), 2)
        self.assertEqual(len(result["attempted"]), 3)
        self.assertEqual(result["problems"]["luogu:P1001"]["difficultyLabel"], "入门")

    def test_duplicate_count_cannot_hide_a_missing_problem(self):
        value = capture()
        value["solvedGroups"][0]["problems"] = [problem(), problem()]
        with self.assertRaisesRegex(ValueError, "unique captured problems"):
            luogu.normalize_capture(value)

    def test_other_users_or_origins_are_rejected(self):
        variants = {
            "platform": ["qoj", None], "uid": [571083, "571082", True],
            "handle": ["SomeoneElse", "lucius7"],
            "sourceUrl": ["https://www.luogu.com.cn/user/571083/practice",
                          "http://www.luogu.com.cn/user/571082/practice",
                          "https://example.com/user/571082/practice"],
        }
        for field, options in variants.items():
            for option in options:
                with self.subTest(field=field, option=option), self.assertRaises(ValueError):
                    value = capture()
                    value[field] = option
                    luogu.normalize_capture(value)

    def test_capture_requires_a_real_timestamp_with_an_explicit_timezone(self):
        for date in [None, 123, "2026-09-08", "2026-09-08T01:21:21",
                     "2026-02-30T01:21:21Z", "2026-09-08T25:21:21Z",
                     "2026-09-08T01:21:21+99:00", "2026-09-08T01:21:21+08:60",
                     "1970-01-01T00:00:00Z"]:
            with self.subTest(date=date), self.assertRaisesRegex(ValueError, "capturedAt"):
                value = capture()
                value["capturedAt"] = date
                luogu.normalize_capture(value)
        value = capture()
        value["capturedAt"] = "2026-09-08T09:21:21+08:00"
        self.assertEqual(luogu.normalize_capture(value)["accepted"], [])

    def test_problem_id_and_url_must_match_the_official_problem_path(self):
        variants = [
            {"id": "../P1001"}, {"id": "P1001?x=1"}, {"id": ""}, {"id": 1001},
            {"url": "https://www.luogu.com.cn/problem/P1002"},
            {"url": "https://www.luogu.com.cn.evil.test/problem/P1001"},
            {"url": "javascript:alert(1)"}, {"title": " "}, {"title": None},
        ]
        for update in variants:
            with self.subTest(update=update), self.assertRaises(ValueError):
                value = capture()
                value["solvedGroups"][0]["problems"][0].update(update)
                luogu.normalize_capture(value)

    def test_conflicting_duplicate_titles_or_difficulty_groups_fail(self):
        value = capture()
        value["attempted"].append(problem(title="Different problem"))
        with self.assertRaisesRegex(ValueError, "titles disagree"):
            luogu.normalize_capture(value)
        value = capture()
        value["solvedGroups"].append({"difficulty": "提高", "problems": [problem()]})
        with self.assertRaisesRegex(ValueError, "difficulty groups disagree"):
            luogu.normalize_capture(value)

    def test_bad_shapes_and_counts_fail_instead_of_becoming_empty_success(self):
        for field, options in {
            "solvedGroups": [None, {}, [None], [{"difficulty": "入门", "problems": None}]],
            "attempted": [None, {}, [None]],
            "reportedSolved": [None, 2, "通过3", "通过-2", "通过2题"],
            "reportedSubmitted": [None, 585, "585"],
        }.items():
            for option in options:
                with self.subTest(field=field, option=option), self.assertRaises(ValueError):
                    value = capture()
                    value[field] = option
                    luogu.normalize_capture(value)
        with self.assertRaises(ValueError):
            luogu.normalize_capture([])

    def test_valid_empty_capture_and_absent_optional_displayed_submit_count(self):
        value = capture()
        value.update(solvedGroups=[], attempted=[], reportedSolved="通过0")
        del value["reportedSubmitted"]
        result = luogu.normalize_capture(value)
        self.assertEqual(result["problems"], {})
        self.assertEqual(result["undatedSolved"], [])
        self.assertIsNone(result["reportedCounts"]["submitted"])

    def test_normalization_is_deterministic_and_does_not_mutate_capture(self):
        value = capture()
        original = deepcopy(value)
        first = luogu.normalize_capture(value)
        second = luogu.normalize_capture(value)
        self.assertEqual(first, second)
        self.assertEqual(value, original)
        first["problems"]["luogu:P1001"]["name"] = "changed"
        self.assertEqual(value, original)
        self.assertEqual(second["problems"]["luogu:P1001"]["name"], "A+B Problem")


if __name__ == "__main__":
    unittest.main()
