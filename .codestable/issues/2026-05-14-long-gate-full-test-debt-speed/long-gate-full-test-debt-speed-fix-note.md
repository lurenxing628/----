---
doc_type: issue-fix
issue: long-gate-full-test-debt-speed
status: fixed
severity: medium
root_cause_type: test-performance
tags:
  - quality-gate
  - full-test-debt
  - long-gate-cache
  - win7
---

# long gate 与 full-test-debt 耗时修复记录

## 1. 问题描述

本地诊断发现，`tools/check_full_test_debt.py` 慢不是因为 JSON 解析慢，也不是测试收集慢，而是它会真正执行完整 full pytest。

同时，完整 pytest 里有两类额外拖慢：

- Win7 runtime stop 相关测试在验证“不能误删运行时文件、不能把未停止误判成成功”时，真的等待了生产代码里的 2 秒到 12 秒窗口。
- long gate cache 相关测试把大量“路径或环境变量变化会不会让缓存失效”的小判断，都跑成了完整 fake gate 流程，反复 import runner、建临时 git repo、种缓存、再跑一次假门禁。

## 2. 根因

- `web.bootstrap.launcher_stop.stop_runtime_from_dir()` 的等待语义是生产行为，默认等待窗口最高 12 秒，最低 2 秒。测试本来只需要证明“等待结束后仍然不能错误清理或错误成功”，却用了真实时间等待。
- `tests/test_long_gate_required_regression_cache.py` 和 `tests/test_long_gate_startup_regression_cache.py` 的路径/环境变量参数化测试，真正要证明的是 `fingerprint_entry()` 会变化，但原来每个参数都完整跑 runner 级流程。
- `--long-gate-cache-explain` 原来只显示 `reason`，当本地只有 `tools/check_full_test_debt.py` 写出的 current/summary proof、但没有 long gate success cache 时，不够直白，容易让维护者误以为“单跑 check 已经预热了 pre-push 缓存”。

## 3. 修复方案

- 只改测试，不改 Win7 runtime stop 生产等待语义。测试侧新增 fake clock，让 `_wait_for_runtime_stop()` 仍按原 deadline 和 sleep 逻辑推进，只是不真的睡 2 秒或 12 秒。
- 给默认 12 秒等待窗口补断言，确认测试没有把生产等待窗口改短。
- 把 required/startup 两组 long gate path/env 参数化从 runner 级 E2E 下沉到 `fingerprint_entry()` 级合同测试；runner 级仍保留写 proof、复用缓存、坏 proof/log 重跑、force rerun、no-cache、explain 等代表场景。
- 增强 `--long-gate-cache-explain`：当 full_test_debt 没有 success cache，但 current/summary proof 已存在时，直接提示“裸跑 `tools/check_full_test_debt.py` 不会创建 long gate success cache”，并给出预热命令。
- 同步 README 和开发文档，说明单跑 check 和 long gate success cache 的边界。

## 4. 改动文件清单

- `tests/test_win7_launcher_runtime_paths.py`
- `tests/test_long_gate_required_regression_cache.py`
- `tests/test_long_gate_startup_regression_cache.py`
- `tests/test_long_gate_full_test_debt_cache.py`
- `scripts/run_quality_gate.py`
- `README.md`
- `开发文档/README.md`
- `.codestable/issues/2026-05-14-long-gate-full-test-debt-speed/long-gate-full-test-debt-speed-fix-note.md`

## 5. 验证结果

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_win7_launcher_runtime_paths.py --tb=short -p no:cacheprovider --durations=30`：`77 passed in 1.21s`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_long_gate_required_regression_cache.py tests/test_long_gate_startup_regression_cache.py tests/test_long_gate_full_test_debt_cache.py --tb=short -p no:cacheprovider --durations=50`：`200 passed in 40.54s`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache-explain`：通过；该命令只打印缓存决策，不执行门禁，不写 proof。
- `PYTHONDONTWRITEBYTECODE=1 PYTHONUTF8=1 PYTHONIOENCODING=utf-8 .venv/bin/python tools/check_full_test_debt.py`：完整 full pytest 已执行完成，collector payload 里 `exitstatus=0`；随后因为当前工作区有本次未提交修改，正式 clean proof 被拒绝，错误为 `worktree_clean_before 必须为 true`。
- 基于上一步已经生成的 current payload 只做 dirty-worktree 诊断校验：`run_check_from_existing_payload(..., require_clean_worktree_proof=False)` 通过，关键结果为 `collected_count=2304`、`unexpected_failure_count=0`、`collection_error_count=0`、`active_xfail_count=0`、`fixed_count=5`、`max_registered_xfail=0`。

## 6. 遗留事项

- `tools/check_full_test_debt.py` 仍然会真正跑完整 full pytest，这是它作为 full-test-debt proof 的核心职责，本次没有也不应该跳过。
- 这次聚焦修掉测试里的真实等待和重复 fake gate 初始化；剩余 0.8 秒级 runner 测试主要是必须保留的端到端代表场景，后续如继续提速，应优先考虑把 bad proof/log 的枚举补成更细的 `evaluate_reuse()` 级单测。
- 当前记录里的 full-test-debt 验证不是 clean-worktree proof，因为验证时工作区包含本次修改。最终 clean proof 仍需要在提交或清空工作区后跑完整 `scripts/run_quality_gate.py --require-clean-worktree`。

## 7. 2026-05-14 继续修复

- 修复 full-test-debt special incremental 的 success cache 误判：`returncode=0` 现在会被当成真正成功，不再因为 `0` 在 Python 里是假值而被误判成非零。
- `--long-gate-cache-explain` 现在会展示 fingerprint 变更组件，以及 full_test_debt special fallback 的前置证据路径、上一份 success returncode、node cache 路径和 nodeid 数量。
- full-test-debt node cache 新增只读诊断字段：`result_returncode`、`collected_nodeid_count`、`collect_nodeids_by_file_count`。旧 node cache 缺这些字段不直接失败，可信校验仍以 success cache `output_files` hash、payload hash、summary hash 和日志 hash 为准。
- 新增 `scripts/run_daily_quality_gate.py` 作为日常快门禁；pre-push 现在走日常快门禁，不再把完整 clean gate 挂到每次 push 上。最终完整门禁入口仍是 `scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache`。
- required/startup 两个 long gate cache 自测文件把坏 proof/log 的 runner 级枚举从 7 类缩成 3 个代表：proof 缺失、proof 损坏、stdout log hash 不匹配。
- startup host/portfile 回归保留 `app.py` 与 `app_new_ui.py` 真实启动，但真实子进程 host case 从 4 个缩到 2 个；完整 host 解析规则改由 `tests/test_startup_host_resolution_contract.py` 的纯函数测试覆盖。
- 真浏览器 geometry smoke 去掉了重复的每宽度 HTTP 预请求，改为每个页面只预请求一次；真实 Chrome/CDP 的 10 个页面 × 2 个宽度检查仍保留。
- scheduler batches 页面测试新增进程内 schema 模板库：第一次按真实 `schema.sql` 建空库，后续每个测试复制空库再插入自己的数据，不共享测试数据、不绕过 schema 契约。
- 继续优化时又收了三处高性价比慢点：真浏览器 geometry smoke 改成每个页面只开一个 Chrome 标签、导航一次后切两个宽度检查；资源派工非法查询清理测试把 7 个只读重定向场景合成一个 client 场景；full-test-debt registry contract 把多次 `git ls-files` 子进程改成一次读取 tracked 文件集合。
- `tools/quality_gate_scan.py` 给 AST 解析加了进程内缓存，缓存键包含源码内容，避免测试 monkeypatch 出来的同名假文件串数据；该改动只小幅降低 architecture 文件总耗时，repository bundle drift 单点仍是后续优化对象。
- 阶段性耗时记录写入 `reports/quality_gate_performance_before_after.md`。本轮测速显示 long gate cache 三个自测文件为 `199 passed in 34.24s`，startup host/portfile 相关测试为 `10 passed in 6.01s`，browser geometry smoke 为 `2 passed in 9.53s`，scheduler resource dispatch 为 `13 passed in 3.66s`，full-test-debt registry contract 为 `37 passed in 5.86s`，scheduler batches 为 `28 passed in 12.05s`。受影响慢测试组合为 `128 passed in 47.69s`，日常快门禁为 `real 2.35s`。
