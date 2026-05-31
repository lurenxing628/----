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

# Finding 10：roadmap/items 没有完整承接设计稿首版边界

## 结论

设计稿已经写得比较细，但 roadmap/items 有几处只写了方向，没有把“第一版不做什么”“空状态怎么说”“哪些字段不能外露”落成可执行验收。这个问题不一定会立刻导致 bug，但会让实现时边界漂移。

## 证据

- 设计稿要求非正式方案下所有写入入口和 `data-*` URL 都不可用；items 更偏按钮层，没有完整列出 API 和隐藏 URL。
- 设计稿要求首页有资源高负荷风险卡；roadmap 的 `WorkbenchRiskCard.kind` 没有明确 `resource_overload`。
- 设计稿要求最近排产结果改成交接摘要；roadmap/items 没有明确 `handover_summary` 字段。
- 设计稿有完整跨页参数矩阵；items 没有把 `date_from/date_to` 和 `start_date/end_date` 的互转写清楚。
- 设计稿把甘特左侧任务简表、保存视图、模拟沙盒放到第二阶段；items 没有把这些写成第一版禁区。
- 设计稿要求资源派工“双车道”可被测试断言；items 里更像“视觉上分清”。
- 设计稿要求每个新增区都有空状态、加载失败、数据不足状态；items 只在部分条目写了。
- 设计稿要求普通用户可见页面、表格、详情、按钮、导出公开列、对外 payload 都不能显示内部字段；items 主要写页面文案，没有完全覆盖导出和 payload。

## 影响

实现时会出现两种风险：一种是做少了，比如只加按钮但没加空状态；另一种是做多了，比如第一版顺手加了甘特左侧任务简表或现场异常按钮，反而偏离设计稿。

## 建议

在进入单个 feature 前，先把 items 补成更硬的验收清单：

- 每个 item 增加“第一版不做什么”。
- 每个新增区域都写空状态、加载失败、数据不足。
- 对写入类页面，列出按钮、手填、Excel、API、`data-*` URL 五类入口。
- 对跨页跳转，列出源页面、目标页面、参数名、目标页如何解析。
- 对普通用户可见字段，把页面、导出列、公开 payload 一起纳入。
