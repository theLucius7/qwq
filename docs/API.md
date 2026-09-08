# API 与数据获取说明

[返回 README](../README.md) · [OpenAPI 3.1 契约](openapi.json) · [在线快照](https://thelucius7.github.io/qwq/data/dashboard.json)

本文描述 `schemaVersion: 2`，覆盖 AtCoder、Codeforces、QOJ 与洛谷。v2 新增无 AC 时间的已通过题目，并区分完整提交历史与手动通过题目快照；累计解题不能再仅使用 `accepted`。实现依据为 [同步器](../scripts/sync.py)、[前端统计模型](../public/model.js) 和 [部署工作流](../.github/workflows/pages.yml)。上游接口说明核对日期：2026-09-08。

## 目录

- [公开接口](#公开接口)
- [调用示例](#调用示例)
- [数据结构](#数据结构)
- [统计与关联规则](#统计与关联规则)
- [上游数据获取](#上游数据获取)
- [错误与新鲜度](#错误与新鲜度)
- [接入边界](#接入边界)
- [版本与维护](#版本与维护)

## 公开接口

### GET /data/dashboard.json

生产环境基地址为 `https://thelucius7.github.io/qwq`，完整地址为 [dashboard.json](https://thelucius7.github.io/qwq/data/dashboard.json)。本地运行 `npm run dev` 后可访问 [本地 JSON](http://127.0.0.1:4173/data/dashboard.json)。

| 项目 | 约定 |
| --- | --- |
| 方法 | `GET` |
| 认证 | 无需登录、API Key、Token 或 Cookie |
| 请求参数 / 请求体 | 无 |
| 成功响应 | HTTP `200`，UTF-8 JSON，结构为 `Dashboard` |
| 数据范围 | Lucius7 的四平台题目与来源状态；AtCoder / Codeforces / QOJ 的通过提交及目录；洛谷的无时间通过题目 |
| 更新 | 每日同步、推送 `main` 或手动触发后，经构建与部署发布；可发布保留的降级数据 |
| 分页 / 筛选 | 整份快照一次返回；平台、日期、比赛等筛选在客户端完成 |
| 写入 | 不提供写入、实时查询或远程触发同步的业务接口 |

GitHub Pages 托管静态文件。添加 `?handle=...`、`?date=...` 等参数不会切换用户或筛选记录，也不会触发上游刷新。站点内调用使用 `./data/dashboard.json`，保留项目站点的 `/qwq/` 路径；不要写成域名根目录下的 `/data/dashboard.json`。

客户端应先检查 HTTP 状态，再解析 JSON。Pages 的 404、网络错误等没有本项目定义的 JSON 错误体。HTTP 200 也可能包含上游失败后保留的旧数据，应检查 `sources`。缓存及响应头由 GitHub Pages 管理，本项目未实现独立的客户端调用配额、强制刷新接口或实时可用性保证；建议复用快照，避免高频轮询。

### 数据获取方式

| 场景 | 获取方式 |
| --- | --- |
| 读取当前部署数据 | 请求上面的 Pages JSON 地址 |
| 固定到某次仓库版本 | 从该 commit 读取 `public/data/dashboard.json`，如 `git show <commit>:public/data/dashboard.json` |
| 本地联网更新 | `npm run sync` 更新 AtCoder / Codeforces / 已配置 QOJ，复用洛谷快照；不直接发布 |
| 本地离线重建 | 执行 `python3 scripts/sync.py --offline`；需要已有 `data/sources/*.json` |
| 刷新线上数据 | 在 GitHub Actions 运行 **Daily sync and GitHub Pages**，等待部署完成 |

仓库中的数据提交与 Pages 部署有时间差；需要精确复现时，记录 commit 和各平台的 `lastSuccess`。`data/sources/*.json` 是内部成功快照，其结构不属于本公开接口契约。

## 调用示例

### cURL：下载快照

```sh
curl --fail --silent --show-error --max-time 45 \
  'https://thelucius7.github.io/qwq/data/dashboard.json' \
  --output dashboard.json
```

如果已安装 `jq`，可直接查看同步状态及已解题数：

```sh
jq '{generatedAt, sources, solved: ([.accepted[].problemId, .undatedSolved[]] | unique | length), undatedSolved: (.undatedSolved | length)}' dashboard.json
```

### JavaScript：按天统计首次 AC

可在支持 `fetch` 的现代浏览器模块或 Node.js 22+ 的 `.mjs` 文件中运行。需要先从**全历史**找出每道题首次 AC，再按日期筛选，以免把重复 AC 算成当天新增。

```js
const response = await fetch('https://thelucius7.github.io/qwq/data/dashboard.json');
if (!response.ok) throw new Error(`HTTP ${response.status}`);
const data = await response.json();
if (data.schemaVersion !== 2) throw new Error('不支持的数据版本');

for (const [platform, source] of Object.entries(data.sources)) {
  if (!source.lastSuccess) {
    console.warn(platform, source.status, source.message);
    continue;
  }
  const stale = Date.now() - Date.parse(source.lastSuccess) > 36 * 3600 * 1000;
  if (source.error || stale) console.warn(platform, source.lastSuccess, source.error);
  for (const warning of source.warnings) console.warn(platform, warning);
}

const first = new Map();
for (const event of data.accepted) {
  const previous = first.get(event.problemId);
  if (!previous || event.epoch < previous.epoch ||
      (event.epoch === previous.epoch && event.id < previous.id)) {
    first.set(event.problemId, event);
  }
}

// schemaVersion 2 的统计时区固定为 Asia/Taipei（UTC+8）。
// undatedSolved 只证明已通过；不能填入导入日期或 epoch=0 来参与每日统计。
const dayKey = epoch => new Date((epoch + 8 * 3600) * 1000).toISOString().slice(0, 10);
const daily = new Map();
for (const event of first.values()) {
  const day = dayKey(event.epoch);
  daily.set(day, (daily.get(day) ?? 0) + 1);
}

const solved = new Set([...first.keys(), ...data.undatedSolved]);
console.log({
  solved: solved.size,
  solvedWithKnownTime: first.size,
  solvedWithoutTime: data.undatedSolved.length,
  recordedAcceptedSubmissions: data.accepted.length,
});
console.table([...daily].sort(([a], [b]) => a.localeCompare(b))
  .map(([date, solved]) => ({ date, solved })));
```

如需统计当天**已记录的 AC 次数**，将最后一个循环的 `first.values()` 改为 `data.accepted`。仅看一个平台时先按 `event.platform` 筛选。

### Python：查询指定日期的新题

仅使用 Python 标准库，将 `target_date` 改为所需 UTC+8 日期。无时间题目不参与日期查询；全部累计解题另取两个集合的并集。

```python
import datetime as dt
import json
from urllib.request import urlopen

url = "https://thelucius7.github.io/qwq/data/dashboard.json"
with urlopen(url, timeout=45) as response:
    data = json.load(response)
if data["schemaVersion"] != 2:
    raise ValueError("不支持的数据版本")

first = {}
for event in data["accepted"]:
    previous = first.get(event["problemId"])
    if previous is None or (event["epoch"], event["id"]) < (previous["epoch"], previous["id"]):
        first[event["problemId"]] = event

timezone = dt.timezone(dt.timedelta(hours=8))
target_date = "2026-09-08"
problems = {problem["id"]: problem for problem in data["problems"]}
for event in sorted(first.values(), key=lambda item: (item["epoch"], item["platform"], item["id"])):
    timestamp = dt.datetime.fromtimestamp(event["epoch"], timezone)
    if timestamp.date().isoformat() == target_date:
        problem = problems[event["problemId"]]
        print(timestamp.isoformat(), problem["name"], problem["url"], event["url"])

solved = set(first) | set(data["undatedSolved"])
print("累计解题:", len(solved), "AC 时间未知:", len(data["undatedSolved"]))

for platform, source in data["sources"].items():
    print(platform, "最后成功:", source["lastSuccess"], "错误:", source["error"], "提示:", source["warnings"])
```

## 数据结构

下表中的字段除明确注明“可省略”外均为必填。`null` 表示未知或不可用，不能等同于 `0`。所有 URL 优先直接使用响应值，不要通过拆分 ID 自行拼接。时间戳 `epoch`、`startEpoch` 的单位为**秒**；日期时间字符串使用带时区的 ISO 8601 / RFC 3339 格式，通常为 UTC，例如 `2026-09-08T00:17:00Z`。

### Dashboard

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `schemaVersion` | integer | 当前为 `2`，包含破坏性语义变化 |
| `handle` | string | 当前为 `Lucius7` |
| `timezone` | string | 当前为 `Asia/Taipei` |
| `generatedAt` | string · date-time | 汇总 JSON 生成时间，不等于各数据源刷新时间 |
| `sources` | object | 包含 `atcoder`、`codeforces`、`qoj`、`luogu`，值为 `Source`；尚未连接的来源也保留状态 |
| `problems` | `Problem[]` | 收录题库，包含大量未尝试题目；长度不是解题数 |
| `contests` | `Contest[]` | 收录比赛，包含未参加的常规比赛；题目列表非空 |
| `accepted` | `AcceptedSubmission[]` | 已获得真实时间的通过提交，含重复通过；当前来自 AtCoder / Codeforces / QOJ，不包含洛谷 |
| `undatedSolved` | `string[]` | 唯一的已通过题目 ID，但首次 AC 时间未知；引用题库，并与 `accepted` 的题目集合不相交 |
| `attempted` | `string[]` | 去重后的已尝试题目 ID，包含已 AC 的题目 |

### Source

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `lastSuccess` | string · date-time 或 null | 已获取来源的最后成功时间；手动导入使用采集时间，尚未连接时为 null |
| `profile` | `Profile` | 用户 Rating 摘要 |
| `warnings` | `string[]` | 可选数据缺失或陈旧提示；成功时也可能非空 |
| `submissionCount` | integer 或 null | 提交历史去重后的总提交数，含非 AC / 重复；洛谷与未连接来源为 null，不能当作 0 |
| `error` | string 或 null | 本次该平台核心同步错误；成功、离线重建和仅复用洛谷快照时为 null |
| `coverage` | string | `submission_history` 或 `solved_only`，说明是否具备逐条提交历史 |
| `collectionMethod` | string | `http`、`authenticated_http` 或 `browser_import`，表示当前成功快照的获取方式 |
| `reportedCounts` | object，可省略 | 来源页面展示的摘要数字，见下文；当前用于洛谷 |
| `status` | string，可省略 | 未连接来源的 `needs_auth`、`needs_import` 或 `error`；已有成功快照通常省略，错误仍查看 `error` |
| `message` | string，可省略 | 未连接状态的人类可读说明 |

`error`、`warnings`、`message` 是供人阅读的文本，不是稳定错误码。空错误不证明数据刚刚刷新；始终结合 `lastSuccess` 和 `collectionMethod`。

`coverage: "solved_only"` 当前用于洛谷：只有通过题目及已尝试状态，不能生成 AC 次数和日期。`collectionMethod: "browser_import"` 表示手动导入，**不表示每天自动刷新**；QOJ 首次也可从正常登录浏览器的已导出页面导入，此后配置 Secret 的成功同步会变成 `authenticated_http`。

`reportedCounts` 若存在，包含 `solved: integer` 与 `submitted: integer | null`，分别保留页面“通过”和“提交”摘要。洛谷“提交”摘要的口径未被验证为逐条提交总数，因此不填入 `submissionCount`，也不可推算 AC 次数。`solved` 会与去重后的导入通过题目数核对。

### Profile

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `handle` | string | 平台用户名 |
| `url` | string · URI | 用户主页 |
| `rating` | integer 或 null | 当前 Rating；未定级或获取不到时可为空；QOJ / 洛谷不采集，固定 null |
| `maxRating` | integer 或 null | 最高 Rating |
| `rank` | string 或 null | AtCoder 为 `Algorithm`，Codeforces 为官方段位；QOJ / 洛谷为 null |
| `lastSuccess` | string · date-time 或 null | Rating 独立的最后成功获取时间；可能早于 Source 时间 |

### Problem

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `id` | string | 带平台前缀的题目唯一 ID |
| `platform` | string | `atcoder`、`codeforces`、`qoj` 或 `luogu` |
| `contestId` | string 或 null | 题库中的主要比赛关联；不是完整的比赛成员关系，也不保证出现在 `contests` 中 |
| `index` | string | 主要目录中的题目标号，例如 `A`、`D1` |
| `name` | string | 题目名称；元数据缺失时可能回退为题号 |
| `url` | string · URI | 题目链接 |
| `difficulty` | integer 或 null | AtCoder Problems 换算后估计难度或 CF rating；QOJ / 洛谷为 null |
| `difficultyLabel` | string 或 null，可省略 | 洛谷页面上的难度分组文字；未获取时为 null，不转换成数值 rating |

ID 格式：

| 对象 | 格式 |
| --- | --- |
| AtCoder 题目 | `atcoder:{problem_id}`，例如 `atcoder:abc001_1` |
| Codeforces 题目 | `codeforces:{contestId}:{index}`，例如 `codeforces:1:A` |
| CF 无比赛 ID 的特殊题库 | `codeforces:problemset:{problemsetName}:{index}`，其 `contestId` 为 null |
| QOJ 题目 | `qoj:{problemId}`，例如 `qoj:1` |
| 洛谷题目 | `luogu:{problemId}`，例如 `luogu:P1001` |
| QOJ 比赛 | `qoj:{contestId}`；与 QOJ 题目 ID 属于不同集合 |
| AtCoder 比赛 | `atcoder:{contest_id}` |
| Codeforces 比赛 | `codeforces:{contestId}` |

题目与比赛分别属于自己的 ID 集合。题目 ID 可直接用作跨平台题目键；不要按名称合并题目。

### Contest

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `id` | string | 带平台前缀的比赛唯一 ID |
| `platform` | string | `atcoder`、`codeforces`、`qoj` 或 `luogu` |
| `name` | string | 比赛名称 |
| `kind` | string | 展示类别，例如 `ABC`、`ADT`、`Div. 2`、`Educational`、`Gym`；不固定为封闭枚举 |
| `startEpoch` | integer | 比赛开始的 Unix 秒；`0` 表示未知，不应显示为 1970 年 |
| `url` | string · URI | 比赛链接 |
| `problems` | `string[]` | 该比赛按题号排序的题目 ID，引用 `problems[].id` |
| `problemIndices` | object，可省略 | 题目 ID → 本场题号；当前用于 AtCoder / QOJ |
| `lastSubmissionEpoch` | integer，可省略 | 本场最新一次实际提交的 Unix 秒，当前用于 QOJ；不等于比赛开始时间 |
| `catalogComplete` | boolean | 是否按当前数据来源获得完整目录；不代表隐藏 / 移除的题目也已知 |
| `hasSubmissions` | boolean | 用户是否实际在此比赛有提交；无需 AC，也不要求是正式参赛 |

某题在本场的显示标号使用 `contest.problemIndices?.[problem.id] ?? problem.index`。不能仅按 `Problem.contestId` 分组还原比赛，因为同一题目可能被多个比赛复用。QOJ 仅保留 `hasSubmissions: true` 的比赛，不因题目的“曾用于这些比赛”列表推断参加；`startEpoch` 当前为 0，前端排序可退回 `lastSubmissionEpoch`。洛谷当前不提供任何比赛对象。

### AcceptedSubmission

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `id` | integer | 源平台提交 ID，仅在同一平台内唯一 |
| `platform` | string | 当前为 `atcoder`、`codeforces` 或 `qoj`；洛谷不产生提交事件 |
| `problemId` | string | 引用 `problems[].id` |
| `epoch` | integer，> 0 | 当前判定通过的提交的提交时间，Unix 秒 |
| `url` | string · URI | 此次提交的详情链接 |

跨平台去重使用 `(platform, id)`，例如 `${event.platform}:${event.id}`。`epoch` 取 AtCoder `epoch_second`、Codeforces `creationTimeSeconds` 或 QOJ 页面中的提交时间（按 UTC+8 解析），不记录评测完成时间、重判转 AC 的时刻或采集时刻。

`accepted` 由各平台数组合并，**不是全局时间排序**；需要按时间展示时自行排序。其他顶层数组也不应被依赖为跨平台全局排序。非 AC 提交不以逐条事件返回；它们用于已尝试状态、提交总数、比赛参与及缺失目录补全。API 不保存非 AC 提交的逐条时间、错误类型、语言或源码。

## 统计与关联规则

| 需求 | 算法 |
| --- | --- |
| 累计已解题 | `accepted.map(event => event.problemId)` 与 `undatedSolved` 取并集 |
| AC 时间未知的已解题数 | `undatedSolved.length`；不能分配到导入当天或其他日期 |
| 首次 AC | 每个 `problemId` 取最小 `epoch`，同秒取较小提交 `id` |
| 每日新增 / 热力图 | 只从 `accepted` 算全历史首次 AC，再按 UTC+8 日期计数；未知时间题目排除 |
| 已记录 AC 次数 | `accepted.length`，包括重复通过；不代表洛谷等缺失历史来源的全部次数 |
| 比赛已 AC 数 | `contest.problems` 中已出现在首次 AC 集合的题目数量 |
| 比赛整场完成 | `catalogComplete === true`、题目数大于 0，且已 AC 数等于题目数 |
| 有提交的比赛 | `contest.hasSubmissions === true` |
| 连续做题 | 仅以 `accepted` 的不同日期计算；今天无 AC 则可结束于昨天；无时间记录不贡献天数 |

API 不提供顶层 `summary` 对象；CLI / Actions 的摘要会同时输出累计解题、已记录 AC 次数及未知时间题数。累计解题可多于每日新增的历史合计，差额来自 `undatedSolved`。单独查看 `solved_only` 来源时，本月、今日和连续天数应显示“未知”，而不是 0；前端隐藏没有日期依据的热力图和每日清单。

在上面的 JavaScript 示例之后，可这样计算已提交比赛的进度：

```js
const progress = data.contests.filter(contest => contest.hasSubmissions).map(contest => {
  const solved = contest.problems.filter(id => first.has(id)).length;
  const total = contest.problems.length;
  return {
    id: contest.id,
    name: contest.name,
    solved,
    total: contest.catalogComplete ? total : null,
    complete: contest.catalogComplete && total > 0 && solved === total,
  };
});
console.table(progress);
```

目录不完整时显示 `solved / ?`。AtCoder 共享题在其他比赛通过也会贡献本场进度，因此 `hasSubmissions: false` 与已完成若干题甚至整场完成可以同时成立。Codeforces 跨 Div 题目按各自 ID 保留，未复用 CFTracker 的同题推断。

## 上游数据获取

这部分供维护同步器使用。普通 API 使用方读取一次本项目快照即可，无需直接访问上游。网络采集使用 `GET`，洛谷走已有文件导入；以下源站地址不是本项目新增的 API 路由。

### AtCoder Problems

服务由社区项目 AtCoder Problems 维护，不是 AtCoder 官方 API。无需账号凭据。数据接口和请求间隔依据其 [API / Datasets 文档](https://github.com/kenkoooo/AtCoderProblems/blob/master/doc/api.md)。基地址为 `https://kenkoooo.com/atcoder`。

| 路径 | 参数 | 用途 / 响应 |
| --- | --- | --- |
| `/atcoder-api/v3/user/submissions` | `user=Lucius7`、`from_second=0` 起步 | 提交对象数组，每页最多 500 条 |
| `/resources/problems.json` | 无 | 题目对象数组 |
| `/resources/contests.json` | 无 | 比赛对象数组 |
| `/resources/contest-problem.json` | 无 | 比赛与题目映射数组，包含本场题号 |
| `/resources/problem-models.json` | 无 | 按题目 ID 索引的难度模型对象，可选 |

单页调用示例：

```sh
curl --fail --silent --show-error --max-time 45 \
  'https://kenkoooo.com/atcoder/atcoder-api/v3/user/submissions?user=Lucius7&from_second=0'
```

完整同步每次从 `from_second=0` 开始；收到不足 500 条时结束，否则以本页最大的 `epoch_second` 作为下一页游标，保留边界并按提交 `id` 去重，**不加 1 秒**。如果满页游标无法前进则报错，避免悄悄截断同秒提交。包含边界的查询行为可见上游 [submission_client.rs](https://github.com/kenkoooo/AtCoderProblems/blob/master/atcoder-problems-backend/sql-client/src/submission_client.rs)。

只把 `result == "AC"` 转为通过记录。目录默认收录已开始的比赛，再补入实际提交涉及的缺失比赛。难度 `d < 400` 时转为 `floor(400 × exp((d − 400) / 400) + 0.5)`，否则使用 Python `round(d)`；缺失模型时为 null。

### AtCoder 官方 Rating

获取地址为 [用户比赛历史 JSON](https://atcoder.jp/users/Lucius7/history/json)，即 `https://atcoder.jp/users/{handle}/history/json`，无需登录。同步器筛选 `IsRated` 为真的记录，按 `EndTime` 排序，以最后一项 `NewRating` 为当前值、最大 `NewRating` 为历史最高值。

这是项目实际使用的官方站点 JSON 地址；本文不将其描述为带独立版本或配额承诺的通用开放 API。当前只采集 Algorithm Rating。

### Codeforces 官方 API

基地址为 `https://codeforces.com/api`。当前使用公开数据，可匿名调用，无需申请 API Key 或签名。响应使用 `status` 与 `result` 包装，失败时为 `status: "FAILED"` 和 `comment`；HTTP 成功后仍须检查 `status`。参见 [官方 API 介绍](https://codeforces.com/apiHelp) 与 [方法文档](https://codeforces.com/apiHelp/methods)。

| 方法 | 当前参数 | 用途 |
| --- | --- | --- |
| `user.status` | `handle=Lucius7&from=1&count=1000` 起步 | 用户提交历史，`result` 为提交数组 |
| `problemset.problems` | `lang=en` | 读取 `result.problems` 题库 |
| `contest.list` | `lang=en` | 常规比赛目录 |
| `contest.list` | `gym=true&lang=en` | Gym 名称与比赛元数据 |
| `user.info` | `handles=Lucius7` | 读取 `result[0]` 的 Rating / 段位，可选 |

单页调用示例：

```sh
curl --fail --silent --show-error --max-time 45 \
  'https://codeforces.com/api/user.status?handle=Lucius7&from=1&count=1000'
```

`from` 从 1 开始，提交按 ID 降序返回。项目每次完整拉取，每页请求 1000 条；满页后令 `from += 990`，重叠 10 条以减少新提交导致偏移变化的影响，并按提交 ID 去重。不足 1000 条时结束；满页但没有新增记录时报错。偏移分页无法保证同步期间持续大量新增时的事务一致性，后续每日完整同步会重新读取。

只将 `verdict == "OK"` 转为通过记录，不按参加类型过滤练习、比赛、虚拟赛等。常规目录默认收录 `phase == "FINISHED"` 的比赛，再补入实际提交涉及的其他比赛。源站不可见的私人提交和隐藏数据无法补齐。

### Codeforces Gym 题目目录

对有提交记录的 Gym，额外读取官方公开 HTML `https://codeforces.com/gym/{contestId}?locale=en`，仅解析 `table.problems` 中的题目链接。它是页面解析，不是 JSON API；页面结构变化可能需要维护解析器。当前不调用需要认证的 Gym standings 接口。

若旧快照已具备完整题表，且覆盖当前已知的提交题目，则复用题表；否则重新获取。补全失败时保留已知题目，设置 `catalogComplete: false` 并提示，不把已提交题目的数量当作比赛总题数。只收录有提交的 Gym，不把全站 Gym 目录全部展示出来。

### QOJ：登录后的 HTML 提交记录

基地址为 `https://qoj.ac`。本项目读取正常登录会话可访问的 HTML 页面，不调用官方 JSON 历史 API。首次验证快照包含 **69 次提交、18 次 AC、18 道已解题、24 道已尝试题、10 场实际有提交的比赛**；目录合计 130 题，其中 128 题属于这些比赛、2 题来自独立练习。数量是首次导入时的状态，不是固定 API 限额。

| 页面 | 参数 / 路径 | 获取内容 |
| --- | --- | --- |
| 提交列表 | `/submissions?submitter=Lucius7&page=1` 起步 | 提交 ID、题目链接、提交者、判定 / 得分、提交时间及分页控件 |
| 已提交比赛 | `/contest/{contestId}` | 比赛标题、本场题号与完整题表 |

以提交行中的实际比赛题目链接 `/contest/{contestId}/problem/{problemId}` 作为有提交的证据。独立练习 `/problem/{problemId}` 的 AC 仍计入累计与日期，但不会凭“本题曾用于这些比赛”添加比赛。QOJ 题目复用仍以同一 `qoj:{problemId}` 去重。

每页 10 条，从第 1 页逐页读取并验证当前页、下一页及用户过滤条件；按 ID 去重，分页不前进、缺页或到第 1000 页后仍需继续读取则失败。当前 Cookie 登录采集会完整重读提交历史，完整比赛目录若已缓存且覆盖当前提交题目则复用。必需的比赛目录解析失败会使本次 QOJ 整体回退，不会发布部分新历史。

通过判定优先使用有效的 `data-score` 与正的 `data-full` 相等；没有完整分值属性时只接受明确的 `AC` / `Accepted` 文本。不会把固定数值 100 或部分分自行解释为满分。提交页面时间按 UTC+8 解析；比赛开始时间未获取时保持 `startEpoch: 0`，最新提交另存 `lastSubmissionEpoch`。

#### 配置每日 QOJ 同步

1. 在自己的浏览器正常登录 [QOJ](https://qoj.ac/login)，打开自己的提交列表，完成站点要求的验证。
2. 从浏览器开发者工具的 Network 面板中选中该 QOJ 请求，在 Request Headers 找到 `Cookie`，复制其**值**。不要复制到聊天、截图、源码或文档。
3. 打开仓库 **Settings → Secrets and variables → Actions → New repository secret**，将值存为 `QOJ_COOKIE`。如果用户名不同，可在 Variables 添加 `QOJ_HANDLE`；当前默认 `Lucius7`。
4. 手动运行 **Daily sync and GitHub Pages**，查看 QOJ 来源的 `lastSuccess` 和 `error`。之后每日工作流使用同一 Secret；失效时按相同步骤更新。

浏览器登录本身不会将 Cookie 自动传到 GitHub Actions。请求只向 `https://qoj.ac` 携带 Cookie；拒绝跨域重定向，遇到登录页、访问验证、401 / 403 或 429 会停止本次 QOJ 同步。已有快照时保留旧数据并告警，无旧快照时提供未连接状态。Cookie 有效也不保证站点允许来自 Actions 的请求；遇到验证需正常处理，不能绕过。

### 洛谷：公开通过题目手动快照

来源为 [Lucius7 公开练习页](https://www.luogu.com.cn/user/571082/practice)，用户 UID 为 `571082`。从用户正常打开的页面保存通过题号、名称、难度分组，以及已尝试题目；**不会自动抓取洛谷、调用个人历史 API 或使用 Cookie**。

首次规范化得到 **547 道通过题目、589 道目录 / 已尝试题目**。所有通过题目放入 `undatedSolved`；`accepted: []`、`contests: []`、`submissionCount: null`。采集时间仅用于 Source `lastSuccess`；不能把 547 题归到导入当天，也无法根据此快照恢复历史每日练习、AC 次数或比赛进度。

源状态为 `coverage: "solved_only"`、`collectionMethod: "browser_import"`。页面“通过”“提交”摘要存入 `reportedCounts`，其中“提交”不冒充逐条提交数量。`npm run sync` 和每日 Actions 只复用 `data/sources/luogu.json`，其 `lastSuccess` 保持原采集时间，直到维护者再次导入新快照。

### 手动导入已保存的浏览器数据

[import_browser.py](../scripts/import_browser.py) 仅解析已有 JSON 文件，不联网。QOJ 提交与比赛文件必须成对传入；洛谷文件可独立导入，也可在同一命令一起导入。输入文件应只包含下述必要数据，不能含 Cookie、源码或无关账号信息。

```sh
# 洛谷：从正常打开的公开练习页保存结构化数据后导入
python3 scripts/import_browser.py --luogu-practice /path/to/luogu-practice.json

# QOJ：从正常登录后的所有提交页及所需比赛页保存数据后导入
python3 scripts/import_browser.py \
  --qoj-submissions /path/to/qoj-submissions.json \
  --qoj-contests /path/to/qoj-contests.json

# 导入只保存平台快照；随后离线汇总、校验并构建
python3 scripts/sync.py --offline
npm test
npm run build
```

这不是随意的浏览器导出文件或 HAR 导入器。捕获格式由 [QOJ 规范化器](../scripts/qoj_import.py) 与 [洛谷规范化器](../scripts/luogu.py) 定义；维护者需把页面中实际可见字段保存成相应 JSON。核心结构如下：

| 文件 | 必要结构 |
| --- | --- |
| 洛谷练习页 | `platform: "luogu"`、`uid: 571082`、`handle: "Lucius7"`、`sourceUrl`、带时区的 `capturedAt`、`reportedSolved`（如“通过 547”）、`solvedGroups`、`attempted`；`reportedSubmitted` 可选 |
| 洛谷题目分组 | 每组 `difficulty` 为页面难度文字，`problems` 为 `{id, title, url}` 数组；`attempted` 也使用此题目结构 |
| QOJ 提交页 | `platform: "qoj"`、`handle`、UTC `capturedAt`、第一页 `sourceUrl`、连续的 `pages`；每页保存 `page`、全部 `rows` 和真实分页 `pager` |
| QOJ 比赛页 | 相同 `platform` / `handle`、UTC `capturedAt`、`pages`；每页含 `cid`、标题 `headings` 及题表 HTML `table` |

QOJ 每条 row 使用 `id`、`problem`、`problemUrl`、`submitter`、`verdict`、`score`、`fullScore`、`submitTime`。`score` 与 `fullScore` 必须同时为页面分数字符串或同时为 null；`submitterUrl` 可省略，但显示名带 `#` 时必须保留该链接来核实真实账号。分页项为 `{text, url, active, disabled}`，不能删除中间页或猜测末页。导入器会检查用户、页序、题目 URL、比赛映射与数量一致性；洛谷通过数量必须与去重后的题目集合相等。导入先验证所有输入，再逐平台原子保存成功快照，不会触发在线更新或直接部署。

### 调用节流与重试

当前 [Client](../scripts/sync.py) 在同一进程中按主机顺序节流：

| 主机 | 项目最小请求起始间隔 | 依据 |
| --- | --- | --- |
| `kenkoooo.com` | 1.1 秒 | AtCoder Problems 要求访问间隔大于 1 秒 |
| `atcoder.jp` | 1.1 秒 | 项目的保守设置，不代表官方公布的配额 |
| `codeforces.com` | 2.2 秒 | Codeforces 文档规定 API 最多每 2 秒 1 次；项目对同主机 Gym 页面也使用该间隔 |

每次请求超时为 45 秒，最多尝试 3 次；前两次失败后分别等待 3 秒、6 秒，再按主机间隔继续。请求带可识别的项目 User-Agent。该限制是单进程内的设置，不协调多台机器或多个同步进程；维护者应避免重复启动采集器。

现有 AtCoder / Codeforces 客户端未实现特殊的 `Retry-After` 解析或针对 403 / 429 的独立停止策略，不能把有限重试误写为这些能力。上游拒绝访问或限流时应检查官方规则和运行记录，避免手工连续重跑。QOJ 使用独立客户端：起始间隔 2.2 秒、超时 40 秒，普通网络错误最多 3 次尝试并等待 3 / 6 秒；登录或访问验证、401 / 403 / 429 立即停止，不重试。洛谷导入完全不联网，不使用上述节流策略；这些设置不是账号不会被限制的保证。

## 错误与新鲜度

| 情况 | 输出行为 |
| --- | --- |
| 核心同步成功 | 原子保存该平台快照，推进 Source `lastSuccess`，`error` 为 null |
| 核心同步失败且已有缓存 | 保留整个平台旧快照；本次汇总的 Source `error` 为错误文本，另一平台仍可更新 |
| AtCoder / CF 首次失败且无缓存 | 同步中止，不覆盖汇总 JSON，不进入本次部署；此前已成功写入的其他平台快照可以保留 |
| QOJ 首次无 Cookie 或离线且无缓存 | `lastSuccess: null`、`submissionCount: null`、`status: "needs_auth"`，不计入统计 |
| QOJ 首次已尝试但失败且无缓存 | `status: "error"`、错误文本与 null 时间 / 数量；其他来源仍可部署，并报告降级 |
| 洛谷尚无手动快照 | `status: "needs_import"`、null 时间 / 提交数，不联网、不伪造 0 道题 |
| QOJ Cookie 失效或必需页面失败，有缓存 | 保留整份 QOJ 历史与旧时间，设置 `error` 并报告降级 |
| 洛谷已有手动快照 | 普通同步仅校验并复用，不联网、不更新其采集时间 |
| 原本非空的提交历史突然变为空 | 拒绝覆盖，按核心同步失败处理 |
| Rating 失败 | 保留旧 Rating 及 Profile `lastSuccess`，增加 warning；首次无旧值时保持 null |
| AtCoder 难度模型失败 | 本次难度为 null，增加 warning，不沿用旧难度 |
| Gym 题表补全失败 | 保留已知题目，目录标为不完整，增加 warning |
| `--offline` 重建 | 不联网；推进 `generatedAt`，保留 Source 时间、Rating 时间及 warnings，将本次 `error` 置为 null |

平台快照分别写入临时文件后原子替换；汇总 JSON 也原子写入。该机制不代表所有上游数据来自同一时刻，也不代表一次运行中的所有文件整体事务提交。

新鲜度检查应分别看：

1. `sources[platform].error` 是否非空。
2. `sources[platform].lastSuccess` 距当前时间多久；网页以超过 36 小时为陈旧提示阈值。
3. `warnings` 是否说明可选数据有问题；Rating 另看 `profile.lastSuccess`。

`collectionMethod: "browser_import"` 的来源必须按手动采集时间理解；36 小时提示不意味着程序将自动刷新洛谷。`generatedAt` 只表示汇总生成时间。AtCoder Problems 的收录也可能落后于 AtCoder 实时提交，即使本项目刚刚同步成功，仍受上游延迟影响。

GitHub Actions 会先部署可用的降级快照，然后通过 `degraded=true` 将工作流标为失败，便于发现问题。仅可选数据的 warnings 不会设置这个降级标记。不要用“站点 HTTP 200”或“工作流成功”代替逐平台的新鲜度检查。

## 接入边界

本项目的 QOJ 采集使用正常登录的账号会话，不提供代理登录或无认证的实时用户历史接口。只有实际返回且能验证的提交和比赛纳入快照；不绕过登录页、人机验证或访问限制。已有快照的 Cookie 失效时保留旧数据并提示；首次未连接时不伪造 0 条提交。

洛谷当前只导入用户正常打开的公开练习页中的题目资料，不调用历史提交 API、不自动翻页采集，也不使用 Cookie 或测试账号限额。已查阅的 [官方 OpenAPI](https://docs.lgapi.cn/open/openapi) 主要提供评测任务提交、结果和配额查询，不能当作个人历史提交接口。当前未确认适用于本需求的官方历史接口和调用配额，所以 **`npm run sync` 与 GitHub Actions 不向洛谷发出网络请求**。导入流程在本地校验已有数据，不保证网页本身永远可访问。

## 版本与维护

### 从 v1 升级到 v2

这是破坏性版本升级，不能只把版本检查从 `1` 改成 `2` 而沿用旧统计：

1. 平台增加 `qoj`、`luogu`，`sources` 包含四个来源及未连接状态。
2. 新增必填 `undatedSolved`；累计解题取它与 `accepted` 题目集合的并集，日期统计仍只使用 `accepted`。
3. `Source.lastSuccess`、`Source.submissionCount` 允许 null；新增必填 `coverage`、`collectionMethod` 及可选 `reportedCounts`、`status`、`message`。
4. 新增可选 `Problem.difficultyLabel` 与 `Contest.lastSubmissionEpoch`；QOJ 题目 ID 与比赛 ID 属于不同集合。
5. `accepted.length` 现在明确表示“已记录且有时间的 AC 次数”，不能宣称四个平台完整 AC 总次数；洛谷采集时间不能转为 AC 事件。

- 当前公开数据版本为 `schemaVersion: 2`；OpenAPI 格式为 `3.1.0`，文档自身版本为 `2.0.0`，三者含义不同。内部 `data/sources/*.json` 仍使用内部版本 `1`，不属于公开契约。
- 客户端应检查支持的数据版本、允许未知的附加字段，并正确处理可空值、可选字段和未知展示类别；当前平台枚举为 `atcoder` / `codeforces` / `qoj` / `luogu`。
- 维护者更改字段含义、必填性或平台契约时，应同步更新本文、OpenAPI 与相关测试，评估是否需要升级 `schemaVersion`；不要静默改变统计口径。
- OpenAPI 只描述本项目的静态快照，不为上游网站的稳定性、权限或配额提供承诺。
- 展示原始链接时使用返回的 `url`；消费名称、warnings、error 等上游相关文本时按文本渲染，避免作为 HTML 插入。
