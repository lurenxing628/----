## 12. 分区【web-all】(Web 层 routes / viewmodels / bootstrap) 水下语义债

> **分区健康一句话**：地基整体健康——P1 写死假值 exemplar(ADOPTED_PLAN_RESOLUTION) 已修、资源/版本/数值收口点基本被尊重、P4 静默兜底被 `regression_web_silent_fallback_contract` 钉死、路由 `except` 全部 log+flash 可见。水下债集中在三处真债（一处真 P5 枚举中文标签两套实现且语义漂移、一处真 P6 `plan_id` 死面包屑被在途 roadmap 制度化供养、一处**承重 P2** execution-review 护栏写死且零注释）+ 一组 roadmap 明示有意延期的 P3 顶层 wrapper + 一条轻量 P5 getter 副本。

> **本节复核口径**：所有 file:line 已回到【当前 git 工作区代码】逐条复核（多个文件处于 modified/added 状态）。每条债末尾给出复核结论标记：✅证据仍准 / ⚠️行号(或路径)已变 / 🔧疑似已被修复。

**复核汇总**：5 条债全部仍然成立（无一条被修复）。其中 1 条行号完全未变（P3 wrapper），4 条因上游文件被改动导致 file:line 漂移（最大一处是整文件从顶层迁入 `domains/`）。无误报、无已修复。

---

### 12.1 【P5｜medium｜load_bearing=false】enum_display.py + process_bp 中文枚举标签是 enum_normalizers 收口点的第二套私有实现，且语义已漂移

**位置**
- `web/routes/enum_display.py:13-79`——6 个裸标签函数：`machine_status_zh:13` / `operator_status_zh:24` / `day_type_zh:33` / `batch_status_zh:47` / `priority_zh:62` / `ready_zh:73`
- `web/routes/process_bp.py:16-25`——`_merge_mode_zh:16` / `_source_zh:22`

**引用链（已逐条复核）**
- 真正的收口点 `core/services/common/enum_normalizers.py` 已齐备且每个函数都先 `normalize_*`（归一别名）再贴标签：`operator_status_label:82` / `machine_status_label:124` / `source_type_label:159` / `batch_priority_label:209` / `ready_status_label:220` / `calendar_day_type_label:231`。
- 两套同时活在生产，且**同一概念在不同页面用不同函数**：
  - **齐套状态**：排产侧 `web/routes/domains/scheduler/scheduler_bp.py:9` `from ...enum_display import ... ready_zh` → 包装为 `_ready_zh:28-29` → `scheduler_batches.py:150 "ready_status_label": _ready_zh(b.ready_status)` 渲染排产批次页，另 `scheduler_batch_detail.py:251 ready_status_zh=_ready_zh(b.ready_status)`；而物料侧 `web/routes/material.py:9 from core.services.common.enum_normalizers import ready_status_label` → `material.py:124 row["ready_status_zh"]=ready_status_label(row.get("ready_status"))`（另 `:131`）。同一个批次齐套状态，两套标签函数。
  - **设备/人员状态**：`web/routes/equipment_bp.py:9` 与 `personnel_bp.py:9` `from .enum_display import machine_status_zh, operator_status_zh` → `equipment_pages.py:111 / :230 / :276`、`personnel_pages.py:68 / :136` 渲染；而 Excel 导入/导出侧 `equipment_excel_machines.py:12,161` 用收口点 `machine_status_label`、`personnel_excel_operators.py:12,71` 用收口点 `operator_status_label`。
- `process_bp._source_zh:22-25` 不调 `normalize_op_type_category`（收口点该归一器在 `enum_normalizers.py:135`，能吃 `外协/外/外包/外部` 等中文别名），裸 `== SourceType.EXTERNAL.value` 比较后 `else` 直接返回「自制」。

**为何算债**
同一概念（枚举→中文）绕开已存在的收口点又实现一遍，且两者**语义已实证漂移**：
1. **operator 停用文案不一致**：`enum_display.operator_status_zh:29` 对 INACTIVE 返回「停用/休假」，收口点 `operator_status_label:87` 返回「停用」——同一台账状态在设备页/人员页(走 enum_display) 与 Excel 导入预览(走收口点) 显示不同。
2. **ready 坏值被静默贴成确定状态**：`enum_display.ready_zh:73-79` 对未知/None 一律落到 `return "未齐套"`（被 `tests/test_enum_display_consistency.py:59-61` 钉死：`ready_zh("weird")==ready_zh("")==ready_zh(None)=="未齐套"`）；收口点 `ready_status_label:228` 则是 passthrough `return v or "未知"`，坏值原样暴露。前者把一个无法识别的齐套值伪装成「未齐套」这一确定结论，**直接违背灵魂暗线「坏数据不准静默兜底」**。
3. **source 别名误判**：`_source_zh` 不归一，任何未归一中文别名（如导入残留的「外协」「外」）走 `==` 比较都不等于 `SourceType.EXTERNAL.value`，落到 `else` 被误标「自制」——外协工序当成自制。

**爆炸半径**
若把 enum_display 这套删掉统一到收口点：scheduler 批次页/批次详情页、设备页、人员页、日历页的状态列文案会改变（「停用/休假」→「停用」），且齐套坏值从「未齐套」变为「未知/原值暴露」；必须同步改 `tests/test_enum_display_consistency.py:18,25,43,51,55-61` 的钉死断言。反向风险更隐蔽：若 LLM 以为两套等价而只改其一，会造成同一状态在不同页面显示不一致（现场看排产批次页和物料批次页对不上）。

**处置建议（收口到哪个已存在统一点）**
收口到 `core/services/common/enum_normalizers.py` 的 6 个 `*_label` 函数（已是项目认定的统一点）。具体：把 `enum_display.py` 6 个函数与 `process_bp._merge_mode_zh/_source_zh` 改为薄转发（`return machine_status_label(status)` 等），删除裸 `==` 比较体；`_source_zh` 必须经 `source_type_label`（内含 `normalize_op_type_category`）。同步：(1) 改 `test_enum_display_consistency.py` 的钉死断言，把「ready 坏值=未齐套」改成与收口点一致的 passthrough 语义，让这条测试不再为「坏数据静默兜底」续命；(2) 确认 operator 停用文案以收口点「停用」为准（或反向在收口点补「停用/休假」，二选一全局统一）。

**复核结论**：⚠️**路径已变（核心债仍准）**。`location` 字段两处（`enum_display.py:13-79`、`process_bp.py:16-25`）行号完全准确，债仍成立。但引用链里的排产消费方路径已迁移：旧证据 `web/routes/scheduler_bp.py:9` 对应的**顶层文件已不存在**，现位于 `web/routes/domains/scheduler/scheduler_bp.py:9`（import）+ `web/routes/domains/scheduler/scheduler_batches.py:150`（渲染，行号仍是 150）+ 新增消费点 `scheduler_batch_detail.py:251`。收口点 6 函数行号、operator 漂移(:29 vs :87)、ready passthrough(:228)、source 归一器(:135) 均复核为准。

---

### 12.2 【P6｜medium｜load_bearing=false】plan_id 是死面包屑：从 request 读入、存进工作台上下文、回吐进所有导航/导出 URL，却从不进任何 resolver/query，且被在途 roadmap 制度化保留

**位置**
- 读入：`web/navigation_context.py:86` + `web/routes/reports_page_support.py:98,135`
- 存：`web/viewmodels/scheduler_workbench_links.py:229`
- 回吐 URL：`web/viewmodels/scheduler_workbench_link_query.py:118,154`

**引用链（已逐条复核）**
- **request 读入**：`navigation_context.py:86 plan_id=_request_arg("plan_id")`；`reports_page_support.py:98 plan_id=_request_text("plan_id")`（在 `_publish_report_context`），`:135 build_report_context(plan_id=_request_text("plan_id"), ...)`（在 `reports_index_context`）。
- **流入收口点**：`build_workbench_plan_context`（`scheduler_workbench_links.py:187` 形参 `plan_id`，`:229 "plan_id": _text(plan_id) or None` 仅写进 context dict）。
- **去向只有回吐 URL**：`scheduler_workbench_link_query.py:118 _append_param(query,"plan_id",context.get("plan_id"))`（通用计划查询）、`:154`（execution_review 专用计划查询）。并在透传白名单里旅行：`scheduler_navigation_links.py:5`（`_REPORT_CONTEXT_FIELD_NAMES` 首项）+ `:12`（`_has_navigation_context` 探测项）、`reports_export_support.py:14`（导出参数白名单）。
- **零 resolver 消费——关键反证**：`grep -rn` 整个 `core/` 与 `data/` 找「以 request 参数 plan_id 为键的读取」结果为**空**（仅命中无关的 `plan_identity` 数据类、`schedule_plan_identity.py` 等，以及 `core/services/scheduler/resource_dispatch_actual_record_service.py:397,405` 的 `_plan_idempotency_keys`——那是 import_token 幂等键，与 request 的 plan_id 完全无关）。即 request 来的 plan_id 没有任何 query/resolver/计算读它。
- **对比同行 back_to（真承重）**：`scheduler_resource_dispatch.py:184 back_to=_current_back_to()` → `_workbench_context(..., back_to=back_to)` → 多处 `redirect(_page_url(...))`，back_to 确实驱动跳转，证明 plan_id 的「在用」是假象。

**为何算债**
典型死面包屑：定义后散布在 16+ 处透传白名单/URL 拼装里制造「在用」假象，实际没有任何查询/解析/计算读它。更隐蔽的是它被**在途 feature 制度化**成了验收项：`aps-frontend-workbench-items.yaml:289` 的 exit_check、`reports-workbench-backlink-acceptance.md:52`、`reports-workbench-backlink-checklist.yaml:82` 都把 `plan_id` 与**真正承重的 `back_to` 并列**写成「必须保留的返回上下文」。未来 LLM 读 roadmap 会以为 plan_id 承重而**永久供养**一个零消费参数。

**爆炸半径**
删除 plan_id 传递链需同时修改 3 处验收项（`aps-frontend-workbench-items.yaml:289`、`reports-workbench-backlink-acceptance.md:52`、`reports-workbench-backlink-checklist.yaml:82`）+ `tests/regression_reports_workbench_navigation_contract.py` 的相关断言。误删的**功能风险低**（无任何 resolver 依赖），但会触碰 in-progress feature 的契约测试与 roadmap 验收项。

**处置建议（收口到哪个已存在统一点）**
这条不是「收口到某统一点」，而是「确认死后整链删除 + 同步勘误 roadmap」：(1) 先与 `2026-06-01-reports-workbench-backlink` feature 负责人对齐——把 acceptance/checklist/items 三处的「保留 plan_id 与 back_to」修订为只保留 `back_to`，明确记录 plan_id 为「零消费、已移除」，**杜绝它被当成承重契约再供养**；(2) 删 `build_workbench_plan_context` 的 plan_id 形参与 `:229` 写入、两处 `_append_param(..., "plan_id", ...)`、两处白名单条目、两处 request 读入；(3) 改 `regression_reports_workbench_navigation_contract` 去掉 plan_id 断言。动手前必须先和 roadmap 对齐，不能直接删契约项。

**复核结论**：⚠️**行号已变（+1）**。`reports_page_support.py` 两处读入由旧证据 `:97,134` 漂移到当前 `:98,135`（上游文件有改动）。其余位置全部复核为准：`navigation_context.py:86`、`scheduler_workbench_links.py:229`、`scheduler_workbench_link_query.py:118,154`、白名单 `scheduler_navigation_links.py:5,12` / `reports_export_support.py:14`、roadmap 三处 `:289/:52/:82`、`resource_dispatch_actual_record_service.py:397,405`、back_to 对照 `scheduler_resource_dispatch.py:184` 均准确。core/data 零消费 grep 复跑仍为空，债成立。

---

### 12.3 【P2｜high｜load_bearing=true】★承重护栏★ execution-review 报表页写死 plan_role='adopted'/scenario_id=None，代码处零保护注释

> **⚠️ 这是本分区唯一一条承重护栏（load_bearing=true，对抗验证裁定 load_bearing、未被推翻）。下面给出该补的「我是故意的」注释文案。任何「统一参数方言」的重构在动它之前必须先读本节。**

**位置**
- `web/routes/reports_page_support.py:367,369`（两处写死 `"adopted", None`）
- `web/navigation_context.py:80-82`（execution-review 端点的强制分支）
- 结构性写死的根：`core/services/report/execution_review.py:141`（签名）+ `:153`

**引用链（已逐条复核）**
- `reports_page_support.py:367 plan_resolution=page_plan_resolution(services.schedule_plan_query_service, version, "adopted", None)`；`:369 page_date_range_or_version_span(engine, int(version or 0), "adopted", None, raw_date_from, raw_date_to)`。
- **刻意和同类不一致**：同文件所有兄弟报表页都从 request 读 plan_role/scenario_id——`_standard_request_context:57 raw_plan_role=request_plan_role()`、`:58 scenario_id=request_scenario_id()`（overdue/utilization/downtime 全经此函数）。**就 execution-review 这一页写死 adopted/None**。
- **导航上下文侧的第二道强制**：`navigation_context.py:42-47 _is_execution_review_request()` 专门识别该端点（`endpoint=="reports.execution_review_page"` 或 path 命中 `/reports/execution-review`）；`:80-82` 当 `is_execution_review` 时强制 `plan_role=ROLE_ADOPTED`、`scenario_id=""`。
- **底层结构性写死（最硬的证据）**：`core/services/report/execution_review.py:141 def execution_review(self, version, *, date_from, date_to, batch_id, resource_type, resource_id)`——签名**根本不接受 plan_role/scenario_id 入参**；`:153 resolution=host._resolve_plan(v, ROLE_ADOPTED, None)`，行数据按 adopted-only 结构性写死取出。
- **用户文案印证意图**：`core/services/scheduler/scheduler_reports_workbench.py:210 "只复盘正式采用方案，不复盘模拟预览和对比参考方案。"`（另 `:248 "它不复盘模拟预览，也不在这里写现场记录。"`）。
- **模板静态承诺**：`templates/reports/execution_review.html:61` 渲染 `{{ report_plan_status.source_text }} 这张表只复盘正式排产结果；模拟预览和对比参考方案不在这里写入或复盘现场事实。`

**为何算债（P2 承重不对称 + 缺注释）**
刻意和同类不一致（别处都从 request 读 plan_role/scenario_id，就它写死 adopted/None），这个不一致是**承重的**——但在三个写死/强制点（`reports_page_support.py:367`、`:369`、`navigation_context.py:80-82`）都**没有任何 `#` 注释说明「这里故意忽略 request 的 plan_role 是护栏」**。保护意图只散落在 viewmodel 用户文案和 core 签名里，对修改者不可见。

**对抗验证结论（裁定 load_bearing，但精化了「危害边界」）**
对抗验证**确认承重，未推翻**，但纠正了原始 finding「会污染复盘行数据」的措辞——危害边界更精确：
- **行数据本身是安全的**：core 的 `execution_review()` 签名不收 plan_role/scenario_id（`:141`），`reports_page_support.py:327-334` 调用也不传，所以即使 `:367/:369` 被统一成 `request_plan_role()`，**预览/对比方案的「行」也进不了复盘**——行级护栏在 core，结构性安全。
- **真正承重的是「标签身份」与「导航上下文泄漏」两条路径**：
  1. `reports_page_support.py:367 page_plan_resolution(...)` 是**显示用计划身份的唯一来源** → `report_plan_template_fields(:388)` → `report_plan_status.label/source_text` 渲染到 `templates/reports/execution_review.html:56,61`。统一成 request 读会让表头显示「模拟方案甲/preview」盖在 adopted 行数据上——**表头≠表体的自欺式误标**，模板那句「这张表只复盘正式排产结果」当场变成谎言，**违背灵魂暗线「宁可暴露错误也不自欺」**。
  2. `reports_page_support.py:373 _publish_report_context` → `set_current_workbench_navigation_context`。而 `navigation_context.py:77-79` **先读这个已发布的 override**，绕过 `:80-82` 的 is_execution_review 强制。所以若 `:367` 携带了 preview resolution，会经 `build_report_navigation_links` 把 plan_role/scenario_id **泄漏进后续所有导航链接**。`:80-82` 只守「未发布 context 的回退路径」——`:367` 与 `:80-82` 是守**两条不同代码路径**的两道承重闸，不是冗余。
  3. `reports_page_support.py:369 page_date_range_or_version_span(...,"adopted",None,...)` → `version_date_range(plan_role, scenario_id)`，默认日期窗口取自被解析方案的 span；统一后会用 preview 方案的 span 算默认筛选窗口。
- **测试盲区（恰好对应「无害清理」陷阱）**：`grep` tests/ 下**没有**任何用例带 `?plan_role=/scenario_id=` 显式参数 GET `/reports/execution-review`——只有无参或被取代版次场景（`regression_reports_workbench_navigation_contract.py:84,130`）。护栏类测试（`regression_scheduler_workbench_link_guardrails.py:131,149`；`regression_scheduler_workbench_links_contract.py:281`）只钉**viewmodel 链接构造器**，不钉页面 route 的 `:367/:369`。**一个 naive 的统一改动会 CI 全绿通过，却悄悄打破标签/导航不变量。**

**爆炸半径**
未来 LLM 以「消除参数方言、统一所有报表页都从 request 读 plan_role」之名，把 `:367/:369` 的 `"adopted", None` 改成 `request_plan_role()/request_scenario_id()`——护栏即被抹掉：预览/对比方案的身份标签与导航上下文冒充正式采用方案，**表头自欺、导航污染、默认日期窗错位**，且因测试盲区 **CI 不报红**。改动看起来是无害的一致性清理，实为安全回退。

**处置建议（收口 + 必补注释，不是改成从 request 读）**
对抗验证给出的安全前置条件：
1. **绝不**给 core 的 `execution_review()` 加 plan_role/scenario_id 入参——行级承重护栏在 core，原样保留。
2. **先补一条缺失的页面级回归**（堵测试盲区）：`GET /reports/execution-review?plan_role=baseline_best&scenario_id=xxx`，断言渲染出的「排产方案」标签仍为正式采用方案、`source_text` 不出现预览/对比文案、且发布的 nav context `plan_role=adopted` / 无 scenario_id。
3. **若目的是消除魔法字面量方言**：抽一个具名收口 `execution_review_plan_context()`（内部强制 adopted/None）替换 `:367/:369` 两处字面量——而不是改成从 request 读；并在该收口处补上「此处故意忽略 request 的 plan_role 是护栏」注释。
4. **保留** `navigation_context.py:80-82` 的 is_execution_review 强制分支（守未发布 context 回退路径）。

**该补的「我是故意的」注释文案**（直接落到三处）：
- `reports_page_support.py:367` 上方：
  ```python
  # 护栏(load_bearing)：本页【故意】写死 "adopted", None，绝不从 request 读 plan_role/scenario_id。
  # 它是「显示用计划身份」与「发布给后续导航的 context」的唯一来源——若改成 request_plan_role()/
  # request_scenario_id()，模拟预览/对比方案的身份标签会盖在 adopted 行数据上(表头≠表体的自欺)，
  # 并经 _publish_report_context(:373) 泄漏进 navigation_context.py:77-79 的已发布 override，绕过
  # :80-82 的强制分支。行级数据本身安全(core execution_review() 不收这两个参数)，但标签/导航不变量
  # 在此守。改动前必须先补 GET /reports/execution-review?plan_role=...&scenario_id=... 的页面级回归。
  ```
- `reports_page_support.py:369` 上方：
  ```python
  # 护栏(load_bearing)：同上，默认日期窗口必须按正式采用方案的 span 计算，故写死 "adopted", None。
  ```
- `navigation_context.py:80-82` 上方：
  ```python
  # 护栏(load_bearing)：execution-review 端点【故意】无视 request 的 plan_role/scenario_id，强制 adopted。
  # 这是「未发布 context 回退路径」的护栏；已发布 context 的护栏在 reports_page_support.py:367。两道分守不同路径，非冗余。
  ```

**复核结论**：⚠️**行号已变（+1），承重性与全部引用链复核为准**。两处写死由旧证据 `:366,368` 漂移到当前 `:367,369`（上游 +1；对抗验证的 `_adv_precondition` 已按 :367/:369 表述，与当前一致）。`navigation_context.py:80-82` 行号准确；`_is_execution_review_request:42-47`、core 签名 `execution_review.py:141`+`:153 _resolve_plan(v, ROLE_ADOPTED, None)`、viewmodel 文案 `scheduler_reports_workbench.py:210`、模板承诺 `execution_review.html:61` 全部复核为准。

---

### 12.4 【P3｜low｜load_bearing=false】顶层 9 个 scheduler_*.py wrapper 是迁移到 domains/scheduler 后的别名残渣，仅测试续命，roadmap 有意延期清理

**位置**
- `web/routes/scheduler_run.py:7-8`（sys.modules 别名样板）+ 同型 8 个：`scheduler_analysis.py` / `scheduler_batch_detail.py` / `scheduler_batches.py` / `scheduler_config.py` / `scheduler_excel_calendar.py` / `scheduler_ops.py` / `scheduler_week_plan.py`，以及逐符号 re-export 变体 `scheduler_excel_batches.py`
- `web/routes/_scheduler_compat.py`

**引用链（已逐条复核）**
- `scheduler_run.py:7 _impl=load_scheduler_route_module(".domains.scheduler.scheduler_run")`；`:8 sys.modules[__name__]=_impl`——整模块被替换为 domains 实现的强别名（`web.routes.scheduler_run is web.routes.domains.scheduler.scheduler_run` 为 True，且 import 它不会拉起 registrar，无副作用）。`scheduler_excel_batches.py` 是逐符号 re-export 变体。
- **生产引用**：`grep web/ core/ data/`（含 .py/.html/config/json）对顶层 wrapper 路径**零非测试命中**；`web/routes/__init__.py` 为空（无 re-export）。生产入口是 `web/bootstrap/factory.py:449 importlib.import_module("web.routes.scheduler")`（根入口，非这些 wrapper）；路由注册实际由 `web/routes/domains/scheduler/scheduler_route_registrar.py` 的 `_ROUTE_MODULES`（列 14 个 domains 叶子）`:30 importlib.import_module(f".{module_name}", __package__)` 直接 import domains 真身完成。
- **唯一引用方是 tests/**：`tests/regression_scheduler_wrapper_import_order_contract.py:12 LEGACY_SCHEDULER_WRAPPERS`（列出全部 9 个，并断言 wrapper 自身 import 旁路无副作用）+ `test_sp05_path_topology_contract.py` 的 `ROUTE_COMPAT_MODULES/ROUTE_BEHAVIOR_COMPAT_SYMBOLS` + ~20 个 route-contract 回归。
- **roadmap 明示延期**：`.codestable/roadmap/p1-scheduler-debt-cleanup/p1-scheduler-debt-cleanup-roadmap.md:522 "先保留旧 wrapper，避免一次改动冲击启动链。"`
- `_scheduler_compat.load_scheduler_route_module` 对缺失目标 `raise ModuleNotFoundError`（无静默兜底，灵魂不变量完好）。

**为何算债**
同一职责两套路径（顶层 wrapper 别名 vs domains 真身），迁移做了一半：真身已搬到 `domains/scheduler/` 并由 registrar 注册，顶层只剩 `sys.modules` 别名，生产代码已不走它们，靠测试续命。属 P3 迁移残渣——但 roadmap 明确记录为**有意延期（降低启动链风险）**，非失忆搁置。

**对抗验证结论（real_debt，原始判定被精化为「确属可收债，但现在删是抢跑」）**
对抗验证裁定删除**安全**（无任何生产安全不变量失守：无预览冒充/无旧版冒充——wrapper 就是现行 leaf 本身/无坏数据吞噬/无跨层违规；启动链 passivity 由 `test_sp05_path_topology_contract.py:484-571` 在**真生产路径**独立守护，删 wrapper 不解除该守卫）。但动手前必须满足三前置：(1) 先认账或修订 roadmap `:522` 的「先保留」延期决定——现在删属**抢跑该决定**，不是安全问题；(2) 把 22 个 test-only 消费者的 `import web.routes.scheduler_xxx` 迁到 domains leaf 路径；(3) 同步删/改两处 wrapper 专属契约：`regression_scheduler_wrapper_import_order_contract.py` 整文件 + `test_sp05_path_topology_contract.py` 的 `ROUTE_COMPAT_MODULES/ROUTE_BEHAVIOR_COMPAT_SYMBOLS` 区块与 `SCHEDULER_REAL_ROUTE_FILES` 清单。

**爆炸半径**
删除这 9 个 wrapper + `_scheduler_compat` 需同步删/改 `regression_scheduler_wrapper_import_order_contract.py`、`test_sp05_path_topology_contract.py` 及十余个 `import web.routes.scheduler_xxx` 的测试。误删会让仍按旧路径 import 的测试断裂。因 roadmap 标注「先保留」，现在动属抢跑。

**处置建议（收口到哪个已存在统一点）**
统一到 `web/routes/domains/scheduler/` 真身 + `scheduler_route_registrar` 注册路径（已是生产唯一路径）。但**此条不建议现在清理**——尊重 roadmap `p1-scheduler-debt-cleanup-roadmap.md:522` 的有意延期，挂到该 roadmap 的 wrapper 清理 PR 里，按上述三前置一次性收口。在那之前保持现状即可，不属于「该立即还的债」。

**复核结论**：✅**证据仍准（行号完全未变）**。9 个 wrapper 文件全部在位，`scheduler_run.py:7-8` 别名样板、`_scheduler_compat.py` 存在且 `raise ModuleNotFoundError`、`factory.py:449` 生产入口、registrar `_ROUTE_MODULES`(14 叶子)、roadmap `:522` 延期句、`LEGACY_SCHEDULER_WRAPPERS:12`(列全 9 个) 均逐条复核为准。

---

### 12.5 【P5｜low｜load_bearing=false】scheduler_navigation_publish.selected_plan_role 是 core schedule_result_view_context.selected_plan_role 的副本

**位置**
- `web/routes/domains/scheduler/scheduler_navigation_publish.py` `selected_plan_role:31-32`（另 `requested_plan_role:27-28` 同理）

**引用链（已逐条复核）**
- web 版 `selected_plan_role:31-32 return str(plan_resolution.get("selected_role") or ROLE_ADOPTED)`。
- 收口点 `core/services/scheduler/schedule_result_view_context.py:201-202 def selected_plan_role(...): return str((plan_resolution or {}).get("selected_role") or ROLE_ADOPTED)`——已存在的统一点。
- `core/services/scheduler/gantt_plan_query.py:46-47` 已做过一次 re-export 包装（`:18 selected_plan_role as _selected_plan_role`，`:46 def selected_plan_role(...)` → `:47 return _selected_plan_role(...)`），是「正好做这种统一」的现成先例。
- web 版被真实调用（非死代码）：`scheduler_week_plan.py:37`(import)、`:337 effective_plan_role=selected_plan_role(plan_resolution)`；`scheduler_gantt.py:29`(import)、`:298 effective_plan_role=selected_plan_role(plan_resolution)`。两处都只作为模板**显示**用 kwarg `effective_plan_role=`，不进任何闸门。

**为何算债**
已有收口点（core `selected_plan_role`）的取值职责在 web 层又私实现一遍，绕过了已存在的统一点。属轻量 P5——3 行 getter，是同概念第三处落地（core 原版 `:201` + `gantt_plan_query` re-export `:46` + 这里 `:28`）。

**对抗验证结论（real_debt，且推翻了原始 finding 的一处事实陈述）**
对抗验证确认是可收的真债，**但推翻了原始 finding「只是 web 版多加 or ROLE_ADOPTED 兜底」这句**——事实正相反：两版都有 `or ROLE_ADOPTED`，且 **core 版更稳健**（`:202` 的 `(plan_resolution or {})` 额外处理了 None）。因此原始 finding 担心的「统一会改变缺 selected_role 时的角色」是**不成立的**——两者对缺失 selected_role 都返回 'adopted'，统一只会保持或增强行为。另外：web 与 core 都 import 同一个 `ROLE_ADOPTED`(`core/models/schedule_plan_role.py:5 ='adopted'`)，无取值漂移；真正的安全闸门(can_dispatch/can_write_feedback/is_scenario_preview/is_superseded_by_newer_version 等)走**独立的** `_PLAN_GUARD_FIELD_NAMES`/`_plan_guard_fields` 路径(`scheduler_navigation_publish.py:12-21,75-86`)，`selected_plan_role` **不是**预览/版本/派工闸门。

**爆炸半径**
改动小且安全：让 web 版直接 re-export core（照搬 `gantt_plan_query.py:46` 写法）即可。等价性已实证，week_plan/gantt 行为不变（仅显示 kwarg）。唯一注意：`requested_plan_role:27-28`（core 无同名函数，等价逻辑内联在 `schedule_result_view_context.py:74-79` 区域）若一并收口需另抽 helper，属清洁度优化、非安全必需。

**处置建议（收口到哪个已存在统一点）**
收口到 `core/services/scheduler/schedule_result_view_context.py:201 selected_plan_role`。把 web 版改为 `from core.services.scheduler.schedule_result_view_context import selected_plan_role`（或照 `gantt_plan_query.py:46` 做一层 re-export）。改后跑 `tests/regression_reports_workbench_navigation_contract.py` 及 week_plan/gantt 回归即可。`requested_plan_role` 可选地一并提一个 core 共享 helper 承载（清洁度优化）。

**复核结论**：⚠️**行号已变（一处消费方 +5）**。web 版 getter `:28-29`、`requested_plan_role:24-25`、core `:201-202`、`gantt_plan_query.py:46-47`、`scheduler_week_plan.py:337` 均复核为准。唯一漂移：消费方 `scheduler_gantt.py` 由旧证据 `:293` 移到当前 `:298`（import 在 `:29`）。core 版更稳健(`:202` 处理 None)这一对抗结论复核为准，原始 finding 的「web 多加兜底」措辞确属事实倒置。
