---
doc_type: refactor-fix-note
refactor: 2026-04-30-techdebt-phase5-startup-fallbacks
status: completed
scope: 阶段 5 review 后的启动链补强
tags: [techdebt, startup, fallback, win7]
---

# 阶段 5 review 修复记录

## 背景

阶段 5 原本已经通过自动化门禁，但 review 指出它还不能说成“Win7 启动链彻底闭环”。主要原因有四个：

- 运行锁释放遇到非法 `expected_pid` 时，必须失败闭合，不能继续删锁。
- `runtime contract` 损坏、缺字段、版本不对，不能和“文件不存在”混成同一种结果。
- 关键启动链日志不能只退到控制台，要尽量落到 `launcher.log` 或 `aps_launch_error.txt`。
- 台账自动对齐不能太宽，不能把已经变了语义的 fallback 悄悄换绑到旧 accepted risk。

## 本轮改动范围

- 新增 `web/bootstrap/launcher_observability.py`，统一启动链 warning 落盘：
  - 有 `state_dir` 时写 `state_dir/launcher.log`。
  - 有 `cfg_log_dir` 时写 `cfg_log_dir/launcher.log`。
  - 只有 `runtime_dir` 时写 `runtime_dir/logs/launcher.log`。
  - 需要用户可读错误时同步写 `aps_launch_error.txt`。
- 新增 `web/bootstrap/launcher_contract_result.py`，让契约读取分清：
  - `missing`：文件不存在。
  - `unreadable`：文件打不开或 JSON 损坏。
  - `invalid`：JSON 能读但字段、版本或类型不对。
  - `valid`：字段完整，可以用于停止链判断。
- 新增 `web/bootstrap/launcher_lock_result.py`，让运行锁读取也分清：
  - `missing`：锁文件不存在。
  - `empty`：锁文件存在但还没有内容，按“可能正在写入”处理。
  - `unreadable`：锁文件读不了。
  - `invalid`：锁文件格式坏、缺 pid、pid 非法，或者夹杂无法解释的坏行。
  - `valid`：锁文件完整，可以用于判断归属。
- 拆出 `web/bootstrap/launcher_health.py` 和 `web/bootstrap/launcher_chrome.py`，让停止链文件重新低于 500 行，也让健康探测和 Chrome profile 停止更容易单独审查。
- 拆出 `web/bootstrap/launcher_stop_state.py`，把停止链状态判断放进小模块，保证 `launcher_stop.py` 继续低于 500 行。
- `release_runtime_lock()` 改为失败闭合：
  - `expected_pid="bad"`、`0`、负数、不匹配 pid 都不会删锁。
  - `expected_pid is None` 时只释放当前进程自己的锁。
- `acquire_runtime_lock()` 和 `release_runtime_lock()` 对坏锁失败闭合：
  - 空锁、读不了的锁、格式坏的锁，不会被当成“没有锁”或“陈旧锁”清理。
  - 锁里同时有合法字段和坏行时，也按 `invalid` 处理，避免半坏文件被误删。
- `stop_runtime_from_dir()` 的最终收尾顺序已调整：
  - 先确认 APS Chrome 停止成功。
  - Chrome 停止失败时保留 `aps_runtime.json`、`aps_runtime.lock`、host/port 等现场文件，方便重试和排查。
  - Chrome 停止成功后才清理运行痕迹。
- `stop_runtime_from_dir()` 继续补强 contract 和清理失败闭合：
  - `invalid` / `unreadable` 的 `aps_runtime.json` 不再落到 `stale` 状态。
  - endpoint 不通、lock 不活跃但 contract 损坏时，状态为 `blocked_contract`，停止命令返回失败并保留现场文件。
  - 新增 `RuntimeCleanupResult`，运行时文件清理失败会让停止命令返回失败，不再把“删不干净”当成停止成功。
  - 旧 `delete_runtime_contract_files()` 仍保留给退出钩子和旧调用方使用，新停止链改走 `delete_runtime_contract_files_result()`。
- 继续补强运行时 endpoint 文件读取：
  - 新增 `RuntimeEndpointReadResult`，把 `aps_host.txt` / `aps_port.txt` 的缺失、不可读和非法内容分开。
  - 停止主链不再把 host 文件不可读或 port 文件非法压成空值 / 0 后当作 `stale` 清理。
  - endpoint 文件读坏且仍有 runtime 痕迹时，状态进入 `blocked_endpoint`，停止命令返回失败并保留现场文件。
  - 旧 `_read_runtime_endpoint_files()` 仍保留旧 dict 返回形状，便于旧测试和旧调用方兼容。
- `TransactionManager.transaction()` 的事务归属判断改为失败闭合：
  - `conn.in_transaction` 缺失或读取失败时直接抛错。
  - 不再猜“当前上下文拥有事务”，避免误提交或误回滚外层事务。
- 启动链关键路径不再直接用 `safe_log(None)` 当唯一可见渠道。
  - 停止链进入运行状态判断时，会把 `state_dir/runtime_dir` 写入进程探测上下文。
  - 进程枚举、PowerShell、进程路径确认和强杀失败会写入 `launcher.log`。
  - 端口选择 `pick_port()` 保留 `(host, port)` 返回形状，同时可以接收 `state_dir/runtime_dir/cfg_log_dir` 写日志。
  - 启动错误文件写入失败时，也会通过 `launcher_log_warning()` 写 `launcher.log`。
- 台账 silent fallback 增加 `handler_context_hash`，自动 realign 必须检查 fallback 类型、scope_tag 和处理器上下文。
  - 同 id、同 kind 但 `handler_context_hash` 变化会被拒绝。
  - 旧 architecture fitness 迁移条目的 `silent_swallow -> cleanup_best_effort` 只允许非启动链历史条目使用，并有测试锁住边界。
- `web/bootstrap/*.py` 统一回到 Python 3.8 类型写法。

## `safe_log(None)` 替换情况

- 已替换范围：
  - `web/bootstrap/launcher_contracts.py`
  - `web/bootstrap/launcher_stop.py`
  - `web/bootstrap/launcher_processes.py`
  - `web/bootstrap/launcher_network.py`
  - `web/bootstrap/runtime_probe.py`
  - `web/bootstrap/entrypoint.py`
  - `web/bootstrap/launcher_paths.py`
  - `web/bootstrap/paths.py`
  - `web/bootstrap/plugins.py`
- 当前检查命令：
  - `rg -n 'safe_log\\(None' web/bootstrap`
- 预期结果：
  - 无直接命中。
- 白名单：
  - 本轮没有保留 `web/bootstrap` 下的直接 `safe_log(None)`。

## Win7 风险状态

- 当前机器是 macOS 开发环境，仍未执行 Win7 真机或虚拟机复测。
- 4 条 Win7 accepted risk 继续保留，不在本轮关闭：
  - 端口/主机绑定现场差异。
  - 进程探测与 Chrome profile 现场差异。
  - runtime lock / contract 残留清理现场差异。
  - 运行根目录和 owner 判断现场差异。
- 本轮只能证明：
  - 启动链更容易查日志。
  - 运行锁更不容易误删。
  - contract 损坏不再被当成普通 missing。
  - endpoint 文件读坏不再被当成普通 stale。
  - Chrome/profile 相关自动化负例仍保持失败闭合。
- 本轮不能证明：
  - Win7 真机启动、停止、再次启动已经现场闭环。
  - Win7 上 PowerShell/WMI/CIM、Chrome109 runtime 和第二账户持锁场景已经实测通过。

## 已验证命令

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_win7_launcher_runtime_paths.py tests/regression_runtime_contract_launcher.py tests/regression_runtime_probe_resolution.py tests/regression_runtime_lock_reloader_parent_skip.py tests/regression_runtime_stop_cli.py tests/test_launcher_observability.py tests/regression_transaction_savepoint_nested.py`
  - 结果：`77 passed`。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_architecture_fitness.py::test_no_silent_exception_swallow tests/test_architecture_fitness.py::test_startup_silent_fallback_samples tests/regression_quality_gate_scan_contract.py tests/test_sync_debt_ledger.py tests/test_check_full_test_debt.py tests/test_full_test_debt_registry_contract.py`
  - 结果：`138 passed`。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_launcher_observability.py tests/test_win7_launcher_runtime_paths.py tests/regression_runtime_contract_launcher.py tests/regression_runtime_probe_resolution.py tests/regression_runtime_lock_reloader_parent_skip.py tests/regression_runtime_stop_cli.py tests/test_sync_debt_ledger.py tests/regression_quality_gate_scan_contract.py`
  - 结果：`142 passed`。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_architecture_fitness.py::test_cyclomatic_complexity_threshold tests/test_architecture_fitness.py::test_file_size_limit tests/test_architecture_fitness.py::test_no_silent_exception_swallow tests/test_sync_debt_ledger.py::test_refresh_auto_fields_rejects_silent_entry_when_except_ordinal_drifted --tb=short -ra`
  - 结果：`4 passed`。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_architecture_fitness.py::test_file_size_limit tests/test_architecture_fitness.py::test_startup_silent_fallback_samples tests/test_architecture_fitness.py::test_no_silent_exception_swallow`
  - 结果：`3 passed`。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check web/bootstrap tools tests`
  - 结果：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check core data web tests scripts tools`
  - 结果：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright -p pyrightconfig.gate.json`
  - 结果：`0 errors`，仍有 6 个既有 warning，位置在 `core/services/scheduler/__init__.py`，不属于本轮启动链改动。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/check_full_test_debt.py`
  - 结果：通过，`active_xfail_count=0`，`collected_count=899`，旧 5 条测试债仍为 fixed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/sync_debt_ledger.py check`
  - 结果：通过，`silent_fallback_count=135`，`accepted_risk_count=4`。

## 对抗审查结果

- 运行锁和 contract 失败闭合复审：无 blocker。
- launcher 日志可见性初审发现 4 个 blocker；已修复后重新复审，无 blocker。
- 台账 realign 初审发现 1 个 blocker；已修复后重新复审，无 blocker。
- wrapper / monkeypatch / Python 3.8 兼容复审：无 blocker。
- 运行锁结果化、Chrome 收尾顺序和事务失败闭合的最终复审：无 blocker。
- 本轮 P1 二次收口后的 4 个全新 subagent 复审：
  - 坏 contract 不再被 `stale cleanup` 删除：无 blocker。
  - `RuntimeCleanupResult` 与停止链清理失败返回：无 blocker。
  - Chrome 清理失败后的 retry 证据保留：无 blocker。
  - Python 3.8、`safe_log(None)`、scanner 与台账对齐：无 blocker。
- 本次剩余增强：
  - bba3604 review 中 lock / contract / Chrome / cleanup 阻断项已经由后续提交修复。
  - endpoint 文件读取失败本次补为结果对象，避免 host/port 文件异常被误当作可清理旧残留。
  - 这仍不代表 Win7 现场风险关闭，4 条 Win7 accepted risk 继续保留。

## 全量验证

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests -q -p no:cacheprovider`
  - 结果：`899 passed`。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --require-clean-worktree`
  - 结果：干净工作区通过，输出 `质量门禁通过`。
