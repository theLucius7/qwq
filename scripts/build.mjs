import { cp, mkdir, readFile, rm, stat } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = fileURLToPath(new URL('../', import.meta.url));
const dataPath = path.join(root, 'public/data/dashboard.json');
const data = JSON.parse(await readFile(dataPath, 'utf8'));
if (data.schemaVersion !== 1 || !data.accepted.length || !data.problems.length || !data.sources.atcoder || !data.sources.codeforces) throw new Error('Complete source snapshots are required before publishing. Run npm run sync.');
for (const [name, source] of Object.entries(data.sources)) if (!source.lastSuccess) throw new Error(`Missing successful snapshot: ${name}`);
await rm(path.join(root, 'dist'), { recursive: true, force: true });
await mkdir(path.join(root, 'dist'), { recursive: true });
await cp(path.join(root, 'public'), path.join(root, 'dist'), { recursive: true });
await stat(path.join(root, 'dist/index.html'));
console.log(`Built static site with ${data.accepted.length} AC submissions and ${data.problems.length} catalogued problems.`);
