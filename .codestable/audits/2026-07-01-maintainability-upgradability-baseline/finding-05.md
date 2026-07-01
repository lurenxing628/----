---
doc_type: audit-finding
audit: 2026-07-01-maintainability-upgradability-baseline
created: 2026-07-01
finding_id: "maintainability-05"
nature: maintainability
severity: P2
confidence: medium
suggested_action: cs-refactor
status: open
---

# Finding 05：前端重页面升级会偏慢

## 速答

页面层整体不是散装状态，但甘特图等重页面依赖长脚本顺序、全局对象和黑名单过滤。以后如果想替换图组件、拆包或做更现代的前端结构，会比普通页面慢。

## 关键证据

- `.codestable/architecture/ui-gantt.md:30-38` — 甘特前端拆成多个脚本，且文档明确“脚本加载顺序必须保持”。
- `templates/scheduler/gantt.html:281-301` — 模板按固定顺序加载 `frappe-gantt.min.js`、`gantt_*` 多个脚本和 `report_plan_filter.js`。
- `templates/scheduler/gantt.html:99-100`、`templates/scheduler/gantt.html:250-263` — 甘特页面通过 `plan_context_token` 保留模拟方案上下文，不直接暴露裸 `scenario_id`，这是优点。
- `web/viewmodels/scheduler_gantt_public_payload.py:5-7` — 公开甘特数据用内部字段黑名单递归剔除，注释明确新增内部字段必须同步登记。
- `tests/web_pages/test_css_token_source_contract.py:18-29` — CSS 裸色值白名单仍然存在，`ui_contract.css` 允许 294 处、`aps_gantt.css` 允许 115 处，说明样式令牌迁移还没清完。
- 本次静态统计显示 `static/css/ui_contract.css` 约 6169 行，`static/js/table_resize.js` 约 949 行，`static/js/gantt_boot.js` 约 517 行，`templates/components/ui_macros.html` 约 455 行，`templates/scheduler/resource_dispatch.html` 约 446 行。

## 影响

这不是当前用户立刻会遇到的 bug，而是升级成本：

- 脚本顺序错一点，页面可能空白或局部失效。
- 黑名单过滤靠记忆，新增内部字段时容易漏登记。
- 大 CSS / 大 JS 文件会让局部改版阅读成本变高。

## 修复方向

按小步走：

- 先把公开数据改成白名单投影，减少内部字段漏出的可能。
- 再给甘特脚本建立依赖声明或统一启动器，不继续靠模板顺序表达依赖。
- 样式令牌白名单只降不升，逐步把 `ui_contract.css` 和 `aps_gantt.css` 的裸色债清掉。

## 建议动作

走 `cs-refactor`，适合在前端专项改版时顺手纳入，不建议和排产核心结构治理混在一个变更里。
