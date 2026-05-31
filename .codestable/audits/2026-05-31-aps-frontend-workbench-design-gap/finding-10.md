---
doc_type: audit-finding
audit: 2026-05-31-aps-frontend-workbench-design-gap
finding_id: "design-gap-10"
classification: NOW_LAYOUT_ONLY
nature: arch-drift
severity: P2
confidence: high
status: open
suggested_action: cs-roadmap
---

# Finding 10：roadmap/items 已补关键边界，后续仍要逐条写硬验收

## 结论

设计稿已经写得比较细。当前 roadmap/items 已经补上 A/B/C 顺序、完整目标页字典、非正式方案写入护栏、Excel 不预览、计划员代录现场事实、Win7/Python 3.8/Chrome 109/离线约束等关键边界，所以这条不再挡第一轮开工。后续每个 feature design 仍要把“第一版不做什么”“空状态怎么说”“哪些字段不能外露”写成更硬的验收。

## 证据

- 已补：非正式方案下不输出写入按钮、表单 action、API URL、Excel 导入 URL、模板下载 URL 或任何 `data-*` 写入地址。
- 已补：跨页参数统一翻译，覆盖 `date_from/date_to`、`start_date/end_date`、资源视角和甘特定位。
- 已补：资源派工明确是计划员代录现场事实，短期不新增现场员工账号、多人权限、“我的任务”、扫码、推送、审批。
- 已补：Excel 短期直接导入，不做预览或二次确认。
- 已补：甘特资源负荷摘要、延期解释接现场事实都放到第二阶段增强。
- 仍建议补强：每个 item 的第一版禁区、空状态、加载失败、数据不足、公开 payload 和导出字段边界。

## 影响

实现时剩下的风险主要是 feature design 写得不够硬：只加按钮但没加空状态，或者页面上不露内部字段了、导出和公开 payload 却还露内部字段。另一类风险是第一版顺手加了甘特左侧任务简表或现场异常按钮，反而偏离当前已拍板边界。

## 建议

在进入单个 feature design 前，把对应 item 再落成更硬的验收清单：

- 每个 item 增加“第一版不做什么”。
- 每个新增区域都写空状态、加载失败、数据不足。
- 对写入类页面，列出按钮、手填、Excel、API、`data-*` URL 五类入口。
- 对跨页跳转，列出源页面、目标页面、参数名、目标页如何解析。
- 对普通用户可见字段，把页面、导出列、公开 payload 一起纳入。
