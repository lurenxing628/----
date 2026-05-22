---
doc_type: feature-acceptance
feature: 2026-05-22-gantt-adjustment-draft-model
status: accepted
roadmap: gantt-result-view-and-manual-adjustment
roadmap_item: gantt-adjustment-draft-model
tags: [scheduler, gantt, draft, database, acceptance]
---

# gantt-adjustment-draft-model acceptance

## 验收结论

已完成。

本阶段只落后端 Draft 草稿模型，不开放页面编辑，不新增 route，不保存 Scenario，不正式采用。草稿只写 `ScheduleAdjustmentDraft` 和 `ScheduleAdjustmentChange`，不会写 `Schedule`、`ScheduleHistory`、`ScheduleCandidate*` 或 `ScheduleVersionSeq`。

## 已完成内容

- 新增 `ScheduleAdjustmentDraft` / `ScheduleAdjustmentChange` 表和 v12 迁移。
- 新增 Draft dataclass、仓储和 `GanttAdjustmentDraftService`。
- 创建草稿前必须显式给出 `base_plan_role`，不能空值回退到 `adopted`。
- 创建草稿前必须确认基准正式版本存在，并确认基准方案有真实排程明细。
- 只有 `editing` 状态草稿才能继续记录时间或资源调整。
- 回归测试锁住：创建、记录调整、丢弃、删除草稿都不改变正式排产数据和正式版本指针。

## 对抗性审核修复

- 修复空 `base_plan_role` 静默变成 `adopted` 的风险。
- 修复小数 `base_version` 被截断成整数的风险。
- 修复废弃草稿仍可继续写调整的风险。
- 修复只有 `ScheduleHistory`、没有 `Schedule` 明细时仍能创建 adopted 草稿的风险。
- 修复候选方案没有保存明细或没有 `ScheduleCandidateRows` 时仍能创建草稿的风险。
- 修复 schema 当前检测漏查 `ScheduleVersionSeq` 的风险。
- 修复 required regression 分组混入低频测试导致 coverage 校验不干净的问题。
- 修正 roadmap 旧口径：Draft 完成后先进入后端校验与试算，不直接开放真实模拟入口。

## 验证记录

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/regression_gantt_adjustment_draft_model.py`：11 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/regression_gantt_adjustment_draft_model.py tests/test_run_quality_gate.py tests/test_long_gate_manifest.py`：127 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check core/services/scheduler/schedule_plan_query_service.py core/services/scheduler/gantt_adjustment_draft_service.py core/infrastructure/migration_state.py tests/regression_gantt_adjustment_draft_model.py tools/test_registry.py tests/test_run_quality_gate.py`：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --file .codestable/roadmap/gantt-result-view-and-manual-adjustment/gantt-result-view-and-manual-adjustment-items.yaml`：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --dir .codestable/features/2026-05-22-gantt-adjustment-draft-model`：通过。
- `git diff --check`：通过。

## 后续承接

下一阶段是 `gantt-adjustment-validate-simulate`：拖动落点校验与试算。它可以读取 Draft 草稿和调整项，但仍不能正式发布版本；正式采用必须等 `gantt-draft-publish-official-version` 阶段单独实现二次确认、原因必填、重新校验和审计记录。
