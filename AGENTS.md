# 项目级代理约定

## 语言

- 面向用户默认使用简体中文。

## 事实源约定

当前项目中，下列目录共同构成本仓库的事实源：

- `.limcode/skills/`
- `.limcode/rules/`
- `.limcode/subagents/`：LimCode 原生子代理模板与安装口径
- `.limcode/agents/`：角色正文源文件与回退提示词来源，不是 LimCode 自动扫描的原生注册目录

`.cursor/` 仅作为旧宿主兼容层保留，不再作为首选事实源。

## 宿主降级约束（重要）

即使当前宿主**不自动加载** `.limcode/rules/`，也必须继续遵守本文件中的同等约束：

- 仍以 `.limcode` 为事实源
- 仍先读取 `.limcode/skills/using-superpowers/SKILL.md`
- 仍按 `.limcode/skills/` 技能体系分流
- 如果目标技能尚未注册到专用技能入口，就直接读取 `.limcode/skills/<技能名>/SKILL.md`
- 如果需要子代理：优先使用 LimCode 原生已注册子代理；未注册时，再回退到 `.limcode/agents/*.md` 角色正文源文件
- 只有当前宿主只扫描 `.cursor/` 时，才允许把 `.cursor` 作为兼容发现入口；实际执行与落盘一律以 `.limcode` 为准

## 会话起步规则

本文件是会话起步的首要兜底入口。无论当前会话有没有显式注入规则上下文，在任何回复、澄清问题、搜索、改文件、跑命令之前，先读取：

- `.limcode/skills/using-superpowers/SKILL.md`

然后按其中的技能路由规则分流处理任务。

## 默认工作流

- 新功能 / 行为变更 → `brainstorming`
- 复杂新功能 / 需要三轮对抗式设计 → `feature-design`
- BUG / 失败用例 / 异常行为 → `systematic-debugging`
- 复杂排查 / 独立验证 / 对抗审查 → `deep-investigate`
- design 批准后 → `writing-plans`
- plan 执行 → `subagent-driven-development` 或 `executing-plans`
- 实现时 → `test-driven-development`
- 任务完成后 → `requesting-code-review`
- 大范围深审 → `aps-deep-review`
- 改后快检 → `aps-post-change-check`
- 文档联动 → `aps-dev-doc-backfill`
- 收尾 → `finishing-a-development-branch`

## 落盘约定

- design：`.limcode/design/`
- plan：`.limcode/plans/`
- review：`.limcode/review/`
- 审计取舍报告：`audit/YYYY-MM/`

## 子代理兼容

涉及 LimCode 原生已注册子代理、角色正文回退、宿主通用子代理与主代理降级执行时，统一以：

- `.limcode/subagents/README.md`
- `.limcode/skills/_shared/subagent-compat.md`

为准。
