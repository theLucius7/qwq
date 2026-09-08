export const TIMEZONE = 'Asia/Taipei';
export const PLATFORM_NAMES = { atcoder: 'AtCoder', codeforces: 'Codeforces', qoj: 'QOJ', luogu: '洛谷' };
export const PLATFORM_CODES = { atcoder: 'At', codeforces: 'Cf', qoj: 'Q', luogu: '洛' };

export function solvedProblemIds(events, undatedSolved = []) {
  return new Set([...events.map(event => event.problemId), ...undatedSolved]);
}

export function includedContest(contest) {
  return contest.platform !== 'qoj' || contest.hasSubmissions === true;
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
