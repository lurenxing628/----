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

## 步骤 4.1：收敛 paths/contracts 启动链回退

- 完成时间：2026-04-30
- 改动文件：
  - `web/bootstrap/launcher_paths.py`
  - `web/bootstrap/launcher_contracts.py`
  - `tools/quality_gate_operations.py`
  - `tests/test_sync_debt_ledger.py`
  - `开发文档/技术债务治理台账.md`
- 改动内容：
  - `current_runtime_owner()` 读取当前用户失败时仍按旧合同回到 `unknown`，但会写 warning，现场能看到原因。
  - `read_shared_data_root_from_registry()` 读注册表失败、读值失败、关闭句柄失败时继续保留旧回退顺序，但会写 warning。
  - `resolve_runtime_state_dir()` 遇到非法 `cfg_log_dir` 对象时仍回到 `runtime/logs`，但会写 warning。
  - `read_runtime_lock()`、`read_runtime_contract()`、契约字段规范化、镜像写入、清理锁/错误/契约文件失败等路径保留旧返回值和 best effort 行为，但补了 warning。
  - `refresh-auto-fields` 增加同路径、同函数、同序号唯一命中时的自动字段对齐能力，解决“同一个 except 从静默改成可观测后指纹变化，台账受控刷新无法继续”的问题；旧 entry id 会保留，避免 accepted risk 引用断裂。
  - 台账通过受控刷新更新本批自动字段；`silent_fallback_count` 保持 153，后续 accepted risk 收口阶段再删除已消除风险。
- 扫描结果：
  - raw fallback scanner：observable_degrade 52、silent_default_fallback 27、cleanup_best_effort 17、silent_swallow 13。
  - 台账数量仍为 153；本小批只迁移已登记处理器的自动字段和 accepted risk 引用，不扩大历史未处理范围。
- 已完成验证：
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_win7_launcher_runtime_paths.py tests/regression_runtime_contract_launcher.py tests/regression_runtime_lock_reloader_parent_skip.py tests/test_sync_debt_ledger.py::test_refresh_auto_fields_realigns_silent_entry_when_handler_fingerprint_changed tests/test_sync_debt_ledger.py::test_refresh_auto_fields_realigns_silent_entry_when_only_except_ordinal_drifted tests/test_sync_debt_ledger.py::test_refresh_auto_fields_realigns_silent_entries_when_earlier_handler_left_scan tests/test_architecture_fitness.py::test_no_silent_exception_swallow tests/test_architecture_fitness.py::test_startup_silent_fallback_samples`：45 passed。
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check tools/quality_gate_entries.py tools/quality_gate_operations.py tests/test_sync_debt_ledger.py web/bootstrap/launcher_paths.py web/bootstrap/launcher_contracts.py`：通过。
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright -p pyrightconfig.gate.json`：0 errors，6 个既有 warning。
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/check_full_test_debt.py`：passed，active_xfail_count=0，fixed_count=5，collected_count=852。
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/sync_debt_ledger.py refresh --mode refresh-auto-fields`：通过，silent_fallback_count=153。
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/sync_debt_ledger.py check`：通过，silent_fallback_count=153。
- 偏离：
  - 此小批只处理 paths/contracts；processes/stop/network/runtime_probe 按后续小批继续处理。

## 步骤 4.2：收敛 processes/stop 运行时停止回退

- 完成时间：2026-04-30
- 改动文件：
  - `web/bootstrap/launcher_processes.py`
  - `web/bootstrap/launcher_stop.py`
  - `web/bootstrap/launcher_contracts.py`
  - `web/bootstrap/launcher.py`
  - `tools/quality_gate_operations.py`
  - `tools/quality_gate_shared.py`
  - `tests/test_sync_debt_ledger.py`
  - `tests/test_win7_launcher_runtime_paths.py`
  - `开发文档/技术债务治理台账.md`
- 改动内容：
  - 新增 `_pid_state()`，把 pid 状态分成存在、不存在、未知；旧 `runtime_pid_exists()` 和 `_pid_exists()` 仍返回 bool，保持旧 public 口径。
  - Windows `tasklist` 不可用、PowerShell/WMI/CIM 查询失败时不再被当作“没有进程”，内部停止链按未知处理，无法确认身份时失败闭合。
  - `_is_runtime_lock_active()` 在 pid 状态未知时按“仍可能活跃”处理，避免把无法枚举误判成可以清理。
  - runtime stop 失败时即使没有 logger，也会通过 `safe_log()` 打出 `runtime_stop_failed`、reason、pid、pid_match、endpoint 等原因。
  - Chrome stop 失败日志改用 `safe_log()`，日志器自身失败时不再制造新的静默吞错。
  - 强杀 runtime pid 仍必须先确认 `pid_match is True`；强杀命令失败只记录原因，最终仍以复查结果为准。
  - `refresh-auto-fields` 支持 `_pid_exists` 到 `_pid_state` 的受控条目迁移，并能移除已经不再被扫描命中的静默回退条目，同时同步 accepted risk 引用。
  - `_pid_state()` 拆成 pid 解析、Windows 枚举、POSIX 探测三个小 helper，避免新增高复杂度函数。
  - 启动链样本点从已消除的 `_log_runtime_stop_failure` 静默吞错，改为 `_request_runtime_shutdown` 的可观测降级样本。
- 扫描结果：
  - raw fallback scanner：observable_degrade 64、cleanup_best_effort 17、silent_default_fallback 15、silent_swallow 11。
  - 台账数量从 153 降到 151。
- 已完成验证：
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_win7_launcher_runtime_paths.py tests/regression_runtime_contract_launcher.py tests/regression_runtime_probe_resolution.py tests/regression_runtime_stop_cli.py tests/regression_runtime_lock_reloader_parent_skip.py tests/regression_entrypoint_meta_failure_visible.py`：52 passed。
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_architecture_fitness.py::test_no_silent_exception_swallow tests/test_architecture_fitness.py::test_startup_silent_fallback_samples tests/regression_quality_gate_scan_contract.py`：18 passed。
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check tools/quality_gate_operations.py tests/test_sync_debt_ledger.py web/bootstrap/launcher_processes.py web/bootstrap/launcher_stop.py web/bootstrap/launcher_contracts.py web/bootstrap/launcher.py tests/test_win7_launcher_runtime_paths.py`：通过。
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_architecture_fitness.py::test_cyclomatic_complexity_threshold tests/test_win7_launcher_runtime_paths.py::test_windows_pid_state_unknown_when_tasklist_unavailable`：2 passed。
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/sync_debt_ledger.py refresh --mode refresh-auto-fields`：通过，silent_fallback_count=151。
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/sync_debt_ledger.py check`：通过，silent_fallback_count=151。
- 偏离：
  - 此小批只处理 processes/stop；network/runtime_probe 按后续小批继续处理。
