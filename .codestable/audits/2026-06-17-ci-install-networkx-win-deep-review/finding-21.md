# Finding 21：超期清单行级跳转丢日期，用户看到的操作入口会被禁用

- 优先级：P1 阻塞
- 结论：超期清单能展示行数据，但行里的“定位甘特 / 回资源派工 / 查看计划和现场实际”需要日期范围。当前超期页面上下文把 `start_date` / `end_date` 固定为 `None`，所以这些行级链接会被禁用。

## 根因

报表页 `_version_report_context()` 刻意不从页面 URL 传播 `date_from/date_to`，但超期清单生成行级工作台链接时仍使用同一套“日期必需”的工作台链接 helper。结果是：报表有行，但链接上下文没有日期，helper 只能返回禁用原因。

大白话说：页面告诉用户“这批超期了”，旁边又给按钮说“去甘特图看”。但按钮生成时没带日期，所以到了最后只能变成灰色不可点。

## 调用链

- `reports_page_support.py::overdue_page_context()`
- `_version_report_context()` 生成 `start_date=None` / `end_date=None`
- `_publish_report_context(... date_from=None, date_to=None ...)`
- `decorate_overdue_rows()`
- `build_workbench_link()`
- 模板根据 `link.disabled` 渲染禁用 span

## 证据

- `web/routes/reports_page_support.py:93-114`：版本报表上下文固定 `start_date=None`、`end_date=None`、`date_source="none"`。
- `web/routes/reports_page_support.py:216-238`：超期页面用这些空日期发布 report context 并装饰行。
- `web/viewmodels/scheduler_reports_workbench.py:290-301`：每行生成 `定位甘特`、`回资源派工`、`查看计划和现场实际`、`查看为什么晚了`。
- `web/viewmodels/scheduler_workbench_links.py:295-301`：Gantt、资源派工、现场实际这类目标缺日期时返回“还没有确认日期范围...”。
- `templates/reports/overdue.html:167-171`：链接禁用或无 URL 时渲染为 disabled span。
- 现有测试 `tests/web_pages/test_reports_workbench_backlink_contract.py::test_overdue_rows_link_to_workbench_with_batch_context` 通过，但没有覆盖行级链接在真实超期页上下文里被禁用的反例。

## 影响

- 用户从超期清单无法直接跳到甘特、资源派工、现场实际页面定位问题。
- 报表和工作台之间的“闭环操作”不成立。

## 建议

- 超期清单行级链接需要有明确日期来源：使用版本 span、行自身计划跨度、或只对不需要日期的目标放开。
- 如果产品决定超期页不传播日期，就不要显示这些看似可操作的入口，改成清楚的解释。
- 增加页面级测试：有超期行时，期望可点击的链接必须有 URL；期望禁用时必须有明确业务原因。
