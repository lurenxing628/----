---
name: using-superpowers
description: 旧流程兼容入口；仅用于明确调用旧 superpowers 流程、续作旧 .limcode 任务或回查历史记录。
---

# 旧流程兼容入口

新任务遵循根 `AGENTS.md`，按需进入 [cs](../cs/SKILL.md)。旧流程不与 CodeStable 叠加。

续作旧任务时，读取对应的 `.limcode/design/`、`.limcode/plans/` 或 `.limcode/review/` 记录，并核实当前代码与本轮要求。已有历史文件留在原路径；新 CodeStable 产物写入 `.codestable/`。

只调用当前任务需要的入口：设计参考 [brainstorming](../brainstorming/SKILL.md)，实施参考 [executing-plans](../executing-plans/SKILL.md)，排查参考 [systematic-debugging](../systematic-debugging/SKILL.md)。无需串联一整套技能。

当前用户要求和已有授权决定范围。研究、审查只读；已授权实施连续推进，遇到新的关键取舍或实质扩范围再确认。
