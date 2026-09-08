# Lucius7 · 解题日志

[打开网站](https://thelucius7.github.io/qwq/) · [每日同步](https://github.com/theLucius7/qwq/actions/workflows/pages.yml)

在一个页面查看 Lucius7 的 AtCoder / Codeforces 做题记录：

- 累计解题、本月新增、今日首次 AC 和连续做题天数。
- 按年份、平台筛选的 AC 热力图；点击日期查看题目、难度和提交时间。
- 每日「首次 AC / 全部 AC」切换，重复通过不会增加解题总数。
- 比赛题目矩阵，区分已 AC、尝试过和未完成；支持比赛类别、完成状态和题目搜索。
- AtCoder Algorithm / Codeforces 当前与最高 Rating，原始主页和跟踪器链接。

## 更新与部署

GitHub Actions 每天 **08:17（Asia/Taipei / UTC+8）** 自动拉取数据、提交快照并部署 GitHub Pages。GitHub 定时任务可能排队延迟，并非精确到分钟。也可在 Actions → **Daily sync and GitHub Pages** → **Run workflow** 手动刷新；推送到 `main` 同样触发。

仓库 Pages 的发布来源应设为 **GitHub Actions**。站点完全静态，不需要 API 密钥、数据库或付费服务；浏览器读取同源 JSON，不直接跨域请求外部平台。工作流仅将 `public/` 的构建结果发布到 Pages。

每天完整重新读取提交记录，以覆盖重判和延迟判题。数据按平台原子更新；源站失败时沿用其上次成功快照，网页显示提示及最后成功时间。另一平台仍可更新。降级结果部署后工作流会报告失败，以便 GitHub 发出失败通知。首次同步没有可用快照则中止发布。每日提交也使仓库保持活动，避免公开仓库定时工作流的长期不活动停用问题。

## 统计口径

- **已解题 / 每日新增**：仅计 AtCoder `AC` 和 Codeforces `OK`，按平台题号取最早通过时间。AtCoder 键为 `problem_id`；Codeforces 为 `contestId + index`，包含练习、比赛、虚拟赛和公开 Gym 提交。
- **全部 AC**：每次通过都记录。**连续做题**：当天有任意 AC 即算一天，允许今天尚未 AC 时延续到昨天的连续天数。
- **日期**：统一按 UTC+8 的 00:00–23:59:59 归档，不受访问者设备时区影响。顶部本月和今天始终相对当前日期；年份选择仅筛选热力图。每日清单初次打开定位最近一次 AC。
- **比赛进度**：按题号统计真实 AC。「有提交记录」仅显示实际在该比赛提交过的记录。AtCoder 跨比赛重复题目共用题目 ID，但不会因此伪造参赛记录；Codeforces 跨 Div 的不同题号分别显示，不将 CFTracker 的“同题推断”当成实际提交，格子数可能与 CFTracker 不同。
- **Gym**：从官方公开比赛页补全已尝试比赛的题目目录，并复用已获得的目录。补全失败时显示 `已 AC / ?`，不会错误标为整场完成。常规比赛目录来自公开题库，未公开或被移除的题目无法显示；私人、隐藏、不可访问提交不在统计范围内。
- **难度**：AtCoder Problems 的估计难度（低于 400 按该站公式换算）与 CF 题目 rating；缺失值不虚构为 0。
- **新鲜度**：页面按每个平台的最后成功同步时间判断；超过 36 小时也会提示。AtCoder Problems 本身可能滞后于 AtCoder 实时提交。

## 数据来源

| 数据 | 来源 |
| --- | --- |
| AtCoder 提交、题目、比赛映射、难度 | [AtCoder Problems API](https://github.com/kenkoooo/AtCoderProblems/blob/master/doc/api.md) / [Lucius7 题表](https://kenkoooo.com/atcoder/#/table/Lucius7) |
| AtCoder Algorithm Rating | [官方历史 JSON](https://atcoder.jp/users/Lucius7/history/json) / [个人主页](https://atcoder.jp/users/Lucius7) |
| CF 提交、题库、比赛、Gym 名称、Rating | [Codeforces 官方 API](https://codeforces.com/apiHelp) / [个人主页](https://codeforces.com/profile/Lucius7) |
| Gym 完整题表 | Codeforces 官方公开 `/gym/{contestId}` 页面 |
| CF 进度视图参考 | [CFTracker](https://cftracker.netlify.app/contests)，其提交数据同样来自 Codeforces API |

AtCoder 请求间隔至少 1.1 秒；Codeforces 至少 2.2 秒。AtCoder 时间戳分页保留边界重叠并按提交 ID 去重；Codeforces 使用分页和重叠窗口。所有请求带超时及有限次数重试。仅保存展示所需的公开数据，不保存源码、API 凭据或其他个人资料字段。

## 本地运行

需要 Node.js 22+、Python 3.11+，无需安装第三方依赖。

```sh
npm run sync    # 更新真实数据；首次需要额外获取 Gym 题表
npm test        # 日期、分页、去重、Gym 和降级回归测试
npm run dev     # http://127.0.0.1:4173
npm run build   # 静态文件输出到 dist/
```

离线重建数据：`python3 scripts/sync.py --offline`。平台成功快照位于 `data/sources/`；公开页面数据位于 `public/data/dashboard.json`。可以直接打开 Actions 运行记录查看每次同步的题目总数。
