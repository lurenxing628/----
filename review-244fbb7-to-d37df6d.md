# 深度 Review 结论：244fbb7e5cfe68713e59b15a741d8e459657b207..d37df6dc8fc0a819a8c415809e733c0abd41c560

## 结论摘要

本次 review 只基于指定提交区间：

```text
244fbb7e5cfe68713e59b15a741d8e459657b207
..d37df6dc8fc0a819a8c415809e733c0abd41c560
```

未把当前工作区未提交改动作为事实依据。

总体结论：**不建议按当前形态合入 / 发布**。

这次变更表面上是大幅删除 Gantt 手工调整、场景预览、adapter、zoom、迁移和测试等内容，但实际不是一次优雅的功能收口，而更像一次缺少废弃协议的硬回滚。核心问题不是“删了很多代码”，而是删除了关键边界、迁移历史、URL 合同、只读保护、vendor patch 说明和质量门禁，却没有提供显式 tombstone、fail-fast、兼容迁移或替代测试。

本次 diff 规模：

```text
96 files changed, 192 insertions(+), 9439 deletions(-)
```

主要阻断风险：

1. `CURRENT_SCHEMA_VERSION` 从 14 降到 11，破坏迁移版本单调性。
2. 已升级到 v12/v13/v14 的数据库会被 d37 静默当作“无需迁移”。
3. 只读甘特图合同被破坏，页面重新变成可拖拽但不可保存。
4. 旧 `scenario_id` 预览链接会被静默忽略，展示普通正式/候选排程。
5. `gantt_zoom` URL 语义被删除，旧分钟级链接静默降级。
6. Frappe Gantt vendor patch 大幅回退，尤其显式午夜结束时间会被错误加一天。
7. 大量高价值回归测试和 quality gate required suite 被同步删除/削弱。
8. 前端数据合同错误可被空数组、泛化 HTTP 错误或 degradation 掩盖。
9. `static/js/gantt_render.js` 仍有 943 行，超过 500 行质量门禁目标，职责过重。
10. `.codestable` 架构/roadmap/vendor patch 合同文档被删除，但没有替代 ADR / closeout。

---

## P0 / 阻断问题

### P0-1：Schema 版本从 14 倒退到 11，旧 v12/v13/v14 数据库会被静默接受

#### 证据

244 版本：

```text
core/infrastructure/migration_state.py:8
CURRENT_SCHEMA_VERSION = 14
```

244 迁移注册了 v12/v13/v14：

```text
core/infrastructure/migrations/__init__.py:18-20
from .v12 import run as run_v12
from .v13 import run as run_v13
from .v14 import run as run_v14
```

d37 版本变成：

```text
core/infrastructure/migration_state.py:8
CURRENT_SCHEMA_VERSION = 11
```

d37 迁移注册表只剩 v1-v11：

```text
core/infrastructure/migrations/__init__.py:20-32
MIGRATIONS = {
    ...
    11: run_v11,
}
```

迁移触发条件只有“小于当前版本”：

```text
core/infrastructure/database.py:157
if current_version < CURRENT_SCHEMA_VERSION:
```

没有任何：

```python
if current_version > CURRENT_SCHEMA_VERSION:
    raise ...
```

#### 影响

如果某个部署已经跑过 244，对应数据库 `SchemaVersion.version` 可能已经是 12/13/14。切到 d37 后：

```text
14 < 11 == false
```

结果是：

- 不迁移；
- 不降级；
- 不报错；
- 不备份；
- 不提示“数据库版本高于当前代码”；
- 已删除的 `ScheduleAdjustment*` 表可能残留在库里但不再由 schema/model/service 管理。

这违反迁移系统最基本的单调性和 fail-fast 原则，是典型静默回退。

#### 建议

不要把 `CURRENT_SCHEMA_VERSION` 从 14 降回 11。

更合理做法：

1. 保留 v12/v13/v14 迁移文件和注册表，保证历史升级链连续。
2. 如果决定下线 adjustment，新增 v15 做显式 decommission：
   - 保留旧表但标记废弃；或
   - 迁移/归档旧数据；或
   - 显式 drop 旧表，并说明备份策略。
3. 在 `ensure_schema()` 中加入高版本数据库 fail-fast：

```python
if current_version > CURRENT_SCHEMA_VERSION:
    raise MigrationContractError(...)
```

---

### P0-2：只读甘特图合同被破坏，页面变成“能拖但不保存”

#### 证据

d37 模板不再加载 adapter / zoom：

```text
templates/scheduler/gantt.html:253-263
frappe-gantt.min.js
gantt.js
gantt_color.js
gantt_outline.js
gantt_contract.js
gantt_popup_fit.js
gantt_render.js
gantt_ui.js
gantt_boot.js
```

d37 直接实例化 Frappe Gantt，没有传只读参数：

```text
static/js/gantt_render.js:857-860
const gantt = new Gantt("#gantt", tasks, {
  view_mode: ...,
  language: "zh",
  popup_trigger: "click",
```

缺失：

```text
readonly
readonly_dates
readonly_progress
```

d37 的 vendor 文件中也没有这些关键词：

```text
static/js/frappe-gantt.min.js
readonly: 0
readonly_dates: 0
readonly_progress: 0
```

页面提示只剩配色/超期说明：

```text
templates/scheduler/gantt.html:147-155
```

不再有“当前为查看模式 / 拖动拉伸不会修改计划”的明确提示。

#### 影响

用户可以在浏览器里拖动、拉伸任务条，甚至看起来像修改了排程，但：

- 不会保存；
- 不会生成草稿；
- 不会校验；
- 不会发布正式版本；
- 刷新后恢复原排程。

这比“没有调整功能”更危险，因为它制造了假编辑体验。

#### 建议

如果 d37 的目标是只读甘特：

- 恢复一个薄 adapter 层；或
- 在 `new Gantt(...)` 层显式传入只读参数；
- vendor 层必须支持 readonly；
- CSS 可作为兜底隐藏 resize/progress handles；
- 页面恢复明确提示：当前是查看模式，拖动/拉伸不会修改计划。

---

### P0-3：旧 `scenario_id` 预览链接会被静默忽略，展示普通排程

#### 244 旧链路证据

244 会读取 `scenario_id`：

```text
web/routes/domains/scheduler/scheduler_gantt.py:76-104
_get_scenario_id_arg()
resolve_plan_view(..., scenario_id)
```

页面 route 也会传递：

```text
web/routes/domains/scheduler/scheduler_gantt.py:137-160
scenario_id = _get_scenario_id_arg()
plan_resolution = _resolve_plan_context(..., scenario_id)
```

模板下发 scenario 数据：

```text
templates/scheduler/gantt.html:276-280
data-scenario-id
data-scenario-preview
data-scenario-label
data-gantt-mode
data-zoom-level
```

JS 请求 data API 时带上 scenario：

```text
static/js/gantt_boot.js:207
scenarioId: ds.scenarioId || ""

static/js/gantt_boot.js:282
if (cfg.scenarioId) url.searchParams.set("scenario_id", ...)
```

#### d37 当前证据

d37 页面 route 只读这些参数：

```text
web/routes/domains/scheduler/scheduler_gantt.py:110-115
view
week_start
start_date
end_date
plan_role
```

没有 `scenario_id`。

d37 data API 也只传：

```text
web/routes/domains/scheduler/scheduler_gantt.py:183-197
view
week_start
offset_weeks
start_date
end_date
version
include_history
plan_role
plan_query_service
```

没有 `scenario_id`。

模板 data attrs 也没有 scenario：

```text
templates/scheduler/gantt.html:233-248
data-url
data-view
data-week-start
data-start-date
data-end-date
data-offset
data-version
data-plan-role
...
```

#### 影响

旧链接：

```text
/scheduler/gantt?version=12&plan_role=candidate_x&scenario_id=abc
```

在 d37 中不会报错，也不会提示“模拟方案预览已下线”，而是正常打开，并展示普通 `version + plan_role` 对应的数据。

这是 silent wrong-data：用户以为看到的是模拟方案预览，实际看到的是正式/候选排程。

#### 建议

如果 scenario preview 已下线：

- `/scheduler/gantt` 检测到 `scenario_id` 时返回 410 Gone 或阻断式提示；
- `/scheduler/gantt/data` 检测到 `scenario_id` 时返回 410 JSON；
- 文案明确：模拟方案预览链接已失效/功能已下线；
- 不允许静默展示普通排程。

如果 scenario preview 仍是产品能力，则应恢复：

```text
resolve_plan_view -> scenario rows -> template attrs -> JS data fetch
```

---

## P1 / 高风险问题

### P1-1：Frappe Gantt vendor patch 大量回退，午夜结束时间会被错误加一天

#### 证据

d37 vendor 仍保留了短任务宽度和 hitbox：

```text
static/js/frappe-gantt.min.js:1
draw_hitbox()
bar-hit
```

但这些关键 patch 已消失：

```text
readonly: 0
readonly_dates: 0
readonly_progress: 0
step_ms: 0
step_minutes: 0
_end_is_date_only: 0
Fifteen Minute: 0
Five Minute: 0
One Minute: 0
```

d37 vendor 仍有无条件午夜扩展逻辑：

```text
static/js/frappe-gantt.min.js:1
h.get_date_values(t._end).slice(3).every((t=>0===t)) && (t._end=h.add(t._end,24,"hour"))
```

#### 影响

合法任务：

```text
start = 2026-05-11 23:24:00
end   = 2026-05-12 00:00:00
```

本应是 36 分钟。

d37 会把 end 改成：

```text
2026-05-13 00:00:00
```

结果 36 分钟短任务被画成 24 小时 36 分钟。

这是排程可视化严重错误，不是可接受的防御性兜底。

#### 建议

- 恢复 `_end_is_date_only` 区分：
  - 纯日期 `2026-05-12` 可以按整天；
  - 显式 datetime `2026-05-12 00:00:00` 不得自动加一天。
- 恢复 vendor patch 文档。
- 恢复最小测试：
  - 普通 36 分钟短任务；
  - 跨午夜且 end 为 `00:00:00`；
  - `.bar-hit >= 12px`；
  - readonly；
  - Hour / Fifteen / Five / One Minute。

---

### P1-2：`gantt_zoom` URL 契约和分钟级缩放被删除，旧链接静默失效

#### 证据

244 会读取 `gantt_zoom`：

```text
static/js/gantt_ui.js:110-116
const zoomParam = params.get("gantt_zoom")
```

244 persist 时写 `gantt_zoom` 并清理 legacy 参数：

```text
static/js/gantt_ui.js:172-175
setOrDelete("gantt_zoom", ...)
url.searchParams.delete("gantt_vm")
url.searchParams.delete("view_mode")
```

d37 只读 `gantt_vm/view_mode`：

```text
static/js/gantt_ui.js:54-58
const vm = params.get("gantt_vm") || params.get("view_mode")
if (vm === "Day" || vm === "Week" || vm === "Month")
```

d37 persist 只写：

```text
static/js/gantt_ui.js:108
setOrDelete("gantt_vm", ...)
```

模板时间粒度也只剩：

```text
templates/scheduler/gantt.html:162-167
Day / Week / Month
```

#### 影响

旧链接：

```text
/scheduler/gantt?...&gantt_zoom=fifteen-minute
```

在 d37 中会被忽略，静默回到 Day/默认视图。

同时删除 range guard 后，大版本跨度 + Day 视图可能直接创建超大 SVG，低配浏览器有卡死风险。

#### 建议

如果要下线细粒度 zoom，也要显式处理旧参数：

- 读到 `gantt_zoom` 时给出提示或映射；
- persist 时清理 `gantt_zoom/view_mode`；
- 保留范围/节点数保护；
- 不允许旧 URL 静默失效。

更好的方式是恢复薄 `gantt_zoom` 模块，让缩放映射、范围保护、URL 契约都内聚在那里。

---

### P1-3：关键回归测试和 quality gate 被删除，保护网失效

#### 证据

244 quality gate 必跑包含：

```text
tools/test_registry.py:77-88
tests/regression_gantt_adapter_contract.py
tests/regression_gantt_simulation_entry_shell.py
tests/regression_gantt_adjustment_draft_model.py
tests/regression_gantt_adjustment_validate_simulate.py
tests/regression_gantt_draft_save_and_preview.py
tests/regression_gantt_scenario_publish.py
tests/regression_frappe_gantt_short_task_contract.py
tests/regression_gantt_readonly_mode_contract.py
tests/regression_gantt_zoom_contract.py
tests/regression_gantt_zoom_decoration_sync.py
tests/regression_gantt_zoom_range_guard.py
tests/regression_gantt_url_persistence.py
```

d37 同一区域只剩基础 Gantt 测试：

```text
tools/test_registry.py:73-85
regression_gantt_page_version_default_latest.py
regression_gantt_default_version_span.py
regression_gantt_layout_contract.py
regression_gantt_calendar_load_failed_degraded.py
regression_gantt_bad_time_rows_surface_degraded.py
regression_gantt_contract_snapshot.py
regression_gantt_critical_chain_unavailable.py
regression_gantt_critical_chain_provider.py
regression_scheduler_candidate_gantt_plan_role_contract.py
```

后台测试专项统计：

- tests + registry 约 `47 insertions / 3030 deletions`；
- 至少 10 个 Gantt 专项测试文件被删除；
- 约 52 个 `test_*` 函数、2511 行覆盖消失；
- 至少 57 个命名 pytest 测试被移除。

#### 影响

当前变更之所以可能“变绿”，很大程度是因为删掉了会拦住它的测试。
这不是健康的简化，而是质量门禁主动放松。

#### 建议

如果功能保留：恢复 active tests。

如果功能下线：新增 decommission tests：

- 旧 endpoint 返回 410；
- 旧 `scenario_id/gantt_zoom` 参数显式提示；
- 页面不暴露保存/发布入口；
- RequestServices 不暴露 adjustment；
- vendor short-task / readonly / range guard 仍需保留测试。

---

### P1-4：前端数据错误会被空数据或泛化 HTTP 错误掩盖

#### 证据

HTTP 非 2xx 时，d37 不读 JSON body：

```text
static/js/gantt_boot.js:283-284
if (!resp || !resp.ok) {
  throw new Error(`甘特图数据请求失败（HTTP ${resp ? resp.status : "0"}）`);
}
```

后端其实会返回标准 JSON error：

```text
web/routes/domains/scheduler/scheduler_gantt.py:199-203
except AppError as exc:
    return json_error_response(exc)
```

但前端用户只能看到：

```text
HTTP 400 / HTTP 404 / HTTP 500
```

而不是业务错误。

另外，接口合同异常会被变成空数组：

```text
static/js/gantt_boot.js:323-324
const data = payload.data || {};
const tasks = Array.isArray(data.tasks) ? data.tasks : [];
```

#### 影响

如果后端返回 `success: true` 但 `data/tasks` shape 错误，页面会显示“暂无排程数据”，而不是“数据格式异常”。

这会隐藏真实契约失败。

#### 建议

- HTTP error 分支先尝试读取 JSON error message；
- `success:true` 后强校验 `payload.data` 和 `data.tasks`；
- shape 错误必须显示“甘特图数据格式异常”，不要变成空排程；
- 渲染入口增加可见错误边界。

---

### P1-5：Gantt 主链已拿到 resolved plan，却又按 role 重新解析，可能导致数据和元数据不一致

#### 证据

`GanttService.get_gantt_tasks()` 先解析出 `plan_resolution`：

```text
core/services/scheduler/gantt_service.py:289-310
```

但读取任务行时又按 role 重新解析：

```text
core/services/scheduler/gantt_service.py:322-327
list_plan_detail_rows_between(version=ver, role=selected_plan_role(...))
```

对应 service 内部会再次 `resolve_plan()`：

```text
core/services/scheduler/schedule_plan_query_service.py:167-181
list_plan_detail_rows_between() -> resolve_plan(version, role)
```

`resolve_plan()` 可能 fallback 到 adopted：

```text
core/services/scheduler/schedule_plan_query_service.py:145-157
fallback_to_adopted
```

但 critical chain 仍使用第一次解析出的 resolution-aware 查询：

```text
core/services/scheduler/gantt_critical_chain_provider.py:151-155
list_plan_detail_rows_all_for_resolution(version, source_table, candidate_id)
```

#### 影响

同一次响应里可能出现：

- metadata / critical chain 基于 candidate A；
- tasks / overdue 因二次 fallback 变成 adopted；
- 页面整体仍返回 200。

这是入口解析职责和数据读取职责没有高内聚导致的隐性一致性风险。

#### 建议

上层已经完成方案解析后，下层查询应使用 resolved identity：

```text
source_table + candidate_id
```

不要在数据读取阶段再次按 role 调用带 fallback 的 `resolve_plan()`。

---

### P1-6：公开展示层回退，内部值重新暴露给用户

#### 证据

d37 popup 直接展示原始字段：

```text
static/js/gantt_render.js:878-890
startText = str(task.start)
endText = str(task.end)
sourceText = str(meta.source)
priorityText = str(meta.priority)
dueText = str(meta.due_date)
```

弹窗字段也偏内部诊断：

```text
static/js/gantt_render.js:913-916
关键链前驱
类型
间隔（分钟）
关键链依据
```

`decorate_history_version_options()` 不再生成 `schedule_time_display`：

```text
web/viewmodels/scheduler_history_summary.py:90-112
```

#### 影响

用户可能看到：

```text
来源：internal / external
优先级：urgent / critical
时间：2026-05-04T03:20:59Z
关键链依据：machine / process
```

这与中文业务页面不一致。

#### 建议

恢复公开 formatter：

- `publicSourceLabel`
- `publicPriorityLabel`
- `formatChineseDateTime`
- `publicCriticalEdgeReason`
- `publicGapLabel`

所有用户可见 HTML 只能展示公开中文标签，不应直接暴露内部枚举和诊断 reason。

---

## P2 / 架构、复杂度、文档问题

### P2-1：前端复杂度未降，adapter/zoom 职责被压回 render

#### 量化结果

d37 关键文件行数：

```text
static/js/gantt_render.js                         943 行  ❌ 超 500
static/js/gantt_contract.js                       408 行
static/js/gantt_ui.js                             203 行
core/services/scheduler/gantt_service.py          449 行
web/viewmodels/page_manuals_scheduler_outputs.py  474 行
static/docs/scheduler_manual.md                   1900 行 ❌
web_new_test/static/docs/scheduler_manual.md      1900 行 ❌
docs/dev/aps-browser-scheduler-qa-replay.md        826 行 ❌
```

`static/js/gantt_render.js` 同时承担：

- 任务过滤；
- render task 构造；
- Frappe 实例化；
- popup HTML；
- 假期背景；
- critical chain 高亮；
- overdue/external 装饰；
- legend；
- DOM/SVG 修补；
- performance cache；
- 多处 try/catch best-effort 装饰。

这不满足高内聚低耦合，也不满足文件控制在 500 行以内的质量目标。

#### 建议

拆分职责：

```text
gantt_readonly_adapter.js     只负责 Frappe options / readonly / mode
gantt_zoom.js                 只负责 zoom spec / URL / range guard
gantt_popup.js                只负责公开字段格式化和 HTML escape
gantt_decorations.js          只负责 critical/overdue/external SVG/DOM 装饰
gantt_render.js               只做编排
```

不要把 adapter/zoom 删除后把职责直接塞回 render。

---

### P2-2：文档和架构合同被删除，但没有替代 ADR / closeout

本次删除了大量 `.codestable` Gantt 架构、roadmap、feature、vendor patch 文档。d37 剩余文档没有提供等价说明：

- 当前 Gantt 是只读还是半可交互？
- adjustment 是永久删除还是延期？
- v12-v14 schema 如何处理？
- 旧 scenario preview URL 如何处理？
- vendor patch 哪些必须保留？
- zoom / range guard 是否仍是合同？

用户手册只剩面向用户的简化说明，不能替代架构决策记录。

#### 建议

不要直接抹掉历史合同。建议：

- 恢复关键架构文档，标记为 `superseded/deprecated`；
- 新增 closeout / ADR：
  - 为什么下线 adjustment；
  - 当前只读 Gantt 合同；
  - 旧 URL / 旧 DB / 旧测试如何处理；
  - 哪些能力保留，哪些明确废弃。

---

### P2-3：后端核心链路基本清理干净，但仍有一致性和吞错边界

正向点：

- 删除的 Python adjustment 模块没有明显 import 断链；
- route registrar / RequestServices / `__init__.py` 基本同步清理；
- adopted / candidate_rows 主查询字段形状基本一致；
- critical chain / overdue 基础链路仍在。

但仍有问题：

1. `GanttCriticalChainProvider` 捕获过宽：

   ```text
   core/services/scheduler/gantt_critical_chain_provider.py:149-157
   ```

   会把 `RuntimeError/ValueError/TypeError/KeyError/sqlite3.Error` 折叠成 `repo_exception`，且无 `logger.exception`。这会隐藏真实 DB/schema/代码错误。

2. `plan_overdue_markers.py` 从 repository 模块导入领域常量，形成反向依赖：

   ```text
   core/services/scheduler/plan_overdue_markers.py:5
   from data.repositories.schedule_plan_query_repo import SOURCE_CANDIDATE_ROWS, SOURCE_SCHEDULE
   ```

   常量真实定义在：

   ```text
   core/models/schedule_plan_role.py
   ```

   应改成 service 直接依赖 model，而不是 service -> repository -> model。

3. `ScheduleCandidateRows` schema 约束弱于 service 层约束，candidate rows 可出现 dangling op/resource 后被 left join 成空字段。

---

### P2-4：Week/Month 视图下假期背景宽度可能错误

#### 证据

d37 仍提供 Week/Month：

```text
templates/scheduler/gantt.html:163-166
```

假期列计算使用 `step` 和 `column_width`：

```text
static/js/gantt_render.js:500-502
```

每个假期 rect 宽度直接设为整列 `col`：

```text
static/js/gantt_render.js:520-524
```

#### 影响

Week 视图中一列代表一周，Month 视图中一列代表约一个月。单日假期不应覆盖整周/整月。当前逻辑可能把一天假期画成整周/整月背景。

#### 建议

恢复类似旧 `getGanttScale().dayWidth` 的计算：日宽应基于分钟比例，而不是直接用 column width。

---

### P2-5：`window.Gantt` 加载缺失没有 fail-fast

#### 证据

boot 缺依赖检查没有检查 `window.Gantt`：

```text
static/js/gantt_boot.js:39-75
```

render 直接使用全局 `Gantt`：

```text
static/js/gantt_render.js:857
```

#### 影响

如果 vendor 静态资源 404、缓存损坏或被拦截，页面会晚期 `ReferenceError: Gantt is not defined`，而不是进入“页面脚本加载不完整”的可读错误分支。

#### 建议

在 boot 缺依赖检查中加入：

```js
typeof window.Gantt === "function"
```

或在 render 前显式保护并调用 `reportClientError()`。

---

## 相对合理的部分

有些删除本身是同步的：

- 删除 adjustment Python model/repo/service 后，包级 import 基本已清理；
- route registrar 不再注册 `scheduler_gantt_adjustments`；
- RequestServices 不再暴露 adjustment services；
- 模板不再引用已删除的 `gantt_adapter.js/gantt_zoom.js/aps_gantt_simulation.css`；
- 删除功能的主体链路没有留下大量生产 import 断链。

但这些“删干净”不能抵消：

- migration 版本倒退；
- 只读合同破坏；
- 旧 URL 静默错显；
- vendor patch 回退；
- 测试门禁削弱；
- 文档合同丢失。

---

## 最优解决方案建议

如果目标是“删除未成熟的手工调整 / scenario / publish 功能”，建议按下面路线收口，而不是当前硬删。

### 1. 数据库版本必须单调

- 恢复 v12/v13/v14 文件和注册；
- `CURRENT_SCHEMA_VERSION` 不要降；
- 新增 v15 做 decommission；
- `current_version > CURRENT_SCHEMA_VERSION` 必须 fail-fast；
- 对旧 adjustment 表：
  - 要么保留但标记废弃；
  - 要么迁移归档；
  - 要么显式 drop；
  - 不能让 schema.sql、migration_state、实际旧库三者各说各话。

### 2. 下线功能必须显式 tombstone

- 旧 adjustment API 返回 410；
- 旧 `scenario_id` URL 返回 410 或明确页面提示；
- 旧 `gantt_zoom` 参数要提示或映射；
- 不允许静默忽略参数后展示普通排程。

### 3. 只读 Gantt 合同必须保留

即使删除 adjustment，也不应删除只读能力。

必须保留：

- readonly；
- readonly_dates；
- readonly_progress；
- click popup；
- 禁止拖拽假编辑；
- 页面明确“查看模式”。

### 4. Zoom / range guard 不应和 adjustment 一起删掉

zoom 是查看能力，不是 adjustment 能力。

即使暂时只保留 Day/Week/Month，也需要：

- URL 兼容；
- 旧参数处理；
- 大范围保护；
- 短工序可见和可点击合同。

### 5. Vendor patch 要有治理文档和测试

最小测试集必须覆盖：

- 36 分钟短任务；
- 跨午夜且 end 为 `00:00:00`；
- `.bar-hit >= 12px`；
- readonly 禁拖/禁拉伸/禁进度；
- Hour / 15min / 5min / 1min；
- URL zoom persistence；
- range guard。

### 6. 恢复或替代 quality gate

如果功能下线，测试也不能直接删除，应改为 decommission tests。

quality gate 应继续阻止：

- 静默错显 scenario；
- 只读退化；
- vendor patch 回退；
- 旧 URL 静默失效；
- schema version 倒退。

### 7. 降低前端复杂度

`static/js/gantt_render.js` 必须拆。当前 943 行不符合文件质量门禁，也不符合高内聚低耦合。

---

## 最终判定

**不建议合入。**

这次变更违反了以下质量目标：

- 不得静默回退：schema 高版本库被静默接受、`scenario_id` 被静默忽略、data contract 错误被空数据吞掉；
- 控制复杂度：`gantt_render.js` 943 行，职责过多；
- 高内聚低耦合：adapter/zoom 职责被删除后没有新的边界；
- 文件行数控制：多个核心文件/文档超过 500 行；
- 深入引用链后的最佳解：当前是硬删，不是受控下线。

最优路线是：**保留只读 Gantt 和 vendor/zoom 合同；用显式 tombstone 下线 adjustment；保持 schema 版本单调；恢复测试门禁；补 ADR/closeout 文档；再做小步重构。**
