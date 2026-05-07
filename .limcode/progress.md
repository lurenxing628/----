# 项目进度
- Project: APS Test
- Updated At: 2026-05-07T16:20:33.962Z
- Status: active
- Phase: implementation

## 当前摘要

<!-- LIMCODE_PROGRESS_SUMMARY_START -->
- 当前进度：尚无里程碑记录
- 当前焦点：P1 排产债务收尾：提交批次页尾项、最终复审证据和进度说明，然后跑干净工作区质量门禁。
- 最新结论：第 2 轮确认多数页面说明已与后端实现对齐：批次/日历/供应商/工序工时 Excel 校验、工种/供应商模板、齐套状态归一化、物料齐套汇总和模拟/执行排产持久化边界均有代码依据。但齐套检查仍存在一类操作者可见文案不精确：后端只要发现任一非齐套批次就抛出 `ValidationError` 并停止本次排产，不会自动过滤未齐套批次后继续排；部分运行选项、配置元数…
- 当前阻塞：工作区仍有未提交修复和证据文件，最终 clean gate 尚未绑定干净 HEAD。
- 下一步：进入第 3 轮，聚焦操作者可理解性、全页面覆盖、相关模块跳转、整本说明/V2 镜像/模板副本一致性；并在最终结论中明确上述文案精度风险是否阻断验收。
<!-- LIMCODE_PROGRESS_SUMMARY_END -->

## 关联文档

<!-- LIMCODE_PROGRESS_ARTIFACTS_START -->
- 审查：`.limcode/review/frontend_manual_backend_behavior_three_round_review.md`
<!-- LIMCODE_PROGRESS_ARTIFACTS_END -->

## 当前 TODO 快照

<!-- LIMCODE_PROGRESS_TODOS_START -->
- [x] 路线图收口：p1-scheduler-debt-cleanup 已标记 completed，13 个 item 全部 done。  `#p1-roadmap`
- [x] 最终复审：多路检查确认 P1 主线、页面、runtime/plugin/Win7 支线没有发现阻塞合并问题。  `#p1-review`
- [x] 批次页尾项：非待排和全部状态列表不再显示表头全选框，普通模板和镜像模板已同步。  `#p1-batches-checkbox`
- [ ] 提交收口：把批次页修复、复审证据和本进度说明按主题提交。  `#p1-commit`
- [ ] 干净门禁：工作区干净后运行 scripts/run_quality_gate.py --require-clean-worktree。  `#p1-clean-gate`
- [ ] 合并验证：快进合并回 main 后，在 main 上复跑同一质量门禁。  `#p1-merge-main`
<!-- LIMCODE_PROGRESS_TODOS_END -->

## 项目里程碑

<!-- LIMCODE_PROGRESS_MILESTONES_START -->
<!-- 暂无里程碑 -->
<!-- LIMCODE_PROGRESS_MILESTONES_END -->

## 风险与阻塞

<!-- LIMCODE_PROGRESS_RISKS_START -->
- risk-dirty-worktree | active | 工作区未收口：当前工作区还有未提交修复和证据文件，质量门禁只能得到 passed_but_unbound，不能当作最终合并证明。
- risk-schema-v7-duplicate-schedule | active | schema v7 会拦住重复排程老库：已有重复 Schedule(version, op_id) 的老库会在 v7 迁移时被阻止继续升级；部署前要先备份并清理重复排程行。
- risk-full-test-debt-unchanged | active | full-test-debt 未减少：当前 full-test-debt 仍是 5 条已登记旧 xfail；本轮 P1 不能写成减少 full-test-debt。
<!-- LIMCODE_PROGRESS_RISKS_END -->

## 最近更新

<!-- LIMCODE_PROGRESS_LOG_START -->
- 2026-04-29T12:24:33+08:00 | artifact_changed | review | 同步审查文档：.limcode/review/a94d3ac048b81c50a6279c1b1119b6fad4c4a14a_deep_review.md
- 2026-04-29T12:48:54+08:00 | artifact_changed | evidence | 归档 Round 4 直接 diff 证据和目标验证结果。
- 2026-05-07T15:24:08.558Z | artifact_changed | review | 同步审查文档：.limcode/review/frontend-manual-backend-behavior-review.md
- 2026-05-07T15:25:42.812Z | artifact_changed | review | 同步审查里程碑：round1-manual-content
- 2026-05-07T15:28:48.016Z | artifact_changed | review | 同步审查里程碑：round2-backend-reference-chain
- 2026-05-07T15:29:40.604Z | artifact_changed | review | 同步审查里程碑：round3-tests-acceptance
- 2026-05-07T15:29:53.137Z | artifact_changed | review | 同步审查结论：.limcode/review/frontend-manual-backend-behavior-review.md
- 2026-05-07T15:51:35.230Z | artifact_changed | review | 同步审查文档：.limcode/review/frontend_manual_backend_behavior_three_round_review.md
- 2026-05-07T15:53:28.907Z | artifact_changed | review | 同步审查里程碑：round1-frontend-entry-render-chain
- 2026-05-07T16:20:33.962Z | artifact_changed | review | 同步审查里程碑：round2-backend-behavior-alignment
<!-- LIMCODE_PROGRESS_LOG_END -->

<!-- LIMCODE_PROGRESS_METADATA_START -->
{
  "formatVersion": 1,
  "kind": "limcode.progress",
  "projectId": "aps-test",
  "projectName": "APS Test",
  "createdAt": "2026-04-07T06:34:24.925Z",
  "updatedAt": "2026-05-07T16:20:33.962Z",
  "status": "active",
  "phase": "implementation",
  "currentFocus": "P1 排产债务收尾：提交批次页尾项、最终复审证据和进度说明，然后跑干净工作区质量门禁。",
  "latestConclusion": "第 2 轮确认多数页面说明已与后端实现对齐：批次/日历/供应商/工序工时 Excel 校验、工种/供应商模板、齐套状态归一化、物料齐套汇总和模拟/执行排产持久化边界均有代码依据。但齐套检查仍存在一类操作者可见文案不精确：后端只要发现任一非齐套批次就抛出 `ValidationError` 并停止本次排产，不会自动过滤未齐套批次后继续排；部分运行选项、配置元数据和整本说明书仍使用“未齐套批次不进入排产/不排/拦排产”的过滤式简称，建议收口为“报错并停止本次排产”。另一个低风险点是新增 Excel 模板合同测试尚未纳入质量门禁必跑清单。",
  "currentBlocker": "工作区仍有未提交修复和证据文件，最终 clean gate 尚未绑定干净 HEAD。",
  "nextAction": "进入第 3 轮，聚焦操作者可理解性、全页面覆盖、相关模块跳转、整本说明/V2 镜像/模板副本一致性；并在最终结论中明确上述文案精度风险是否阻断验收。",
  "activeArtifacts": {
    "review": ".limcode/review/frontend_manual_backend_behavior_three_round_review.md"
  },
  "todos": [
    {
      "id": "p1-roadmap",
      "content": "路线图收口：p1-scheduler-debt-cleanup 已标记 completed，13 个 item 全部 done。",
      "status": "completed"
    },
    {
      "id": "p1-review",
      "content": "最终复审：多路检查确认 P1 主线、页面、runtime/plugin/Win7 支线没有发现阻塞合并问题。",
      "status": "completed"
    },
    {
      "id": "p1-batches-checkbox",
      "content": "批次页尾项：非待排和全部状态列表不再显示表头全选框，普通模板和镜像模板已同步。",
      "status": "completed"
    },
    {
      "id": "p1-commit",
      "content": "提交收口：把批次页修复、复审证据和本进度说明按主题提交。",
      "status": "pending"
    },
    {
      "id": "p1-clean-gate",
      "content": "干净门禁：工作区干净后运行 scripts/run_quality_gate.py --require-clean-worktree。",
      "status": "pending"
    },
    {
      "id": "p1-merge-main",
      "content": "合并验证：快进合并回 main 后，在 main 上复跑同一质量门禁。",
      "status": "pending"
    }
  ],
  "milestones": [],
  "risks": [
    {
      "id": "risk-dirty-worktree",
      "title": "工作区未收口",
      "description": "当前工作区还有未提交修复和证据文件，质量门禁只能得到 passed_but_unbound，不能当作最终合并证明。",
      "status": "active"
    },
    {
      "id": "risk-schema-v7-duplicate-schedule",
      "title": "schema v7 会拦住重复排程老库",
      "description": "已有重复 Schedule(version, op_id) 的老库会在 v7 迁移时被阻止继续升级；部署前要先备份并清理重复排程行。",
      "status": "active"
    },
    {
      "id": "risk-full-test-debt-unchanged",
      "title": "full-test-debt 未减少",
      "description": "当前 full-test-debt 仍是 5 条已登记旧 xfail；本轮 P1 不能写成减少 full-test-debt。",
      "status": "active"
    }
  ],
  "log": [
    {
      "at": "2026-04-29T12:24:33+08:00",
      "type": "artifact_changed",
      "refId": "review",
      "message": "同步审查文档：.limcode/review/a94d3ac048b81c50a6279c1b1119b6fad4c4a14a_deep_review.md"
    },
    {
      "at": "2026-04-29T12:48:54+08:00",
      "type": "artifact_changed",
      "refId": "evidence",
      "message": "归档 Round 4 直接 diff 证据和目标验证结果。"
    },
    {
      "at": "2026-05-07T15:24:08.558Z",
      "type": "artifact_changed",
      "refId": "review",
      "message": "同步审查文档：.limcode/review/frontend-manual-backend-behavior-review.md"
    },
    {
      "at": "2026-05-07T15:25:42.812Z",
      "type": "artifact_changed",
      "refId": "review",
      "message": "同步审查里程碑：round1-manual-content"
    },
    {
      "at": "2026-05-07T15:28:48.016Z",
      "type": "artifact_changed",
      "refId": "review",
      "message": "同步审查里程碑：round2-backend-reference-chain"
    },
    {
      "at": "2026-05-07T15:29:40.604Z",
      "type": "artifact_changed",
      "refId": "review",
      "message": "同步审查里程碑：round3-tests-acceptance"
    },
    {
      "at": "2026-05-07T15:29:53.137Z",
      "type": "artifact_changed",
      "refId": "review",
      "message": "同步审查结论：.limcode/review/frontend-manual-backend-behavior-review.md"
    },
    {
      "at": "2026-05-07T15:51:35.230Z",
      "type": "artifact_changed",
      "refId": "review",
      "message": "同步审查文档：.limcode/review/frontend_manual_backend_behavior_three_round_review.md"
    },
    {
      "at": "2026-05-07T15:53:28.907Z",
      "type": "artifact_changed",
      "refId": "review",
      "message": "同步审查里程碑：round1-frontend-entry-render-chain"
    },
    {
      "at": "2026-05-07T16:20:33.962Z",
      "type": "artifact_changed",
      "refId": "review",
      "message": "同步审查里程碑：round2-backend-behavior-alignment"
    }
  ],
  "stats": {
    "milestonesTotal": 0,
    "milestonesCompleted": 0,
    "todosTotal": 6,
    "todosCompleted": 3,
    "todosInProgress": 0,
    "todosCancelled": 0,
    "activeRisks": 3
  },
  "render": {
    "rendererVersion": 1,
    "generatedAt": "2026-05-07T16:20:33.962Z",
    "bodyHash": "sha256:23ded92879605c30d19020a39da02a1238e9c88cf0fc7766ae48e99c949c278c"
  }
}
<!-- LIMCODE_PROGRESS_METADATA_END -->
