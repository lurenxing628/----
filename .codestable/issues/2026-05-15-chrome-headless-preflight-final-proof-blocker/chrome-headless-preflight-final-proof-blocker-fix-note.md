---
doc_type: issue-fix
issue: chrome-headless-preflight-final-proof-blocker
status: fixed
severity: P1
root_cause_type: config
tags:
  - quality-gate
  - long-gate-cache
  - chrome
  - final-proof
---

# Chrome headless preflight final proof blocker 修复记录

## 1. 修复目标

这次修的是 NEXT-11 完成后遗留的 final proof blocker：`full_test_debt` 的 strict runtime fingerprint 可能被 `chrome_headless_preflight` 卡住。修复目标不是回滚 NEXT-11，也不是提前做 NEXT-12，而是让 Chrome 失败时能看懂、让 runner 安全地禁用该 entry 的缓存读写，并继续执行真实命令。

## 2. 改动范围

- `tools/long_gate_fingerprint.py`
  - `LongGateFingerprintError` 增加 `details`，让调用方能读取结构化失败原因。
  - Chrome preflight 失败 payload 增加 Chrome 路径、来源、realpath、版本 probe、启动参数摘要、profile 可写性、`DevToolsActivePort` 状态、stdout/stderr tail、平台和环境摘要。
  - 成功 preflight 的 hash 纳入 preflight schema、headless mode、remote debugging mode 和稳定 launch flags；临时 profile、pid、随机端口和 stderr 原文不进入成功 fingerprint。

- `scripts/run_quality_gate.py`
  - `_prepare_long_gate_cache_decisions()` 捕获 strict fingerprint error，把该 entry 标成 `cache_unavailable`。
  - fingerprint error 时不调用 `evaluate_reuse()`，所以不会读旧 success cache。
  - final gate 遇到 cache unavailable 时执行真实 command，但跳过 output proof writer 和新 success cache 写入。
  - `full_test_debt` 遇到 cache unavailable 时不刷新复用决策，也不走 nodeid / ledger-only 特殊增量。
  - explain 输出会显示 `runtime_key`、`failure_kind` 和关键 Chrome 诊断字段，但仍明确 explain 不是 proof。

- `tools/long_gate_cache.py`
  - `write_success()` 增加底层硬保护：空 fingerprint、空 hash、非 `sha256:` hash、缺 `schema_version`、缺 `components` 都直接拒绝落盘。

- `tools/long_gate_summary.py`
  - summary entry 增加 `cache_unavailable` 和 `fingerprint_error` 字段，方便后续看 JSON 时知道这次为什么没有复用 / 写入 cache。

- `tests/`
  - 新增 `tests/test_long_gate_chrome_preflight_diagnostics.py`，用 fake Chrome 覆盖失败诊断和成功 hash 稳定性，不依赖本机真实 Chrome。
  - 扩展 runner 测试，锁住 explain/final 的 cache unavailable 行为。
  - 扩展 cache 测试，锁住 `write_success()` 不接受空 fingerprint。
  - 同步 `full_test_debt` helper impact 合同，把 `tests/test_long_gate_debt_ledger_cache.py` 纳入 `tests/long_gate_cache_helpers.py` 的声明影响面。

## 3. 保持不变

- `debt_ledger_sync` 仍是 enabled。
- `architecture_fitness` 仍是 planned。
- `quickref_vs_routes` 仍是 planned。
- daily gate / pre-push 默认语义不变。
- 没有跳过 Chrome preflight。
- 没有把失败 preflight 返回成普通 hash。
- 没有把 explain、cache hit、daily gate 或 `debt_ledger_sync.json` 当 clean-worktree final proof。

## 4. 对抗审查结果

- CodeStable 状态锚定：NEXT-11 已 accepted，缺 final clean proof；无 blocker。
- Manifest / enabled 边界：enabled/planned 列表正确；无 blocker。
- Chrome strict fingerprint：指出失败诊断不足；已补结构化诊断并用 fake Chrome 测试锁住。
- Runner / explain / final gate：指出 `write_success()` 缺底层 fingerprint 校验；已补。
- Browser smoke / Chrome 参数：建议只统一诊断，不把 headless/DevTools 参数带进用户 launcher；本次没有改 launcher。
- Hook / daily / CI：确认 daily/final/CI 边界清楚；本次没有降低门禁。
- Artifact / proof hygiene：提醒新增运行产物要保护；本次没有新增 diagnostic artifact 文件路径。
- False reuse 对抗：重点锁住 fingerprint error 不进入 reuse、不走 force 绕过、不写不完整 success cache；已用测试覆盖。
- 测试覆盖：新增测试都用 monkeypatch / fake process，不依赖真实 Chrome。
- 本地诊断命令：确认 explain、smoke、hook artifact 等都不是 final proof；最终 proof 仍只能是 clean-worktree final gate。

## 5. 验证记录

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_long_gate_chrome_preflight_diagnostics.py tests/test_long_gate_cache.py::test_write_success_rejects_missing_or_invalid_fingerprint tests/test_run_quality_gate.py::test_long_gate_cache_explain_marks_fingerprint_error_cache_unavailable tests/test_run_quality_gate.py::test_final_gate_fingerprint_error_runs_command_without_success_cache`
  - 结果：`9 passed`。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_long_gate_full_test_debt_cache.py`
  - 结果：`145 passed`。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_long_gate_chrome_preflight_diagnostics.py tests/test_run_quality_gate.py tests/test_long_gate_summary_output.py tests/test_long_gate_cache.py tests/test_long_gate_full_test_debt_cache.py tests/test_long_gate_debt_ledger_cache.py tests/test_long_gate_manifest.py tests/test_git_hook_checks.py tests/test_ui_browser_geometry_env.py`
  - 结果：`454 passed`。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_long_gate_startup_regression_cache.py tests/test_long_gate_required_regression_cache.py tests/test_long_gate_chrome_preflight_diagnostics.py tests/test_long_gate_debt_ledger_cache.py tests/test_long_gate_manifest.py tests/test_long_gate_cli_controls.py tests/test_long_gate_cache.py tests/test_long_gate_full_test_debt_cache.py tests/test_long_gate_collect_cache.py tests/test_long_gate_fingerprint.py tests/test_long_gate_summary_output.py`
  - 结果：`493 passed`。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check ...`
  - 结果：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright -p pyrightconfig.tools.json`
  - 结果：`0 errors, 0 warnings`。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright -p pyrightconfig.gate.json`
  - 结果：`0 errors, 6 warnings`；warnings 是既有 `core/services/scheduler/__init__.py` 的 `__all__` 提示。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/sync_debt_ledger.py check`
  - 结果：通过，stdout 显示 `治理台账校验通过`。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/git_hook_checks.py check-staged-artifacts`
  - 结果：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --long-gate-cache-explain`
  - 结果：通过；这只是 explain，不是 proof。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --file .codestable/issues/2026-05-15-chrome-headless-preflight-final-proof-blocker/chrome-headless-preflight-final-proof-blocker-checklist.yaml`
  - 结果：通过。
- `git diff --check`
  - 结果：通过。

## 6. Clean proof 状态

没有 clean-worktree final proof。

原因是本轮修复还没有提交，当前工作区存在源代码、测试和 CodeStable 文档改动。`scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache` 必须在干净工作区里跑，当前这些验证不能冒充最终 proof。

## 7. 后续建议

- 本轮改动确认后，先提交本地改动。
- 提交后在干净工作区运行：
  `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache`
- 如果 clean proof 通过，再回到 roadmap 继续 NEXT-12 `quickref_vs_routes` cache。
- 如果 Chrome 仍失败，先看新的 `runtime_key`、`failure_kind`、`stderr_tail`、Chrome path/source、profile/DevTools 字段，不要推进 NEXT-12。
