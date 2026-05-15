---
doc_type: feature-acceptance
feature: 2026-05-16-quickref-vs-routes-cache
roadmap: quality-gate-long-cache
roadmap_item: quickref-vs-routes-cache
status: accepted
accepted_at: 2026-05-16
---

# quickref-vs-routes-cache 验收记录

## 1. 完成范围

- 已启用 `quickref_vs_routes` long gate success cache。
- `quickref_vs_routes` 继续来自真实 `build_quality_gate_command_plan()`，命令仍是 `python tests/check_quickref_vs_routes.py`。
- 已为 `quickref_vs_routes` 声明 `output_result_files`：`evidence/Conformance/quickref_vs_routes.md`。
- fingerprint 覆盖系统速查表、app/bootstrap/routes/web 代码、模板、静态资源、配置、依赖、Python/env 和声明输出 path。
- `evidence/Conformance/quickref_vs_routes.md` 缺失或 hash 不一致时不能复用旧成功。
- quickref stdout 已改为仓库相对路径，并在扫描 app 路由期间静音 app 启动日志，避免本机路径、临时目录和时间戳进入稳定输出。
- `.gitignore`、`tools/git_hook_checks.py` 和 clean-worktree generated path 说明已保护 quickref report，运行产物不能混入提交。
- `tests/test_long_gate_quickref_cache.py` 已加入正式 quality gate guard 测试清单和 required regression 分组。

## 2. 明确未做

- 没有启用 `architecture_fitness` success cache。
- 没有回滚 `debt_ledger_sync` success cache。
- 没有改变 daily gate 或 pre-push 默认语义。
- 没有降低 CI / final gate 要求。
- 没有改变 APS 排产、导入、保存等业务逻辑。
- 没有把 `--long-gate-cache-explain` 当 proof。
- 没有把 cache hit 或 `evidence/Conformance/quickref_vs_routes.md` 当 clean-worktree final proof。
- 没有提交 `evidence/Conformance/quickref_vs_routes.md` 的本次生成内容。
- 没有完成 clean-worktree final quality gate。

## 3. 对抗审查

- CodeStable 状态锚定 subagent：无启动 blocker；确认 branch / HEAD 匹配，NEXT-12 依赖已满足，但 feature 文档需要新建。
- quickref 合同 subagent：发现 stdout 打印本机绝对路径；已改为仓库相对路径，并补测试。
- manifest / fingerprint subagent：发现 quickref 只有 output scope、没有专属输入边界；已补系统速查表、路由、app/bootstrap、模板、静态资源、配置、依赖、环境和输出 path 防线。
- runner / hook / artifact subagent：确认 explain、fingerprint error、success cache 写入主链路已有保护；指出 quickref report 身份必须明确，本阶段按运行产物处理并补 artifact hygiene。

## 4. 验收核对

- `quickref_vs_routes` 当前是 enabled。
- `architecture_fitness` 仍是 planned。
- `debt_ledger_sync` 仍是 enabled。
- `quickref_vs_routes` 命令身份仍是 `python tests/check_quickref_vs_routes.py`。
- 系统速查表、路由、app/bootstrap、模板、静态资源、配置、依赖、环境和输出 path 变化都会导致 quickref fingerprint 变化。
- quickref report 缺失或 hash mismatch 会导致重跑。
- quickref stdout 不再输出本机绝对路径。
- app 启动 INFO 日志不再污染 quickref 成功 stdout/stderr。
- `.gitignore`、hook 和 clean generated path 说明已保护 quickref report。
- daily gate / pre-push / CI final 命令语义不变。

## 5. 验证结果

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_check_quickref_vs_routes.py tests/test_long_gate_quickref_cache.py`：通过，21 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/check_quickref_vs_routes.py`：通过，stdout 为 `evidence/Conformance/quickref_vs_routes.md` 和 `OK`。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_long_gate_manifest.py tests/test_long_gate_cache.py tests/test_run_quality_gate.py tests/test_long_gate_summary_output.py tests/test_git_hook_checks.py tests/test_long_gate_quickref_cache.py tests/test_check_quickref_vs_routes.py`：通过，309 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python codestable/tools/validate-yaml.py --file codestable/features/2026-05-16-quickref-vs-routes-cache/quickref-vs-routes-cache-checklist.yaml`：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python codestable/tools/validate-yaml.py --file codestable/roadmap/quality-gate-long-cache/quality-gate-long-cache-items.yaml`：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m tools.long_gate_manifest --print`：通过，显示 `quickref_vs_routes` 为 `CACHE-ENABLED`，`architecture_fitness` 为 `LONG-CANDIDATE`。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --long-gate-cache-explain`：通过，显示 `quickref_vs_routes` 为 enabled / RUN，`architecture_fitness` 为 planned_only。说明：explain 不是 proof。

## 6. Proof 口径

- `evidence/Conformance/quickref_vs_routes.md` 只证明 quickref 对账报告内容，不证明整个仓库 clean-worktree final gate 通过。
- cache hit 只代表旧 successful result 的 command、fingerprint、report、log、repo identity、schema 等重新校验后可信，不代表跳过安全检查。
- `--long-gate-cache-explain` 只展示缓存决策，不执行命令，不写 proof，不是 quality gate proof。
- 未运行 `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache`。
- 未完成 clean-worktree final proof，不能宣称本次变更已通过完整 final quality gate。

## 7. Roadmap 回写

- `codestable/roadmap/quality-gate-long-cache/quality-gate-long-cache-items.yaml` 中 `quickref-vs-routes-cache` 已从 `in-progress` 改为 `done`。
- roadmap 主文档已同步 NEXT-12 完成状态、当前 enabled entry 列表、artifact hygiene、proof 口径和后续 planned 列表。
- 后续 roadmap planned item 仍包括 `long-gate-docs-final-proof`；manifest planned entry 仍包括 `architecture_fitness`。
