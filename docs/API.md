# API 与数据获取说明

[返回 README](../README.md) · [OpenAPI 3.1 契约](openapi.json) · [在线快照](https://thelucius7.github.io/qwq/data/dashboard.json)

本文描述当前已发布的 `schemaVersion: 1`，覆盖 AtCoder 与 Codeforces。实现依据为 [同步器](../scripts/sync.py)、[前端统计模型](../public/model.js) 和 [部署工作流](../.github/workflows/pages.yml)。上游接口说明核对日期：2026-09-08。

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
| 数据范围 | Lucius7 的两平台题库目录、比赛目录、通过提交及已尝试题目 |
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
| 本地联网更新 | 在仓库执行 `npm run sync`；只更新本地文件，不直接发布 |
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
jq '{generatedAt, sources, solved: ([.accepted[].problemId] | unique | length)}' dashboard.json
```

### JavaScript：按天统计首次 AC

可在支持 `fetch` 的现代浏览器模块或 Node.js 22+ 的 `.mjs` 文件中运行。需要先从**全历史**找出每道题首次 AC，再按日期筛选，以免把重复 AC 算成当天新增。

```js
const response = await fetch('https://thelucius7.github.io/qwq/data/dashboard.json');
if (!response.ok) throw new Error(`HTTP ${response.status}`);
const data = await response.json();
if (data.schemaVersion !== 1) throw new Error('不支持的数据版本');

for (const [platform, source] of Object.entries(data.sources)) {
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

// schemaVersion 1 的统计时区固定为 Asia/Taipei（UTC+8）。
const dayKey = epoch => new Date((epoch + 8 * 3600) * 1000).toISOString().slice(0, 10);
const daily = new Map();
for (const event of first.values()) {
  const day = dayKey(event.epoch);
  daily.set(day, (daily.get(day) ?? 0) + 1);
}

console.log({ solved: first.size, acceptedSubmissions: data.accepted.length });
console.table([...daily].sort(([a], [b]) => a.localeCompare(b))
  .map(([date, solved]) => ({ date, solved })));
```

如需统计当天**所有 AC 次数**，将最后一个循环的 `first.values()` 改为 `data.accepted`。仅看一个平台时先按 `event.platform` 筛选。

### Python：查询指定日期的新题

仅使用 Python 标准库，将 `target_date` 改为所需 UTC+8 日期。

```python
import datetime as dt
import json
from urllib.request import urlopen

url = "https://thelucius7.github.io/qwq/data/dashboard.json"
with urlopen(url, timeout=45) as response:
    data = json.load(response)
if data["schemaVersion"] != 1:
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

for platform, source in data["sources"].items():
    print(platform, "最后成功:", source["lastSuccess"], "错误:", source["error"], "提示:", source["warnings"])
```

## 数据结构

下表中的字段除明确注明“可省略”外均为必填。`null` 表示未知或不可用，不能等同于 `0`。所有 URL 优先直接使用响应值，不要通过拆分 ID 自行拼接。时间戳 `epoch`、`startEpoch` 的单位为**秒**；日期时间字符串使用 UTC 的 ISO 8601 / RFC 3339 格式，例如 `2026-09-08T00:17:00Z`。

### Dashboard

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `schemaVersion` | integer | 当前为 `1` |
| `handle` | string | 当前为 `Lucius7` |
| `timezone` | string | 当前为 `Asia/Taipei` |
| `generatedAt` | string · date-time | 汇总 JSON 生成时间，不等于各数据源刷新时间 |
| `sources` | object | 当前包含 `atcoder`、`codeforces`，值为 `Source` |
| `problems` | `Problem[]` | 收录题库，包含大量未尝试题目；长度不是解题数 |
| `contests` | `Contest[]` | 收录比赛，包含未参加的常规比赛；题目列表非空 |
| `accepted` | `AcceptedSubmission[]` | 当前判定通过的全部公开提交，含重复通过 |
| `attempted` | `string[]` | 去重后的已尝试题目 ID，包含已 AC 的题目 |

### Source

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `lastSuccess` | string · date-time | 该平台提交与目录快照最后成功更新时间 |
| `profile` | `Profile` | 用户 Rating 摘要 |
| `warnings` | `string[]` | 可选数据缺失或陈旧提示；成功时也可能非空 |
| `submissionCount` | integer | 拉取后按提交 ID 去重的全部提交数量，包括非 AC 和重复提交 |
| `error` | string 或 null | 本次该平台核心同步的错误；正常联网成功时为 null，离线重建也为 null |

`error`、`warnings` 是供人阅读的文本，不是稳定错误码。空错误不证明数据刚刚刷新；始终结合 `lastSuccess`。

### Profile

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `handle` | string | 平台用户名 |
| `url` | string · URI | 用户主页 |
| `rating` | integer 或 null | 当前 Rating；未定级或获取不到时可为空 |
| `maxRating` | integer 或 null | 最高 Rating |
| `rank` | string 或 null | AtCoder 当前为 `Algorithm`；Codeforces 为官方段位字符串 |
| `lastSuccess` | string · date-time 或 null | Rating 独立的最后成功获取时间；可能早于 Source 时间 |

### Problem

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `id` | string | 带平台前缀的题目唯一 ID |
| `platform` | string | `atcoder` 或 `codeforces` |
| `contestId` | string 或 null | 题库中的主要比赛关联；不是完整的比赛成员关系，也不保证出现在 `contests` 中 |
| `index` | string | 主要目录中的题目标号，例如 `A`、`D1` |
| `name` | string | 题目名称；元数据缺失时可能回退为题号 |
| `url` | string · URI | 题目链接 |
| `difficulty` | integer 或 null | AtCoder Problems 换算后估计难度，或 CF 题目 rating |

ID 格式：

| 对象 | 格式 |
| --- | --- |
| AtCoder 题目 | `atcoder:{problem_id}`，例如 `atcoder:abc001_1` |
| Codeforces 题目 | `codeforces:{contestId}:{index}`，例如 `codeforces:1:A` |
| CF 无比赛 ID 的特殊题库 | `codeforces:problemset:{problemsetName}:{index}`，其 `contestId` 为 null |
| AtCoder 比赛 | `atcoder:{contest_id}` |
| Codeforces 比赛 | `codeforces:{contestId}` |

题目与比赛分别属于自己的 ID 集合。题目 ID 可直接用作跨平台题目键；不要按名称合并题目。

### Contest

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `id` | string | 带平台前缀的比赛唯一 ID |
| `platform` | string | `atcoder` 或 `codeforces` |
| `name` | string | 比赛名称 |
| `kind` | string | 展示类别，例如 `ABC`、`ADT`、`Div. 2`、`Educational`、`Gym`；不固定为封闭枚举 |
| `startEpoch` | integer | 比赛开始的 Unix 秒；`0` 表示未知，不应显示为 1970 年 |
| `url` | string · URI | 比赛链接 |
| `problems` | `string[]` | 该比赛按题号排序的题目 ID，引用 `problems[].id` |
| `problemIndices` | object，可省略 | 题目 ID → 本场题号；当前主要用于 AtCoder 共享题 |
| `catalogComplete` | boolean | 是否按当前数据来源获得完整目录；不代表隐藏 / 移除的题目也已知 |
| `hasSubmissions` | boolean | 用户是否实际在此比赛有提交；无需 AC，也不要求是正式参赛 |

某题在本场的显示标号使用 `contest.problemIndices?.[problem.id] ?? problem.index`。不能仅按 `Problem.contestId` 分组还原比赛，因为 AtCoder 同一题目可能出现在多个比赛中。

### AcceptedSubmission

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `id` | integer | 源平台提交 ID，仅在同一平台内唯一 |
| `platform` | string | `atcoder` 或 `codeforces` |
| `problemId` | string | 引用 `problems[].id` |
| `epoch` | integer，> 0 | 当前判定通过的提交的提交时间，Unix 秒 |
| `url` | string · URI | 此次提交的详情链接 |

跨平台去重使用 `(platform, id)`，例如 `${event.platform}:${event.id}`。`epoch` 取 AtCoder `epoch_second` 或 Codeforces `creationTimeSeconds`，不记录评测完成时间、重判转 AC 的时刻或采集时刻。

`accepted` 由各平台数组合并，**不是全局时间排序**；需要按时间展示时自行排序。其他顶层数组也不应被依赖为跨平台全局排序。非 AC 提交不以逐条事件返回；它们用于已尝试状态、提交总数、比赛参与及缺失目录补全。API 不保存非 AC 提交的逐条时间、错误类型、语言或源码。

## 统计与关联规则

| 需求 | 算法 |
| --- | --- |
| 累计已解题 | `accepted` 按 `problemId` 去重 |
| 首次 AC | 每个 `problemId` 取最小 `epoch`，同秒取较小提交 `id` |
| 每日新增 / 热力图 | 先算全历史首次 AC，再按 UTC+8 日期计数 |
| 全部 AC 次数 | `accepted.length`，包括重复通过 |
| 比赛已 AC 数 | `contest.problems` 中已出现在首次 AC 集合的题目数量 |
| 比赛整场完成 | `catalogComplete === true`、题目数大于 0，且已 AC 数等于题目数 |
| 有提交的比赛 | `contest.hasSubmissions === true` |
| 连续做题 | 以全部 AC 的不同日期计算；当前连续可结束于今天，今天无 AC 则结束于昨天 |

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

这部分供维护同步器使用。普通 API 使用方读取一次本项目快照即可，无需直接访问上游。以下调用均为 `GET`；它们是**上游地址**，不是本项目新增的 API 路由。

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

### 调用节流与重试

当前 [Client](../scripts/sync.py) 在同一进程中按主机顺序节流：

| 主机 | 项目最小请求起始间隔 | 依据 |
| --- | --- | --- |
| `kenkoooo.com` | 1.1 秒 | AtCoder Problems 要求访问间隔大于 1 秒 |
| `atcoder.jp` | 1.1 秒 | 项目的保守设置，不代表官方公布的配额 |
| `codeforces.com` | 2.2 秒 | Codeforces 文档规定 API 最多每 2 秒 1 次；项目对同主机 Gym 页面也使用该间隔 |

每次请求超时为 45 秒，最多尝试 3 次；前两次失败后分别等待 3 秒、6 秒，再按主机间隔继续。请求带可识别的项目 User-Agent。该限制是单进程内的设置，不协调多台机器或多个同步进程；维护者应避免重复启动采集器。

现有 AtCoder / Codeforces 客户端未实现特殊的 `Retry-After` 解析或针对 403 / 429 的独立停止策略，不能把有限重试误写为这些能力。上游拒绝访问或限流时应检查官方规则和运行记录，避免手工连续重跑。上述策略不适用于尚未接入的洛谷，也不是账号不会被限制的保证。

## 错误与新鲜度

| 情况 | 输出行为 |
| --- | --- |
| 核心同步成功 | 原子保存该平台快照，推进 Source `lastSuccess`，`error` 为 null |
| 核心同步失败且已有缓存 | 保留整个平台旧快照；本次汇总的 Source `error` 为错误文本，另一平台仍可更新 |
| 首次同步失败且无缓存 | 同步中止，不覆盖汇总 JSON，不进入本次部署；此前已成功写入的其他平台快照可以保留 |
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

`generatedAt` 只表示汇总生成时间。AtCoder Problems 的收录也可能落后于 AtCoder 实时提交，即使本项目刚刚同步成功，仍受上游延迟影响。

GitHub Actions 会先部署可用的降级快照，然后通过 `degraded=true` 将工作流标为失败，便于发现问题。仅可选数据的 warnings 不会设置这个降级标记。不要用“站点 HTTP 200”或“工作流成功”代替逐平台的新鲜度检查。

## 接入边界

### QOJ

QOJ 尚未发布为本项目数据源，当前公开 `schemaVersion: 1` 不定义 `qoj` 数据。接入目标为只展示用户有提交记录的比赛；登录态获取、真实页面解析与同步验证仍待完成。浏览器中完成登录不会自动使 GitHub Actions 获得登录态。本文没有提供已可用的 QOJ Token 申请步骤或调用承诺，也不要求将 Cookie 写入仓库、前端、示例或聊天。

### 洛谷

洛谷自动同步未启用。已查阅的 [官方 OpenAPI](https://docs.lgapi.cn/open/openapi) 主要提供评测任务提交、结果和配额查询，不能据此当作个人历史提交接口；其中 OpenApp 的认证方式也不能替代普通用户历史记录授权。当前未确认满足本项目需求的官方接口与明确调用配额。

因此项目不调用未确认的历史接口，不通过高频请求测试账号限制，也不绕过访问控制。每日调用一次同样不能被承诺为不会触发账号限制。若后续接入，应先核实官方允许的接口和配额；手动导入目前也尚未实现。

## 版本与维护

- 当前数据版本为 `schemaVersion: 1`；OpenAPI 文档使用 OpenAPI `3.1.0` 格式，文档自身版本为 `1.0.0`，三者含义不同。
- 客户端应检查支持的数据版本、允许未知的附加字段，并正确处理可空值、可选字段和未知展示类别；当前平台枚举为 `atcoder` / `codeforces`。
- 维护者更改字段含义、必填性或平台契约时，应同步更新本文、OpenAPI 与相关测试，评估是否需要升级 `schemaVersion`；不要静默改变统计口径。
- OpenAPI 只描述本项目的静态快照，不为上游网站的稳定性、权限或配额提供承诺。
- 展示原始链接时使用返回的 `url`；消费名称、warnings、error 等上游相关文本时按文本渲染，避免作为 HTML 插入。
