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

## 步骤 2：更新 ui_mode 拆分后的启动链扫描范围

- 完成时间：2026-04-30
- 改动文件：
  - `tools/quality_gate_shared.py`
  - `tools/quality_gate_scan.py`
  - `tools/quality_gate_ledger.py`
  - `tools/quality_gate_support.py`
  - `scripts/sync_debt_ledger.py`
  - `tests/regression_quality_gate_scan_contract.py`
  - `tests/test_sync_debt_ledger.py`
  - `tests/test_full_test_debt_registry_contract.py`
  - `开发文档/技术债务治理台账.md`
- 改动内容：
  - `STARTUP_SCOPE_PATTERNS` 增加 `web/ui_mode_request.py`、`web/ui_mode_store.py`、`web/render_bridge.py`、`web/manual_src_security.py`，为后续拆 `web/ui_mode.py` 先补扫描范围。
  - `ui_mode_scope_tag()` 支持按文件区分职责：request/store 归 `startup_guard`，render_bridge/manual_src_security 归 `render_bridge`，原 `web/ui_mode.py` 仍按旧 public 函数名区分。
  - `is_startup_scope_path()` 同步识别新增的 UI mode 拆分文件，避免架构门禁只看 `web/ui_mode.py` 和 `web/bootstrap/`。
  - `refresh-auto-fields` 改用不预校验读取，解决“扫描范围变更时旧台账 scope 先不匹配，受控刷新还没来得及修”的卡点；最终仍通过 `finalize_ledger_update()` 校验后保存。
  - 台账通过受控刷新更新 `silent_fallback.scope`，`silent_fallback_count` 保持 153。
- 已完成验证：
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_architecture_fitness.py::test_no_silent_exception_swallow tests/test_architecture_fitness.py::test_startup_silent_fallback_samples tests/regression_quality_gate_scan_contract.py tests/test_sync_debt_ledger.py::test_refresh_command_dispatches_expected_mode tests/test_sync_debt_ledger.py::test_refresh_auto_fields_skips_prevalidation_and_loads_required_ledger tests/test_sync_debt_ledger.py::test_check_command_validates_current_ledger tests/test_full_test_debt_registry_contract.py::test_finalize_ledger_update_preserves_test_debt_and_stable_updated_at`：24 passed。
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check ...`：通过。
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright -p pyrightconfig.gate.json`：0 errors，6 个既有 warning。
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/check_full_test_debt.py`：passed，active_xfail_count=0，fixed_count=5，collected_count=847。
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/sync_debt_ledger.py check`：通过，silent_fallback_count=153。
- 偏离：无。此步骤只补扫描和台账刷新能力，不拆 `web/ui_mode.py` 业务逻辑。

## 步骤 3：引入启动运行时能力结果模型

- 完成时间：2026-04-30
- 改动文件：
  - `web/bootstrap/runtime_capabilities.py`
  - `tests/test_runtime_capabilities.py`
- 改动内容：
  - 新增 `CapabilityResult`，统一表达 `available`、`degraded`、`unavailable` 三种状态。
  - 新增 `available()`、`degraded()`、`unavailable()` helper。
  - `degraded()` 和 `unavailable()` 必须提供 reason；空 reason 会直接抛 `ValueError`，避免后续继续制造“没解释的降级”。
  - 降级和不可用都会写 warning 日志，后续 launcher 接入时可以用它替代无声默认值。
- 已完成验证：
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_runtime_capabilities.py -q -p no:cacheprovider`：通过。
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check web/bootstrap/runtime_capabilities.py tests/test_runtime_capabilities.py`：通过。
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright -p pyrightconfig.gate.json`：0 errors，6 个既有 warning。
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/check_full_test_debt.py`：passed，active_xfail_count=0，fixed_count=5，collected_count=850。
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/sync_debt_ledger.py check`：通过，silent_fallback_count=153。
- 偏离：无。此步骤只新增模型和测试，尚未批量改 launcher 调用方。
