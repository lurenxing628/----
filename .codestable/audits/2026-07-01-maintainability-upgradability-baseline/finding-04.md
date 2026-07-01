---
doc_type: audit-finding
audit: 2026-07-01-maintainability-upgradability-baseline
created: 2026-07-01
finding_id: "maintainability-04"
nature: maintainability
severity: P2
confidence: medium
suggested_action: cs-refactor
status: open
---

# Finding 04：质量门禁强，但门禁系统自身复杂

## 速答

质量门禁是项目维护能力的强项，但它本身已经变成一个不小的系统。以后维护门禁时，不能只把它当一个脚本看。

## 关键证据

- `scripts/run_quality_gate.py:3048-3069` — 门禁会写 manifest，并区分是否要求干净工作区。
- `scripts/run_quality_gate.py:3094-3096` — 要求干净工作区时，只要门禁前已有脏状态就失败。
- `tools/quality_gate_shared.py:706-844` — 统一门禁计划包含版本检查、Ruff、测试收集、Python 3.8 语法扫描、架构检查、类型检查、启动回归、完整测试债务检查、必跑回归校验等多步。
- `.github/workflows/quality.yml:77-78` — 持续集成入口执行 `python scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache`。
- 本次 `git status --short | wc -l` 输出 `345`，所以没有运行 clean-worktree 门禁，避免把必然失败包装成证明。

## 影响

这是“好东西变重”的典型情况：

- 好处：它能防很多回潮。
- 成本：门禁自身改错，会影响全项目开发节奏。
- 成本：脏工作区下不能给正式证明，长审计容易被现场状态影响。

## 修复方向

不是削弱门禁，而是给门禁拆更清楚的层：

- 快速只读诊断入口。
- 干净工作区正式证明入口。
- Win7/打包专项证明入口。
- 门禁自身变更的最小回归集合。

## 建议动作

走 `cs-refactor`，但优先级低于核心循环依赖和 Win7 交付证明。
