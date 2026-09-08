import test from 'node:test';
import assert from 'node:assert/strict';
import { PLATFORM_NAMES, activeDashboard, contestMatrix, includedContest, solvedProblemIds, dateKey, shiftDay, firstAccepted, dailyCounts, cumulativeSeries, streaks, calendarDays, completion, matchesStatus } from '../public/model.js';

test('cumulative trend carries earlier solves forward, deduplicates repeats and stops before future dates', () => {
  const event = (id, problemId, time) => ({ id, problemId, epoch: Date.parse(time) / 1000 });
  const events = [
    event(5, 'qoj:future', '2026-01-03T16:00:00Z'),
    event(4, 'qoj:1', '2026-01-01T16:00:00Z'),
    event(3, 'atcoder:a', '2026-01-01T08:00:00Z'),
    event(2, 'codeforces:1:A', '2025-12-31T16:00:00Z'),
    event(1, 'atcoder:a', '2025-12-31T15:59:59Z'),
  ];
  assert.deepEqual(cumulativeSeries(events, '2026-01-01', '2026-01-03'), [
    { day: '2026-01-01', total: 2, added: 1 },
    { day: '2026-01-02', total: 3, added: 1 },
    { day: '2026-01-03', total: 3, added: 0 },
  ]);
});

test('cumulative trend includes leap days and represents inactive days without inventing solves', () => {
  assert.deepEqual(cumulativeSeries([], '2024-02-28', '2024-03-01'), [
    { day: '2024-02-28', total: 0, added: 0 },
    { day: '2024-02-29', total: 0, added: 0 },
    { day: '2024-03-01', total: 0, added: 0 },
  ]);
  const events = [{ id: 1, problemId: 'atcoder:a', epoch: Date.parse('2023-01-01T00:00:00Z') / 1000 }];
  assert.equal(cumulativeSeries(events, '2024-02-28', '2024-03-01').at(-1).total, 1);
});

test('solved problems without timestamps add to cumulative totals without inventing daily events', () => {
  const events = [{ id: 1, platform: 'qoj', problemId: 'qoj:42', epoch: Date.parse('2026-09-08T01:00:00Z') / 1000 }];
  const ids = solvedProblemIds(events, ['luogu:P1000', 'luogu:CF1A', 'luogu:P1000']);
  assert.equal(PLATFORM_NAMES.luogu, '洛谷');
  assert.equal(ids.size, 3);
  assert.equal(firstAccepted(events).size, 1);
  assert.deepEqual([...dailyCounts(events)], [['2026-09-08', 1]]);
  assert.deepEqual(streaks(dailyCounts(events).keys(), '2026-09-08'), { current: 1, longest: 1 });
  assert.equal(solvedProblemIds(events, ['qoj:42']).size, 1);
});

test('AC dates use UTC+8 at midnight, independent of machine timezone', () => {
  assert.equal(dateKey(Date.parse('2026-09-07T15:59:59Z') / 1000), '2026-09-07');
  assert.equal(dateKey(Date.parse('2026-09-07T16:00:00Z') / 1000), '2026-09-08');
  assert.equal(shiftDay('2024-03-01', -1), '2024-02-29');
  assert.equal(shiftDay('2025-01-01', -1), '2024-12-31');
});

test('first AC deduplicates by platform-specific problem identity, not title or submission id', () => {
  const events = [
    { id: 8, problemId: 'atcoder:abc001_a', epoch: 1720000000 },
    { id: 2, problemId: 'atcoder:abc001_a', epoch: 1710000000 },
    { id: 2, problemId: 'codeforces:1:A', epoch: 1710000000 },
    { id: 1, problemId: 'atcoder:abc001_a', epoch: 1710000000 },
    { id: 1, problemId: 'nowcoder:321116', epoch: 1710000000 },
  ];
  const first = firstAccepted(events);
  assert.equal(first.size, 3);
  assert.equal(first.get('atcoder:abc001_a').id, 1);
  assert.equal([...dailyCounts([...first.values()]).values()].reduce((a, b) => a + b), 3);
  assert.equal([...dailyCounts(events).values()].reduce((a, b) => a + b), 5);
});

test('streak permits today to be unfinished, excludes future days, and handles year boundaries', () => {
  const dates = ['2025-12-30', '2025-12-31', '2026-01-01', '2026-01-04', '2026-01-04', '2026-01-08'];
  assert.deepEqual(streaks(dates, '2026-01-02'), { current: 3, longest: 3 });
  assert.deepEqual(streaks(dates, '2026-01-06'), { current: 0, longest: 3 });
  assert.deepEqual(streaks([], '2026-01-06'), { current: 0, longest: 0 });
});

test('calendar includes leap days, uses Monday-first rows, and preserves end of year', () => {
  const leap = calendarDays(2024);
  assert.equal(leap.length, 366);
  assert.deepEqual(leap[0], { day: '2024-01-01', week: 0, weekday: 0 });
  assert.equal(leap.at(-1).day, '2024-12-31');
  const year = calendarDays(2026);
  assert.equal(year.length, 365);
  assert.equal(year[0].weekday, 3);
  assert.equal(calendarDays(2012).at(-1).week, 53);
});

test('unknown Gym denominator cannot imply full contest completion', () => {
  const first = new Map([['codeforces:100001:A', {}]]);
  const attempted = new Set(['codeforces:100001:A']);
  const partial = completion({ problems: ['codeforces:100001:A'], catalogComplete: false }, first, attempted);
  assert.deepEqual(partial, { solved: 1, total: 1, started: true, complete: false });
  assert.equal(matchesStatus(partial, 'completed'), false);
  assert.equal(matchesStatus(partial, 'unfinished'), true);
  const complete = completion({ problems: ['codeforces:100001:A'], catalogComplete: true }, first, attempted);
  assert.equal(complete.complete, true);
  const untouched = completion({ problems: ['codeforces:100001:B'], catalogComplete: true }, first, attempted);
  assert.equal(matchesStatus(untouched, 'untouched'), true);
});

test('shared AtCoder tasks show AC without inventing a contest submission', () => {
  const first = new Map([['atcoder:abc001_a', {}]]);
  const attempted = new Set(['atcoder:abc001_a']);
  const reused = completion({ problems: ['atcoder:abc001_a'], catalogComplete: true, hasSubmissions: false }, first, attempted);
  assert.equal(reused.solved, 1);
  assert.equal(matchesStatus(reused, 'started'), false);
  const original = completion({ problems: ['atcoder:abc001_a'], catalogComplete: true, hasSubmissions: true }, first, attempted);
  assert.equal(matchesStatus(original, 'started'), true);
});

test('every platform excludes contests without explicit submission evidence', () => {
  assert.equal(PLATFORM_NAMES.qoj, 'QOJ');
  const contests = [
    { id: 'qoj:1', platform: 'qoj', hasSubmissions: true },
    { id: 'qoj:2', platform: 'qoj', hasSubmissions: false },
    { id: 'qoj:3', platform: 'qoj' },
    { id: 'atcoder:abc001', platform: 'atcoder', hasSubmissions: false },
    { id: 'atcoder:abc002', platform: 'atcoder', hasSubmissions: true },
    { id: 'codeforces:1', platform: 'codeforces', hasSubmissions: true },
    { id: 'codeforces:2', platform: 'codeforces', hasSubmissions: 1 },
    { id: 'codeforces:3', platform: 'codeforces', hasSubmissions: 'true' },
  ];
  assert.deepEqual(contests.filter(includedContest).map(contest => contest.id), ['qoj:1', 'atcoder:abc002', 'codeforces:1']);
  const first = firstAccepted([{ problemId: 'qoj:1', id: 1, epoch: 100 }, { problemId: 'qoj:1', id: 2, epoch: 200 }, { problemId: 'codeforces:1:A', id: 1, epoch: 100 }]);
  assert.equal(first.size, 2);
  assert.equal(first.get('qoj:1').epoch, 100);
});

test('an older cached payload cannot restore disabled Luogu or unsubmitted contests', () => {
  const original = {
    sources: { atcoder: {}, luogu: {}, nowcoder: {} },
    problems: [{ id: 'atcoder:task', platform: 'atcoder' }, { id: 'luogu:P1', platform: 'luogu' }, { id: 'nowcoder:1', platform: 'nowcoder' }],
    accepted: [{ id: 1, platform: 'atcoder', problemId: 'atcoder:task', epoch: 100 }],
    attempted: ['atcoder:task', 'luogu:P1', 'nowcoder:1'], undatedSolved: ['luogu:P1'],
    contests: [{ id: 'atcoder:1', platform: 'atcoder', hasSubmissions: true }, { id: 'atcoder:2', platform: 'atcoder', hasSubmissions: false }],
  };
  const data = activeDashboard(original);
  assert.deepEqual(Object.keys(data.sources), ['atcoder', 'nowcoder']);
  assert.deepEqual(data.problems.map(p => p.id), ['atcoder:task', 'nowcoder:1']);
  assert.deepEqual(data.attempted, ['atcoder:task', 'nowcoder:1']);
  assert.deepEqual(data.undatedSolved, []);
  assert.equal(data.contests.length, 1);
  assert.equal(solvedProblemIds(data.accepted, data.undatedSolved).size, 1);
  assert.equal(original.problems.length, 3);
});

test('matrix aligns contest-local labels, split problems, gaps and AtCoder H / Ex', () => {
  const problems = new Map([
    ['atcoder:shared', { index: 'D' }], ['atcoder:ex', { index: 'Ex' }],
    ['codeforces:a1', { index: 'A1' }], ['codeforces:a2', { index: 'A2' }], ['codeforces:h', { index: 'H' }],
  ]);
  const contests = [
    { id: 'atcoder:1', problems: ['atcoder:shared', 'atcoder:ex'], problemIndices: { 'atcoder:shared': 'A' } },
    { id: 'codeforces:1', problems: ['codeforces:a1', 'codeforces:a2', 'codeforces:h'], catalogComplete: false },
  ];
  const matrix = contestMatrix(contests, problems);
  assert.deepEqual(matrix.columns, [{ key: 'A', label: 'A' }, { key: 'H', label: 'H / Ex' }]);
  assert.deepEqual(matrix.rows[0].cells.get('A'), [{ id: 'atcoder:shared', index: 'A' }]);
  assert.deepEqual(matrix.rows[1].cells.get('A').map(p => p.index), ['A1', 'A2']);
  assert.equal(matrix.rows[0].cells.get('H')[0].index, 'Ex');
  assert.equal(matrix.rows[0].cells.has('D'), false);
  assert.equal(matrix.rows[1].contest.catalogComplete, false);
  assert.equal(matrix.rows.flatMap(row => [...row.cells.values()].flat()).length, 5);
});
