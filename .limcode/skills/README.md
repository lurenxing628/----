# `.limcode/skills` 归档索引

本目录曾经是当前项目的技能体系事实源。自 2026-04-27 起，新任务默认走 CodeStable，入口在 `codestable/` 与已安装的 `cs-*` 技能。

## 当前定位

`.limcode/skills/` 现在主要保留三类内容：

- 旧 superpowers 风格流程技能：`using-superpowers`、`brainstorming`、`systematic-debugging`、`writing-plans` 等。
- APS 项目专项技能：`aps-deep-review`、`aps-post-change-check`、`aps-dev-doc-backfill`、`aps-full-selftest` 等。
- 子代理和旧实施流程辅助：`subagent-driven-development`、`executing-plans`、`requesting-code-review` 等。

## 默认不再使用的入口

新任务不要再默认从 `using-superpowers` 起步。

需要分流时，优先使用 CodeStable：

- `cs`
- `cs-onboard`
- `cs-feat`
- `cs-issue`
- `cs-refactor`
- `cs-explore`
- `cs-req`
- `cs-arch`
- `cs-roadmap`
- `cs-learn`
- `cs-trick`
- `cs-decide`

## 仍然可以使用的场景

这些内容暂时不删除，因为它们仍有参考价值：

- 续作历史 `.limcode/plans/` 时，需要沿用当时的执行口径。
- 做 APS 专项深审、门禁快检、文档联动时，需要参考 `aps-*` 技能。
- 排查旧任务、旧审查、旧计划时，需要读取历史技能说明。
- 子代理能力和降级执行口径仍可参考 `_shared/subagent-compat.md`。

## 新旧落盘边界

新任务默认落盘到 `codestable/`：

- `codestable/requirements/`
- `codestable/architecture/`
- `codestable/roadmap/`
- `codestable/features/`
- `codestable/issues/`
- `codestable/refactors/`
- `codestable/compound/`

只有续作旧任务或用户明确要求时，才继续写 `.limcode/design/`、`.limcode/plans/`、`.limcode/review/`。
