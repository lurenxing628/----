---
doc_type: feature-acceptance
feature: 2026-04-28-downtime-resource-pool-contract
status: accepted
created: 2026-04-28
last_reviewed: 2026-04-28
roadmap: p1-scheduler-debt-cleanup
roadmap_item: downtime-resource-pool-contract
---

# 停机区间与自动分配资源池合同验收

## 1. 验收结论

M3 已完成停机区间和自动分配资源池合同收口。本次只处理 P1-16 / P1-17 的当前事实源：停机读取、资源池候选设备补停机、部分失败保留成功设备，以及这两处函数的复杂度登记。

本次完成：

- `load_machine_downtimes` 和 `extend_downtime_map_for_resource_pool` 复用内部 helper 读取停机、整理时间段、记录失败设备和写 meta/sample。
- 停机读取成功、无记录、整体失败、单设备失败保留健康设备、逐设备查询全部失败按 partial 暴露均有测试。
- 资源池候选设备补停机、候选设备无停机不加空 key、候选设备部分失败保留成功设备、extend 查询前整体失败保留原 map 均有测试。
- `MachineDowntimeRepository.list_active_after()` 已有真实查询测试，固定 active 行、结束时间、跨过排产开始时间的记录和排序口径。
- collector 真实 DB 链路已证明固定设备和资源池候选设备都会进入 `downtime_map`。

本次没有做：

- 没有改冻结窗口、优化器主逻辑、落库、页面、runtime/plugin 或质量门禁工具。
- 没有新增 fallback、兜底、静默吞错或算法候选规则。
- 没有减少 full-test-debt；active xfail 仍是 5 条 operator-machine/query service 旧登记。

## 2. 代码和测试改动

- `core/services/scheduler/resource_pool_builder.py`：把 load/extend 重复的停机读取和失败记录流程收口到内部 helper，公开字段和值保持不变。
- `tests/test_resource_pool_builder_contract.py`：补齐资源池构建、停机读取、资源池停机扩展、部分失败和整体准备失败合同。
- `tests/test_machine_downtime_repository_contract.py`：补真实查询合同，包括跨过排产开始时间的停机记录。
- `tests/regression_schedule_input_collector_downtime_resource_pool_contract.py`：补真实 collector 链路。
- `开发文档/技术债务治理台账.md`：由受控脚本刷新，只反映 complexity 改善。

## 3. 债务口径

| 项目 | 结果 |
|---|---|
| `load_machine_downtimes` 复杂度 | 21 降到 5 |
| `extend_downtime_map_for_resource_pool` 复杂度 | 21 降到 8 |
| 高复杂度登记 | 42 降到 40 |
| full-test-debt | 不减少，仍是 5 条 active xfail |
| P1-16 / P1-17 | `fixed-by-M3`，只表示当前 complexity/test_coverage 事实源关闭 |

## 4. 已运行验证

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_resource_pool_builder_contract.py tests/test_machine_downtime_repository_contract.py tests/regression_schedule_input_collector_downtime_resource_pool_contract.py`：14 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_schedule_summary_v11_contract.py tests/regression_schedule_input_collector_contract.py tests/regression_scheduler_user_visible_messages.py tests/regression_scheduler_run_surfaces_resource_pool_warning.py`：32 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_downtime_timeline_ordered_insert.py tests/regression_downtime_overlap_skips_invalid_segments.py`：6 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_architecture_fitness.py::test_cyclomatic_complexity_threshold`：1 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check core/services/scheduler/resource_pool_builder.py data/repositories/machine_downtime_repo.py tests/test_resource_pool_builder_contract.py tests/test_machine_downtime_repository_contract.py tests/regression_schedule_input_collector_downtime_resource_pool_contract.py`：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright core/services/scheduler/resource_pool_builder.py data/repositories/machine_downtime_repo.py`：0 errors。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/check_full_test_debt.py`：通过，active xfail 仍为 5，`collected_count=744`。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/sync_debt_ledger.py check`：通过，complexity_count 为 40，test_debt_count 为 5。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python codestable/tools/validate-yaml.py --dir codestable/roadmap/p1-scheduler-debt-cleanup`：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python codestable/tools/validate-yaml.py --dir codestable/features/2026-04-28-downtime-resource-pool-contract`：通过。
- `git diff --check`：通过。
- 本地提交完成后，`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --require-clean-worktree`：通过。

## 5. Subagent 复审

- 停机/资源池合同复审：代码合同通过；指出 load 部分失败缺新增测试，本次已补齐并复跑转绿。
- 无新增兜底对抗审查：通过，确认 helper 只是搬移和合并已有判断，没有新增业务 fallback 或静默吞错。
- 下游影响复审：通过，未发现 summary、页面、导出、落库、runtime/plugin 被带坏。
- 测试和债务证明复审：指出文档回填和 clean gate 仍需收尾，本文件、roadmap、items 和 source-map 已回填；clean gate 已在本地提交后的干净工作区通过。
- 二次 review findings 复审：根因确认在测试和文档证据没有钉牢，不在业务代码；本次只补测试和文档，没有新增业务 `if`、fallback 或兜底。

## 6. 后续承接

M4 只能承接优化器输出和 summary 事实源。M3 的证明不能拿来替代优化器 proof，也不能顺手改资源池候选设备口径、停机读取或页面展示。
