---
doc_type: feature-acceptance
feature: 2026-05-27-delay-diagnosis-core-service
status: accepted
roadmap: aps-three-gap-directions
roadmap_item: delay-diagnosis-core-service
created: 2026-05-27
---

# 延期诊断核心服务验收

## 验收结论

已完成。

本阶段只新增“只读延期诊断服务”。它会把超期事实、建议先复核的工序、物料齐套状态、停机重叠、证据、缺口和建议动作组织成结构化结果，但不改正式排程、不改候选方案、不改模拟预览，也不下“唯一根因”结论。

## 已落地范围

- 新增延期诊断结果模型，包含已确认事实、可能线索、建议动作、工序线索、单批次诊断、整版诊断和 trace_meta。
- 新增延期诊断服务 `ScheduleDelayDiagnosisService`，提供 `diagnose_plan_overdue` 和 `diagnose_batch`。
- 复用现有 `compute_overdue_buckets()`，保持已排程超期和未排程超期口径一致。
- 无模拟预览时使用严格的 `resolve_existing_plan()`；有模拟预览时使用 `resolve_plan_view()`，候选和模拟预览缺明细直接报错，不回退正式采用方案。
- 新增批次齐套原始快照读取，避免 `Batch.from_row` 把空齐套状态默认成已齐套。
- 物料线索只读取 `Batches.ready_status / ready_date` 和 `BatchMaterials` 明细；没有明细或状态缺失时输出缺数据证据。
- 停机只作为“待核对线索”，不写成已确认原因。
- trace_meta 的证据来源能覆盖行级证据、汇总证据和缺数据证据，不为了凑字段伪造 source_table。

## 验证

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_scheduler_delay_diagnosis_contract.py tests/regression_due_exclusive_consistency.py tests/regression_gantt_adjustment_validate_simulate.py`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/scan_py38plus_syntax.py --fail-on-hit core/services/scheduler/schedule_delay_diagnosis_service.py core/services/scheduler/schedule_delay_diagnosis_clues.py core/services/scheduler/schedule_delay_diagnosis_utils.py core/models/schedule_delay_diagnosis.py core/models/schedule_plan_identity.py data/repositories/batch_repo.py tests/regression_scheduler_delay_diagnosis_contract.py`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --file .codestable/roadmap/aps-three-gap-directions/aps-three-gap-directions-roadmap.md --require doc_type --require slug --require status --require created --require last_reviewed --require tags`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --file .codestable/roadmap/aps-three-gap-directions/aps-three-gap-directions-items.yaml --yaml-only --require roadmap --require created --require items`
- `git diff --check`

## 子代理复审

- 调查阶段 4 个子代理分别检查了超期分桶和计划身份、物料齐套、停机/负荷/关键链口径、测试设计。
- 第一轮实现后对抗审核 4 个子代理分别检查了只读边界、候选和模拟预览不回退、证据链和 trace_meta、物料/停机/用户文案。
- 审核发现两个阻塞：只读测试覆盖不完整、汇总/缺数据证据的 evidence_sources 可能为空。已修复。
- 修复后再派 2 个子代理复审只读证明和证据来源摘要，均确认无阻塞。

## 未做

- 不接超期清单页面入口。
- 不做超期导出增强。
- 不做 AI 根因判断。
- 不改排程算法。
- 不引入车间开工、完工、暂停、异常反馈。
