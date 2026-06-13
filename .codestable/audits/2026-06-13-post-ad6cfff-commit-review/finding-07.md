---
doc_type: audit-finding
audit: 2026-06-13-post-ad6cfff-commit-review
finding_id: "bug-07"
nature: bug
severity: P1
confidence: medium
suggested_action: cs-issue
status: resolved
---

# Finding 07：周派工单打印会把“外协”开头的真实设备名并入外协兜底页

## 速答

周派工单打印按资源分组，一台设备一页。当前 machine 视图里，只要设备显示名以“外协”开头，就会被改成外协兜底标签。这会误伤真实设备名，比如“外协机01”。

## 关键证据

- `core/services/scheduler/week_plan_print_sheet.py:29` — `_resource_label` 从行里的分组列取展示名。
- `core/services/scheduler/week_plan_print_sheet.py:31` — 注释说明 machine 视图里外协行统一归兜底段。
- `core/services/scheduler/week_plan_print_sheet.py:32` — 判断条件是 `group_column == "设备" and label.startswith("外协")`。
- 当前代码没有看到“设备名称不能以外协开头”的业务约束。

## 影响

如果现场真的有一台设备叫“外协机01”，打印时会被合并进“外协/未分配”页。计划员拿到纸面后，会把真实设备任务看成外协或未分配任务，现场派工容易错。

置信度标 medium，是因为需要真实数据里出现这种命名才会触发；但代码条件本身明确存在误判。

## 修复方向

不要靠中文前缀判断外协身份。应该使用更稳定的字段，例如 supplier_id、resource_type、machine_id 是否为空、或后端已经明确标出的外协标记。打印分组显示名可以叫“外协/未分配”，但判断身份不应靠显示文案。

## 建议动作

建议走 `cs-issue`，因为这是打印分组的业务误判。
