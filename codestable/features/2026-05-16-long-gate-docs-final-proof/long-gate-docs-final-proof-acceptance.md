---
doc_type: feature-acceptance
feature: 2026-05-16-long-gate-docs-final-proof
roadmap: quality-gate-long-cache
roadmap_item: long-gate-docs-final-proof
status: accepted
accepted_at: 2026-05-16
---

# long-gate-docs-final-proof 验收记录

## 1. 完成范围

- 已新增 NEXT-13 feature 方案和 checklist。
- `quality-gate-long-cache-items.yaml` 已把 `long-gate-docs-final-proof` 从 `planned` 推到 `in-progress`，并在验收阶段回写为 `done`。
- `README.md`、`开发文档/README.md` 和 roadmap 已统一当前 long gate entry 状态。
- 当前 enabled long gate entry 是：
  - `pytest_collect_all`
  - `full_test_debt`
  - `ruff_check_full`
  - `pyright_gate_full`
  - `pyright_tools_full`
  - `required_regressions`
  - `debt_ledger_sync`
  - `startup_runtime_regressions`
  - `quickref_vs_routes`
- 当前仍 planned 的 long gate entry 只有 `architecture_fitness`。
- `quickref_vs_routes` 已从 roadmap 的当前 planned 列表中移出；历史段落只保留“当时尚未启用、后续 NEXT-12 已启用”的语境。
- final proof 命令已统一为 `scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache`，或等价入口 `tools/git_hook_checks.py run-final-quality-gate`。

## 2. 明确未做

- 没有启用 `architecture_fitness` success cache。
- 没有新增 long gate entry。
- 没有修改 long gate cache 核心实现、fingerprint、success cache 写入逻辑、hook 或 CI 命令。
- 没有修改 APS 排产、导入、保存等业务逻辑。
- 没有升级依赖。
- 没有引入外部前端资源。
- 没有新增 `shell=True`。
- 没有提交 `evidence/QualityGate/**` 运行产物。
- 没有提交 `evidence/Conformance/quickref_vs_routes.md` 的本次生成差异。

## 3. Proof 口径核对

- `--long-gate-cache-explain` 只打印决策，不执行门禁，不是 proof。
- cache hit 只说明旧成功结果在 command、fingerprint、日志、输出文件、schema 和 repo identity 等证据重新校验后可信，不是跳过安全检查。
- summary counts 只说明本轮 executed / reused / failed / planned_only / disabled 的数量，不是 final proof。
- daily gate、pre-push fast gate、fast-precheck、单独 pytest、单独 ruff、单独 pyright、单独 `tools/check_full_test_debt.py` 都不是 final proof。
- final clean proof 必须在干净工作区运行完整门禁，并在结束后确认 `git status --short` 为空。

## 4. 局部验证

这些验证用于证明文档、状态和相关测试链没有明显问题，但它们不是 final clean proof。

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python codestable/tools/validate-yaml.py --file codestable/roadmap/quality-gate-long-cache/quality-gate-long-cache-items.yaml`：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python codestable/tools/validate-yaml.py --file codestable/features/2026-05-16-long-gate-docs-final-proof/long-gate-docs-final-proof-checklist.yaml`：通过。
- `git diff --check`：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_long_gate_manifest.py tests/test_long_gate_quickref_cache.py tests/test_git_hook_checks.py tests/test_run_quality_gate.py`：通过，140 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_long_gate_full_test_debt_cache.py tests/test_long_gate_startup_regression_cache.py tests/test_long_gate_required_regression_cache.py tests/test_architecture_scan_cache.py tests/test_fast_static_precheck.py tests/test_long_gate_manifest.py tests/test_long_gate_cache.py tests/test_run_quality_gate.py tests/test_git_hook_checks.py tests/test_long_gate_debt_ledger_cache.py tests/test_long_gate_quickref_cache.py tests/test_long_gate_summary_output.py`：通过，603 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_long_gate_cache.py tests/test_long_gate_manifest.py tests/test_run_quality_gate.py tests/test_architecture_fitness.py`：通过，278 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check`：通过，All checks passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright -p pyrightconfig.gate.json`：通过，0 errors, 6 warnings。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright -p pyrightconfig.tools.json`：通过，0 errors, 0 warnings。

## 5. 运行产物检查

- `evidence/QualityGate/` 下有本机 ignored 运行产物残留，它们不是本次未提交 diff。
- `evidence/Conformance/quickref_vs_routes.md` 是历史已跟踪文件；本次 diff 没有新增或修改它。
- README、开发文档和 NEXT-13 design 已明确：hook 只拦已登记路径，不会自动通配保护整个 `evidence/QualityGate/`；新产生的 QualityGate 运行产物仍不能进入提交。
- 提交前必须重新运行 `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/git_hook_checks.py check-staged-artifacts`，确认暂存区没有已登记运行产物。

## 6. 兼容性核对

- README 和开发文档面向 Windows 开发者继续使用 `.venv\Scripts\python`。
- roadmap 和 CodeStable 验证命令使用 `.venv/bin/python`，这是当前开发机验证命令，不代表 Win7 目标机要安装 Python。
- 没有要求 Win7 目标机安装 Python、Node、npm 或 npx。
- 没有引入 Python 3.9+ 语法。
- 没有新增依赖。
- 没有新增外部 JS / CSS / CDN 资源。
- 没有新增 `shell=True`。

## 7. Roadmap 回写

- `quality-gate-long-cache-items.yaml` 中 `long-gate-docs-final-proof` 已回写为 `done`。
- roadmap 主文档已同步 `long-gate-docs-final-proof` 为 `done`。
- 这条 long gate cache 路线本阶段收口为 `completed`；如果后续要启用 `architecture_fitness` success cache，应另起新的 feature / roadmap，不混进 NEXT-13。

## 8. Final clean proof

本 acceptance 只记录文档、状态和 proof 口径已经收口，不把提交后才运行的 final gate 写成历史事实。最终 clean proof 必须在本 acceptance 所属提交落地后运行：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache
```

验收条件：

- final gate 命令完整通过。
- 命令结束后 `git status --short` 为空。
- 没有运行产物进入提交边界。

本轮最终交付说明必须记录实际命令结果和 `git status --short` 输出；如果最终命令失败或工作区不干净，不能宣称 NEXT-13 final clean proof 已完成，并且应回退本 acceptance、items 和 roadmap 的完成状态。

## 9. 后续建议

- 如果要启用 `architecture_fitness` success cache，必须另起新 feature。
- 如果要改变 CI 的 long gate cache 口径，必须另起新 feature。
- 如果后续新增 `evidence/QualityGate/` 运行产物路径，要同步 `.gitignore`、hook block 规则和文档说明。
