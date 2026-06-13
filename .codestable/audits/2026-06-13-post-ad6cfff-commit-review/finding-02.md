---
doc_type: audit-finding
audit: 2026-06-13-post-ad6cfff-commit-review
finding_id: "maintainability-02"
nature: maintainability
severity: P1
confidence: high
suggested_action: cs-issue
status: resolved
---

# Finding 02：UI 基线截图脚本仍可能把坏页面或半截结果记成功

## 速答

基线截图脚本的目标是给后续 UI 改动留“可信截图”。现在脚本已经修过一部分等待和落点问题，但仍有几处成功判定太宽，可能把错误页、少截页面或清理失败后的产物当成成功。

## 关键证据

- `tests/_scripts_e2e/capture_ui_baseline.py:35` — Python 入口只判断 Chrome 是否存在，没有判断 `_resolve_chrome()` 的 `failure_kind`。
- `tests/_scripts_e2e/capture_ui_baseline.py:92` — 只从 stdout 里收集 JSON 结果，没有校验结果数量必须等于 `FULL_UI_CONTRACT_PATHS`。
- `tests/_scripts_e2e/capture_ui_baseline.py:97` — 只有“零输出”才报错，少输出几页仍可能进入后续成功统计。
- `tests/ui_baseline_capture.mjs:79` — 只检查 `Page.navigate.errorText`。
- `tests/ui_baseline_capture.mjs:93` — 只确认浏览器地址栏路径等于目标路径，没有确认 HTTP 200，也没有确认页面关键 DOM 存在。
- `tests/ui_baseline_capture.mjs:153` — profile 清理失败只向 stderr 打 warning，Python 入口没有把这个 warning 当失败。

## 影响

这不是普通页面 bug，而是“验收证据可能掺假”。如果某个页面实际是 500 错误页，但路径没变，脚本仍可能截图并收进基线。后续大家拿这批图对比，就会以为坏页面是正确基线。

## 修复方向

截图脚本应该更严格：

- Chrome 探测不仅看 `exists`，也要看失败类型。
- JSON 结果数量必须和输入路径数量完全一致。
- 每个页面至少确认 HTTP 状态和关键 DOM 信号。
- profile 清理失败如果说明产物不可信，应让外层脚本 fail loud。

## 建议动作

建议走 `cs-issue`，因为这是测试工具的可信度问题，目标是让失败更早暴露。
