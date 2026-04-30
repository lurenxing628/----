# 阶段 5 Win7 启动链复核

## 环境

- 日期：2026-04-30
- 当前开发机：macOS（本机不是 Win7）
- 当前分支：`codex/techdebt-phase5-startup-fallbacks`
- 阶段 5 代码与台账收口 HEAD：`b95f7d9`
- 说明：本文件后续如有修正，只修复审计记录文字，不改变阶段 5 代码与台账事实；最终证明仍以本文件所在提交之后重新运行的本地验证和 clean quality gate 为准。
- Python 口径：`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python ...`
- Chrome runtime：未在本机执行 Win7 Chrome109 运行时复测

## 自动化结果

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_win7_launcher_runtime_paths.py tests/regression_runtime_contract_launcher.py tests/regression_runtime_probe_resolution.py tests/regression_runtime_stop_cli.py tests/regression_runtime_lock_reloader_parent_skip.py tests/regression_entrypoint_meta_failure_visible.py tests/test_architecture_fitness.py::test_no_silent_exception_swallow tests/test_architecture_fitness.py::test_startup_silent_fallback_samples tests/regression_quality_gate_scan_contract.py`：已通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_ui_mode.py tests/regression_ui_mode_startup_guard_observability.py tests/regression_scheduler_config_manual_url_normalization.py tests/regression_safe_next_url_hardening.py tests/regression_manual_entry_scope.py tests/regression_config_manual_markdown.py tests/test_architecture_fitness.py::test_request_service_target_files_no_direct_assembly tests/test_sync_debt_ledger.py::test_validate_ledger_rejects_ui_mode_split_scope_drift`：已通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright -p pyrightconfig.gate.json`：0 errors，6 个既有 scheduler `__all__` warning。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/check_full_test_debt.py`：通过，active_xfail_count=0。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/sync_debt_ledger.py check`：通过。

## 人工复测

- Win7 真机/虚拟机复测：未执行。
- 启动：未执行真机复测，相关 accepted risk 保留。
- 停止：未执行真机复测，相关 accepted risk 保留。
- 再启动：未执行真机复测，相关 accepted risk 保留。
- 端口占用：未执行真机复测，相关 accepted risk 保留。
- 损坏 runtime contract：未执行真机复测，相关 accepted risk 保留。
- 普通 Chrome 不被误杀：自动化负例已覆盖，Win7 真机复测未执行。
- APS Chrome profile 精确匹配：自动化负例已覆盖，Win7 真机复测未执行。
- 第二账户或无法确认归属时失败闭合：自动化负例已覆盖，Win7 真机复测未执行。
- ui_mode 切换：自动化已覆盖，真机复测未执行。
- render bridge：自动化已覆盖 V2 命中、缺失回退和真实渲染异常透出，真机复测未执行。

## 已删除风险

- `risk:ui-mode-render-bridge-observable-degrade`
  - 删除原因：该风险不依赖 Win7 真机/虚拟机才能证明；阶段 5 已拆分 `web/ui_mode.py`，并通过 public API、render bridge、manual src 和扫描器合同测试，不再把它作为 accepted risk 保留。

## 保留风险

- `risk:launcher-bind-host-port-win7`
  - owner：SP03
  - 保留原因：端口绑定、自动换路和 socket 行为需要 Win7 x64 目标机确认。
  - review_after：2026-05-31
  - exit_condition：完成 Win7 x64 启动、端口占用后自动换路、再次启动和 launcher.log 可读原因复测。
- `risk:launcher-process-probe-kill-win7`
  - owner：SP03
  - 保留原因：tasklist、PowerShell、WMI/CIM、Chrome profile 精确匹配和不误杀普通 Chrome 需要 Win7 x64 目标机确认。
  - review_after：2026-05-31
  - exit_condition：完成普通 Chrome 共存、APS Chrome profile 精确匹配、Profile2/_bak/URL 伪造负例、无法枚举进程时失败闭合和 runtime stop 复测。
- `risk:launcher-runtime-lock-contract-win7`
  - owner：SP03
  - 保留原因：运行锁、runtime contract、残留文件清理和停机链需要 Win7 x64 目标机确认。
  - review_after：2026-05-31
  - exit_condition：完成启动、停止、再次启动、损坏 runtime contract、残留 lock/contract 清理和停止失败可读原因复测。
- `risk:launcher-runtime-root-owner-win7`
  - owner：SP03
  - 保留原因：运行根目录、注册表、owner 解析和第二账户持锁阻止进入需要 Win7 x64 目标机确认。
  - review_after：2026-05-31
  - exit_condition：完成机器级注册表、当前进程环境变量、共享数据目录、第二账户持锁阻止进入和 owner 归属可读原因复测。
