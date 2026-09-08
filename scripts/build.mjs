import { cp, mkdir, readFile, rm, stat } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = fileURLToPath(new URL('../', import.meta.url));
const dataPath = path.join(root, 'public/data/dashboard.json');
const data = JSON.parse(await readFile(dataPath, 'utf8'));
if (data.schemaVersion !== 2 || !data.accepted.length || !data.problems.length || !Array.isArray(data.undatedSolved) || !data.sources.atcoder || !data.sources.codeforces) throw new Error('Complete source snapshots are required before publishing. Run npm run sync.');
for (const [name, source] of Object.entries(data.sources)) {
  if (!source.lastSuccess && !(name === 'qoj' && ['needs_auth', 'error'].includes(source.status)) && !(name === 'luogu' && ['needs_import', 'error'].includes(source.status)) && !(name === 'nowcoder' && ['needs_sync', 'error'].includes(source.status))) throw new Error(`Missing successful snapshot: ${name}`);
}
if (data.contests.some(contest => contest.platform === 'qoj' && contest.hasSubmissions !== true)) throw new Error('QOJ must only include contests with submissions.');
if (data.contests.some(contest => contest.platform === 'nowcoder')) throw new Error('Nowcoder practice history does not provide contest records.');
const problemIds = new Set(data.problems.map(problem => problem.id));
const dated = new Set(data.accepted.map(event => event.problemId));
if (data.undatedSolved.some(id => !problemIds.has(id) || dated.has(id))) throw new Error('Invalid solved problems without AC timestamps.');
await rm(path.join(root, 'dist'), { recursive: true, force: true });
await mkdir(path.join(root, 'dist'), { recursive: true });
await cp(path.join(root, 'public'), path.join(root, 'dist'), { recursive: true });
await stat(path.join(root, 'dist/index.html'));
console.log(`Built static site with ${data.accepted.length} AC submissions and ${data.problems.length} catalogued problems.`);
