import { TIMEZONE, PLATFORM_NAMES, PLATFORM_CODES, includedContest, solvedProblemIds, dateKey, shiftDay, firstAccepted, dailyCounts, cumulativeSeries, streaks, calendarDays, completion, matchesStatus } from './model.js?v=20260908-curve';
import { mountTrend } from './trend.js?v=20260908-curve';

const $ = selector => document.querySelector(selector);
const number = new Intl.NumberFormat('en-US');
const time = new Intl.DateTimeFormat('zh-CN', { timeZone: TIMEZONE, hour: '2-digit', minute: '2-digit', hour12: false });
const stamp = new Intl.DateTimeFormat('zh-CN', { timeZone: TIMEZONE, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false });
let today = dateKey(Date.now() / 1000);
const state = { platform: 'all', year: Number(today.slice(0, 4)), date: today, mode: 'first', search: '', kind: 'all', status: 'started', page: 1, undatedSearch: '', undatedPage: 1 };
const PAGE_SIZE = 15;
let data, problems, contests, events, first, attempted, visibleEvents, visibleFirst, counts, solvedIds, undatedIds;
let disposeTrend;

function el(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
}
function link(text, url, className = '') {
  const anchor = el('a', className, text);
  // Only allow source URLs from the generated, public-data snapshot.
  const parsed = new URL(url, location.href);
  if (['https:'].includes(parsed.protocol)) anchor.href = parsed.href;
  anchor.target = '_blank';
  anchor.rel = 'noopener noreferrer';
  return anchor;
}
function platformLogo(platform) { return el('span', `platform-logo ${platform}`, PLATFORM_CODES[platform]); }
function inPlatform(item) { return state.platform === 'all' || item.platform === state.platform; }
function hasOnlyUndatedRecords() { return state.platform !== 'all' && data.sources[state.platform]?.coverage === 'solved_only'; }
function fmt(value) { return number.format(value); }
function empty(title, description) {
  const container = el('div', 'empty-state');
  container.append(el('strong', '', title), el('span', '', description));
  return container;
}

function renderStats() {
  disposeTrend?.();
  const solved = [...visibleFirst.values()];
  const allSolved = [...solvedIds].map(id => problems.get(id)).filter(inPlatform);
  const noDates = hasOnlyUndatedRecords();
  const month = today.slice(0, 7);
  const monthCount = solved.filter(event => dateKey(event.epoch).startsWith(month)).length;
  const activeStreaks = streaks(dailyCounts(visibleEvents).keys(), today);
  const currentCount = counts.get(today) || 0;
  const todayACs = visibleEvents.filter(event => dateKey(event.epoch) === today).length;
  const available = Object.keys(data.sources).filter(platform => inPlatform({ platform }) && data.sources[platform].lastSuccess);
  const platformCounts = available.map(platform => `${PLATFORM_NAMES[platform]} ${fmt(allSolved.filter(problem => problem.platform === platform).length)}`).join(' / ');
  const unavailable = state.platform !== 'all' && !data.sources[state.platform]?.lastSuccess;
  const panel = $('#stats');
  const header = el('div', 'trend-heading');
  const headline = el('div'); headline.append(el('h3', 'trend-title', '累计解题'));
  const total = el('div', 'trend-total', unavailable ? '—' : fmt(allSolved.length)); total.append(el('small', '', '题'));
  headline.append(total, el('p', 'trend-platforms', unavailable ? '等待首次同步' : platformCounts));
  const summary = el('div', 'trend-summary');
  if (noDates || unavailable) summary.append(el('span', '', '日期统计暂不可用'));
  else {
    const metrics = [['今日', currentCount, `已记录 ${todayACs} 次 AC，包含重复通过`], ['本月', monthCount, `${today.slice(0, 7)} · 首次 AC`], ['连续', activeStreaks.current, `最长连续 ${activeStreaks.longest} 天`]];
    for (const [label, value, title] of metrics) {
      const metric = el('span'); metric.title = title;
      metric.append(document.createTextNode(`${label} `), el('strong', '', fmt(value)), document.createTextNode(label === '连续' ? ' 天' : ' 题'));
      summary.append(metric);
    }
  }
  header.append(headline, summary);
  panel.replaceChildren(header);
  if (noDates || unavailable || !solved.length) {
    panel.append(empty(noDates ? '已通过题目暂无时间记录' : unavailable ? '等待数据源连接' : '还没有可绘制的 AC 记录', noDates ? '通过题目已计入累计数量；提供 AC 时间后才能展示解题曲线。' : '有首次 AC 记录后，解题曲线会显示在这里。'));
    return;
  }
  const dated = solved.filter(event => dateKey(event.epoch) <= today);
  const start = dated.length ? shiftDay(dateKey(Math.min(...dated.map(event => event.epoch))), -1) : today;
  const points = cumulativeSeries(visibleEvents, start, today);
  const plot = el('div', 'trend-plot');
  const footer = el('div', 'trend-footer');
  const readout = el('span', 'trend-readout');
  const unknown = allSolved.filter(problem => undatedIds.has(problem.id)).length;
  const note = el('span', 'trend-note', unknown ? `另有 ${fmt(unknown)} 题时间未知，未计入曲线` : '按首次 AC 时间累计 · UTC+8');
  footer.append(readout, note); panel.append(plot, footer);
  disposeTrend = mountTrend(plot, readout, points);
}

function renderProfiles() {
  $('#profiles').replaceChildren(...Object.entries(data.sources).filter(([platform]) => inPlatform({ platform })).map(([platform, source]) => {
    const card = el('article', 'profile-card');
    const title = el('div');
    title.append(link(PLATFORM_NAMES[platform], source.profile.url, 'profile-name'));
    const solved = [...solvedIds].filter(id => problems.get(id).platform === platform).length;
    title.append(el('div', 'profile-detail', !source.lastSuccess ? '等待连接提交记录' : platform === 'luogu' ? `${fmt(solved)} 题已通过 · AC 时间未知` : platform === 'qoj' ? `${fmt(solved)} 题已 AC · 有提交的比赛` : `${fmt(solved)} 题已 AC · ${source.profile.rank || (platform === 'atcoder' ? 'Algorithm' : '暂无段位')}`));
    const rating = el('div', 'profile-rating');
    if (platform === 'luogu') rating.append(el('strong', '', source.lastSuccess ? fmt(solved) : '—'), el('small', '', '公开通过题目'));
    else if (platform === 'qoj') rating.append(el('strong', '', source.submissionCount != null ? fmt(source.submissionCount) : '—'), el('small', '', '提交记录'));
    else rating.append(el('strong', '', source.profile.rating ?? '—'), el('small', '', `Rating · 最高 ${source.profile.maxRating ?? '—'}`));
    card.append(platformLogo(platform), title, rating, link('↗', source.profile.url, 'profile-link'));
    return card;
  }));
}

function renderHeatmap() {
  $('.activity-panel').hidden = hasOnlyUndatedRecords();
  if (hasOnlyUndatedRecords()) return;
  const calendar = calendarDays(state.year);
  const weekCount = calendar.at(-1).week + 1;
  const heatmap = $('#heatmap');
  heatmap.style.gridTemplateColumns = `24px repeat(${weekCount}, minmax(10px, 1fr))`;
  const children = [];
  ['一', '', '三', '', '五', '', '日'].forEach((label, day) => {
    const item = el('span', 'weekday-label', label); item.style.gridColumn = 1; item.style.gridRow = day + 2; children.push(item);
  });
  for (const { day, week, weekday } of calendar) {
    if (day.endsWith('-01')) {
      const label = el('span', 'month-label', `${Number(day.slice(5, 7))}月`);
      label.style.gridColumn = `${week + 2} / span 3`; label.style.gridRow = 1; children.push(label);
    }
    const count = counts.get(day) || 0;
    const button = el('button', `day${day === state.date ? ' selected' : ''}${day > today ? ' future' : ''}`);
    button.type = 'button'; button.dataset.date = day;
    button.dataset.level = count === 0 ? 0 : count <= 2 ? 1 : count <= 5 ? 2 : count <= 9 ? 3 : 4;
    button.style.gridColumn = week + 2; button.style.gridRow = weekday + 2;
    button.setAttribute('aria-label', `${day}，${count} 道首次 AC`);
    button.setAttribute('aria-pressed', String(day === state.date));
    button.title = `${day} · ${count} 道首次 AC`;
    button.disabled = day > today;
    children.push(button);
  }
  heatmap.replaceChildren(...children);
  const yearDays = [...counts.entries()].filter(([day]) => day.startsWith(String(state.year)));
  const total = yearDays.reduce((sum, [, count]) => sum + count, 0);
  $('#activity-summary').textContent = state.platform !== 'all' && !data.sources[state.platform]?.lastSuccess ? '等待首次同步，尚无可展示的记录' : `${state.year} 年解开 ${fmt(total)} 道新题，留下 ${yearDays.length} 天足迹`;
}

function renderDaily() {
  $('#daily').hidden = hasOnlyUndatedRecords();
  if (hasOnlyUndatedRecords()) return;
  $('#date-select').value = state.date;
  $('#next-day').disabled = state.date >= today;
  const selected = (state.mode === 'all' ? visibleEvents : [...visibleFirst.values()]).filter(event => dateKey(event.epoch) === state.date).sort((a, b) => b.epoch - a.epoch || b.id - a.id);
  const dailyNew = counts.get(state.date) || 0;
  const dailyAll = visibleEvents.filter(event => dateKey(event.epoch) === state.date).length;
  const date = new Date(`${state.date}T00:00:00+08:00`);
  $('#daily-title').textContent = `${Number(state.date.slice(5, 7))} 月 ${Number(state.date.slice(8))} 日 · ${new Intl.DateTimeFormat('zh-CN', { timeZone: TIMEZONE, weekday: 'long' }).format(date)}`;
  $('#daily-summary').textContent = `${state.date} / ${dailyNew} 道新题 · ${dailyAll} 次 AC`;
  if (state.platform !== 'all' && !data.sources[state.platform]?.lastSuccess) {
    $('#daily-summary').textContent = `${state.date} / 等待首次同步`;
    $('#daily-list').replaceChildren(empty(`${PLATFORM_NAMES[state.platform]} 尚未连接`, '完成数据源配置后，每日 AC 记录会出现在这里。'));
    return;
  }
  if (!selected.length) {
    $('#daily-list').replaceChildren(empty(state.mode === 'first' && dailyAll ? '这一天复习了已经解开的题目' : '这一天还没有 AC 记录', state.mode === 'first' && dailyAll ? '切换到「全部 AC」查看重复通过的记录。' : '可以在上方热力图中选择其他日期。'));
    return;
  }
  $('#daily-list').replaceChildren(...selected.map(event => {
    const problem = problems.get(event.problemId);
    const row = el('article', 'daily-row');
    const clock = el('time', 'daily-time', time.format(new Date(event.epoch * 1000)));
    clock.dateTime = new Date(event.epoch * 1000).toISOString();
    const body = el('div'); body.append(link(problem?.name || event.problemId, problem?.url || event.url, 'problem-name'));
    const meta = el('div', 'problem-meta');
    meta.append(el('span', 'problem-index', problem?.index || ''), el('span', '', PLATFORM_NAMES[event.platform]));
    if (problem?.difficulty != null) meta.append(el('span', '', `${event.platform === 'atcoder' ? '估计难度' : 'Rating'} ${problem.difficulty}`));
    meta.append(link('提交 ↗', event.url)); body.append(meta);
    const isFirst = first.get(event.problemId)?.id === event.id;
    const badge = el('span', `ac-badge${isFirst ? '' : ' repeat-badge'}`, isFirst ? '✓' : '↻ 再次 AC');
    badge.title = isFirst ? '首次 AC' : '再次 AC';
    badge.setAttribute('aria-label', badge.title);
    row.append(clock, platformLogo(event.platform), body, badge);
    return row;
  }));
}

function renderUndated() {
  const all = [...undatedIds].map(id => problems.get(id)).filter(inPlatform);
  $('#undated').hidden = all.length === 0;
  if (!all.length) return;
  if (hasOnlyUndatedRecords()) $('#undated-details').open = true;
  $('#undated-heading').textContent = `已通过题目 · ${fmt(all.length)} 题`;
  const query = state.undatedSearch.toLocaleLowerCase().trim();
  const filtered = all.filter(problem => !query || `${problem.id} ${problem.name} ${problem.difficultyLabel || ''}`.toLocaleLowerCase().includes(query));
  const size = 25;
  const pages = Math.max(1, Math.ceil(filtered.length / size));
  state.undatedPage = Math.min(state.undatedPage, pages);
  const rows = filtered.slice((state.undatedPage - 1) * size, state.undatedPage * size).map(problem => {
    const row = el('article', 'undated-row');
    const body = el('div'); body.append(link(problem.name, problem.url, 'problem-name'));
    const meta = el('div', 'problem-meta');
    meta.append(el('span', 'problem-index', problem.index), el('span', '', PLATFORM_NAMES[problem.platform]));
    if (problem.difficultyLabel) meta.append(el('span', '', problem.difficultyLabel));
    meta.append(el('span', '', 'AC 时间未知')); body.append(meta);
    const badge = el('span', 'ac-badge', '✓'); badge.title = '已通过，首次 AC 时间未知'; badge.setAttribute('aria-label', badge.title);
    row.append(platformLogo(problem.platform), body, badge); return row;
  });
  $('#undated-list').replaceChildren(...(rows.length ? rows : [empty('没有符合条件的题目', '试试题号、名称或难度。')]));
  $('#undated-count').textContent = `共 ${fmt(filtered.length)} 题`;
  $('#undated-page').textContent = `${state.undatedPage} / ${pages}`;
  $('#undated-prev').disabled = state.undatedPage === 1;
  $('#undated-next').disabled = state.undatedPage === pages;
}

function renderContests() {
  $('#contests').hidden = hasOnlyUndatedRecords();
  if (hasOnlyUndatedRecords()) return;
  $('#contest-scope-note').hidden = state.platform !== 'qoj';
  const query = state.search.toLocaleLowerCase().trim();
  const filtered = contests.filter(contest => {
    if (!inPlatform(contest) || (state.kind !== 'all' && contest.kind !== state.kind)) return false;
    if (!matchesStatus(contest.progress, state.status)) return false;
    return !query || `${contest.name} ${contest.id}`.toLowerCase().includes(query) || contest.problems.some(id => `${problems.get(id)?.name || ''} ${id}`.toLowerCase().includes(query));
  });
  const pages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  state.page = Math.min(state.page, pages);
  const shown = filtered.slice((state.page - 1) * PAGE_SIZE, state.page * PAGE_SIZE);
  const rows = shown.map(contest => {
    const row = el('tr');
    const name = el('td'); name.append(link(contest.name, contest.url, 'contest-name'));
    const meta = el('div', 'contest-meta'); meta.append(el('span', `platform-tag ${contest.platform}`, PLATFORM_NAMES[contest.platform]), document.createTextNode(`${contest.kind}${contest.startEpoch ? ` · ${dateKey(contest.startEpoch)}` : ''}`));
    if (!contest.catalogComplete) meta.append(document.createTextNode(' · 题目目录不完整'));
    name.append(meta);
    const cells = el('td'); const group = el('div', 'problem-cells');
    for (const id of contest.problems) {
      const problem = problems.get(id); if (!problem) continue;
      const accepted = first.get(id);
      const status = accepted ? 'solved' : attempted.has(id) ? 'attempted' : 'unseen';
      const cell = link(contest.problemIndices?.[id] || problem.index, problem.url, `problem-cell ${status}`);
      const description = `${problem.name} · ${accepted ? `首次 AC ${stamp.format(new Date(accepted.epoch * 1000))}` : status === 'attempted' ? '已尝试，尚未 AC' : '尚未完成'}${problem.difficulty != null ? ` · 难度 ${problem.difficulty}` : ''}`;
      cell.title = description; cell.setAttribute('aria-label', description); group.append(cell);
    }
    cells.append(group);
    const progress = el('td', `contest-progress${contest.progress.complete ? ' completed' : ''}`, `${contest.progress.solved} / ${contest.catalogComplete ? contest.progress.total : '?'}`);
    if (contest.catalogComplete) {
      const track = el('div', 'progress-track'); const bar = el('span'); bar.style.width = `${contest.progress.total ? contest.progress.solved / contest.progress.total * 100 : 0}%`; track.append(bar); progress.append(track);
    }
    row.append(name, cells, progress); return row;
  });
  if (!rows.length) {
    const row = el('tr'); const cell = el('td'); cell.colSpan = 3; cell.append(empty('没有符合条件的比赛', '试试其他平台、类别，或清空搜索内容。')); row.append(cell); rows.push(row);
  }
  $('#contest-rows').replaceChildren(...rows);
  $('#contest-count').textContent = state.platform === 'qoj' && !data.sources.qoj?.lastSuccess ? '等待 QOJ 首次同步' : `共 ${fmt(filtered.length)} 场比赛${filtered.length ? ` · 显示 ${(state.page - 1) * PAGE_SIZE + 1}–${Math.min(state.page * PAGE_SIZE, filtered.length)}` : ''}`;
  $('#page-label').textContent = `${state.page} / ${pages}`;
  $('#prev-page').disabled = state.page === 1; $('#next-page').disabled = state.page === pages;
}

function renderPlatform() {
  visibleEvents = events.filter(inPlatform);
  visibleFirst = new Map([...first].filter(([, event]) => inPlatform(event)));
  counts = dailyCounts([...visibleFirst.values()]);
  renderStats(); renderProfiles(); renderHeatmap(); renderDaily(); renderUndated();
  const kinds = [...new Set(contests.filter(inPlatform).map(contest => contest.kind))].sort();
  if (!kinds.includes(state.kind)) state.kind = 'all';
  $('#contest-kind').replaceChildren(new Option('所有类别', 'all'), ...kinds.map(kind => new Option(kind, kind)));
  $('#contest-kind').value = state.kind;
  renderContests();
}

function chooseDay(day) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(day) || day > today || day < '1970-01-01') return;
  state.date = day;
  state.year = Number(day.slice(0, 4));
  if (![...$('#year-select').options].some(option => Number(option.value) === state.year)) $('#year-select').add(new Option(String(state.year), String(state.year)));
  $('#year-select').value = state.year;
  renderDaily(); renderHeatmap();
}

function bindEvents() {
  $('#platform-filter').addEventListener('click', event => {
    const button = event.target.closest('button'); if (!button) return;
    state.platform = button.dataset.platform; state.page = 1; state.undatedPage = 1;
    $('#platform-filter').querySelectorAll('button').forEach(item => item.setAttribute('aria-pressed', String(item === button)));
    renderPlatform();
  });
  $('#activity-filter').addEventListener('click', event => {
    const button = event.target.closest('button'); if (!button) return;
    state.mode = button.dataset.mode;
    $('#activity-filter').querySelectorAll('button').forEach(item => item.setAttribute('aria-pressed', String(item === button))); renderDaily();
  });
  $('#heatmap').addEventListener('click', event => { const button = event.target.closest('button[data-date]'); if (button) { chooseDay(button.dataset.date); $('#daily').scrollIntoView({ behavior: 'smooth', block: 'start' }); } });
  $('#year-select').addEventListener('change', event => { state.year = Number(event.target.value); renderHeatmap(); });
  $('#date-select').max = today;
  $('#date-select').addEventListener('change', event => chooseDay(event.target.value));
  $('#prev-day').addEventListener('click', () => chooseDay(shiftDay(state.date, -1)));
  $('#next-day').addEventListener('click', () => chooseDay(shiftDay(state.date, 1)));
  $('#today-button').addEventListener('click', () => chooseDay(today));
  $('#contest-search').addEventListener('input', event => { state.search = event.target.value; state.page = 1; renderContests(); });
  for (const name of ['kind', 'status']) $('#contest-' + name).addEventListener('change', event => { state[name] = event.target.value; state.page = 1; renderContests(); });
  $('#prev-page').addEventListener('click', () => { state.page--; renderContests(); });
  $('#next-page').addEventListener('click', () => { state.page++; renderContests(); });
  $('#undated-search').addEventListener('input', event => { state.undatedSearch = event.target.value; state.undatedPage = 1; renderUndated(); });
  $('#undated-prev').addEventListener('click', () => { state.undatedPage--; renderUndated(); });
  $('#undated-next').addEventListener('click', () => { state.undatedPage++; renderUndated(); });
  const refreshDate = () => {
    const currentDay = dateKey(Date.now() / 1000);
    if (currentDay === today) return;
    const followToday = state.date === today;
    const followYear = state.year === Number(today.slice(0, 4));
    today = currentDay;
    $('#date-select').max = today;
    if (followYear) {
      state.year = Number(today.slice(0, 4));
      if (![...$('#year-select').options].some(option => Number(option.value) === state.year)) $('#year-select').add(new Option(String(state.year), String(state.year)), 0);
      $('#year-select').value = state.year;
    }
    if (followToday) state.date = today;
    renderPlatform();
  };
  document.addEventListener('visibilitychange', () => { if (!document.hidden) refreshDate(); });
  setInterval(refreshDate, 60_000);
}

async function start() {
  try {
    const response = await fetch('./data/dashboard.json', { cache: 'no-cache' });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    data = await response.json();
    if (data.schemaVersion !== 2 || !data.problems || !data.sources || !Array.isArray(data.undatedSolved)) throw new Error('不支持的数据格式');
    problems = new Map(data.problems.map(problem => [problem.id, problem]));
    events = data.accepted; first = firstAccepted(events); attempted = new Set(data.attempted);
    solvedIds = solvedProblemIds(events, data.undatedSolved);
    undatedIds = new Set(data.undatedSolved.filter(id => !first.has(id)));
    contests = data.contests.filter(includedContest).map(contest => ({ ...contest, progress: completion(contest, first, attempted) })).sort((a, b) => (b.startEpoch || b.lastSubmissionEpoch || 0) - (a.startEpoch || a.lastSubmissionEpoch || 0) || b.id.localeCompare(a.id, undefined, { numeric: true }));
    const years = new Set([state.year, ...events.map(event => Number(dateKey(event.epoch).slice(0, 4)))]);
    $('#year-select').replaceChildren(...[...years].sort((a, b) => b - a).map(year => new Option(String(year), String(year))));
    const latest = events.length ? events.reduce((a, b) => a.epoch > b.epoch ? a : b) : null;
    state.date = latest ? dateKey(latest.epoch) : today;
    $('#sync-label').textContent = `更新于 ${stamp.format(new Date(data.generatedAt))} · UTC+8`;
    const alerts = [];
    for (const [platform, source] of Object.entries(data.sources)) {
      if (!source.lastSuccess) {
        alerts.push(`${PLATFORM_NAMES[platform]} 尚未连接，未计入统计。${source.message || '等待首次同步。'}`);
        continue;
      }
      if (source.collectionMethod === 'browser_import') alerts.push(`${PLATFORM_NAMES[platform]} 展示 ${stamp.format(new Date(source.lastSuccess))} 手动导入的记录，${platform === 'luogu' ? '自动采集未启用' : '自动更新待连接'}。`);
      else if (source.error || Date.now() - Date.parse(source.lastSuccess) > 36 * 3600 * 1000) alerts.push(`${PLATFORM_NAMES[platform]} 暂未更新，展示 ${stamp.format(new Date(source.lastSuccess))} 的记录。`);
      if (source.warnings?.length) alerts.push(`${PLATFORM_NAMES[platform]}：${source.warnings.join('；')}`);
    }
    $('#source-alerts').replaceChildren(...alerts.map(message => el('p', 'source-warning', message)));
    renderPlatform(); bindEvents();
    $('#dashboard').hidden = false; $('#loading').hidden = true;
  } catch (error) {
    $('#loading').hidden = true;
    $('#sync-label').textContent = '记录加载失败';
    const banner = $('#load-error'); banner.hidden = false;
    banner.append(document.createTextNode(`暂时无法读取做题记录（${error.message}）。`));
    const retry = el('button', 'text-button', '重新加载'); retry.type = 'button'; retry.addEventListener('click', () => location.reload()); banner.append(retry);
  }
}
start();
