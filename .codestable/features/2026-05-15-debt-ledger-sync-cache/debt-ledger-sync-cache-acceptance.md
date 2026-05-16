---
doc_type: feature-acceptance
feature: 2026-05-15-debt-ledger-sync-cache
roadmap: quality-gate-long-cache
roadmap_item: debt-ledger-sync-cache
status: accepted
accepted_at: 2026-05-15
---

# debt-ledger-sync-cache 验收记录

## 1. 完成范围

- 已启用 `debt_ledger_sync` long gate success cache。
- `debt_ledger_sync` 继续来自真实 `build_quality_gate_command_plan()`，命令身份仍是 `python scripts/sync_debt_ledger.py check`。
- 已为 `debt_ledger_sync` 声明 `output_result_files`：`evidence/QualityGate/debt_ledger_sync.json`。
- runner 在 `debt_ledger_sync` 命令成功后写 proof JSON；完整 clean gate 成功收尾后，才允许写 long gate success cache。
- proof JSON 记录命令身份、fingerprint、stdout/stderr long-gate 日志 hash、台账 counts、台账 schema、architecture scan metadata 和 `does_not_claim: clean_worktree_proof`。
- `.gitignore`、`tools/git_hook_checks.py` 和 clean-worktree generated path 排除清单已保护 `evidence/QualityGate/debt_ledger_sync.json`，运行产物不能混入提交。
- fingerprint 覆盖台账、roadmap/feature 文档、sync 脚本、ledger/operations/scan/architecture helper、源码、配置、依赖、Python/env、architecture scan metadata 和声明输出 path。
- `architecture_scan_cache.json` 本身仍是 helper 运行产物，不作为 `debt_ledger_sync` 的输入指纹，避免生成时间造成 fingerprint 抖动。
- `tests/test_long_gate_debt_ledger_cache.py` 已加入正式 quality gate guard 测试清单和 required regression 分组。

## 2. 明确未做

- 没有启用 `architecture_fitness` success cache。
- 没有启用 `quickref_vs_routes` success cache。
- 没有改变 daily gate 或 pre-push 默认语义。
- 没有改变 `scripts/sync_debt_ledger.py check` 的业务语义；它仍只校验台账，不刷新台账，不直接写 proof。
- 没有把 `--long-gate-cache-explain` 当 proof。
- 没有把 cache hit 或 `debt_ledger_sync.json` 当 clean-worktree final proof。
- 没有提交 `evidence/QualityGate/**` 运行产物。
- 没有完成 clean-worktree final quality gate。

## 3. 对抗审查

- 阶段 1 scaffold：文档 / proof 口径审查先发现 roadmap 和 items 里有 NEXT-10 旧口径残留，已修复并复审通过。
- 阶段 2 artifact hygiene：proof/output artifact 审查和 Python 3.8 / Win7 审查无 blocker。
- 阶段 3 manifest / fingerprint：fingerprint false reuse 审查和 manifest/enabled 边界审查无 blocker，确认没有把 generated `architecture_scan_cache.json` 当输入。
- 阶段 4 proof writer：debt ledger 命令语义审查先发现 runner 只会给 enabled entry 写 proof，planned 阶段的 `debt_ledger_sync` proof writer 没真正挂上主流程；已修复为 planned 阶段可写 proof 但不写 success cache，并复审通过。
- 阶段 5 enable：manifest/enabled、fingerprint false reuse、测试覆盖三类复审均无 blocker。
- 阶段 5 non-blocker 收口：改掉旧测试名、补完整 NEXT-11 primary_paths，并新增 explain/dirty 的 debt 专项测试；复审无 blocker，允许进入阶段 6。
- 阶段 6 acceptance / roadmap：收口后会继续做只读对抗审查；如果发现 blocker，先修复并复审通过后才交付。

## 4. 验收核对

- `debt_ledger_sync` 当前是 enabled，`architecture_fitness` 和 `quickref_vs_routes` 仍是 planned。
- `--long-gate-force-rerun-all` 只强制 enabled entry 重跑，不会把 planned entry 变 enabled。
- 台账文件、roadmap/feature 文档、sync 脚本、quality gate ledger/operations/scan/architecture helper、扫描源码、配置、依赖、Python/env、architecture scan metadata、声明输出 path 变化都会让 `debt_ledger_sync` fingerprint 变化。
- `evidence/QualityGate/architecture_scan_cache.json` 的存在或内容变化不会让 `debt_ledger_sync` fingerprint 抖动。
- `evidence/QualityGate/debt_ledger_sync.json` 缺失或被改，缓存不能继续复用，必须重新执行。
- stdout/stderr long-gate 日志缺失或被改，缓存不能继续复用，必须重新执行。
- `--long-gate-cache-explain` 只准备并打印缓存决策，不写 `debt_ledger_sync.json`。
- dirty / 不允许写 success cache 的路径不会写 `debt_ledger_sync.json`，也不会写 `debt_ledger_sync.success.json`。
- direct `python scripts/sync_debt_ledger.py check` 不直接写 long gate proof，proof 写入只属于 runner 的 long gate 成功路径。

## 5. 验证结果

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_long_gate_debt_ledger_cache.py`：通过，11 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_long_gate_debt_ledger_cache.py tests/test_long_gate_manifest.py tests/test_long_gate_cache.py tests/test_run_quality_gate.py tests/test_git_hook_checks.py tests/test_long_gate_required_regression_cache.py tests/test_sync_debt_ledger.py tests/test_architecture_scan_cache.py`：通过，457 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/sync_debt_ledger.py check`：通过，stdout 显示 `治理台账校验通过`，schema_version 为 2。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/long_gate_manifest.py --print`：通过，显示 `debt_ledger_sync` 为 `CACHE-ENABLED`，`architecture_fitness` 和 `quickref_vs_routes` 仍为 `LONG-CANDIDATE`。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --long-gate-cache-explain`：失败，原因是本机 Chrome headless preflight 在 DevTools 端口写出前退出，错误为 `chrome_exited_before_devtools`。该命令只是缓存决策预览，本次没有把它当 proof。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check`：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright -p pyrightconfig.gate.json`：通过，0 errors，6 warnings；warnings 为既有 `core/services/scheduler/__init__.py` 的 `__all__` 提示。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright -p pyrightconfig.tools.json`：通过，0 errors，0 warnings。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_daily_quality_gate.py`：通过；这是日常快门禁，不是 clean-worktree final proof。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --file .codestable/roadmap/quality-gate-long-cache/quality-gate-long-cache-items.yaml`：通过。
- `git diff --check`：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/git_hook_checks.py check-staged-artifacts`：通过。

## 6. Proof 口径

- `evidence/QualityGate/debt_ledger_sync.json` 只证明 `debt_ledger_sync` 单条 entry 的输出和日志完整，不证明整个仓库 clean-worktree final gate 通过。
- cache hit 只代表旧 successful result 的 command、fingerprint、proof、log、repo identity、schema 等重新校验后可信，不代表跳过安全检查。
- `--long-gate-cache-explain` 只展示缓存决策，不执行命令，不写 proof，不是 quality gate proof。
- 未运行 `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache`。
- 未完成 clean-worktree full proof，不能宣称本次变更已通过完整 final quality gate。

## 7. Roadmap 回写

- `.codestable/roadmap/quality-gate-long-cache/quality-gate-long-cache-items.yaml` 中 `debt-ledger-sync-cache` 已从 `in-progress` 改为 `done`。
- roadmap 主文档已同步 NEXT-11 完成状态、当前 enabled entry 列表、artifact hygiene、proof 口径和后续 planned 列表。
- 后续 roadmap planned item 仍包括 `quickref-vs-routes-cache` 和 `long-gate-docs-final-proof`；manifest planned entry 仍包括 `architecture_fitness` 和 `quickref_vs_routes`。

## 8. AGENTS.md 候选

- 本 feature 未暴露必须补入 AGENTS.md 的新长期规则。
- 可作为后续维护注意项：新增 long gate success cache entry 时，必须同时补 output proof、artifact hygiene、fingerprint scope、proof 缺失/篡改测试、explain/dirty 口径测试，并明确 proof JSON 不是 clean-worktree final proof。

## 9. 遗留

- 没有 clean-worktree final proof；提交或合并前仍需要在干净工作区运行完整 final quality gate。
- 当前本机 `--long-gate-cache-explain` 被 Chrome headless preflight 阻塞；这会影响依赖 strict browser fingerprint 的 explain/final cache gate，需要单独处理本机 Chrome 环境。
- `quickref_vs_routes` 仍 planned，按 roadmap 应作为 NEXT-12 处理。
- `architecture_fitness` 仍 planned，不应顺手启用。
