export const TIMEZONE = 'Asia/Taipei';
export const PLATFORM_NAMES = { atcoder: 'AtCoder', codeforces: 'Codeforces', qoj: 'QOJ', luogu: '洛谷', nowcoder: '牛客' };
export const PLATFORM_CODES = { atcoder: 'At', codeforces: 'Cf', qoj: 'Q', luogu: '洛', nowcoder: '牛' };
export const ACTIVE_PLATFORMS = ['atcoder', 'codeforces', 'qoj', 'nowcoder'];

export function solvedProblemIds(events, undatedSolved = []) {
  return new Set([...events.map(event => event.problemId), ...undatedSolved]);
}

export function includedContest(contest) {
  return ACTIVE_PLATFORMS.includes(contest.platform) && contest.hasSubmissions === true;
}

export function activeDashboard(data) {
  const problems = data.problems.filter(problem => ACTIVE_PLATFORMS.includes(problem.platform));
  const ids = new Set(problems.map(problem => problem.id));
  return {
    ...data,
    sources: Object.fromEntries(Object.entries(data.sources).filter(([platform]) => ACTIVE_PLATFORMS.includes(platform))),
    problems,
    accepted: data.accepted.filter(event => ACTIVE_PLATFORMS.includes(event.platform) && ids.has(event.problemId)),
    attempted: data.attempted.filter(id => ids.has(id)),
    undatedSolved: data.undatedSolved.filter(id => ids.has(id)),
    contests: data.contests.filter(includedContest),
  };
}

export function contestMatrix(contests, problems) {
  const keys = new Set();
  let hasEx = false;
  const rows = contests.map(contest => {
    const cells = new Map();
    for (const id of contest.problems) {
      const problem = problems.get(id);
      if (!problem) continue;
      const index = contest.problemIndices?.[id] ?? problem.index;
      // Keep split CF problems together and align AtCoder's H / Ex slot.
      const key = index === 'Ex' ? 'H' : index.match(/^([A-Z])[0-9]*$/)?.[1] || index;
      hasEx ||= index === 'Ex';
      keys.add(key);
      if (!cells.has(key)) cells.set(key, []);
      cells.get(key).push({ id, index });
    }
    return { contest, cells };
  });
  const columns = [...keys].sort((a, b) => a.localeCompare(b, 'en', { numeric: true })).map(key => ({ key, label: key === 'H' && hasEx ? 'H / Ex' : key }));
  return { columns, rows };
}

export function dateKey(epochSeconds) {
  return new Date(epochSeconds * 1000 + 8 * 3600 * 1000).toISOString().slice(0, 10);
}

export function shiftDay(day, amount) {
  const date = new Date(`${day}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + amount);
  return date.toISOString().slice(0, 10);
}

export function firstAccepted(events) {
  const first = new Map();
  for (const event of events) {
    const previous = first.get(event.problemId);
    if (!previous || event.epoch < previous.epoch || (event.epoch === previous.epoch && event.id < previous.id)) first.set(event.problemId, event);
  }
  return first;
}

export function dailyCounts(events) {
  const counts = new Map();
  for (const event of events) {
    const day = dateKey(event.epoch);
    counts.set(day, (counts.get(day) || 0) + 1);
  }
  return counts;
}

export function cumulativeSeries(events, start, end) {
  const counts = dailyCounts([...firstAccepted(events).values()]);
  let total = [...counts].filter(([day]) => day < start).reduce((sum, [, count]) => sum + count, 0);
  const points = [];
  for (let day = start; day <= end; day = shiftDay(day, 1)) {
    const added = counts.get(day) || 0;
    total += added;
    points.push({ day, total, added });
  }
  return points;
}

export function streaks(days, today) {
  const sorted = [...new Set(days)].filter(day => day <= today).sort();
  let longest = 0, run = 0, previous;
  for (const day of sorted) {
    run = previous && shiftDay(previous, 1) === day ? run + 1 : 1;
    longest = Math.max(longest, run);
    previous = day;
  }
  const active = new Set(sorted);
  let cursor = active.has(today) ? today : shiftDay(today, -1);
  let current = 0;
  while (active.has(cursor)) { current++; cursor = shiftDay(cursor, -1); }
  return { current, longest };
}

export function calendarDays(year) {
  const start = `${year}-01-01`;
  const offset = (new Date(`${start}T00:00:00Z`).getUTCDay() + 6) % 7;
  const result = [];
  let day = start, index = offset;
  while (day.startsWith(String(year))) {
    result.push({ day, week: Math.floor(index / 7), weekday: index % 7 });
    day = shiftDay(day, 1);
    index++;
  }
  return result;
}

export function completion(contest, first, attempted) {
  const solved = contest.problems.filter(id => first.has(id)).length;
  const started = contest.hasSubmissions ?? contest.problems.some(id => attempted.has(id));
  const total = contest.problems.length;
  const complete = contest.catalogComplete && total > 0 && solved === total;
  return { solved, total, started, complete };
}

export function matchesStatus(progress, status) {
  if (status === 'started') return progress.started;
  if (status === 'completed') return progress.complete;
  if (status === 'unfinished') return progress.started && !progress.complete;
  if (status === 'untouched') return !progress.started;
  return true;
}
