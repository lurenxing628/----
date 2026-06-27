---
doc_type: feature-ff-note
feature: optimizer-candidate-profile-contract
date: 2026-06-28
status: done
tags: [scheduler, optimizer, candidate-profile, search-profile, public-boundary, python38]
---

# optimizer-candidate-profile-contract fast-forward note

## 本轮目标

执行 roadmap item 4：`optimizer-candidate-profile-contract`。

把"想跑什么搜索 profile、配置了多少预算、实际生效多少预算、为什么被系统限制、哪些参数非法"
显式化、可校验、可报告。本轮只锁现有 optimizer 已有能力的 profile 合同与校验边界，不新增
GRASP / IG / VNS / SA / ALNS，不实现完整 CandidateFingerprint（item 5）。

## 落地内容

- 新增 `core/services/scheduler/run/optimizer_candidate_profile.py`：
  - `CandidateProfile` dataclass（22 字段）+ `build_candidate_profile(...)` 解析校验入口。
  - `derive_iteration_limits(time_budget_seconds)`：迭代上限/重启阈值公式的**单一真相源**
    （`it_limit = max(200, min(5000, time_budget*20))`、`restart_after = max(50, min(800, it_limit//8))`，
    与历史 `optimizer_local_search` 内联公式逐位一致）。
- `optimizer_local_search.py`：原内联迭代/重启公式改为调用 `derive_iteration_limits`，消除重复公式
  （语义漂移债），行为零变化、文件仍 493 行。
- `optimizer_search_report.py`：`OptimizationSearchReportState` 新增 `candidate_profile` 字段，
  `finalize()` 输出 `candidate_profile` 嵌套 dict。
- `schedule_optimizer.py`：构造 `candidate_profile` 并注入 report state；`algorithm_profile` 改由
  `candidate_profile.profile` 稳定派生，删除旧 `_algorithm_profile` 模糊串函数。
- `optimizer_public_search_report.py`：`project_search_report` 扩展，把 `candidate_profile` 拆成
  `profile_public`（白名单安全摘要）与 `profile_diagnostics`（配置来源/邻域等内部细节），复用 `safe_*` 兜底。
- `summary_size_guard_fields.py`：最小摘要白名单新增 `profile_public`，避免大摘要裁剪后丢失关键合同字段。
- 新增 `tests/algorithm/test_optimizer_candidate_profile_contract.py`（23 用例），并登记
  `tools/test_registry_data.py` 与 `tools/test_registry_groups_scheduler.py`。

## 合同字段如何落地（诚实映射，无伪造）

| 字段 | 来源 |
| --- | --- |
| `profile` | algo_mode 派生：improve→`multi_start_local_search`，greedy→`baseline`，未知→`ValidationError` |
| `enabled` | `profile == multi_start_local_search` |
| `seed` / `seed_source` | `int(version)` / `optimizer_version`（如实标版本派生，非用户显式 seed） |
| `configured_time_budget_seconds` | 配置解析后的 time_budget（如实回显用户配置） |
| `effective_time_budget_seconds` | improve=configured（时间无系统上限）；baseline=0（不跑搜索） |
| `configured_max_iterations` | `time_budget*20`（profile 由预算派生的意图值） |
| `effective_max_iterations` | `derive_iteration_limits` 钳到 `[200,5000]` 后的值；baseline=0 |
| `iteration_limit_source` | 无钳制=`profile_default`；被钳制=`system_limit`；baseline=`not_applicable` |
| `system_limit_applied` / `system_limit_reason` | effective≠configured 时 true + `iteration_floor`/`iteration_ceiling` |
| `restart_after_iterations` | `derive_iteration_limits` 第二返回值；baseline=0 |
| `repair` / `acceptance` / `neighborhoods` | 现仅 `sgs` / `improve_only` / `swap,insert,block`，未知 fail-loud |
| `candidate_strategy_family` | improve=`multi_start`；baseline=`single_shot` |
| `dispatch_mode` / `dispatch_rule` | cfg 取值，graph 强制时 dispatch_mode=`sgs` |
| `ortools_warmstart_enabled` | `ortools_enabled AND enabled`（baseline 恒 false，不升主引擎） |
| `strict_mode` / `validation_status` | 透传 / `ok`（校验通过才返回，否则已 raise） |

## 验证证据（dirty / unbound proof）

- 新增合同测试 23 用例 + item 1/2/3 回归 + 边界测试，多轮实跑全绿。
- `tests/_scripts_e2e/benchmark_optimizer_proof_harness.py --require-optimal`：`proven_optimal`、`gap_to_oracle_pct=0.0`（item 1 回归）。
- `tools/scan_py38plus_syntax.py`：无 3.8 之后语法/注解风险。
- `ruff check`（本轮改动文件）：All checks passed。
- `pyright -p pyrightconfig.gate.json` / `pyrightconfig.tools.json`：0 errors。
- 架构适应度门禁 `test_file_size_limit` / `test_cyclomatic_complexity_threshold` / `test_services_do_not_use_assert_for_runtime_guards`：3 passed。
- registry 一致性门禁（`test_full_test_debt_registry_contract` 等）：passed。
- `git diff --check` / `git diff --cached --check`：clean。
- `scripts/run_quality_gate.py --allow-dirty-worktree`：17/17 步通过，manifest 标 `passed_but_unbound`。

> **证明状态**：当前工作区 dirty（含本轮改动 + symbol_locator 自动刷新的 callgraph json 产物，均未提交）。
> 因此只能称 **dirty / unbound proof**，不是 clean-worktree proof。clean proof 需在工作区干净、本轮改动落到
> HEAD 后重跑 `scripts/run_quality_gate.py --require-clean-worktree`。

## 对抗审查记录

执行者记录本轮派出 4 个只读 OPUS 子代理（fresh context、各自独立、不继承主代理上下文、禁跑 symbol_locator）。
当前仓库只保留本摘要，未附独立审查产物；后续若需要把它作为可复核 proof，应补充原始审查记录或链接。

1. **定向复审**：对照 §4.3 / §4.8 逐条核 8 项合同，全闭环，无硬 blocker。
2. **盲审·正确性/行为保持**：实跑 334 个 time_budget 值确认 `derive_iteration_limits` 与历史公式逐位等价；
   profile.effective 与 local_search it_limit 同函数同参、零漂移；algorithm_profile 两分支均正确；无 import 环/吞错。
3. **盲审·public/diagnostics 泄漏边界**：实跑注入测试穿四出口，白名单封闭、`safe_attempt_text` 拦截注入，无内部 id 泄漏。
4. **盲审·fail-loud/测试缺口**：实跑非法输入逐条验证 fail-loud、无 assert、无全局污染、边界全覆盖。

按 reviewer 非阻塞建议补强：fail-loud 测试加 `exc.value.field` 断言（消除"抛错原因不符"隐患）；
新增 profile↔local_search 同源不变量测试（锁单一真相源）。

## 边界说明

- profile 取值本阶段限 `baseline` / `multi_start_local_search`；`grasp/ig/vns/sa/alns` 待 item 6-10，未知值仍 `ValidationError`。
- `repair` 仅 `sgs`、`acceptance` 仅 `improve_only`、`neighborhoods` 仅 `swap/insert/block`。
- 未引入新依赖；保持 Win7 / Python 3.8 / 离线交付兼容。
- 未做 item 5 完整 CandidateFingerprint；未把 OR-Tools 升为主引擎；未改写正式计划表/results/start_time/end_time。
- 下一项：roadmap item 5 `distinct-candidate-fingerprint-contract`。
