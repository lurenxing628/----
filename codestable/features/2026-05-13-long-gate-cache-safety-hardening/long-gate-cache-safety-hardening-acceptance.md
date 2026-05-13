---
doc_type: feature-acceptance
feature: 2026-05-13-long-gate-cache-safety-hardening
status: accepted
summary: long gate success cache 共用安全和证据链加固已完成
tags: [quality-gate, cache, safety, evidence]
---

# long-gate-cache-safety-hardening 验收报告

> 阶段：阶段 3（验收闭环）
> 验收日期：2026-05-13
> 关联方案 doc：`codestable/features/2026-05-13-long-gate-cache-safety-hardening/long-gate-cache-safety-hardening-design.md`

## 1. 接口契约核对

**新增工具模块逐项核对**：

- [x] 已新增 `tools/long_gate_paths.py`，集中放 long gate cache 目录常量、repo realpath、repo 内路径解析和相对路径规范化。
- [x] 已新增 `tools/long_gate_schema.py`，集中放 cache / fingerprint / manifest / summary schema version。
- [x] `tools/long_gate_schema.py` 已提供 `runner_version_hash`、`tooling_version_hash` 和 repo identity 元数据。
- [x] `tools/quality_gate_shared.py` 的 `QUALITY_GATE_TOOL_PATHS` 已纳入两个新工具文件。

**success cache 字段逐项核对**：

- [x] `cache_schema_version`
- [x] `fingerprint_schema_version`
- [x] `runner_version_hash`
- [x] `tooling_version_hash`
- [x] `cache_dir`
- [x] `repo_root_realpath`
- [x] `git_common_dir_realpath`

## 2. 行为与决策核对

**需求摘要逐项验证**：

- [x] cache schema 变化会失效。
- [x] fingerprint schema 变化会失效。
- [x] runner hash 变化会失效。
- [x] tooling hash 变化会失效。
- [x] runner/tooling 自身如果是 repo 外 symlink，不读取外部目标内容，也不复用旧 cache。
- [x] repo identity 不一致会失效。
- [x] 顶层 JSON 不是 object、缺字段、字段类型错误、bool 冒充数字都会失效。
- [x] success cache 写入侧也拒绝 bool 或坏字符串冒充数字。
- [x] fingerprint 结构坏但 hash 自洽时不会崩溃，会判定重跑。
- [x] repo 外普通路径和 repo 外 glob 都不会变成可复用 success cache。
- [x] stdout/stderr log 和 output file 仍必须存在且 hash 匹配。
- [x] `duration_s` 被损坏时不会复用旧 cache。
- [x] repo 内绝对路径会规范化为相对路径，repo 外绝对路径会报错。
- [x] symlink 指到 repo 外时只记录 symlink 目标本身，不读取外部文件内容，也不复用 success cache。

**明确不做逐项核对**：

- [x] `_CACHE_ENABLED_ENTRY_TYPES` 未新增 entry。
- [x] 当前真正允许 success cache 复用的 entry 仍只有 `pytest_collect_all`。
- [x] 未启用 full-test-debt、startup、required、ruff、pyright、debt ledger、quickref。
- [x] 未把 explain 模式当 proof。
- [x] 未提交运行 evidence 产物。

## 3. 验收场景核对

- [x] **S1/S2/S3**：success cache 写入新字段，cache/fingerprint schema 变化会失效。
  - 证据来源：`tests/test_long_gate_cache.py::test_write_success_records_common_safety_fields`、`test_missing_cache_schema_version_is_not_reused`、`test_cache_schema_version_change_is_not_reused`、`test_cached_fingerprint_schema_version_change_is_not_reused`。

- [x] **S4/S5**：runner/tooling hash 和 repo identity 不一致会失效。
  - 证据来源：`tests/test_long_gate_cache.py::test_runner_version_hash_change_is_not_reused`、`test_tooling_version_hash_change_is_not_reused`、`test_tooling_symlink_to_outside_repo_does_not_read_target_content_and_is_not_reused`、`test_repo_identity_mismatch_is_not_reused`。

- [x] **S6/S7**：坏 JSON、坏类型、坏 fingerprint 结构不会误复用。
  - 证据来源：`tests/test_long_gate_cache.py::test_success_cache_top_level_json_array_is_not_reused`、`test_bool_numeric_fields_are_not_reused`、`test_bad_duration_s_is_not_reused`、`test_write_success_rejects_bool_or_bad_numeric_fields`、`test_cached_fingerprint_with_bad_shape_is_not_reused`。

- [x] **S8/S9/S10**：日志、输出、绝对路径和 repo 外 symlink 继续保守。
  - 证据来源：`tests/test_long_gate_cache.py::test_stderr_log_hash_mismatch_is_not_reused`、`test_non_utf8_success_log_is_not_reused`、`test_absolute_inside_repo_output_path_is_normalized_and_absolute_outside_is_rejected`、`test_outside_repo_scope_is_not_reused`、`test_fingerprint_files_marks_outside_repo_glob_without_reusing_cache`、`test_symlink_to_outside_repo_does_not_hash_target_content`、`test_symlink_to_outside_repo_is_not_reused`。

- [x] **S11/S12**：enabled 范围不变，新工具进入 proof 来源。
  - 证据来源：`tests/test_long_gate_manifest.py::test_only_collect_entry_is_currently_reuse_enabled`、`tests/test_long_gate_cli_controls.py::test_force_planned_entry_is_reported_but_does_not_enable_cache`、`tests/test_run_quality_gate.py::test_main_runs_guard_preflight_before_static_and_startup_checks`、`tests/test_run_quality_gate.py::test_main_writes_quality_gate_manifest_with_git_and_collection_proof`。

**验证命令**：

- [x] `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_long_gate_cache.py tests/test_long_gate_manifest.py`（79 passed）
- [x] `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_long_gate_cache.py tests/test_long_gate_manifest.py tests/test_run_quality_gate.py tests/test_long_gate_cli_controls.py tests/test_long_gate_summary_output.py`（163 passed）
- [x] `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check tools/long_gate_cache.py tools/long_gate_fingerprint.py tools/long_gate_manifest.py tools/long_gate_paths.py tools/long_gate_schema.py tools/long_gate_summary.py tools/quality_gate_shared.py tests/test_long_gate_cache.py tests/test_long_gate_manifest.py tests/test_run_quality_gate.py tests/test_long_gate_cli_controls.py tests/test_long_gate_summary_output.py`
- [x] `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright tools/long_gate_cache.py tools/long_gate_fingerprint.py tools/long_gate_manifest.py tools/long_gate_paths.py tools/long_gate_schema.py tools/long_gate_summary.py tools/quality_gate_shared.py tests/test_long_gate_cache.py tests/test_long_gate_manifest.py tests/test_run_quality_gate.py tests/test_long_gate_cli_controls.py tests/test_long_gate_summary_output.py`

## 4. 术语一致性

- `cache schema`、`fingerprint schema`、`runner hash`、`tooling hash`、`repo identity` 在设计、代码和测试中保持同一口径。
- `planned_only` 仍表示“尚未启用 success cache”，不是说真实命令不会执行。
- `explain 不是 proof` 的边界未改变。

## 5. 架构归并

- [x] 不需要更新 `codestable/architecture/ARCHITECTURE.md`。本 feature 是质量门禁工具链内部安全加固，不改变 APS 排产业务架构。

## 6. requirement 回写

- [x] 无 requirement 回写。本 feature 不新增用户可见业务能力。

## 7. roadmap 回写

- [x] `quality-gate-long-cache-items.yaml` 中 `long-gate-cache-safety-hardening` 已绑定 `feature: 2026-05-13-long-gate-cache-safety-hardening`。
- [x] 已把该 item 标为 `done`。
- [x] 已同步 roadmap 主文档的当前状态、NEXT-3 章节、子 feature 清单和变更日志。

## 8. AGENTS.md / CLAUDE.md 候选盘点

- [x] 无候选。本 feature 的约束已经写在 CodeStable roadmap 和 feature 文档里，不需要提升成仓库级代理规则。

## 9. 遗留

- full-test-debt、startup、required、ruff、pyright、debt ledger、quickref 等 entry 仍然只是 planned，没有启用 success cache。
- 完整 clean-worktree proof 需要等本次改动提交后，在干净工作区运行 `scripts/run_quality_gate.py --require-clean-worktree`。
