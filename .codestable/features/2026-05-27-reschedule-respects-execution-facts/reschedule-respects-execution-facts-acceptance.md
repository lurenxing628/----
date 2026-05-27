---
doc_type: feature-acceptance
feature: 2026-05-27-reschedule-respects-execution-facts
status: accepted
roadmap: aps-three-gap-directions
roadmap_item: reschedule-respects-execution-facts
accepted_at: 2026-05-27
---

# 重排尊重现场执行事实验收报告

> 阶段：阶段 3（验收闭环）
> 验收日期：2026-05-27
> 关联方案 doc：`.codestable/features/2026-05-27-reschedule-respects-execution-facts/reschedule-respects-execution-facts-design.md`

## 1. 接口契约核对

- `ExecutionFactProvider` 按 `op_id` 聚合现场事实，保留实际时间、实际资源、异常影响字段和 `state_revision`；与方案第 2.1 节一致。
- 新增 `ExecutionSnapshot`，普通重排和 scenario 保存都会记录 `execution_snapshot_revision`、`execution_snapshot_op_ids`、`execution_snapshot_op_count`；与 roadmap 第 5.10 节一致。
- `ScheduleRunInput` 已携带执行快照字段，`ScheduleHistory.result_summary` 已写入快照摘要。
- `ScheduleAdjustmentScenario`、repository、schema 和 v17 迁移已保存执行快照字段。
- `ScheduleResult` 已保留 `seed_source` 和 `state_revision`，执行事实 seed 可追溯为 `execution_fact`。

## 2. 行为与决策核对

- 普通重排读取同一批执行事实：生产中和暂停中工序固定，已完工工序不进入待排输入，异常中工序返回 `6003 / 409` 并提示先处理异常。
- 候选比较、多起点、局部搜索、优化器和图排程 ready queue 复用同一批执行 seed。候选明细会把执行固定和已完工工序标成 locked。
- 普通重排落库前复算执行快照；现场状态变化时不写 `Schedule`、`ScheduleHistory` 或版本号。
- `simulate=True` 只做校验和试算返回，不写正式版本，也不写 scenario 快照。
- scenario 保存只写模拟方案和执行快照，不改正式计划；scenario 发布前用保存时同一批工序复算快照和执行事实，冲突时回滚发布状态。
- 保存和发布 scenario 的普通 JSON 响应不再直接返回 `scenario_id`、`source_draft_id`、执行快照等内部字段。

## 3. 验收场景核对

- 已开工工序：`tests/regression_scheduler_reschedule_execution_facts.py` 验证实际开始时间、实际设备、实际人员、执行 seed 来源、候选锁定和工序状态保护。
- 暂停工序：同一测试文件验证暂停工序不被移动，执行状态保持为“暂停中”。
- 已完工工序：同一测试文件验证已完工工序从待排输入剔除，作为执行 seed 保留，下游不能早于真实完工时间。
- 异常中工序：同一测试文件验证普通重排返回 `6003 / 409`，异常影响字段能从执行事实读出，且不写正式计划。
- 执行快照：普通重排历史摘要包含 revision、op_ids、op_count、sample 和 truncated 标记。
- scenario 保存/发布：`tests/regression_gantt_adjustment_publish_execution_revision.py` 验证保存快照、发布前复算、冲突回滚、成功历史摘要和普通接口不外露内部字段。
- 模拟排程：`simulate=True` 在有无现场事实时都不写正式版本。
- 前端浏览器：本条没有新增可点击前端控件，主要变更是后端 JSON 响应和排程链路；通过路由级回归验证用户可见返回字段。

## 4. 术语一致性

- 方案术语“执行事实 / 执行快照 / 执行固定 seed / 普通自动重排 / 甘特模拟方案发布”均有代码落点。
- 用户可见位置继续使用中文大白话；执行快照、`scenario_id`、`source_draft_id` 等内部追踪字段不作为普通接口字段返回。
- `exception` 状态和“报异常”动作沿用第 11 项拆分后的映射，不在本条混用。

## 5. 架构归并

- 已更新 `.codestable/architecture/ARCHITECTURE.md`，新增“重排执行事实快照现状”，说明快照模块、普通重排、候选/图排程、scenario 保存发布和用户可见边界。
- 已更新 `.codestable/architecture/ui-gantt.md`，修正 scenario 保存成功响应不直接返回 `scenario_id` 的现状，并补 scenario 发布执行快照和白名单响应边界。

## 6. requirement 回写

- 已更新 `.codestable/requirements/shop-floor-execution-feedback.md`，从 `draft` 升级为 `current`。
- 已更新 `.codestable/requirements/VISION.md`，把“记录车间实际开工完工和异常”移动到当前有效能力。

## 7. roadmap 回写

- 已把 `.codestable/roadmap/aps-three-gap-directions/aps-three-gap-directions-items.yaml` 中 `reschedule-respects-execution-facts` 改为 `done`。
- 已同步 `.codestable/roadmap/aps-three-gap-directions/aps-three-gap-directions-roadmap.md` 第 13 项状态、对应 feature 和变更日志。

## 8. attention.md 候选盘点

- 本 feature 未暴露需要补入 `.codestable/attention.md` 的新环境或命令陷阱。

## 9. 遗留

- 未做撤销开工、撤销完工、纠错或反冲；这些仍按 requirement 边界另起后续能力。
- 未做异常工序智能重排；异常中仍先阻止普通自动重排，提示计划员处理现场异常。
- 未保留“旧逻辑先红”的单独运行记录；本次通过回归测试和多轮 SubAgent 对抗复审锁住当前正确行为。
- SubAgent 复审记录：初始调查 5 个子代理；实现后多轮整体复审共 19 个子代理参与。最终一轮 5 个切片（普通重排算法链、scenario 持久化链、执行事件/API 边界、测试兼容性、跨模块契约）结论均为 OK、阻塞项 0。

## 10. 最终验证

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --file .codestable/roadmap/aps-three-gap-directions/aps-three-gap-directions-items.yaml --yaml-only --require roadmap --require created --require items`：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_scheduler_reschedule_execution_facts.py tests/regression_scheduler_reschedule_execution_minimum_guardrails.py tests/regression_gantt_adjustment_publish_execution_revision.py tests/regression_gantt_draft_save_and_preview.py tests/regression_gantt_scenario_publish.py`：43 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check ...`：通过，范围覆盖本条新增和修改的 Python 文件。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/scan_py38plus_syntax.py --fail-on-hit ...`：通过，23 个文件未发现 Python 3.8 之后才支持的语法风险。
- `git diff --check`：通过。
