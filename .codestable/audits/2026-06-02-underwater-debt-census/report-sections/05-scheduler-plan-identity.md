## 05 · 分区【scheduler-plan-identity】方案身份解析核心(version_resolution / plan_query)

> **分区健康一句话**：有残渣、非重灾。任务预设的两大重灾点已被治理(被点名的 P1 `ADOPTED_PLAN_RESOLUTION` 常量假冒已彻底删除、`execution_review` 改走真解析;canonical P2 `execution_review` 只复盘 adopted 的承重不对称已被 UI 文案 + disabled 原因 + 导航强制 + 合同测试四层护住)。核心解析链(`schedule_plan_query_service` / `schedule_plan_identity_builder` / `schedule_plan_query_repo`)本身干净:`plan_id` 全链零真实消费,坏数据多处主动抛错(`build_plan_identity` 空 source 即抛、repo `_require_candidate_id` / `_require_scenario_id` 抛、`normalize_plan_role` 非法 role 抛)。真正水下的剩余债共 5 条:1 条承重护栏缺改动点本地注释(P2,load_bearing)、1 条死兼容 shim(P3)、1 条手搓双 dict 私实现无 parity 测试(P5)、1 条身份计算里静默吞坏 JSON(P4,load_bearing 但低危)、1 条 `_normalize_role` 字节级副本(P5 小)。

**复核口径说明**：本分区 5 条全部回到当前 `codex/aps-three-gap-directions` 分支代码逐条 grep/Read 复核。多数文件未被修复 agent 改动,行号仍准;个别条目原证据里写的是裸文件名(未带目录)或键数有 ±1 偏差,已在各条"复核结论"里如实订正。**审计期间未改动任何代码文件。**

---

### 5.1 【P3 · medium · load_bearing=false】gantt_plan_query 收口迁移后遗留的死兼容 shim

**位置**
- `core/services/scheduler/gantt_plan_query.py:32` `default_plan_resolution_dict`(透传到 `_default_plan_resolution_dict`,外加遗留错误文案包装)
- `core/services/scheduler/gantt_plan_query.py:42` `resolve_plan`(纯透传 `_resolve_plan`)
- `core/services/scheduler/gantt_plan_query.py:46` `selected_plan_role`(纯透传 `_selected_plan_role`)
- `core/services/scheduler/gantt_plan_query.py:59` `_has_explicit_gantt_range`(纯透传 `_has_explicit_display_range`)

**引用链(迁移已完成、wrapper 已死的实证)**
- 历史:`git 4428c75a` 时 `resolve_plan` / `selected_plan_role` 原定义在 `gantt_plan_query`;`git 35b3c138` 提交说明明写"把…解析规则收口到 `schedule_result_view_context`。保留 `gantt_plan_query` 的兼容 wrapper,老调用方不用一次性迁移"。
- 这 4 个符号自此变成对 `schedule_result_view_context` 的纯透传(见 `gantt_plan_query.py:11-19` 的 `as _xxx` 别名导入)。
- 全仓实证迁移已完成、wrapper 已死:
  - `gantt_plan_query.resolve_plan`、`gantt_plan_query.selected_plan_role`:全仓(含 tests)0 个走 `gantt_plan_query.` 模块路径的引用。真正存活的 `selected_plan_role` 调用方(`gantt_critical_chain_provider.py:12,152`、`gantt_service.py:34,325,345`、`scheduler_gantt.py:29,298`、`scheduler_week_plan.py:37,337`)**全部直接 import 自 `schedule_result_view_context`,绕过本 shim**。
  - `default_plan_resolution_dict` 的 `gantt_plan_query` 模块路径:仅 `tests/regression_schedule_result_view_context.py:295,298` 一条测试续命(`gantt_plan_query.default_plan_resolution_dict("bad")`)。其余 5 处生产调用(`gantt_critical_chain_provider.py:141`、`gantt_service.py:167`、`scheduler_navigation_publish.py:69`、`scheduler_week_plan.py:74`、`report_plan_preview.py:37`)均直引 `schedule_result_view_context`。
  - `_has_explicit_gantt_range`:全仓 0 caller(仅 `gantt_plan_query.py:59` 的 `def` 本身)。
- 关键对照:`gantt_service.py:12-17` 从 `gantt_plan_query` import 的是**另外 4 个 range 辅助函数**(`attach_gantt_range_metadata` / `build_empty_week_plan_payload` / `get_version_time_span_dates` / `resolve_gantt_range_for_version`),它们仍是 `gantt_service` 真用的活函数;而 `default_plan_resolution_dict` / `selected_plan_role` 它在 `gantt_service.py:29-35` 是从 `schedule_result_view_context` 直引的,**没走 shim**。

**为何算债**
迁移做了一半:"收口到 view_context" + "迁移老调用方直引 view_context"两步都完成了,但收口后留下的空壳 shim 没删,留下 4 个零生产消费的"假在用"符号(其中 `default_plan_resolution_dict` 还靠 1 条测试人工续命),制造 `gantt_plan_query` 仍是解析入口的假象。属 P3 半截迁移残渣。

**爆炸半径**
删除这 4 个死符号(及 `regression_schedule_result_view_context.py:294-298` 那条仅测 wrapper 透传/遗留文案行为的测试)安全;但 **`gantt_plan_query.py` 文件整体不可删**——它还有 4 个被 `gantt_service` 真用的 range 辅助函数(`get_version_time_span_dates` / `resolve_gantt_range_for_version` / `attach_gantt_range_metadata` / `build_empty_week_plan_payload`)。若误判"整模块死"而删文件,会直接打断甘特周计划范围解析。

**处置建议**
删除 `gantt_plan_query.py:32-47` 的 `default_plan_resolution_dict` / `resolve_plan` / `selected_plan_role` 三个透传 wrapper,以及 `:59-71` 的 `_has_explicit_gantt_range`;同步删 `:11-19,23-25` 对应的 `as _xxx` 别名导入。收口到的统一点已存在:`schedule_result_view_context`(`default_plan_resolution_dict`@73、`resolve_plan`@~190、`selected_plan_role`@201)与 `schedule_result_view_range.has_explicit_display_range`。**⚠️ 删 `default_plan_resolution_dict` wrapper 前须先迁移它身上那段"遗留错误文案包装"**(`gantt_plan_query.py:35-38`,把 `ValidationError` 的 `plan_role` 报错重写成历史文案"未知的排产方案角色:{role}")——若有调用方依赖这条特定中文文案,需把它移到 `normalize_plan_role` 或上游;否则删 wrapper 会改变错误文案。F5 的处置说明也明确要求"务必保留 `gantt_plan_query.py:32-38` 的遗留错误文案包装"。

**复核结论**：✅ 证据仍准。`gantt_plan_query.py` 当前未被改动,4 个死符号行号与原证据 `42,46,32,59` 完全一致。grep 复证:`selected_plan_role` 全仓调用方均直引 `schedule_result_view_context`、`_has_explicit_gantt_range` 0 caller、`default_plan_resolution_dict` 走 `gantt_plan_query` 路径的唯一引用仍是 `regression_schedule_result_view_context.py:298`。

---

### 5.2 【P2 · medium · load_bearing=TRUE】⚠️承重护栏:execution_review 服务方法写死 ROLE_ADOPTED/scenario_id=None 的不对称,改动点本体无注释保护

**位置**
- `core/services/report/execution_review.py:141-150` `execution_review(version, *, date_from, date_to, batch_id, resource_type, resource_id)` —— **形参刻意不收 `plan_role` / `scenario_id`**
- `core/services/report/execution_review.py:153` 方法体内恒 `resolution = host._resolve_plan(v, ROLE_ADOPTED, None)`
- `core/services/report/execution_review.py:112,114` `_execution_review_plan_rows` 走 between 分支恒 `plan_role=ROLE_ADOPTED, scenario_id=None`
- `core/services/report/execution_review.py:123,125` 走 all 分支同样恒 `plan_role=ROLE_ADOPTED, scenario_id=None`
- `core/services/report/execution_review.py:166-167` 返回 dict 恒 `plan_label=plan_role_label(ROLE_ADOPTED), plan_role=ROLE_ADOPTED`

**引用链(不对称的实锤 + 护栏分布在四层远处)**
- **不对称对照**:同属 `ReportEngine` 的 sibling 报表方法全部签名带 `plan_role` + `scenario_id` 并透传:`report_engine.py:157` `overdue_batches(self, version, plan_role=None, scenario_id=None, ...)`、`:267` `utilization(...)`、`:371` `downtime_impact(...)`。已逐个读证:`overdue_batches` 在 `:168` `self._resolve_plan(v, plan_role, scenario_id)`、`:169-176` 把 `plan_role/scenario_id` 透传进 `_fetch_overdue_base_rows_for_plan`。**唯独 `execution_review`(:141) 拒带这两个形参。**
- **取数源真会随 role/scenario 改变(护栏不是装饰)**:`schedule_plan_query_service.py` 的 `resolve_plan_view` 中 `scenario_id` 非空即转 `_resolve_scenario_plan` → 返回 `source_table=SOURCE_ADJUSTMENT_SCENARIO_ROWS`、`is_scenario_preview=True`;非 adopted role 选不同 `candidate_id` / `source_table`。`report_plan_helpers.py:56` `_list_plan_rows_between` / `:83` `_list_plan_rows_all` 把 `plan_role/scenario_id` 透传进 detail 取数,FROM 解析出的 `source_table/candidate_id` 决定取哪张表的行——所以 `execution_review` 写死 adopted 是数据层最后一道把关。
- **护栏的"理由"分布在四层远处(都不在改动点本地)**:
  1. 导航强制:`web/navigation_context.py:80-82` —— `is_execution_review` 为真时 `plan_role = ROLE_ADOPTED`、`scenario_id = ""`,把执行复盘请求的 role/scenario 强制清成 adopted。
  2. 入口禁用:`web/viewmodels/scheduler_workbench_links.py:271` `_is_formal_adopted_context`、`:310-311` `if target_page == "execution_review" and not _is_formal_adopted_context(context): return "计划和现场实际只复盘正式采用方案,请切换到正式采用方案后查看。"`;`:267` context_summary 追加"只复盘正式采用方案"。
  3. 用户文案:`web/viewmodels/scheduler_reports_workbench.py:210` "只复盘正式采用方案,不复盘模拟预览和对比参考方案。"
  4. 合同测试钉死:`tests/regression_reports_workbench_backlink_contract.py:266` `test_execution_review_stays_formal_and_links_to_site_record_entry`、`:347` `test_non_adopted_report_nav_disables_execution_review_link`;另有 `regression_reports_workbench_navigation_contract.py:274,450`、`regression_scheduler_workbench_link_guardrails.py:105,128`、`regression_scheduler_workbench_links_contract.py:300`、`regression_plan_vs_actual_review.py:356`、`regression_workbench_nav_entry_contract.py:172` 多处断言"只复盘正式采用方案"。

**为何算债**
这是任务点名的 canonical P2:`execution_review` 刻意拒带 `plan_role`/`scenario_id`,以防模拟预览 / 对比参考方案冒充正式现场复盘——**承重**(删了会让模拟预览数据混入正式现场复盘并可导出)。护栏在 UI / 导航 / 用户文案 / 测试四层都有,但 `execution_review.py:141` 这个**发生不对称的服务方法本体没有任何 inline 注释**说明"我故意和 overdue/utilization/downtime 不一样"。未来 LLM 以"与同类报表方法保持一致"名义给 `execution_review` 补 `plan_role` 形参时,在改动点本地看不到任何阻止信号——这正是承重护栏无注释的典型隐患。

**爆炸半径**
若给 `execution_review` 补 `plan_role`/`scenario_id` 透传:模拟预览 / 对比参考方案的计划时间会和正式现场反馈拼成"计划 vs 实际"复盘并可经 `export_execution_review_xlsx`(`execution_review.py:178-219`)导出,污染唯一可信的正式复盘口径。返回 dict(`:164-176`)既不携带也不拦截 `is_scenario_preview`,预览行会**静默**拼进结果,违背灵魂暗线"坏数据/预览不可静默冒充正式"。链接生成 / 导航类合同测试会拦住一部分入口,但**服务层契约本身已被破坏**——当前全仓无任何测试 `GET /reports/execution-review?plan_role=<非adopted>&scenario_id=X` 并断言服务端回退 adopted,这是最大缺口。

**处置建议(收口到哪个统一点 + 该补的"我是故意的"注释)**
本条**首选不动逻辑、只补防御**。统一点就是 `execution_review` 自身写死 adopted 这一行为,需要做的是把分散在四层的"理由"钉回改动点本地:

1. **(最小、强烈建议立即做)在 `execution_review.py:141` 签名处补 inline 注释**,文案建议:
   > ```python
   > def execution_review(
   >     self,
   >     version: int,
   >     *,
   >     date_from: Any = None,
   >     date_to: Any = None,
   >     batch_id: Any = None,
   >     resource_type: Any = None,
   >     resource_id: Any = None,
   > ) -> Dict[str, Any]:
   >     # 【故意】本方法只复盘 ROLE_ADOPTED(正式采用方案),刻意不收/不透传 plan_role、
   >     # scenario_id —— 与 sibling overdue_batches/utilization/downtime_impact 的不对称是
   >     # 设计而非疏漏。原因:计划-现场实际复盘只对"正式采用方案"成立,若放开 role/scenario,
   >     # 模拟预览(SOURCE_ADJUSTMENT_SCENARIO_ROWS, is_scenario_preview=True)与对比参考方案
   >     # 的计划时间会被拼进"计划 vs 实际"并导出,冒充正式现场复盘、污染唯一可信口径。
   >     # 护栏分布:navigation_context.py:80-82 强制 adopted、scheduler_workbench_links.py:310-311
   >     # 禁用非 adopted 入口、reports_workbench.py:210 用户文案、backlink/navigation 合同测试。
   >     # 若确需放开,改动前必须先满足下方"放开前置条件"三件套(见审计报告 5.2)。
   > ```
   并在 `:112,114,123,125` 写死 `plan_role=ROLE_ADOPTED, scenario_id=None` 处补一行短注释 `# 故意写死 adopted,见 execution_review() 顶部说明`。

2. **(若未来真要放开,对抗验证给出的硬前置条件,缺一不可)**
   - (a) 在取数边界保留强制 adopted:要么继续写死,要么加 service 层断言——`execution_review` 收到非 adopted role 或任何 `scenario_id` 时 `raise ValidationError`(loud,**不得静默回退**),并在返回前校验 `resolution.is_scenario_preview is False`。
   - (b) **新增请求级合同测试(当前最大缺口)**:`client.get('/reports/execution-review?version=..&plan_role=baseline_best&scenario_id=..')` 断言返回 rows 与 `plan_role` 仍为正式采用方案、导出 xlsx 不含预览/对比数据。当前全仓只有 `backlink:355` 一条负向 `assert(... not in html_text)`,无任何服务端回退断言。
   - (c) 同时把 `web/routes/reports_page_support.py`(执行复盘路由自身亦写死 adopted、从不读 request 的 plan_role/scenario_id)与 export 路由接上请求值——注意 sibling 路由 `reports_page_support.py` 用 `request_plan_role()`,证明"与同类对齐"的统一压力真实存在。

**复核结论**：✅ 证据仍准(行号精确)。`execution_review.py` 当前已是 git modified,但复核确认写死点仍在原行:`:153` `host._resolve_plan(v, ROLE_ADOPTED, None)`、`:112/114` 与 `:123/125` 的 `plan_role=ROLE_ADOPTED, scenario_id=None`、`:166-167` 返回值;形参(`:141-150`)仍不收 `plan_role`/`scenario_id`,本体仍无任何 inline 注释。sibling 不对称已复证:`report_engine.py:157 overdue_batches` 形参带 `plan_role/scenario_id` 且 `:168` 透传。两条 backlink 合同测试名仍在(`:266` / `:347`)。唯一需订正的引用细节:原证据写"`navigation_context.py:80-82`"为**裸文件名**,实际路径是 **`web/navigation_context.py:80-82`**(内容一致)。

---

### 5.3 【P5 · medium · load_bearing=false】default_plan_resolution_dict 手搓 plan_identity + resolution 双私有实现,绕过 build_plan_identity / SchedulePlanResolution.to_dict,且无 parity 测试

**位置**
- `core/services/scheduler/schedule_result_view_context.py:77-100` 手搓 `plan_identity` dict(22 键)
- `core/services/scheduler/schedule_result_view_context.py:101-147` 外层 resolution dict
- 调用点:`schedule_result_view_context.py:440`(`no_history` 路径)与 `:448`(`missing_history` 路径)各 `plan_resolution=default_plan_resolution_dict(raw_plan_role)`

**引用链**
- canonical 身份产出口:`build_plan_identity`(`schedule_plan_identity_builder.py:123`)→ `PlanIdentity.to_dict`(`core/models/schedule_plan_identity.py:44`)。
- canonical 外层 resolution 产出:`SchedulePlanResolution.to_dict`(`core/models/schedule_plan_resolution.py:64`)。
- `default_plan_resolution_dict` 在 `no_history`/`missing_history` 两条路径手工拼出同形状的两个 dict,而不委托上述 canonical。
- **"无法委托"理由(对抗验证已推翻)**:`schedule_plan_identity_builder.py:145-146` 对空 `source_table` 主动抛"计划身份缺少有效的数据来源";但该抛错只在 `source ∉ {schedule, candidate_rows, adjustment_scenario_rows}` 时触发。而本占位手搓 dict 的 `source_table` **写死为 `SOURCE_SCHEDULE="schedule"`**(`view_context.py:82` 内层、`:107` 外层),并非空来源 → 走 `build_plan_identity(version=None, source_table='schedule', ...)` 可通过,**今日委托即零差异**。
- **键集核验**:`PlanIdentity.to_dict`(`schedule_plan_identity.py:44-67`)与手搓 `plan_identity`(`view_context.py:77-100`)逐键对齐(今日 0 漂移)。但 grep 实证 `tests/regression_schedule_result_view_context.py` 中 **`build_plan_identity` 出现 0 次**(已 `git grep -c` 复证),即**无任何断言两者键集/取值一致的 parity 测试**。
- **手搓外层反而是 canonical 的子集**:`schedule_plan_resolution.py:64-103` 的 canonical 外层 `to_dict` 是手搓外层的超集——手搓侧缺 `schedule_result_status` / `schedule_lock_status` / `detail_saved` 三键(这三键下游均 `.get()` 读取,无害)。它已非忠实的第二实现,靠"缺键"先一步偏离。

**为何算债**
同一"计划身份 / 解析结果"概念的第二套私有构造,与统一收口点(`build_plan_identity` + `SchedulePlanResolution.to_dict`)并存。今日键集恰好对齐属侥幸——一旦 `PlanIdentity` 增删字段,canonical 侧自动跟随、手搓侧不会,且无测试报警。下游 `plan_role_filter_fields` 的 `_identity_bool`(`view_context.py:271-274`)对缺失键 `.get()` 静默取 `False`,会在"无历史"页面悄悄给出错误的 `is_official` / `can_dispatch` 等。属 P5 第二套私有实现 + 漂移隐患。

**爆炸半径**
误删 / 改坏这个手搓 dict,会让 `no_history`/`missing_history` 页面的资源派工与报表页 `plan_role` 过滤字段崩塌(`KeyError` 或全 `False` 误判);反之放任不管,则承担未来字段漂移时的**静默错值**风险。

**对抗验证裁定(real_debt,但安全方向无虞)**
对抗验证确认这是"第二套该收口的实现"而非"无数据合法占位"。决定性安全证据:**写 / 派工变更不信任该视图 dict**——`operation_execution_feedback_service.py:361` 重新 `resolve_plan_view(...)` 读真 `plan_identity.can_write_feedback`;`resource_dispatch_actual_record_service.py:137` 同样以 `can_write_feedback` 为闸。手搓 dict 仅供**只读的无历史页**。且占位中 `can_dispatch`/`can_write_feedback`/`is_current_executable_official_version` 全硬编码 `False`(`view_context.py:93-94,98`),`_identity_bool` 用 `.get()` 未来缺键 → `False` = 拒绝 = 安全方向,符合灵魂暗线。

**处置建议(收口到统一点)**
1. **先补 parity 测试(对抗验证指出的缺口)**:对 `VALID_PLAN_ROLES` 全集,断言 `default_plan_resolution_dict(role)['plan_identity']` 的键集 + 取值 `== build_plan_identity(无历史输入, source_table='schedule', ...).to_dict()`,并断言外层 dict ⊆ `SchedulePlanResolution.to_dict`。
2. **再把占位委托给 canonical**:`default_plan_resolution_dict` 内部改为调 `build_plan_identity(version=None, source_table=SOURCE_SCHEDULE, ...)` + `SchedulePlanResolution.to_dict`。无历史时多出的 `schedule_result_status` / `schedule_lock_status` / `detail_saved` 三键下游均 `.get()` 读取,无害。
3. **注意外层 `view_context.py:142` `is_official` 用方括号取值**(`plan_identity["is_official"]`,非 `.get()`),收口后改走 `.get()` 反而更稳。
4. **务必保留 `gantt_plan_query.py:32-38` 的遗留错误文案包装**(与 5.1 同一处)。
5. 最后跑 `tests/regression_schedule_result_view_context.py` 与派工 / 反馈契约测试自证行为不变。

**复核结论**：✅ 证据仍准,2 处行号需微订正。`schedule_result_view_context.py` 当前未被改动,手搓 `plan_identity` 仍在 `:77-100`、外层 dict 仍在 `:101-147`。调用点原证据写"`view_context.py:437-449`",复核实际为 **`:440`(no_history)与 `:448`(missing_history)** —— 在原区间内、表述更精确。`_identity_bool` 原证据 `:271-274` 仍准。`tests/regression_schedule_result_view_context.py` 仍 `build_plan_identity` 0 次(parity 测试仍缺)。**🔧 键数订正**:原证据称手搓 `plan_identity`/canonical `to_dict` 为"23 键",**实际复核两侧均为 22 键**(canonical `to_dict` 见 `schedule_plan_identity.py:46-67`,共 22 个键值对;手搓 dict `view_context.py:78-99` 亦 22)——结论"今日键集 0 漂移"不变,仅键计数 -1。

---

### 5.4 【P4 · low · load_bearing=TRUE】⚠️承重(低危):_bool_from_summary 静默吞掉损坏的 result_summary JSON,影响 is_official / 可执行版本 / 可派工判定

**位置**
- `core/services/scheduler/schedule_plan_identity_builder.py:24-29` `_bool_from_summary` 内 `except (TypeError, ValueError): return False`

**引用链**
- `_bool_from_summary` 被 `_history_is_executable`(`:36`)与 `build_plan_identity`(`:150`)调用判 `is_simulation`。
- `is_simulation` 喂入 `_is_official_plan`(`:87-95`,`not is_simulation`)与 `latest_executable_official_version`(`:41-45` 经 `_history_is_executable`)。
- 进而决定 `is_current_executable_official_version`、`can_dispatch`、`can_write_feedback`(`build_plan_identity` 返回的 `PlanIdentity` 字段,`:199,202-203`)。
- `latest_executable_official_version` 的实际消费点:`schedule_plan_query_service.py:99` `latest_official_version=latest_executable_official_version(self.repo.list_history_identity_rows())`。
- 写入侧:`result_summary` 恒由 `schedule_orchestrator` 链的 `build_result_summary_fn` 产 `json.dumps`(`summary/schedule_summary.py:216` `result_summary = json.dumps(result_summary_obj)`,从不手写);`schema.sql` `result_summary TEXT`(可空)。
- 读回:repo `schedule_plan_query_repo.py:80-81`(`list_history_identity_rows`)与 `:104-105`(`get_history_identity_row`)同时 SELECT `h.result_status` 与 `h.result_summary`。

**为何算债**
项目灵魂线是"坏数据不准静默兜底、宁可暴露错误"。此处对损坏 JSON 直接 `except → return False`,把"这条历史的 summary 解析失败"当成"不是模拟"的安全默认,使一条 summary 损坏的记录可能通过 `_history_is_executable` 被选为 `latest_executable_official_version`、并被判 `is_official`。错误被吞,不会让用户 / 运维看见数据缺口。属 P4 静默兜底死角。

**爆炸半径**
改成抛错可能让历史含 NULL / legacy 非 JSON summary 的老库在版本身份解析处直接报错(影响面 = 身份解析全链);保持吞错则牺牲"坏数据可见性"。**低危**,因 `result_summary` 正常恒为机器写 JSON、损坏罕见。

**对抗验证裁定(real_debt,但"承重"含义被精确化、且不可原地改 raise)**
- 对抗验证**推翻了"这处 summary 解析是安全护栏"的说法**:真正承重的是 `result_status='simulated'`(由同一 `ctx.simulate` 原子同写),而非这处 summary 判定。
  - Gate 顺序证据:`schedule_plan_identity_builder.py:33-35` 先查 `result_status in _BLOCKED_RESULT_STATUSES {failed, simulated}`,**早于**(且独立于)`:36` 的 summary gate;每个真模拟先被 Gate1 拦下。
  - `summary/schedule_summary_freeze.py:82-86` `_compute_result_status`:`if simulate: return SIMULATED.value` → 每次模拟跑都被强制 `result_status='simulated'`。
  - `summary/schedule_summary_assembly.py:437` `"is_simulation": bool(ctx.simulate)` 与 `result_status` 同源(冗余副本)。
  - 写入原子性:`run/schedule_persistence.py:309-318` + `data/repositories/schedule_history_repo.py:133-150` 在一条 INSERT 里同写 `result_status` 与 `result_summary`,正常路径下不会分叉。
  - 危险动作闸独立由 `result_status` 兜底:`:161-163` `result_ok = result_status not in _BLOCKED_RESULT_STATUSES`;`is_current_official = is_official and is_current and result_ok`。实际危险派工 / 反馈写入(`resource_dispatch_actual_record_service.py:137`)gate 在 `can_write_feedback`(要求 `is_current_official ⇒ result_ok`),从不单靠 summary `is_simulation`。
  - 所以:删 / 统一这处 summary 判定**不会**让模拟冒充正式或可派工。该处之所以仍标 `load_bearing=true` 并不是因为它独自挡住模拟,而是因为它处在 `is_official` 链路上、且**绝不可原地改成 raise**(见下)。

**处置建议(关键:不可原地 raise)**
- **(硬约束)绝不可把 `:28` 改成 `raise`**——`latest_executable_official_version`(`:41-45`)全量扫历史行,任何一条 legacy/NULL 邻接的损坏 summary 都会让当前方案的 `is_current_executable_official_version` / `can_dispatch` / `can_write_feedback` 整链抛错,这是可用性放大事故而非安全收益。
- **若要落实灵魂线"坏数据可见"**:在读边界加一条**非致命**的完整性日志 / 计数,标记出无法解析的 `result_summary`(例如 `_bool_from_summary` 解析失败时打 warning 日志 + 计数器),而不是让版本身份解析崩溃。这是"暴露而不自欺"与"可用性"的折中收口点。
- **若要移除这处冗余的 summary-based `is_simulation` 判定**(因 `result_status='simulated'` 已是同源权威):先确认没有任何写入方会在不同写 `result_status` 的情况下单独写 `result_summary.is_simulation`(当前 INSERT 是原子同写,成立),然后可删 `:36` 与 `:150` 的 summary 判定,统一信任 `result_status`。

**复核结论**：✅ 证据仍准(基线 `b08162cd`)。⚠️ **工作树超前治理**:该 P4 债在当前 staged 未提交工作树中已被治理(`_bool_from_summary` → `_parsed_summary_flag_is_true(fail_closed=True)` + 新增 `result_summary_parse_failed/_reason` 可见标记),详见 §13.5。以下复核针对 `b08162cd`:`_bool_from_summary` 的 `except (TypeError, ValueError): return False` 仍在 `:24-29`;Gate 顺序(`:33-35` 先于 `:36`)、`build_plan_identity` 的 `:150` 调用、`latest_executable_official_version` 的 `:41-45` 全量扫描均与原证据一致。消费点 `schedule_plan_query_service.py:99` 复证存在;repo 双 SELECT(`:80-81` / `:104-105`)复证。危险动作闸 `can_write_feedback` 在 `resource_dispatch_actual_record_service.py:137` / `operation_execution_feedback_service.py:361` 复证。

---

### 5.5 【P5 · low · load_bearing=false】_normalize_role 在 schedule_plan_role 与 schedule_plan_query_service 字节级重复,且无 plan_role 归一收口点

**位置**
- `core/models/schedule_plan_role.py:21-23` `def _normalize_role(role)`
- `core/services/scheduler/schedule_plan_query_service.py:28-30` `def _normalize_role(role)`

**引用链**
- 两处函数体逐字符相同:`text = str(role or "").strip(); return text or ROLE_ADOPTED`(已逐字复核,完全一致)。
- `dup_symbols.json` 未单列(均为模块私有 `_` 前缀符号)。
- `schedule_result_view_context.py:65` 另有 `normalize_plan_role` 是**带校验**的第三变体(非法 role 抛 `ValidationError`),职责更重,不在本条合并范围。
- 已知收口点核验:grep 实证仓内**无 `enum_normalizers` / `normalization_matrix` 文件**,也无任何 `plan_role` 归一逻辑(即该收口点不存在)。
- `query_service._normalize_role` 完全可 `import` 自 `schedule_plan_role`——`schedule_plan_query_service.py:9-20` 已从 `core.models.schedule_plan_role` import 了 `ROLE_ADOPTED` 等一批符号,加 `_normalize_role` 零成本。

**为何算债**
同一"role 归一(空 → adopted)"职责的两份完全相同私有副本;`schedule_plan_role`(model 层)已是天然归口,`query_service`(service 层)重复造一遍而非复用。属轻度 P5,改一处易漏另一处。

**爆炸半径**
极小:让 `query_service` 复用 `schedule_plan_role._normalize_role` 即可;两者今日行为一致,合并无语义风险。

**处置建议(收口到统一点)**
删 `schedule_plan_query_service.py:28-30` 的本地 `_normalize_role` 定义,改从 `core.models.schedule_plan_role` import(把它加进 `:9-20` 已有的 import 块)。统一点就是 model 层的 `schedule_plan_role._normalize_role`。注意此符号是 `_` 私有,若顾虑跨层引私有名,可在 `schedule_plan_role` 中把它提升为公开 `normalize_role`(无校验版,区别于 `view_context.normalize_plan_role` 带校验版)再 import。

**复核结论**：✅ 证据仍准(行号精确)。两处 `def _normalize_role` 当前仍在 `schedule_plan_role.py:21` 与 `schedule_plan_query_service.py:28`,函数体逐字符相同。grep 复证仓内无 `enum_normalizers`/`normalization_matrix` 含 `plan_role` 的收口点。`view_context.py:65` 的带校验第三变体 `normalize_plan_role` 复证存在。
