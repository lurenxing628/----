---
doc_type: audit-finding
audit: 2026-09-13-frontend-ui-ux-review
finding_id: "usability-10"
nature: usability
severity: P2
confidence: high
suggested_action: cs-issue
status: resolved
reviewed: 2026-09-13
---

# Finding 10：排产检查页页脚仍写「预检」，与同页「排产检查」及词表裁决不一致

## 速答

排产前的检查在词表裁决里定名「排产检查」；「预检」是采用前检查的专名，两者是不同关卡、不同后端。工作区里排产检查页的标题、按钮、分页标签已统一为「排产检查」，只剩页脚一句「预检不生成版本、不写入业务或审计数据。」仍用「预检」。

## 关键证据

- 三道不同关卡：`frontend/workbench/app/PreflightAPI.js:7` → `web/routes/workbench/preflight.py:60`（排产检查）；`RunAdoptionAPI.js:3` → `web/routes/workbench/run_candidate_adoption.py:49` adopt-preview（候选采用预检）；`TrialAdoptionAPI.js:3` → `web/routes/workbench/trial_adoption.py:75` adopt-preview（试调采用预检）。
- 裁决：`.codestable/compound/2026-09-13-decision-ui-copy-glossary.md:28`（预检列入业务词不动）、`:92`（检查 / 预览 → 预检）、`:93`（就绪检查 / 排产检查 / 逐工序检查 / 排产前检查 → 排产检查）；`tools/ui_copy_glossary.json:312,315-317` 已是门禁规则。
- 工作区 `frontend/workbench/app/PreflightWorkspace.jsx:82` 标题「排产检查」、`:91` 按钮「开始排产检查」、`:20`「检查明细」、`:75` 步骤条短标签「检查」、`:90` 页脚「预检不生成版本…」。最后一处按裁决应为「排产检查」。

## 影响

同页两个词指同一件事，是术语治理的残留；范围只剩一处。

## 修复方向

页脚一词改「排产检查」；步骤条短标签「检查」是否作为接受的简称，交词表维护人确认后写进 `tools/ui_copy_glossary.json`。

## 建议动作

`cs-issue`（微小），或并入遗留文案改动一起提交。

## 复核记录（2026-09-13）

- 原「同一道关卡三个名字：检查 / 排产检查 / 预检」前提不成立：采用流程的「预检」是另外两道关卡的专名。
- 原建议「统一为『检查』，采用场景叫『采用前检查』」与裁决第 28 / 92 / 93 行相反，会被 `scan_ui_copy` 门禁拦下，撤销。
- 原引用的 `RunAdoptionControls` / `RunAdoptionAction` / `TrialAdoptionControls` 里的「预检」是遗留改动按裁决第 92 行改出来的（HEAD 为「预览」「核实」），不是缺陷。
- 由 P1 降为 P2；原附注「方案名显示内部 label」无代码位置，转索引「观察项 O2」。

## 实施记录（2026-09-13）

- 状态：resolved。`PreflightWorkspace.jsx` 页脚改「排产检查」。
- 详见 [remediation-record.md](remediation-record.md)。
