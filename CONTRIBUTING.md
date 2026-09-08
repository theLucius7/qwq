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
- 数据同步的 `github-actions[bot]` 是直接提交 `main` 的例外，只提交 `data/sources/` 与 `public/data/dashboard.json`，并使用 `[skip ci]` 防止重复启动同步。部署工作流在写入之前运行测试。主分支仍禁止强推和删除。
- 数据机器人例外用于维持定时同步，不用于人工改动；任何新增有仓库写权限的工作流都需要通过 PR 审查。

## 数据与凭据

默认使用已有快照开发，避免反复联网采集。不要提交 Cookie、Token 或浏览器登录数据；数据问题请提供平台、题目或比赛链接、预期结果和脱敏后的复现步骤。`data/sources/` 属于内部缓存，`dist/` 不提交。
