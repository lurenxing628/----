---
doc_type: refactor-apply-notes
refactor: 2026-04-30-techdebt-phase5-startup-fallbacks
status: in-progress
tags: [techdebt, startup, fallback, win7]
---

# techdebt phase5 startup fallbacks apply notes

## 步骤 1：记录阶段 5 启动链 fallback 基线

- 完成时间：2026-04-30
- 改动文件：
  - `audit/2026-05/phase5_startup_fallback_baseline.json`
  - `codestable/refactors/2026-04-30-techdebt-phase5-startup-fallbacks/*`
- 当前分支：`codex/techdebt-phase5-startup-fallbacks`
- 起点提交：`ae4c421`
- 基线摘要：
  - raw fallback scanner count：109。
  - cleanup_best_effort：17。
  - observable_degrade：35。
  - silent_default_fallback：39。
  - silent_swallow：18。
  - scope_tag=render_bridge：18。
  - scope_tag=startup_guard：5。
  - accepted_risk_count：5。
- 台账口径：
  - 阶段 4 收口后 `scripts/sync_debt_ledger.py check` 的 `silent_fallback_count=153`。
  - raw scanner 记录用于阶段 5 baseline，最终仍以台账 check 和 clean quality gate 为准。
- 验证结果：
  - 本步骤只落审计和 CodeStable 记录，未改业务代码。
- 偏离：无。
