---
doc_type: decision
slug: codestable-default-workflow
status: active
created_at: 2026-04-27
tags:
  - workflow
  - codestable
  - limcode
---

# CodeStable 作为默认 AI 协作入口

## 决定

从 2026-04-27 起，本仓库默认使用 CodeStable 工作流。

以后遇到开放式诉求、新功能、bug、重构、代码探索、知识沉淀、技术决定等任务时，优先从 `cs` 根入口分流；仓库尚未接入或需要刷新骨架时，先用 `cs-onboard`。

## 背景

仓库原来有 `.limcode/skills/using-superpowers` 作为会话起步入口，也有 `brainstorming`、`systematic-debugging`、`writing-plans`、`test-driven-development` 等通用流程技能。这套流程和 CodeStable 的 `cs`、`cs-feat`、`cs-issue`、`cs-roadmap` 在职责上明显重合。

用户明确表示更想使用 CodeStable，因此需要把默认入口切换过去。

## 处理方式

- 新建 `codestable/` 标准骨架，作为后续 CodeStable 产物聚合根。
- 更新根目录 `AGENTS.md`，把会话起步规则改为优先读取 CodeStable。
- `.limcode/` 暂不删除，保留为旧体系归档、历史计划、历史审查、APS 专项技能和子代理资料来源。
- 不批量搬动 `.limcode/plans/`、`.limcode/review/`、`.limcode/design/` 等旧资料，避免打乱历史证据。

## 预期结果

新工作默认在 `codestable/` 下留下需求、架构、功能、问题、重构和知识沉淀记录；旧 `.limcode` 继续可查，但不再抢默认入口。

