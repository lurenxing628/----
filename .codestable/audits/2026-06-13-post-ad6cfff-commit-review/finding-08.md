---
doc_type: audit-finding
audit: 2026-06-13-post-ad6cfff-commit-review
finding_id: "bug-08"
nature: bug
severity: P1
confidence: high
suggested_action: cs-issue
status: resolved
---

# Finding 08：甘特 URL 预筛、清筛选和负荷条带使用的数据范围不一致

## 速答

甘特页现在有两层筛选：后端根据 URL 参数先裁一包数据，前端再在这包数据上本地筛选。用户从 URL 带筛选进入后，点击清筛选只能清前端状态，不能把后端已经裁掉的数据变回来。同时，负荷条带和弹窗还在用初始化数据或全量任务，可能和当前甘特图不同步。

## 关键证据

- `web/routes/domains/scheduler/scheduler_gantt.py:69` — 页面 URL 会读取 `gantt_batch` / `gantt_resource`。
- `web/routes/domains/scheduler/scheduler_gantt.py:343` — 数据接口也会读取 `gantt_batch` / `gantt_resource`。
- `web/routes/domains/scheduler/scheduler_gantt.py:345` — 如果有 `gantt_batch`，后端传 `batch_id` 裁数据。
- `templates/scheduler/gantt.html:252` — 前端 DOM 里的 `data-url` 已经是带筛选的数据 URL。
- `static/js/gantt_boot.js:337` — 前端只把首次返回的 `tasks` 放进 `state.allTasks`。
- `static/js/gantt_legend.js:293` — 点击图例批次只切换本地 `state.ui.filterBatch`。
- `static/js/gantt_render.js:290` — 甘特图用 `applyFilters(state.allTasks)` 本地过滤。
- `static/js/gantt_load_strip.js:35` — 负荷条带保存初始化 `resource_load`。
- `static/js/gantt_load_strip.js:87` — 负荷弹窗读取 `state.allTasks`，不是当前过滤后的任务。
- `static/js/gantt_load_strip.js:238` — 渲染负荷条带时仍用 `strip.rows`。

## 影响

典型场景是：用户打开 `/scheduler/gantt?...&gantt_batch=B2`，页面只加载 B2。然后用户点 B2 图例想清掉筛选，前端状态清了，但 `state.allTasks` 里本来就只有 B2，所以图不会回到全量。

另一个场景是：用户筛选到某个批次或资源，甘特任务变了，但负荷条带还展示初始化范围的资源负荷，弹窗也可能列出当前筛选范围外的任务。

## 修复方向

需要统一“全量数据”和“当前过滤数据”的来源：

- 要么首次始终拉全量，URL 筛选只作为前端初始筛选状态。
- 要么清筛选时重新请求不带 `gantt_batch/gantt_resource` 的数据。
- 负荷条带渲染和弹窗要消费当前过滤后的任务/负荷范围，不能继续用初始化快照。

## 建议动作

建议走 `cs-issue`，因为这是甘特页面用户操作后数据范围不一致。
