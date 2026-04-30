---
doc_type: refactor-apply-notes
refactor: 2026-04-30-techdebt-phase4-ledger-complexity
status: in-progress
tags: [techdebt, oversize, complexity, quality-gate]
---

# techdebt phase4 ledger complexity apply notes

## 步骤 1：记录阶段 4/5 开工基线

- 完成时间：2026-04-30
- 改动文件：
  - `audit/2026-05/phase4_phase5_baseline.txt`
  - `codestable/refactors/2026-04-30-techdebt-phase4-ledger-complexity/*`
- 验证结果：
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/check_full_test_debt.py`：passed，active_xfail_count=0，fixed_count=5，collected_count=841。
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/sync_debt_ledger.py check`：通过，oversize_count=8，complexity_count=29，silent_fallback_count=153，test_debt_count=5，accepted_risk_count=5。
- 偏离：无。
