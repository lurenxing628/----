# 项目进度
- Project: APS Test
- Updated At: 2026-04-29T22:48:10+08:00
- Status: active
- Phase: closure

## 当前摘要

<!-- LIMCODE_PROGRESS_SUMMARY_START -->
- 当前进度：P1 排产债务路线图 13/13 项已完成；最终合并还差工作区收口和干净门禁证明。
- 当前焦点：把批次页全选框修复、最终复审证据和本进度说明按主题提交，然后在干净工作区重新跑质量门禁。
- 最新结论：多路复审没有发现当前 P1 已提交代码存在阻塞合并的 P0/P1/P2 问题；当前未提交的批次页修复是必要尾项，用来避免非待排或全部状态列表还显示“全选”框。full-test-debt 仍是 5 条已登记旧 xfail，本轮不能写成减少。schema v7 会拦住已有重复 Schedule(version, op_id) 的老库，部署前必须先备份并人工清理重复排程行。
- 下一步：先提交批次页尾项和复审证据；确认工作区干净后运行 `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --require-clean-worktree`；通过后再快进合并回 `main`，并在 `main` 上复跑同一门禁。
<!-- LIMCODE_PROGRESS_SUMMARY_END -->

## 关联文档

<!-- LIMCODE_PROGRESS_ARTIFACTS_START -->
- 路线图：`codestable/roadmap/p1-scheduler-debt-cleanup/p1-scheduler-debt-cleanup-roadmap.md`
- 条目清单：`codestable/roadmap/p1-scheduler-debt-cleanup/p1-scheduler-debt-cleanup-items.yaml`
- 映射表：`codestable/roadmap/p1-scheduler-debt-cleanup/drafts/p1-debt-source-map.md`
- 审查：`.limcode/review/a94d3ac048b81c50a6279c1b1119b6fad4c4a14a_deep_review.md`
- 直接证据：`evidence/DeepReview/a94d3ac_round4_git_evidence/`
<!-- LIMCODE_PROGRESS_ARTIFACTS_END -->

## 当前 TODO 快照

<!-- LIMCODE_PROGRESS_TODOS_START -->
- [x] 路线图收口：`p1-scheduler-debt-cleanup` 已标记 completed，13 个 item 全部 done。 `#p1-roadmap`
- [x] 最终复审：多路检查确认 P1 主线、页面、runtime/plugin/Win7 支线没有发现阻塞合并问题。 `#p1-review`
- [x] 批次页尾项：非待排和全部状态列表不再显示表头“全选”框，普通模板和镜像模板已同步。 `#p1-batches-checkbox`
- [ ] 提交收口：把批次页修复、复审证据和本进度说明按主题提交。 `#p1-commit`
- [ ] 干净门禁：工作区干净后运行 `scripts/run_quality_gate.py --require-clean-worktree`。 `#p1-clean-gate`
- [ ] 合并验证：快进合并回 `main` 后，在 `main` 上复跑同一质量门禁。 `#p1-merge-main`
<!-- LIMCODE_PROGRESS_TODOS_END -->

## 项目里程碑

<!-- LIMCODE_PROGRESS_MILESTONES_START -->
### p1-scheduler-debt-cleanup-closeout · P1 排产债务收尾
- 状态：in-progress
- 记录时间：2026-04-29T22:48:10+08:00
- 开始时间：2026-04-27T23:43:00+08:00
- 关联 TODO：p1-roadmap, p1-review, p1-batches-checkbox, p1-commit, p1-clean-gate, p1-merge-main
- 关联文档：
  - 路线图：`codestable/roadmap/p1-scheduler-debt-cleanup/p1-scheduler-debt-cleanup-roadmap.md`
  - 审查：`.limcode/review/a94d3ac048b81c50a6279c1b1119b6fad4c4a14a_deep_review.md`
- 摘要:
P1 排产债务路线图已经完成条目收口，当前分支也已经处理 schema v7、排产落库、冻结窗口、summary/result_summary、插件 reset、Win7 启停链和 P1-14 最终尾项。合并前剩余工作不是继续扩大 P1，而是把当前未提交尾项收干净，并用干净工作区质量门禁绑定最终 HEAD。
- 下一步：提交当前未提交修复和证据，跑 clean gate，通过后快进合并回 `main`。
<!-- LIMCODE_PROGRESS_MILESTONES_END -->

## 风险与阻塞

<!-- LIMCODE_PROGRESS_RISKS_START -->
- risk-dirty-worktree | active | 当前工作区还有未提交修复和证据文件，质量门禁只能得到 passed_but_unbound，不能当作最终合并证明。
- risk-schema-v7-duplicate-schedule | active | schema v7 会阻止已有重复 Schedule(version, op_id) 的老库继续升级；部署前要先备份并清理重复排程行，这属于数据保护，不是代码故障。
- risk-full-test-debt-unchanged | active | 当前 full-test-debt 仍是 5 条已登记旧 xfail；本轮 P1 不能写成减少 full-test-debt。
<!-- LIMCODE_PROGRESS_RISKS_END -->

## 最近更新

<!-- LIMCODE_PROGRESS_LOG_START -->
- 2026-04-29T12:24:33+08:00 | artifact_changed | review | 同步审查文档：`.limcode/review/a94d3ac048b81c50a6279c1b1119b6fad4c4a14a_deep_review.md`
- 2026-04-29T12:48:54+08:00 | artifact_changed | review | 归档 Round 4 直接 diff 证据和目标验证结果。
- 2026-04-29T22:48:10+08:00 | progress_fixed | progress | 改写当前进度为 P1 收尾语境，移除英文截断摘要和旧任务当前焦点。
<!-- LIMCODE_PROGRESS_LOG_END -->

<!-- LIMCODE_PROGRESS_METADATA_START -->
{
  "formatVersion": 1,
  "kind": "limcode.progress",
  "projectId": "aps-test",
  "projectName": "APS Test",
  "createdAt": "2026-04-07T06:34:24.925Z",
  "updatedAt": "2026-04-29T22:48:10+08:00",
  "status": "active",
  "phase": "closure",
  "currentFocus": "P1 排产债务收尾：提交批次页尾项、最终复审证据和进度说明，然后跑干净工作区质量门禁。",
  "latestConclusion": "P1 排产债务路线图 13 个条目已经全部 done，主文档已 completed。多路复审没有发现当前 P1 已提交代码存在阻塞合并的 P0/P1/P2 问题。当前未提交的批次页修复是必要尾项，用来避免非待排或全部状态列表还显示表头全选框。full-test-debt 仍是 5 条已登记旧 xfail，本轮不能写成减少。schema v7 会拦住已有重复 Schedule(version, op_id) 的老库，部署前必须先备份并人工清理重复排程行。",
  "currentBlocker": "工作区仍有未提交修复和证据文件，最终 clean gate 尚未绑定干净 HEAD。",
  "nextAction": "按主题提交当前未提交修复和证据；工作区干净后运行 PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --require-clean-worktree；通过后快进合并回 main，并在 main 上复跑同一门禁。",
  "activeArtifacts": {
    "roadmap": "codestable/roadmap/p1-scheduler-debt-cleanup/p1-scheduler-debt-cleanup-roadmap.md",
    "items": "codestable/roadmap/p1-scheduler-debt-cleanup/p1-scheduler-debt-cleanup-items.yaml",
    "sourceMap": "codestable/roadmap/p1-scheduler-debt-cleanup/drafts/p1-debt-source-map.md",
    "review": ".limcode/review/a94d3ac048b81c50a6279c1b1119b6fad4c4a14a_deep_review.md",
    "evidence": "evidence/DeepReview/a94d3ac_round4_git_evidence/"
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
  "milestones": [
    {
      "id": "p1-scheduler-debt-cleanup-closeout",
      "title": "P1 排产债务收尾",
      "status": "in-progress",
      "summary": "P1 排产债务路线图已经完成条目收口，合并前剩余工作是提交当前未提交尾项并跑干净工作区质量门禁。",
      "relatedTodoIds": [
        "p1-roadmap",
        "p1-review",
        "p1-batches-checkbox",
        "p1-commit",
        "p1-clean-gate",
        "p1-merge-main"
      ],
      "relatedArtifacts": {
        "roadmap": "codestable/roadmap/p1-scheduler-debt-cleanup/p1-scheduler-debt-cleanup-roadmap.md",
        "review": ".limcode/review/a94d3ac048b81c50a6279c1b1119b6fad4c4a14a_deep_review.md"
      },
      "startedAt": "2026-04-27T23:43:00+08:00",
      "recordedAt": "2026-04-29T22:48:10+08:00",
      "nextAction": "提交当前未提交修复和证据，跑 clean gate，通过后快进合并回 main。"
    }
  ],
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
      "at": "2026-04-29T22:48:10+08:00",
      "type": "progress_fixed",
      "refId": "progress",
      "message": "改写当前进度为 P1 收尾语境，移除英文截断摘要和旧任务当前焦点。"
    }
  ],
  "stats": {
    "milestonesTotal": 1,
    "milestonesCompleted": 0,
    "todosTotal": 6,
    "todosCompleted": 3,
    "todosInProgress": 0,
    "todosCancelled": 0,
    "activeRisks": 3
  },
  "render": {
    "rendererVersion": 1,
    "generatedAt": "2026-04-29T22:48:10+08:00",
    "bodyHash": "manual-p1-closeout-progress-2026-04-29"
  }
}
<!-- LIMCODE_PROGRESS_METADATA_END -->
