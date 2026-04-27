# 项目级代理约定

## 语言

- 面向用户默认使用简体中文。
- 对用户解释时尽量用通俗说法，把背景、目的、改动范围和预期结果讲清楚。

## 当前默认工作流

本仓库从 2026-04-27 起默认使用 CodeStable 工作流。

收到任务时，优先按 CodeStable 分流：

- 开放式诉求 / 不知道走哪条路 → `cs`
- 仓库接入 / 刷新 CodeStable 骨架 → `cs-onboard`
- 新功能 / 新能力 → `cs-feat`
- 想法模糊、需要先聊清楚 → `cs-brainstorm`
- 大需求拆解 / 分阶段路线 → `cs-roadmap`
- BUG / 异常 / 文档错误 → `cs-issue`
- 行为不变的重构 / 代码优化 → `cs-refactor`
- 定向研究代码 → `cs-explore`
- 更新需求文档 → `cs-req`
- 更新或检查架构文档 → `cs-arch`
- 技术决定 / 长期约束 → `cs-decide`
- 踩坑经验 / 可复用做法 → `cs-learn` / `cs-trick`
- 用户指南 / 开发者指南 / API 参考 → `cs-guide` / `cs-libdoc`

## 会话起步规则

本文件是会话起步的首要兜底入口。

在任何回复、澄清问题、搜索、改文件、跑命令之前，先确认本仓库是否已有 `codestable/`：

- 如果已有 `codestable/`，优先读取 `codestable/reference/system-overview.md`，再按用户诉求选择对应的 `cs-*` 技能。
- 如果当前宿主没有自动注册 `cs-*` 技能入口，就直接读取已安装技能文件：`~/.codex/skills/<技能名>/SKILL.md`；如果这里没有，再查 `~/.agents/skills/<技能名>/SKILL.md`。
- 如果没有 `codestable/`，先走 `cs-onboard`。

不要再默认读取 `.limcode/skills/using-superpowers/SKILL.md`。只有下面这些情况才回看它：

- 用户明确要求按旧 superpowers / `.limcode` 流程处理。
- 正在续作 `.limcode/plans/`、`.limcode/review/`、`.limcode/design/` 里的历史任务。
- 需要查 APS 专项旧技能或旧审查记录，作为证据或参考。

## 事实源约定

当前项目中，事实源分成新旧两层：

- `codestable/`：新的默认工作流事实源。后续需求、架构、功能、问题、重构、知识沉淀优先落在这里。
- `.limcode/`：旧工作流归档和 APS 专项资产库。里面的历史 plan、review、design、APS 专项技能、子代理说明仍有参考价值，但不再抢默认入口。

`.cursor/` 仅作为旧宿主兼容层保留，不再作为首选事实源。

## 落盘约定

默认落盘位置按 CodeStable 目录执行：

- 需求现状：`codestable/requirements/`
- 架构现状：`codestable/architecture/`
- 大需求规划：`codestable/roadmap/`
- 新功能流程：`codestable/features/`
- 问题修复流程：`codestable/issues/`
- 重构流程：`codestable/refactors/`
- 知识沉淀：`codestable/compound/`

只有在续作旧任务或用户明确要求时，才继续写入 `.limcode/design/`、`.limcode/plans/`、`.limcode/review/`。

## APS 项目硬约束

- 当前目标仍是 Win7 x64 离线场景，因此依赖升级、语法升级与打包方案都要优先服从 Python 3.8 与 Win7 兼容性。
- 目标机不要求安装 Python；源码开发与打包机仍使用 Python 3.8。
- 页面不依赖外部脚本或样式，静态资源应随应用本地交付。
- 质量门禁入口仍以 `scripts/run_quality_gate.py` 为准。
- 需要 APS 专项深审、门禁快检、文档联动时，可以参考 `.limcode/skills/aps-*`，但默认产物仍应回到 CodeStable 结构。

## 子代理兼容

涉及 LimCode 原生已注册子代理、角色正文回退、宿主通用子代理与主代理降级执行时，仍可参考：

- `.limcode/subagents/README.md`
- `.limcode/skills/_shared/subagent-compat.md`
