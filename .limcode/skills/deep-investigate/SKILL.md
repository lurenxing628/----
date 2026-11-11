---
name: deep-investigate
description: 旧深度排查兼容入口；用于明确要求旧多轮调查或续作旧排查记录。新任务优先 cs-issue-analyze 或 cs-explore。
---

# 复杂排查兼容入口

当前问题分析使用 [cs-issue-analyze](../cs-issue-analyze/SKILL.md)，定向研究使用 [cs-explore](../cs-explore/SKILL.md)。跨层或配置一致性调查按需读取 [runtime-evidence.md](runtime-evidence.md)。

先把用户怀疑视为待验证假设，追踪决策链并裁决证据。能静态判定的直接给结论，需要实际运行证据的明确验证方法和限制。不要为了固定轮数、方案数量或脚本数量追加工作。

用户明确要求多轮调查或独立验证时完成对应范围；整项调查已获授权则连续完成，各轮不机械等“继续”。委派遵循 [共享约定](../_shared/subagent-compat.md)，独立审核只读，对争议重新核实证据。

调查、审查不自动授权修复。结论按当前任务需要内联或写入 CodeStable 任务目录；已有 `.limcode/review/` 记录保留原路径。
