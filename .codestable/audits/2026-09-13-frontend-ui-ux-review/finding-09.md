---
doc_type: audit-finding
audit: 2026-09-13-frontend-ui-ux-review
finding_id: "usability-09"
nature: usability
severity: P1
confidence: high
suggested_action: cs-issue
status: resolved
reviewed: 2026-09-13
---

# Finding 09：未提交改动把英文开发者信息 `dependency not wired: …` 当界面兜底文案（已在工作区修复）

## 速答

HEAD 035f9cce 里这串英文一处都没有。工作区遗留的一份未提交改动把 HEAD 中含「尚未接入」的中文兜底替换成 `dependency not wired: window.RunJobPanel` 这类英文开发者信息，共 59 处、31 个文件，其中 29 处、18 个文件位于按钮禁用原因、页脚、状态文字等可见位置，非技术排产员会直接看到。这不是历史债，是当日引入的文案回退。

## 关键证据

- `git grep "dependency not wired" HEAD -- frontend/workbench/app/` 为 0；工作区 `grep -rn` 为 59 处。
- 替换来源：遗留改动把 HEAD 的「候选排产运行服务尚未接入，不能开始排产。」等改成英文，例如 `frontend/workbench/app/PreflightWorkspace.jsx:58,90`。
- 词表裁决 `.codestable/compound/2026-09-13-decision-ui-copy-glossary.md:67`：「接入 / 尚未接入」统一为「尚未开通」，开发期守卫不得显示；`frontend/workbench/app/WorkbenchTerms.js:23` 已备 `outcomes.unavailable = '此功能尚未开通。'`。
- 可见路径无过滤：`frontend/workbench/app/ResourceControls.jsx:22-34` Button 把 reason 原样放进 title、行内 span 与隐藏描述。抛错路径有过滤：`WorkbenchReferences.jsx:13-28` 的 `technical()` 把技术文案折进折叠的「原始错误信息」，属既定处理。

## 影响

降级态本身已是异常，此刻用户最需要可执行的下一步，却看到无法理解的英文。触发条件：脚本加载失败或依赖未注入的降级状态。

## 处置（2026-09-13，工作区，未提交）

- 29 处可见位置全部改为 `window.WorkbenchTerms.outcomes.unavailable`（18 个文件）；30 处 throw / check 路径保留技术信息，由 WorkbenchError 折叠。
- 同步更新断言：`tests/workbench/test_run_history_widgets.py:63`、`tests/workbench/trial_widgets_probe.cjs:237`、`tests/workbench/run_history_widgets_probe.cjs:119-120`。
- 重建 `static/workbench`；`python -m tools.scan_ui_copy --paths frontend/workbench/app` 0 处；`test_run_history_widgets` / `test_trial_widgets` / `test_workbench_plain_language` / `test_el_material_contracts` / `test_ui_refinement_node_contracts` 共 13 个用例通过。

## 建议动作

随遗留改动一起提交，不再单独立 issue。

## 复核记录（2026-09-13）

- 原「30+ 文件把英文当界面兜底」的归因错误：HEAD 中不存在，全部来自当日未提交改动。
- 原建议「新增小工具函数，技术细节改投 console.error」未采用：探针合同要求页面零 console 错误（`tests/workbench/test_run_history_widgets.py:58`），且 HEAD 版本本就不含技术名，直接用词表模板即可。
- 数字精确化：59 处 / 31 文件，其中 29 处 / 18 文件可见。

## 实施记录（2026-09-13）

- 状态：resolved。（此前已修）29 处可见位置改 `WorkbenchTerms.outcomes.unavailable`。
- 详见 [remediation-record.md](remediation-record.md)。
