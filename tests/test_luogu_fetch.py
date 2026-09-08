import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import luogu
import sync

STAMP = '2026-09-08T03:00:00Z'


def page_context():
    return {'instance': 'main', 'template': 'user.show', 'status': 200, 'data': {
        'user': {'uid': 571082, 'name': 'Lucius7', 'passedProblemCount': 1, 'submittedProblemCount': 1},
        'passed': [{'pid': 'P1001', 'name': 'A+B Problem', 'difficulty': 1, 'type': 'P'}],
        'submitted': [{'pid': 'P1002', 'name': '过河卒', 'difficulty': 2, 'type': 'P'}],
    }}


def html(context=None):
    return '<html><script type="application/json" id="lentille-context">' + json.dumps(context or page_context()) + '</script></html>'


def snapshot():
    return sync.make_snapshot('luogu', **luogu.normalize_public_html(html(), STAMP), collectionMethod='http')


class LuoguPublicTests(unittest.TestCase):
    def test_public_html_preserves_unknown_dates_and_does_not_invent_submission_counts(self):
        result = luogu.normalize_public_html(html(), STAMP)
        self.assertEqual(result['undatedSolved'], ['luogu:P1001'])
        self.assertEqual(result['attempted'], {'luogu:P1001', 'luogu:P1002'})
        self.assertEqual(result['accepted'], [])
        self.assertIsNone(result['submission_count'])
        self.assertEqual(result['capturedAt'], STAMP)
        self.assertEqual(result['problems']['luogu:P1002']['difficultyLabel'], '普及−')
        self.assertEqual(result['reportedCounts']['submitted'], 1)  # The union is 2: these are different measures.

    def test_changed_account_truncated_list_and_duplicate_context_are_rejected(self):
        cases = []
        other = page_context(); other['data']['user']['uid'] = 1; cases.append(html(other))
        partial = page_context(); partial['data']['user']['passedProblemCount'] = 2; cases.append(html(partial))
        duplicate = page_context(); duplicate['data']['passed'] *= 2; cases.append(html(duplicate))
        missing = page_context(); del missing['data']['submitted']; cases.append(html(missing))
        cases += [html() + html(), '<html>Access verification required</html>']
        for document in cases:
            with self.subTest(document=document), self.assertRaises(ValueError):
                luogu.normalize_public_html(document, STAMP)

    def test_unknown_difficulty_is_nullable_without_discarding_a_solved_problem(self):
        data = page_context(); data['data']['passed'][0]['difficulty'] = 99
        result = luogu.normalize_public_html(html(data), STAMP)
        self.assertEqual(len(result['undatedSolved']), 1)
        self.assertIsNone(result['problems']['luogu:P1001']['difficultyLabel'])
        self.assertEqual(len(result['warnings']), 2)

    def test_fetch_is_one_request_without_credentials_and_stops_on_restrictions(self):
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = html().encode()
        opener = Mock(); opener.open.return_value = response
        with patch.object(luogu, 'build_opener', return_value=opener):
            self.assertEqual(len(luogu.fetch_public()['undatedSolved']), 1)
        request = opener.open.call_args.args[0]
        self.assertEqual(opener.open.call_count, 1)
        self.assertEqual(request.full_url, luogu.SOURCE_URL)
        self.assertFalse(any(key.lower() in ('cookie', 'authorization') for key, _ in request.header_items()))
        for code in (401, 403, 429):
            opener = Mock()
            opener.open.side_effect = HTTPError(luogu.SOURCE_URL, code, 'restricted', {}, io.BytesIO())
            with patch.object(luogu, 'build_opener', return_value=opener), self.assertRaises(luogu.AccessStopped):
                luogu.fetch_public()
            self.assertEqual(opener.open.call_count, 1)
        with self.assertRaises(luogu.AccessStopped):
            luogu.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://example.com/')

    def test_daily_budget_survives_repeated_runs_and_resets_next_utc_day(self):
        previous = snapshot()
        payload = luogu.normalize_public_html(html(), STAMP)
        with tempfile.TemporaryDirectory() as directory, patch.object(sync, 'SOURCE_DIR', Path(directory)), patch.object(luogu, 'fetch_public', return_value=payload) as fetch:
            with patch.object(sync, 'now', return_value=STAMP):
                first = sync.collect_luogu(None, previous)
                second = sync.collect_luogu(None, first)
            self.assertEqual(fetch.call_count, 1)
            self.assertEqual(first, second)
            with patch.object(sync, 'now', return_value='2026-09-09T00:17:00Z'):
                sync.collect_luogu(None, first)
            self.assertEqual(fetch.call_count, 2)

    def test_restriction_pauses_future_requests_and_keeps_the_previous_snapshot(self):
        previous = snapshot(); original = copy.deepcopy(previous)
        with tempfile.TemporaryDirectory() as directory, patch.object(sync, 'SOURCE_DIR', Path(directory)), patch.object(luogu, 'fetch_public', side_effect=luogu.AccessStopped('HTTP 429: stopped')) as fetch:
            with patch.object(sync, 'now', return_value=STAMP):
                retained, error = sync.refresh_source('luogu', sync.collect_luogu, None, previous)
            self.assertEqual(retained, original)
            self.assertIn('429', error)
            with patch.object(sync, 'now', return_value='2026-09-09T00:17:00Z'):
                retained, error = sync.refresh_source('luogu', sync.collect_luogu, None, previous)
            self.assertEqual(fetch.call_count, 1)
            self.assertEqual(retained, original)
            self.assertTrue(sync.read_json(Path(directory) / 'luogu-request.json')['paused'])

    def test_empty_success_cannot_replace_established_solves(self):
        empty = page_context(); empty['data'].update(passed=[], submitted=[]); empty['data']['user']['passedProblemCount'] = 0
        payload = luogu.normalize_public_html(html(empty), STAMP)
        previous = snapshot()
        with tempfile.TemporaryDirectory() as directory, patch.object(sync, 'SOURCE_DIR', Path(directory)), patch.object(luogu, 'fetch_public', return_value=payload), patch.object(sync, 'now', return_value=STAMP):
            retained, error = sync.refresh_source('luogu', sync.collect_luogu, None, previous)
            self.assertEqual(retained, previous)
            self.assertIsNotNone(error)
            self.assertTrue(sync.read_json(Path(directory) / 'luogu-request.json')['paused'])


if __name__ == '__main__':
    unittest.main()
