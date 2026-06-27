---
doc_type: feature-ff-note
feature: optimizer-search-report-contract
date: 2026-06-27
status: done
tags: [scheduler, optimizer, search-report, public-boundary, python38]
---

# optimizer-search-report-contract fast-forward note

## 本轮目标

执行 roadmap item 3：`optimizer-search-report-contract`。

本轮只补现有 optimizer 的搜索报告合同，让每次优化都能说清楚“试了什么、为什么停、最后最优从哪里来、哪些候选被拒绝”。本轮不做 item 4 candidate profile，不做 item 5 完整 CandidateFingerprint，也不引入 GRASP / IG / VNS / SA / ALNS。

## 落地内容

- 新增 `OptimizationSearchReportState`，统一生成 `OptimizationSearchReport`。
- `OptimizationOutcome`、candidate runner、orchestrator、summary 组装链路都携带 `search_report`。
- baseline fallback、multi-start、optional OR-Tools warm-start failure、ValidationError candidate rejection、local search skipped/noop、time budget、iteration limit、no improvement 都进入同一份 report。
- 新增 report 级最小稳定 fingerprint，用稳定 JSON + sha256 生成，不依赖 dict 随机顺序、对象地址或当前时间。
- public 投影只展示白名单摘要；raw attempts、fingerprint、improvement trace 只进入 diagnostics。
- 因 public 脱敏清单已禁止 `attempts_public` 字段，本轮使用等价白名单字段 `public_attempt_summary`，并继续兼容现有 public `algo.attempts`。
- OperationLogs 的 algo summary 复用 search_report public 投影，不直接透传 raw report。
- summary size guard 的最小摘要路径也保留 search_report public 小摘要，避免大摘要被裁剪后丢失 `stop_reason` / `best_origin` / `seed` 等合同字段。

## 主要改动文件

- `core/services/scheduler/run/optimizer_search_report.py`
- `core/services/scheduler/run/optimizer_step_report_hooks.py`
- `core/services/scheduler/run/schedule_optimizer.py`
- `core/services/scheduler/run/schedule_optimizer_steps.py`
- `core/services/scheduler/run/optimizer_local_search.py`
- `core/services/scheduler/run/optimizer_attempt_records.py`
- `core/services/scheduler/run/schedule_orchestrator.py`
- `core/services/scheduler/run/schedule_candidate_runner.py`
- `core/services/scheduler/run/schedule_candidate_persistence_models.py`
- `core/services/scheduler/summary/schedule_summary_types.py`
- `core/services/scheduler/summary/schedule_summary_assembly.py`
- `core/services/scheduler/summary/optimizer_public_summary.py`
- `core/services/scheduler/summary/optimizer_public_search_report.py`
- `core/services/scheduler/summary/summary_size_guard_fields.py`
- `tests/algorithm/test_optimizer_search_report_contract.py`
- `tests/schedule/summary/test_schedule_summary_size_guard_large_lists.py`
- `tools/test_registry_data.py`
- `tools/test_registry_groups_scheduler.py`

## 验证证据

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/algorithm/test_optimizer_search_report_contract.py`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/algorithm/test_optimizer_search_report_contract.py tests/algorithm/test_optimizer_runtime_seam_contract.py tests/algorithm/test_optimizer_outcome_type_contract.py tests/algorithm/test_optimizer_build_order_once_per_strategy.py tests/algorithm/test_optimizer_local_search_neighbor_dedup.py tests/algorithm/test_optimizer_public_summary_projection_contract.py tests/algorithm/test_optimizer_proof_harness_contract.py tests/schedule/service/test_schedule_orchestrator_contract.py tests/candidate/test_scheduler_candidate_runner_contract.py tests/candidate/test_scheduler_candidate_persistence_contract.py tests/candidate/test_scheduler_candidate_summary_contract.py tests/schedule/summary/test_scheduler_summary_result_summary_contract.py`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/algorithm/test_optimizer_search_report_contract.py tests/gate_meta/test_long_gate_manifest.py tests/gate_meta/test_run_quality_gate.py tests/gate_meta/test_quality_gate_registry_split_scope_contract.py`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/_scripts_e2e/benchmark_optimizer_proof_harness.py --require-optimal`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/scan_py38plus_syntax.py --fail-on-hit <本轮改动文件>`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check <本轮改动文件和测试文件>`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright -p pyrightconfig.gate.json`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright -p pyrightconfig.tools.json`

## 边界说明

- 本轮没有新增 OR-Tools 依赖，也没有把 OR-Tools 升级为主引擎。
- 本轮没有直接写 Schedule 正式计划表、results、result_summary、start_time、end_time 来伪造搜索效果。
- 新候选仍通过现有 Greedy / SGS 主链重新落位。
- `seed_results` 的“只能承载已存在、受保护、执行态固定片段”边界没有放宽。
- 完整 candidate profile 与完整 CandidateFingerprint 合同留给后续 item 4 / item 5。
