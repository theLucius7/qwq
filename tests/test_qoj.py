from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError
from urllib.request import Request

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import qoj


def submission_row(submission_id=10, problem_id=42, result='AC ✓', user='Lucius7', contest_id=None, date='2026-09-08 00:00:00'):
    problem_url = f'/contest/{contest_id}/problem/{problem_id}' if contest_id else f'/problem/{problem_id}'
    return f'''<tr><td><a href="/submission/{submission_id}">#{submission_id}</a></td>
      <td><a href="{problem_url}">Example &amp; Test</a></td>
      <td><a href="//qoj.ac/user/profile/{user}">{user}</a></td><td>{result}</td>
      <td>1ms</td><td>1MB</td><td>C++</td><td>1kb</td><td>{date}</td></tr>'''


def page(rows, next_page=None, current_page=1, pager=True):
    current_query = '' if current_page == 1 else f'&amp;page={current_page}'
    links = f'<li class="page-item active"><a href="submissions?submitter=Lucius7{current_query}">{current_page}</a></li>'
    if next_page:
        links += f'<li class="page-item"><a href="submissions?submitter=Lucius7&amp;page={next_page}">{next_page}</a></li>'
    pagination = f'<ul class="pagination">{links}</ul>' if pager else ''
    return f'<h2>Submissions</h2><table><tbody>{rows}</tbody></table>{pagination}'


class FakeClient:
    def __init__(self, responses):
        self.responses = responses
        self.urls = []

    def get(self, url):
        self.urls.append(url)
        return self.responses[url]


class QojTests(unittest.TestCase):
    def test_ac_score_is_exact_and_time_uses_utc_plus_eight(self):
        ac_forms = ['AC', 'Accepted', 'AC ✓', 'Accepted ✔', '<a class="uoj-score" data-full="100.000000" data-score="100.000000">AC ✓</a>', '<a class="uoj-score" data-full="200.0" data-score="200.0">200 ✔</a>']
        for result in ac_forms:
            rows, more = qoj.parse_submissions(page(submission_row(result=result)), 'Lucius7', 1)
            self.assertTrue(rows[0]['accepted'])
            self.assertEqual(rows[0]['epoch'], 1788796800)
            self.assertFalse(more)
        for result in ['Wrong Answer', '1000', '99.9', '100 ✓', '<a data-score="99.9">100</a>', '<a data-full="200" data-score="100">AC ✓</a>', '<a data-full="100" data-score="0">WA</a>']:
            rows, _ = qoj.parse_submissions(page(submission_row(result=result)), 'Lucius7', 1)
            self.assertFalse(rows[0]['accepted'])

    def test_invalid_scores_cannot_become_accepted(self):
        for score, full in [('NaN', '100'), ('Infinity', '100'), ('oops', '100'), ('0', '0'), ('100', 'NaN'), ('100', '-100')]:
            with self.subTest(score=score, full=full), self.assertRaisesRegex(ValueError, 'Invalid QOJ'):
                qoj.parse_submissions(page(submission_row(result=f'<a data-score="{score}" data-full="{full}">AC ✓</a>')), 'Lucius7', 1)

    def test_all_submissions_including_failed_are_retained_and_problem_ids_are_global(self):
        rows, _ = qoj.parse_submissions(page(submission_row(contest_id=7) + submission_row(9, result='Wrong Answer')), 'Lucius7', 1)
        self.assertEqual([row['problemId'] for row in rows], [42, 42])
        self.assertEqual(rows[0]['contestId'], 7)
        self.assertIsNone(rows[1]['contestId'])
        self.assertFalse(rows[1]['accepted'])
        self.assertEqual(rows[0]['name'], 'Example & Test')

    def test_next_page_is_read_from_pagination_and_duplicate_rows_are_deduplicated(self):
        client = FakeClient({
            'https://qoj.ac/submissions?submitter=Lucius7&page=1': page(submission_row(10) + submission_row(9), 2),
            'https://qoj.ac/submissions?submitter=Lucius7&page=2': page(submission_row(9) + submission_row(8), current_page=2),
        })
        self.assertEqual(len(qoj.get_submissions(client, 'Lucius7')), 3)
        self.assertEqual(len(client.urls), 2)

    def test_repeated_last_page_does_not_silently_truncate(self):
        client = FakeClient({
            'https://qoj.ac/submissions?submitter=Lucius7&page=1': page(submission_row(10), 2),
            'https://qoj.ac/submissions?submitter=Lucius7&page=2': page(submission_row(10), current_page=2),
        })
        with self.assertRaisesRegex(ValueError, 'did not advance'):
            qoj.get_submissions(client, 'Lucius7')

    def test_real_pagination_first_and_last_pages(self):
        rows = ''.join(submission_row(100 - index) for index in range(10))
        links = '<li class="page-item disabled"><a href="#"><span class="glyphicon glyphicon-backward"></span></a></li>'
        links += '<li class="page-item active"><a href="submissions?submitter=Lucius7">1</a></li>'
        links += ''.join(f'<li class="page-item"><a href="submissions?submitter=Lucius7&amp;page={number}">{number}</a></li>' for number in range(2, 8))
        links += '<li class="page-item"><a href="submissions?submitter=Lucius7&amp;page=2"><span class="glyphicon glyphicon-forward"></span></a></li>'
        document = page(rows, pager=False) + f'<ul class="pagination">{links}</ul>'
        parsed, more = qoj.parse_submissions(document, 'Lucius7', 1)
        self.assertEqual(len(parsed), 10)
        self.assertTrue(more)
        _, more = qoj.parse_submissions(page(rows, current_page=7), 'Lucius7', 7)
        self.assertFalse(more)

    def test_pagination_fails_closed_on_missing_current_page_or_skipped_next_page(self):
        rows = ''.join(submission_row(100 - index) for index in range(10))
        with self.assertRaisesRegex(ValueError, 'pagination missing'):
            qoj.parse_submissions(page(rows, pager=False), 'Lucius7', 1)
        with self.assertRaisesRegex(ValueError, 'pagination missing'):
            qoj.parse_submissions(page(submission_row(), pager=False), 'Lucius7', 2)
        malformed = page(rows, 2).replace('page-item active', 'page-item')
        with self.assertRaisesRegex(ValueError, 'current page is missing'):
            qoj.parse_submissions(malformed, 'Lucius7', 1)
        with self.assertRaisesRegex(ValueError, 'different current page'):
            qoj.parse_submissions(page(rows, 2), 'Lucius7', 2)
        with self.assertRaisesRegex(ValueError, 'skipped the next page'):
            qoj.parse_submissions(page(rows, 3), 'Lucius7', 1)
        wrong_user = page(rows, 2).replace('submitter=Lucius7&amp;page=2', 'submitter=Other&amp;page=2')
        with self.assertRaisesRegex(ValueError, 'selected user'):
            qoj.parse_submissions(wrong_user, 'Lucius7', 1)
        wrong_arrow = page(rows, 2).replace('</ul>', '<li><a href="submissions?submitter=Lucius7&amp;page=3"><span class="glyphicon-forward"></span></a></li></ul>')
        with self.assertRaisesRegex(ValueError, 'not consecutive'):
            qoj.parse_submissions(wrong_arrow, 'Lucius7', 1)

    def test_login_page_wrong_user_and_unknown_markup_are_not_empty_success(self):
        with self.assertRaises(qoj.AuthenticationRequired):
            qoj.parse_submissions('<form id="form-login"><input type="password"></form>', 'Lucius7', 1)
        with self.assertRaisesRegex(ValueError, 'another user'):
            qoj.parse_submissions(page(submission_row(user='someone_else')), 'Lucius7', 1)
        with self.assertRaisesRegex(ValueError, 'table missing'):
            qoj.parse_submissions('<h2>Error</h2>', 'Lucius7', 1)

    def test_session_cannot_be_forwarded_to_another_origin(self):
        request = Request('https://qoj.ac/submissions', headers={'Cookie': 'test-session'})
        redirect = qoj.SafeRedirect()
        for destination in ('https://example.com/login', 'http://qoj.ac/login', 'https://qoj.ac/login', 'https://qoj.ac:8443/submissions', 'https://someone@qoj.ac/submissions'):
            with self.assertRaises(qoj.AuthenticationRequired):
                redirect.redirect_request(request, None, 302, '', {}, destination)

    def test_rate_limit_stops_without_retrying_or_exposing_cookie(self):
        client = qoj.QojClient('private-test-cookie')
        client.opener = Mock()
        client.opener.open.side_effect = HTTPError('https://qoj.ac/submissions', 429, 'private-test-cookie', {}, None)
        with patch.object(qoj.time, 'sleep') as sleep:
            with self.assertRaisesRegex(RuntimeError, 'HTTP 429') as error:
                client.get('https://qoj.ac/submissions')
        self.assertEqual(client.opener.open.call_count, 1)
        sleep.assert_not_called()
        self.assertNotIn('private-test-cookie', str(error.exception))

    def test_transient_failures_have_bounded_retries_and_are_sanitized(self):
        client = qoj.QojClient('private-test-cookie')
        client.opener = Mock()
        client.opener.open.side_effect = URLError('private-test-cookie')
        with patch.object(qoj.time, 'sleep'):
            with self.assertRaisesRegex(RuntimeError, 'QOJ request failed') as error:
                client.get('https://qoj.ac/submissions')
        self.assertEqual(client.opener.open.call_count, 3)
        self.assertNotIn('private-test-cookie', str(error.exception))

    def test_problem_provenance_and_complete_contest_table(self):
        problem = qoj.parse_problem('''<html><body><aside><a href="/contest/999">Unrelated</a></aside><h2>#42. Example &amp; Test</h2><div><p>The problem was used in the following contests:</p><ul><li><a href="/contest/7">Example Contest</a></li></ul></div></body></html>''', 42)
        self.assertEqual(problem, {'name': 'Example & Test', 'relatedContestIds': [7]})
        contest = qoj.parse_contest('''<h1>QOJ</h1><h2>Example Contest</h2><table><thead><tr><th>#</th><th>Problem</th></tr></thead><tr><td>A</td><td><a href="/contest/7/problem/42">First</a></td></tr><tr><td>B</td><td><a href="/contest/7/problem/43">Second</a></td></tr></table>''', 7)
        self.assertEqual(contest['name'], 'Example Contest')
        self.assertEqual([p['id'] for p in contest['problems']], ['qoj:42', 'qoj:43'])

    def test_real_contest_layout_ignores_notice_and_question_tables(self):
        title = 'The 2026 ICPC China Shenyang National Invitational Programming Contest'
        rows = ''.join(f'<tr><td>{chr(65 + offset)}</td><td><a href="/contest/3945/problem/{19013 + offset}">Problem {offset}</a></td></tr>' for offset in range(13))
        document = f'<h1>QOJ.ac</h1><h1>{title}</h1><table><thead><tr><th>#</th><th>Problem</th></tr></thead><tbody>{rows}</tbody></table>'
        document += '<h2>Notice</h2><table><thead><tr><th>#</th><th>Message</th></tr></thead><tr><td>1</td><td><a href="/contest/3945/problem/99999">Unrelated link</a></td></tr></table>'
        document += '<h2>My Questions</h2><table><tr><td>1</td><td><a href="/contest/3945/problem/99998">Question link</a></td></tr></table>'
        contest = qoj.parse_contest(document, 3945)
        self.assertEqual(contest['name'], title)
        self.assertEqual(len(contest['problems']), 13)
        self.assertEqual([problem['index'] for problem in contest['problems']], list('ABCDEFGHIJKLM'))

    def test_only_contests_associated_with_submissions_are_fetched_including_wa_only(self):
        client = FakeClient({
            'https://qoj.ac/submissions?submitter=Lucius7&page=1': page(submission_row(10, contest_id=7, result='Wrong Answer')),
            'https://qoj.ac/contest/7': '<h2>Submitted Contest</h2><table><thead><tr><th>#</th><th>Problem</th></tr></thead><tr><td>A</td><td><a href="/contest/7/problem/42">First</a></td></tr><tr><td>B</td><td><a href="/contest/7/problem/43">Second</a></td></tr></table>',
        })
        result = qoj.collect(client, 'Lucius7', None)
        self.assertEqual(list(result['contests']), ['qoj:7'])
        self.assertTrue(result['contests']['qoj:7']['hasSubmissions'])
        self.assertEqual(result['accepted'], [])
        self.assertEqual(result['attempted'], {'qoj:42'})
        self.assertIsNone(result['profile']['lastSuccess'])
        self.assertFalse(any(url == 'https://qoj.ac/contests' for url in client.urls))

    def test_reused_problem_does_not_imply_participation_or_change_contest_activity_time(self):
        client = FakeClient({
            'https://qoj.ac/submissions?submitter=Lucius7&page=1': page(
                submission_row(12, contest_id=8, date='2026-09-08 02:00:00')
                + submission_row(11, date='2026-09-08 01:00:00')
                + submission_row(10, contest_id=7)),
            'https://qoj.ac/contest/7': '<h2>First Contest</h2><table><thead><tr><th>#</th><th>Problem</th></tr></thead><tr><td>A</td><td><a href="/contest/7/problem/42">First</a></td></tr></table>',
            'https://qoj.ac/contest/8': '<h2>Second Contest</h2><table><thead><tr><th>#</th><th>Problem</th></tr></thead><tr><td>B</td><td><a href="/contest/8/problem/42">First</a></td></tr></table>',
        })
        previous = {'problems': [{'id': 'qoj:42', 'platform': 'qoj', 'contestId': 'qoj:99', 'index': '42', 'name': 'First', 'url': 'https://qoj.ac/problem/42', 'difficulty': None, 'relatedContestIds': [7, 8, 99]}], 'contests': []}
        result = qoj.collect(client, 'Lucius7', previous)
        self.assertEqual(set(result['contests']), {'qoj:7', 'qoj:8'})
        self.assertEqual(result['contests']['qoj:7']['lastSubmissionEpoch'], 1788796800)
        self.assertEqual(result['contests']['qoj:8']['lastSubmissionEpoch'], 1788804000)
        self.assertEqual(result['problems']['qoj:42']['contestId'], 'qoj:8')
        self.assertNotIn('relatedContestIds', result['problems']['qoj:42'])
        self.assertTrue(all('/problem/' not in url for url in client.urls))

    def test_practice_only_submissions_remain_visible_without_invented_contest_membership(self):
        client = FakeClient({'https://qoj.ac/submissions?submitter=Lucius7&page=1': page(submission_row())})
        result = qoj.collect(client, 'Lucius7', None)
        self.assertEqual(result['contests'], {})
        self.assertEqual(result['attempted'], {'qoj:42'})
        self.assertEqual(len(result['accepted']), 1)
        self.assertEqual(len(client.urls), 1)


if __name__ == '__main__':
    unittest.main()
