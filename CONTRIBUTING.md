# 贡献与维护

通用分支、PR 和提交约定见 [组织贡献规范](https://github.com/xw7qwq/.github/blob/main/CONTRIBUTING.md)。

## 本地验证

使用 Node.js 22+ 和 Python 3.11+，无需安装第三方依赖：

```sh
npm test
npm run build
```

测试覆盖日期、去重、比赛关联、平台解析与失败回退。构建使用仓库中的快照校验公开数据，不请求上游服务。修改同步逻辑时补充对应边界测试；修改公开字段时同步更新 `docs/API.md`、`docs/openapi.json` 和必要的 `schemaVersion`。

## 分支与检查

- 人工改动从最新 `main` 建立 `feat/`、`fix/`、`docs/` 或 `chore/` 分支，通过 PR 合并。
- `CI` 工作流在 PR、人工主分支提交及手动触发时运行，稳定的必需检查名为 `check`。
- 合并前执行测试与构建，并解决审查讨论；合并后删除临时来源分支。
- `main` 只通过 PR 更新，要求 `check` 通过并禁止强推和删除，没有数据机器人的绕过例外。
- 长期分支 `data/snapshots` 只保存 `data/sources/` 与 `public/data/dashboard.json`，是部署时恢复缓存、请求预算和最新公开数据的来源。保留该分支，不合并到 `main`。源码分支中的快照只供离线开发，日常同步不会更新它们。
- 部署工作流分别检出 `main` 和数据分支，先恢复最新快照再测试、同步，只向数据分支写回更新。数据提交不需要 `[skip ci]`；工作流的 push 触发只匹配 `main`。新增有仓库写权限的工作流必须通过 PR 审查。

## 数据与凭据

默认使用已有快照开发，避免反复联网采集。不要提交 Cookie、Token 或浏览器登录数据；数据问题请提供平台、题目或比赛链接、预期结果和脱敏后的复现步骤。`data/sources/` 属于内部缓存，`dist/` 不提交。

需要用最新线上快照复现问题时，按 README 的数据恢复命令检出 `data/snapshots` 到被忽略的 `.snapshots/`；恢复会替换本地缓存，先保存尚未提交的手动导入数据。不要把 `.snapshots/` 或其 Git 元数据提交到源码分支。
