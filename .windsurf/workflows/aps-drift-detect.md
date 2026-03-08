---
description: APS 漂移检测与一致性体检：综合检测脚本、架构适应度函数、引用链追踪与健康报告
---
当用户提到“漂移检测 / 体检 / 一致性检查 / 健康检查 / milestone 检查 / 全面体检”时，使用本 workflow。

- 本地 skill 说明：`.windsurf/skills/aps-drift-detect/SKILL.md`

1. 先运行综合检测脚本。
   - 默认：`python .windsurf/skills/aps-drift-detect/scripts/drift_detect.py`
   - 需要更长超时时：`python .windsurf/skills/aps-drift-detect/scripts/drift_detect.py --timeout 180 --timeout-ruff 300`

2. 再补两项手工检查。
   - 架构适应度函数：`python -m pytest tests/test_architecture_fitness.py -v`
   - 对近期变更做引用链追踪：`python .windsurf/skills/aps-deep-review/scripts/reference_tracer.py --commit HEAD~1`

3. 读取关键报告。
   - 综合报告：`evidence/DriftDetect/drift_report.md`
   - 架构审计报告：`evidence/ArchAudit/arch_audit_report.md`
   - 引用链追踪报告：`evidence/DeepReview/reference_trace.md`

4. 解读时按 7 个维度组织。
   - 架构合规审计。
   - 架构适应度函数。
   - 一致性对标报告。
   - Ruff 全量 lint。
   - 文档新鲜度。
   - 引用链追踪。
   - 复杂度健康度。

5. 向用户输出结论时至少包含。
   - 哪些维度 PASS，哪些 FAIL。
   - 是否有新增的架构违反。
   - 是否存在近期变更引入的跨层边界风险。
   - 哪些问题应立即处理，哪些可纳入后续体检周期。

6. 使用边界。
   - 本 workflow 适合定期健康检查，不适合代替单次 bug 精修。
   - 若要深挖某个失败维度，转 `aps-arch-audit` 或 `aps-deep-review`。
