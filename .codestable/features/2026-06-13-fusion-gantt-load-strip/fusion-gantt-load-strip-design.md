---
doc_type: feature-design
feature: 2026-06-13-fusion-gantt-load-strip
requirement:
roadmap: aps-frontend-fusion
roadmap_item: fusion-gantt-load-strip
status: approved
summary: 甘特资源负荷热力条带（契约 4.6）——新建 gantt_resource_load.py 资源×日桶纯函数聚合（注入 calendar、容量分母正午采样 helper 单源化、外协行不计、ratio 算不出置 None）；契约新字段 resource_load + CONTRACT_VERSION 2→3；web 装饰层注 severity（阈值 import 唯一字源）与跳转 links（build_workbench_link）；前端新 gantt_load_strip.js 渲染 Top 5 负荷降序条带（列宽对齐 getGanttScale.dayWidth、scrollLeft 同步），点击格弹当天任务清单+去派工/报表链接。前置微重构：gantt_service.py 498/500 行，overdue marker 三方法保签名薄壳化（内部实现搬 support）腾位
tags: [frontend, gantt, load-strip, capacity, module-w]
---

# fusion-gantt-load-strip design

## 0. 术语约定

| 术语 | 定义 | 防冲突结论 |
|---|---|---|
| 负荷条带（load strip） | 甘特图下方按「资源×自然日」的热力格条带，每格 = 该资源当日已排内部工时 / 当日容量 | 全仓 grep `负荷条带/load.strip/loadStrip/resource_load` 零冲突（dashboard 的 resource_load_card 是首页风险卡，口径不同已有 4.6 钉牌） |
| 资源日负荷行（resource_load） | 契约新字段，行 shape `{date, resource_id, resource_label, hours, capacity_hours, ratio, severity, links}`——前六字段 core 纯函数产出，severity/links 由 web 装饰层追加 | ratio 算不出（容量≤0/日历失败）置 **None 不伪装 0**；resource_id 即 machine_id/operator_id（甘特 meta 已公开，4.6 允许）；禁含 plan_role/scenario_id 等内部字段 |
| severity 映射（4.6 要求显式裁决） | ratio None→`unknown`；<0.75→`normal`；0.75≤ratio<0.90→`warning`；≥0.90→`danger`。阈值 **import** `web/viewmodels/dashboard_workbench_cards.py:14-15` 的 LOAD_WARNING_RATIO/LOAD_DANGER_RATIO（已是唯一字源，文件头注释点名本 feature 来 import） | 首页既有 `notice` 档**本条带不使用**（notice 是待办提醒档，负荷四档与其并存不映射）；CSS 只消费 severity-* 类名不复制数值（00-tokens.css:9-11 既定约定） |
| 容量分母（4.6 协议） | 每日容量 = `calendar.policy_for_datetime(datetime.combine(d, time(12,0))).shift_hours × efficiency`——正午采样定口径避开跨午夜归属歧义；**禁直调 calculations.capacity_hours**（midnight 采样无时刻参数） | #16 已落地第一份实现 `_capacity_hours_at_noon`（week_plan_daily_summary.py:23-30 私有）——本 feature **提升为共享 helper 单源化**（见决策 3），不再写第二份 |
| Top 5 承接（老 11 验收点） | 条带行按周内总负荷小时降序，最多渲染 5 行；超出收为「另有 N 个资源有排程」一行文字提示 | 2026-06-11 B 案拍板：Top-N 以色带排序承接、任务数与跳转入口经点击弹层承接；老 roadmap item 11 标 dropped 指向本条属验收待办 |

## 1. 决策与约束

**需求摘要**（roadmap 第 15 条，契约 4.6；依赖 #12 done + #5 done 均满足）：甘特图下方资源负荷热力条带——后端资源×日桶聚合新文件、前端像素对齐挂层、容量来源明示、点击色带格弹当天任务清单与去派工/报表跳转。

**复杂度档位**：Web 应用默认档位，无偏离。

**关键决策**：

1. **功能归属**：聚合纯函数落新文件 `core/services/scheduler/gantt_resource_load.py`（gantt_service.py 498/500 行禁止加码——roadmap notes 钉死）；severity/links 属 Web 展示装饰，沿 `decorate_gantt_task_detail_payload` 既有模式（web/viewmodels/scheduler_gantt_task_detail.py:145「core 只管排程事实、web 装饰不反向污染」）落新文件 `web/viewmodels/scheduler_gantt_load_strip.py`——**core 不得 import web 层阈值常量**（分层约束），所以 severity 判定必须在 web 层。
2. **数据流**：get_gantt_tasks 既有作用域 rows/wr 直接喂聚合函数（计划身份沿已 resolve 的链取行，不另查）；**calendar 由调用方注入**（`CalendarService(self.conn, ...)`，与 #16 build_week_plan_daily_summary 的 `calendar:` 形参同模式——聚合函数本体保持可用轻量桩单测的纯函数，不收 conn 自己 new）；输出走 BuildOutcome（坏时间行 DegradationCollector 计数，与 build_tasks 同款），并入 collect_gantt_degradation_events 聚合；contract 新字段 resource_load + **CONTRACT_VERSION 2→3**（gantt_service.py:49 类属性——测试未锁值，bump 无测试阻力，但 snapshot 测试需补 resource_load 顶层 key）。
3. **行筛选/日桶/容量 helper 单源化**：只计内部行（`SourceType.INTERNAL.value` 同等判断写在新文件内，**不 import core/services/report/calculation_helpers 的 is_internal_source**——避免 scheduler→report 反向依赖；外协不占内部容量，与报表利用率同把尺子）；resource_id 按 view 取 machine_id/operator_id，label 复用 `display_machine/display_operator`（_sched_display_utils.py:46/:55）；日桶 `split_by_day`（:117，跨午夜安全）+ 窗口裁剪（重叠秒数计算在新文件内同等实现或下沉共享，同样不反向依赖 report 包）。**容量正午采样 helper 单源化**：把 #16 的 `_capacity_hours_at_noon` 提升为 `_sched_display_utils.py` 公共函数 `capacity_hours_at_noon`，week_plan_daily_summary.py 改为引用（行为不变由 #16 既有测试守证；其守卫 grep `capacity_hours(` 对 `capacity_hours_at_noon(` 不误报——后缀隔断）。
4. **前端渲染**：新 `static/js/gantt_load_strip.js`，渲染为 `#gantt` 容器下方独立 DOM 条带（非 SVG 内层——行序按负荷降序与甘特行序无关，做 SVG 内层反而错位误导）；列宽/x 坐标用 `getGanttScale(gantt).dayWidth` 与 `gantt.gantt_start` 同一像素公式（gantt_holidays.js:223-229 同源）；横向滚动监听 `#gantt .gantt-container` scroll 事件同步条带 translateX。**止损线**（roadmap notes 钉死）：像素逐格对齐若在缩放级别切换下不稳，退化为「同列宽日期表格」（仍按 dayWidth 定列宽但不强制与图区像素贴合），止损判定在浏览器目检步做。
5. **点击弹层**：格 (resource_id, date) 点击 → 前端从 state.allTasks 过滤该资源当天任务渲染弹层（meta.machine_id/operator_id/start/end 全有，零后端新增）；弹层底部「查看资源排班」「查看资源负荷报表」两链接消费装饰层 links（build_workbench_link 唯一字源，禁前端手拼 URL——#32 收编纪律）。
6. **诚实降级**：容量≤0 或日历失败 → ratio None + severity unknown，格显示「利用率暂时算不了」；日历整体加载失败走既有 calendar_load_failed 降级提示链；条带数据为空（如纯外协周）→ 条带整体隐藏不渲染空壳。
7. **挂接时机与导出口径**：decorateStaticAfterRender（gantt_decorations.js:152）末尾追加 `ns.renderLoadStrip()` 调用——与假期层同一「new Gantt 后单次」时机；数据经 gantt_boot._prepareVisibleState 的 `ns.initResourceLoad(data.resource_load || null)` 注入（initCalendarDays :353 同位置）。**导出钉死为顶层 `ns.initResourceLoad` / `ns.renderLoadStrip`**（与 gantt_holidays.js:248-249 同模式，不挂 ns.loadStrip 命名空间——boot 依赖检查抓顶层函数）；script 插入位置钉死为 **gantt_holidays.js 之后、gantt_decorations.js 之前**（decorations 运行时调用它的导出）。

**明确不做**：不做单台设备/单人容量细分（机器级日历无数据来源——capability-mining 缺口实锤）；不动 calculations.capacity_hours 与报表利用率链路；不新增图表库；不做条带常显开关/折叠记忆（归 #27 controls）；不改 algo 评估器 machine_util_avg（两口径钉牌归 dashboard 侧小修，非本条）；阈值不复制第三份常量。

## 2. 名词与编排

### 2.1 名词层

**现状**：甘特契约 17 字段无负荷数据（gantt_contract.py:66-92 DTO/:94-115 to_dict/:118 签名）；CONTRACT_VERSION=2（gantt_service.py:49）；get_gantt_tasks（:283-421）作用域有 wr（:328）/rows（:341-349），build_tasks 调用 :371-377、build_gantt_contract 调用 :394-412，CalendarService 不在作用域（gantt_tasks.py:70 内部 new）；阈值唯一字源 dashboard_workbench_cards.py:14-15；装饰层先例 scheduler_gantt_task_detail.py:145；前端像素公式 gantt_holidays.js:223-229 + getGanttScale（gantt_zoom.js:169-182）；阈值色 token --ui-warning/--ui-danger 四件套已单源（00-tokens.css）。

**变化**：
- 新增 `core/services/scheduler/gantt_resource_load.py`：`compute_gantt_resource_day_load(*, view, rows, wr, calendar, logger=None) -> BuildOutcome[List[Dict[str, Any]]]`（calendar 注入，可用轻量桩单测），输出行示例：

```python
{"date": "2026-06-15", "resource_id": "MC001", "resource_label": "MC001 CNC-01",
 "hours": 6.5, "capacity_hours": 7.2, "ratio": 0.9028}   # 容量算不出时 ratio: None
```

- 修改 `gantt_contract.py`：DTO 加 `resource_load: List[Dict[str, Any]] = field(default_factory=list)` + to_dict 输出 + build_gantt_contract 加参。
- 修改 `gantt_service.py`：CONTRACT_VERSION 2→3；get_gantt_tasks 加聚合调用+降级并入+contract 传参（微重构腾位后有余量，见 2.5）。
- 新增 `web/viewmodels/scheduler_gantt_load_strip.py`：`decorate_gantt_resource_load_payload(data) -> data`，行追加 `severity`（阈值 import 唯一字源）与 `links`（build_workbench_link 两条：resource_dispatch / utilization 报表，带 resource/日期上下文；scenario 预览态沿 detail_links 同款 disabled+原因）。
- 修改 `web/routes/domains/scheduler/scheduler_gantt.py`：gantt_data 路由 decorate_gantt_task_detail_payload 后串接新装饰。
- 前端：新 `static/js/gantt_load_strip.js`（顶层导出 `ns.initResourceLoad` / `ns.renderLoadStrip`，弹层为模块内部实现）；gantt_boot/gantt_decorations/gantt.html/aps_gantt.css 四处接线（纯 token 着色：normal 用 --ui-success 系、warning/danger 用既有四件套、unknown 用 --ui-muted）。

### 2.2 编排层

```mermaid
flowchart LR
  A[get_gantt_tasks<br/>rows+wr 已就绪] --> B[compute_gantt_resource_day_load<br/>新文件：日桶聚合+容量分母]
  B --> C[build_gantt_contract<br/>resource_load 字段 v3]
  C --> D[gantt_data 路由<br/>decorate: severity+links]
  D --> E[gantt_boot<br/>initResourceLoad]
  E --> F[decorateStaticAfterRender<br/>renderLoadStrip 条带+弹层]
```

**现状**：get_gantt_tasks 线性编排（resolve→rows→calendar_days→tasks→critical→contract）；前端 boot→render→decorations 单次装饰链。

**变化**：后端在 tasks 构建后插一步聚合（同 rows 复用，零额外查询）；路由层装饰串接一步；前端装饰链末尾追加条带渲染。控制流保持线性，无新分支拓扑。

**流程级约束**：
- 聚合失败（非坏行级，如日历整体异常）→ resource_load 置空数组 + DegradationCollector 中文事件，**不 500 不静默**；前端空数组隐藏条带。
- 坏时间行计数与 build_tasks 的 bad_time_row_skipped 同款语义，并入既有 degradation 提示条。
- 装饰层幂等（重复调用不重复追加 links）；severity 判定必须覆盖 ratio None 分支。
- 前端条带渲染在 DOM shim 下可测（不依赖 getBBox）；scroll 同步失败不阻断渲染（对齐止损线兜底）。

### 2.3 挂载点清单（按「删了它 feature 是否消失」收紧）

1. `/scheduler/gantt/data` 契约新字段 `resource_load`（contract_version 3）——对外数据出口
2. `scheduler_gantt.py` 路由串接 `decorate_gantt_resource_load_payload`（severity/links 注入）——展示语义出口
3. `gantt.html` 条带容器 `#ganttLoadStrip` + `gantt_load_strip.js` script 标签——页面注入点
4. `gantt_boot.js` `ns.initResourceLoad(...)` 调用 + `gantt_decorations.js` `ns.renderLoadStrip()` 调用——前端接线两点

（gantt_resource_load.py / scheduler_gantt_load_strip.py / gantt_load_strip.js 三个新文件、gantt_contract.py 字段、CSS 段、测试均为内部改动，归推进策略不列挂载点。）

拔除推演：删四个挂载点+三个新文件+契约字段回退 → 契约回 v2、页面回无条带现状，零悬挂。

### 2.4 推进策略

1. **微重构腾位**（见 2.5）：gantt_service.py 搬 overdue marker 三方法 → 全量 gantt 测试绿 + wc 明显低于 460 行（独立验证退出）
2. 后端：聚合纯函数+契约字段+service 接线 + 纯函数单测（聚合/跨午夜/外协剔除/窗口裁剪/容量 0→None/降级计数/排序）+ snapshot 测试补 resource_load key → 绿
3. web 装饰层：severity 四档（0.74/0.75/0.89/0.90/None 边界）+ links 形状与 preview disabled + 幂等 → 绿
4. 前端：条带渲染+弹层+CSS+JS contract 测试（Top 5 截断/空数组隐藏/unknown 文案/点击过滤任务） → 绿 + 浏览器目检（像素对齐止损判定）
5. 甘特全量回归 + daily gate（stash 隔离并行 WIP）+ 老 roadmap item 11 标 dropped 回写

### 2.5 结构健康度与微重构

##### 评估
gantt_service.py **498/500 行**，本 feature 必须加 6-8 行（调用+降级并入+传参+bump），直接写必爆门禁。文件内 `_log_overdue_marker_degraded/_log_overdue_marker_partial/_overdue_batch_ids_from_history`（:208-251，44 行）是超期标记的自包含簇，gantt_service_support.py 已存在且是该类支持函数的既定去处。目录级无问题；compound 无冲突 convention（search-yaml 零命中）。

##### 结论：微重构（拆文件，保签名薄壳化）
**类方法签名与调用点零改动**：三方法的方法体（日志格式串+历史读取逻辑）搬到 `gantt_service_support.py` 模块函数，原三方法**全部保留为 1-2 行薄壳转发**——不能删名：`_overdue_batch_ids_from_history` 被测试 monkeypatch（test_gantt_critical_chain_unavailable.py:63）、`_log_overdue_marker_degraded` 在 :364 被当 callback 传出（grep 实证）。外部行为/日志文案/签名全部不变，腾出 ~30 行余量。验证行为不变：tests/gantt/ 全量绿 + 超期标记相关测试零改动通过。此项为 checklist 第 1 步，独立验证退出。

##### 超出范围的观察
get_gantt_tasks 139 行偏长（编排+取数+降级聚合混在一个方法），值得拆步骤函数——超出「只搬不改行为」，不阻塞本 feature，归后续 cs-refactor。

## 3. 验收契约

关键场景：
1. 聚合正确性：资源 A 当日两段任务 3h+2h → hours=5.0；跨午夜任务按 split_by_day 切到两日；窗口外部分被 overlap 裁掉；外协行（source=external）不计入。
2. 容量与降级：工作日 8h×0.9 → capacity_hours=7.2；节假日 shift_hours=0 → ratio None + severity unknown + 格文案「利用率暂时算不了」；日历整体失败 → resource_load=[] + 中文降级事件，页面提示条可见。
3. severity 边界：ratio 0.74→normal、0.75→warning、0.89→warning、0.90→danger、None→unknown（锁 import 自唯一字源，无第三份常量——grep 全仓 0.75/0.90 定义点仍仅 dashboard_workbench_cards.py）。
4. 条带渲染：负荷降序 Top 5；>5 资源出「另有 N 个资源有排程」；空数组条带整体不渲染；容量来源文案「按全局工作日历估算，未按单台设备/单人细分」可见。
5. 点击弹层：格点击列出该资源当天任务（批次/工序/时段）；「查看资源排班」「查看资源负荷报表」链接 href 来自后端 links；scenario 预览态派工链接 disabled+原因。
6. 像素对齐：浏览器目检条带格与甘特日列对齐（多缩放级别）；不达标走止损线（同列宽日历对齐）并在验收记录明示。
7. 契约：/gantt/data 顶层含 resource_load；contract_version=3；行字段恰为 8 个公开字段（反向断言无 plan_role/scenario_id/source_table/candidate_id）。
8. 全量回归：tests/gantt/ 绿；daily gate 绿；后端既有报表/周计划零 diff。

明确不做的反向核对：
- **禁直调守卫（4.6 红线，沿 #16 范式 test_week_plan_enrich_page.py:82-91）**：grep 断言 `capacity_hours(` 不出现在新负荷链路全部文件（gantt_resource_load.py、scheduler_gantt_load_strip.py、gantt_service.py、scheduler_gantt.py），`capacity_hours_at_noon(` 白名单豁免。
- calculations.capacity_hours 定义零 diff；algo evaluation.py 零 diff；报表 utilization 链零 diff；新文件零 `from core.services.report` import（反向依赖断言）。
- 无新图表库依赖（package 零增）；无第三份阈值常量（grep 全仓 0.75/0.90 负荷定义点仍仅 dashboard_workbench_cards.py）。
- #12/#13/#14 已落段零 diff；并行 WIP 零接触。

## 4. 与项目级架构文档的关系

验收时归并：ui-gantt.md 补「资源负荷条带」段（数据流+script 顺序协议补 gantt_load_strip.js 位置）；ARCHITECTURE.md 甘特条目补一句；roadmap 第 15 条回写 done + **老 roadmap aps-frontend-workbench item 11 标 dropped 指向本条**（Explore 纠偏：尚未回写，属本 feature 收尾待办）；4.6 协议第二个落地实例无需改协议文本。
