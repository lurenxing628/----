---
doc_type: issue-fix
issue: 2026-05-16-quality-gate-cache-review-hardening
path: fast-track
fix_date: 2026-05-16
tags: [quality-gate, cache, proof, ci, hooks]
---

# 质量门禁缓存 review 加固修复记录

## 1. 问题描述

上一轮深度 review 发现，这条“测试清理 / 质量门禁提速 / long gate 缓存 / hook 提速”链路还有几类需要补强的地方：

- 有些缓存 key 还不够保守，存在“该重跑却命中旧结果”的风险。
- 有些 proof 缺文件、空输出、子证明丢失时没有明确失败。
- CI cache、quickref 产物路径和文档口径还没有完全收齐。
- 被删测试后有几处业务合同需要补回到仍然被 required gate 跑到的测试里。
- 一些边界场景缺测试，比如 Windows 路径、坏缓存、版本变化、collector 失败、benchmark CLI 参数等。

## 2. 根因

这次提速改动覆盖面很宽，缓存和 proof 分散在 hook、daily gate、long gate、CI workflow、静态检查和文档里。单点看多数逻辑能跑，但一些“坏情况”没有被测试锁住：

- pre-push daily gate 的通过缓存只看 HEAD/tree/remote/ref 等输入，但工作区脏改动没有被统一挡住。
- required regressions 复用 full_test_debt 证明时，对 verifier proof 和 child proof 的缺失检查不够硬。
- quickref 路由对账的 tracked 报告和运行时缓存报告容易混在同一路径。
- CI cache save 条件对 PR 过宽，不符合“PR 只 restore、不 save”的口径。
- 一些被删除的旧测试虽然低价值，但其中少量合同风险还需要迁到现有 required 测试里。

## 3. 修复方案

- 收紧 hook / pre-push / final gate 缓存：把工具版本、dirty worktree、remote/ref、staged tree、配置文件和工具文件变化都纳入该保守处理的范围。
- 收紧 long gate proof：缺 verifier proof、缺 child proof、空 stdout、旧输出残留、schema 或文件不一致时，不再静默当成成功。
- 把 quickref 运行时报告迁到 `evidence/QualityGate/quickref_vs_routes.md`，保留 `evidence/Conformance/quickref_vs_routes.md` 作为历史 tracked 证据，避免两类证据互相覆盖。
- CI 只允许 `push` 和手动 `workflow_dispatch` 保存 cache，所有 PR 只恢复 cache。
- 把删测试后仍有价值的合同补进现有 required 测试文件，避免新增未跟踪 required 测试导致门禁清单不稳定。
- 补足针对性测试，覆盖坏缓存、版本变化、Windows 路径、空输出、collector 失败、benchmark argv、workflow 结构和 quickref 路径。
- 同步 README、开发文档、feature 文档和 long gate roadmap，让说明和真实代码一致。

## 4. 改动文件清单

- Hook / cache：`tools/git_hook_checks.py`、`tools/git_hook_cache.py`、`tests/test_git_hook_checks.py`
- Long gate / proof：`scripts/run_quality_gate.py`、`tools/long_gate_cache.py`、`tools/long_gate_manifest.py`、`tools/quality_gate_shared.py`、`tools/quality_gate_support.py`
- Full test debt / benchmark：`tools/benchmark_full_test_debt_shards.py`、`pyrightconfig.tools.json`、`tests/test_benchmark_full_test_debt_shards.py`、`tests/test_check_full_test_debt.py`
- Quickref / static cache：`tests/check_quickref_vs_routes.py`、`.gitignore`、`.github/workflows/quality.yml`、相关 quickref/manifest/workflow 测试
- 被删测试风险补位：`tests/regression_schedule_service_facade_delegation.py`、`tests/regression_scheduler_resource_dispatch_invalid_query_cleanup.py`、`tools/test_registry.py`
- 文档同步：`README.md`、`开发文档/README.md`、`codestable/features/`、`codestable/roadmap/quality-gate-long-cache/`

## 5. 验证结果

已通过：

- `git diff --check`
- 修改文件的 `ruff check`
- `pytest -q tests/test_git_hook_checks.py`：27 passed
- `pytest -q tests/regression_schedule_service_facade_delegation.py tests/regression_scheduler_resource_dispatch_invalid_query_cleanup.py tests/test_full_test_debt_registry_contract.py`：54 passed
- `pytest -q tests/test_long_gate_required_regression_cache.py tests/test_long_gate_startup_regression_cache.py tests/test_run_quality_gate.py tests/test_check_full_test_debt.py tests/test_long_gate_manifest.py tests/test_long_gate_quickref_cache.py tests/test_check_quickref_vs_routes.py`：304 passed
- `pytest -q tests/test_run_daily_quality_gate.py tests/test_long_gate_full_test_debt_cache.py tests/test_long_gate_debt_ledger_cache.py tests/test_long_gate_cli_controls.py tests/test_full_test_debt_registry_contract.py tests/test_verify_required_regressions_from_full_test_debt.py tests/test_quality_workflow_cache.py tests/test_git_hook_checks.py tests/test_benchmark_full_test_debt_shards.py tests/regression_schedule_service_facade_delegation.py tests/regression_scheduler_resource_dispatch_invalid_query_cleanup.py`：277 passed
- `python tests/check_quickref_vs_routes.py`：生成 `evidence/QualityGate/quickref_vs_routes.md` 并输出 `OK`
- `python codestable/tools/validate-yaml.py --file codestable/roadmap/quality-gate-long-cache/quality-gate-long-cache-items.yaml`
- `python codestable/tools/validate-yaml.py --file codestable/features/2026-05-16-github-actions-long-gate-cache-persistence/github-actions-long-gate-cache-persistence-checklist.yaml`
- `pyright -p pyrightconfig.tools.json`：0 errors, 0 warnings
- `pyright -p pyrightconfig.gate.json`：0 errors，保留 6 个既有 warning

未声称完成：

- 还没有跑最终 clean proof：`python scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache`。原因是当前修复还没有提交，工作区本来就是脏的，这个命令会被 `--require-clean-worktree` 正确拦住。需要提交后再把 final proof 绑到最终 HEAD。

## 6. 遗留事项

- 本次修复已经覆盖上一轮 review 里“必须立刻修”和“可以后续补”的问题。
- 仍建议在提交后跑一次完整 clean long gate，把最终通过证明绑定到提交后的干净 HEAD。
