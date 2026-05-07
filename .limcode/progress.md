# 项目进度
- Project: APS Test
- Updated At: 2026-05-08T01:57:53+08:00
- Status: active
- Phase: implementation

## 当前摘要

<!-- LIMCODE_PROGRESS_SUMMARY_START -->
- 当前进度：前端说明书字段级补强已完成主体提交；本轮根据复审意见追加最小修复，正在收口供应商列顺序、提醒去向、版本规则和证据状态。
- 当前焦点：把复审指出的“页面说明会误导填表”和“证据文件仍是旧红灯”的问题收掉，再绑定最终干净质量门禁。
- 最新结论：说明书主流程和页面说明已经按当前后端行为补清：齐套检查是报错并停止，不会过滤后继续排；批次自动生成工序的提醒是当前页局部提醒；正式/模拟排产结果提醒属于历史版本提醒，可到系统历史查看；供应商、工种、日历、工序工时等字段级拒绝条件已经进入说明和测试合同。
- 当前阻塞：无已知代码阻塞。本进度文件不是机器证明，最终 clean gate 以 `scripts/run_quality_gate.py --require-clean-worktree` 和忽略目录中的 `evidence/QualityGate/quality_gate_manifest.json` 为准。
- 下一步：提交本轮 follow-up 后，在干净工作区复跑质量门禁；如门禁通过，即可把本轮说明书补强视为已闭环。
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
- [x] 提交收口：说明书、页面说明、模板刷新、提醒口径和初步证据已按主题提交；本轮 follow-up 将作为补充提交。  `#p1-commit`
- [ ] 干净门禁：follow-up 提交后运行 scripts/run_quality_gate.py --require-clean-worktree。  `#p1-clean-gate`
- [ ] 合并验证：快进合并回 main 后，在 main 上复跑同一质量门禁。  `#p1-merge-main`
<!-- LIMCODE_PROGRESS_TODOS_END -->

## 项目里程碑

<!-- LIMCODE_PROGRESS_MILESTONES_START -->
<!-- 暂无里程碑 -->
<!-- LIMCODE_PROGRESS_MILESTONES_END -->

## 风险与阻塞

<!-- LIMCODE_PROGRESS_RISKS_START -->
- risk-dirty-worktree | mitigated | 工作区收口风险：上一轮 clean gate 已通过；本轮 follow-up 修改尚需提交后重新跑 clean gate，最终以机器 manifest 和最终回复为准。
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
- 2026-05-08T01:57:53+08:00 | artifact_changed | progress | 根据复审意见更新前端说明书补强收口状态：供应商列顺序、提醒去向、版本规则和证据状态进入 follow-up 收口。
<!-- LIMCODE_PROGRESS_LOG_END -->

<!-- LIMCODE_PROGRESS_METADATA_START -->
{
  "formatVersion": 1,
  "kind": "limcode.progress",
  "projectId": "aps-test",
  "projectName": "APS Test",
  "createdAt": "2026-04-07T06:34:24.925Z",
  "updatedAt": "2026-05-08T01:57:53+08:00",
  "status": "active",
  "phase": "implementation",
  "currentFocus": "把复审指出的“页面说明会误导填表”和“证据文件仍是旧红灯”的问题收掉，再绑定最终干净质量门禁。",
  "latestConclusion": "说明书主流程和页面说明已经按当前后端行为补清：齐套检查是报错并停止，不会过滤后继续排；批次自动生成工序的提醒是当前页局部提醒；正式/模拟排产结果提醒属于历史版本提醒，可到系统历史查看；供应商、工种、日历、工序工时等字段级拒绝条件已经进入说明和测试合同。",
  "currentBlocker": "无已知代码阻塞。本进度文件不是机器证明，最终 clean gate 以 scripts/run_quality_gate.py --require-clean-worktree 和忽略目录中的 evidence/QualityGate/quality_gate_manifest.json 为准。",
  "nextAction": "提交本轮 follow-up 后，在干净工作区复跑质量门禁；如门禁通过，即可把本轮说明书补强视为已闭环。",
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
      "content": "提交收口：说明书、页面说明、模板刷新、提醒口径和初步证据已按主题提交；本轮 follow-up 将作为补充提交。",
      "status": "completed"
    },
    {
      "id": "p1-clean-gate",
      "content": "干净门禁：follow-up 提交后运行 scripts/run_quality_gate.py --require-clean-worktree。",
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
      "description": "上一轮 clean gate 已通过；本轮 follow-up 修改尚需提交后重新跑 clean gate，最终以机器 manifest 和最终回复为准。",
      "status": "mitigated"
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
    },
    {
      "at": "2026-05-08T01:57:53+08:00",
      "type": "artifact_changed",
      "refId": "progress",
      "message": "根据复审意见更新前端说明书补强收口状态：供应商列顺序、提醒去向、版本规则和证据状态进入 follow-up 收口。"
    }
  ],
  "stats": {
    "milestonesTotal": 0,
    "milestonesCompleted": 0,
    "todosTotal": 6,
    "todosCompleted": 4,
    "todosInProgress": 0,
    "todosCancelled": 0,
    "activeRisks": 2
  },
  "render": {
    "rendererVersion": 1,
    "generatedAt": "2026-05-08T01:57:53+08:00",
    "bodyHash": "sha256:manual-followup-refresh-2026-05-08"
  }
}
<!-- LIMCODE_PROGRESS_METADATA_END -->
