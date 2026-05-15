---
doc_type: feature-acceptance
feature: 2026-05-15-static-formal-cache
roadmap: quality-gate-long-cache
roadmap_item: static-formal-cache
status: accepted
accepted_at: 2026-05-15
---

# static-formal-cache 验收记录

## 1. 完成范围

- 已启用 `ruff_check_full`：正式命令为 `python -m ruff check`。
- 已启用 `pyright_gate_full`：正式命令为 `python -m pyright -p pyrightconfig.gate.json`。
- 已启用 `pyright_tools_full`：正式命令为 `python -m pyright -p pyrightconfig.tools.json`。
- 已新增 `pyrightconfig.tools.json`，让 tools pyright 明确覆盖 `QUALITY_GATE_TOOL_PATHS`。
- 已在 runner 中增加 tools pyright 覆盖自检：先核对 `pyrightconfig.tools.json` 的 `include` 是否等于 `QUALITY_GATE_TOOL_PATHS`，再用 `--outputjson` 检查 `filesAnalyzed`，防止缓存空覆盖结果。
- 三条 static entry 都声明并写入各自 proof JSON：
  - `evidence/QualityGate/ruff_check_full.json`
  - `evidence/QualityGate/pyright_gate_full.json`
  - `evidence/QualityGate/pyright_tools_full.json`
- 三条 static entry 都绑定了输入文件、配置、依赖、工具版本、Python 环境、声明输出文件、stdout/stderr long-gate 日志和 schema/repo identity。
- 三个 static proof JSON 已被 `.gitignore`、`tools/git_hook_checks.py` 和 clean worktree generated-path 排除清单保护，不能混入普通提交。

## 2. 明确未做

- 没有启用 `architecture_fitness` success cache。
- 没有启用 `debt_ledger_sync` success cache。
- 没有启用 `quickref_vs_routes` success cache。
- 没有把 NEXT-9 fast precheck 当成正式 static cache。
- 没有改变 daily gate 或 pre-push 默认语义。
- 没有提交 `evidence/QualityGate/**` 运行产物。
- 没有运行完整 clean-worktree final quality gate。

## 3. 对抗审查

- Stage 1 审查确认 CodeStable feature scaffold 和 roadmap in-progress 状态无阻塞。
- Stage 2 审查确认 static proof JSON、artifact hygiene 和未启用边界无阻塞。
- Stage 3 审查先发现 ruff scope 漏 `desktop/**/*.py`，已修复并复审通过。
- Stage 4 审查确认 `pyright_gate_full` 启用边界、指纹范围、proof 口径和 Python 3.8 / Win7 兼容无阻塞。
- Stage 5 审查确认 `pyright_tools_full` 启用边界无阻塞；`architecture_fitness`、`debt_ledger_sync`、`quickref_vs_routes` 仍 planned。
- Stage 5 审查确认 `pyright_tools_full` 当前 false reuse 风险无阻塞；import closure 当前 AST 对账无漏项，但后续新增本地 import 时需要同步 scope 和测试。
- Stage 5 审查确认 static proof、cache hit、explain 没有冒充 clean proof。
- Stage 5 审查确认 `pyrightconfig.tools.json` 与 `QUALITY_GATE_TOOL_PATHS` 对齐，runner 覆盖自检和 proof JSON 字段无阻塞。
- Stage 5 审查确认新增代码没有 Python 3.9+ 语法、`shell=True` 或 Win7 明显不兼容点。

## 4. 验收核对

- `ruff_check_full` 的 fingerprint 会因 ruff 实际扫描的 Python 文件、ruff 配置、依赖文件、`ruff_version`、Python version、环境变量或声明输出文件变化而变化。
- `pyright_gate_full` 的 fingerprint 会因 gate include 范围、`.py` / `.pyi` / `py.typed`、pyright 配置、依赖文件、`pyright_version`、Python version、`PYTHONPATH` 或声明输出文件变化而变化。
- `pyright_tools_full` 的 fingerprint 会因 `QUALITY_GATE_TOOL_PATHS` 列表内容和顺序、工具文件内容、import closure helper、pyright 配置、依赖文件、`pyright_version`、Python version、`PYTHONPATH` 或声明输出文件变化而变化。
- `pyright_tools_full` 不再缓存只找到 2 个 source files 的旧空覆盖结果；配置清单不一致或 `filesAnalyzed` 不足都会失败。
- `--long-gate-cache-explain` 只输出决策，不写 proof，不算 quality gate proof。
- `architecture_fitness`、`debt_ledger_sync`、`quickref_vs_routes` 仍是 `PLANNED_ONLY`。
- static proof JSON 只证明单条 static entry 输出完整，不证明整个仓库 clean-worktree final proof。

## 5. 验证结果

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_long_gate_manifest.py tests/test_long_gate_cache.py tests/test_run_quality_gate.py tests/test_git_hook_checks.py tests/test_long_gate_cli_controls.py tests/test_long_gate_summary_output.py tests/test_long_gate_required_regression_cache.py tests/test_long_gate_startup_regression_cache.py tests/test_long_gate_full_test_debt_cache.py tests/test_architecture_scan_cache.py`：通过，569 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check`：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright -p pyrightconfig.gate.json`：通过，0 errors，6 warnings；warnings 为既有 `core/services/scheduler/__init__.py` 的 `__all__` 提示。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright -p pyrightconfig.tools.json`：通过，0 errors，0 warnings。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python codestable/tools/validate-yaml.py --file codestable/roadmap/quality-gate-long-cache/quality-gate-long-cache-items.yaml`：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python codestable/tools/validate-yaml.py --file codestable/features/2026-05-15-static-formal-cache/static-formal-cache-checklist.yaml`：通过。
- `git diff --check`：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/git_hook_checks.py check-staged-artifacts`：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --long-gate-cache-explain`：通过；输出明确写着 explain 不是 quality gate proof。

## 6. Proof 口径

- 未运行 `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache`。
- 未完成 clean-worktree full proof，不能宣称本次变更已通过完整 final quality gate。
- 本次验证只证明 NEXT-10 相关代码、测试、ruff、pyright、YAML、diff 和 artifact hygiene 检查通过。
- static cache hit 只代表单条 entry 的 previous successful result 可复用，不代表整个仓库 clean proof。
- `--long-gate-cache-explain` 只是缓存决策预览，不是 proof。

## 7. Roadmap 回写

- `codestable/roadmap/quality-gate-long-cache/quality-gate-long-cache-items.yaml` 中 `static-formal-cache` 已从 `in-progress` 改为 `done`。
- roadmap 主文档已同步 NEXT-10 完成状态、当前 enabled entry 列表、`pyright_tools_full` 覆盖修复和 proof 口径。
- 后续 planned entry 仍为 `debt_ledger_sync`、`quickref_vs_routes`；`architecture_fitness` 仍不启用整项 success cache。

## 8. AGENTS.md 候选

- 本 feature 未暴露必须补入 AGENTS.md 的新长期规则。
- 可作为后续维护注意项：如果 `QUALITY_GATE_TOOL_PATHS` 新增本地 import，需要同步 `pyright_tools_full` 的 import closure scope 和对应测试。

## 9. 遗留

- 没有 clean-worktree final proof；提交或合并前仍需要在干净工作区运行完整 final quality gate。
- `pyright_gate_full` 仍有既有 6 个 pyright warning，本 feature 没有改变这些应用层 warning。
- `pyright_tools_full` 的 import closure 当前用手工 scope 清单维护；当前审查未发现漏项，后续改工具导入时需要同步更新。
