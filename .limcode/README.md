# .limcode 归档说明

本目录曾经是当前仓库的 AI 协作事实源。自 2026-04-27 起，仓库默认工作流已切换到 CodeStable，新的协作产物优先落在 `codestable/`。

`.limcode/` 现在保留为两类用途：

- 旧工作流归档：历史 plan、review、design、progress、合同文件等。
- APS 专项资产库：`aps-*` 专项技能、历史深审方法、子代理兼容说明、角色正文源文件等。

## 当前默认入口

默认入口已经从：

- `.limcode/skills/using-superpowers/SKILL.md`

切换为：

- `codestable/reference/system-overview.md`
- 已安装的 CodeStable `cs-*` 技能

也就是说，新任务默认走：

- `cs`：开放式诉求分流
- `cs-onboard`：仓库接入 / 骨架刷新
- `cs-feat`：新功能
- `cs-issue`：bug / 异常 / 文档错误
- `cs-refactor`：行为不变的重构
- `cs-explore`：定向代码探索
- `cs-req` / `cs-arch` / `cs-roadmap`：需求、架构、路线图
- `cs-learn` / `cs-trick` / `cs-decide`：知识、做法、决定沉淀

## 什么时候还看 `.limcode`

只有这些情况需要回看 `.limcode`：

- 续作 `.limcode/plans/`、`.limcode/review/`、`.limcode/design/` 里的历史任务。
- 需要引用旧审查、旧计划、旧证据作为上下文。
- 需要 APS 专项技能，例如 `.limcode/skills/aps-deep-review/`、`.limcode/skills/aps-post-change-check/`、`.limcode/skills/aps-dev-doc-backfill/`。
- 需要子代理兼容说明或角色正文源文件。

## 不再做的事

- 不再把 `.limcode/skills/using-superpowers/SKILL.md` 当成会话默认起点。
- 不再把 `.limcode/design/`、`.limcode/plans/`、`.limcode/review/` 当成新任务默认落盘位置。
- 不批量移动或删除历史 `.limcode` 文件；旧资料保持原位，避免破坏证据链。

## 子代理与旧角色资料

以下文件仍可作为参考：

- `.limcode/subagents/README.md`
- `.limcode/skills/_shared/subagent-compat.md`
- `.limcode/agents/README.md`

它们只负责说明旧 LimCode / 子代理兼容口径，不改变 CodeStable 作为默认入口的事实。
