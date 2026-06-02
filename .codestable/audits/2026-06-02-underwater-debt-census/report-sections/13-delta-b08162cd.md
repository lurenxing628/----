## 13 · 增量债 · b08162cd 工作台收口(基准 → 现状)

> 对基准 `65870e47` 之后唯一提交 `b08162cd`("完成报表工作台回跳验收")的同颗粒度 delta 普查。该提交动了 54 个生产文件,把 11 个报表/调度页收口到统一参数合同(reports.py -465 拆成多个新文件,新增 report_context_filters/reports_page_support/scheduler_reports_workbench 等)。
>
> **取证口径**:全部读 `git show b08162cd:<path>`(提交版本),不读工作区——工作区有 in-flight 改动会污染(本提交改的 38 个生产 py 里,有 7 个当前又被未提交工作区二次修改)。
>
> **方法**:4 分区并行 delta 普查 + 1 交叉核验官版本史考古,双信源互证 + 人工亲核关键条目。

### 分区总评:净减债,但增 2 笔承重语义债

`b08162cd` 这次收口**整体方向是减债**:堵掉 web 层私有数值解析、3 处 P4 静默兜底、硬编码 URL,资源归一真收口到单一 collar。代价是新增 2 笔承重/呈现级语义债(N1 护栏字段散 3 抄、N2 关键链子集冒充整版)+ 一批低危死代码残渣。**这正是健康项目演进的典型样态:大重构在堵旧出血的同时,会在新代码的接缝处长出新的失忆债——关键是接缝处的"立约"(注释/收口)有没有跟上。这次没完全跟上。**

---

## 13.0 【更正】原报告"P1 写死常量出血"是幻觉证据(版本史考古)

> 这不是增量债,是对基准报告一条核心结论的**诚实更正**。放在 §13 开头,因为它是用 b08162cd 增量普查的版本史工具才查清的。

**基准报告曾把"execution_review 用写死常量 `ADOPTED_PLAN_RESOLUTION`(reports_page_support.py:36)假冒方案身份"作为头号 P1 实证**,在执行摘要/封面/§90/§12 反复引用,称其为"失忆债最危险形态的实证、唯一已知出血"。

**增量普查证伪了它**:
- `git cat-file -e 65870e47:web/routes/reports_page_support.py` → `fatal: path ... exists on disk, but not in '65870e47'`。**该文件在基准根本不存在**,是 b08162cd 拆分 reports.py 时才新建——所以"基准 reports_page_support:36 有写死常量"在版本史上无法成立。
- `git log --all -S "ADOPTED_PLAN_RESOLUTION"` 全 ref pickaxe → **只命中 stash `725cca79`**("untracked files on codex/...: b08162cd"),且该字符串**只出现在审计自己的 `REPORT.md`/`_consolidated.json` 散文里**,没有任何 `.py` 文件含它。
- execution_review 在 b08162cd:153 调 `host._resolve_plan(v, ROLE_ADOPTED, None)`,真身 `report_plan_helpers._resolve_plan` → `plan_query_service.resolve_plan_view(...)`,`ValueError` 时 `raise ValidationError`——**自基线起即真解析,不存在写死常量假冒**。

**根因**:基准普查取证时读到的"reports_page_support.py:36"是一次工作区 in-flight 中间态(很可能是某个 agent 正在重构 reports.py 时的临时文件),被误当成了"基准事实"。**这是"活工作区污染"陷阱**——也是本报告生成全程反复踩的同一个坑的最深一层。

**处置**:全文凡引用"P1 出血/ADOPTED_PLAN_RESOLUTION 出血"处,应读作"普查快照污染,全项目 P1 真实计数 = 0 且版本史从无此例"。**核心论点不受影响**:承重护栏(execution_review 只复盘 adopted)无注释这条是铁证,独立于这条幻觉 P1 成立。诚实更正自己的错误,正是本项目灵魂线"宁可暴露错误也不自欺"的应用。

---

## 第一部分 · 已修复 / 消除的旧债(基准报告相关条目改标 🔧)

> 这次收口**真的修掉了**基准报告标记的若干债,对应条目的复核状态应更新为 🔧。

### 13.F1 🔧 web 层私有数值解析(疑似第 N 套)已整组删除

- **旧债**:基准 `reports.py:85-101`(65870e47)有 `_report_number`/`_report_nonnegative_int`,基于 `math.isfinite` 私有解析,与 core 解析并存。
- **已修复**:`git grep _report_number b08162cd -- web/` 为空;`reports_export_support.py:44-45` 改为薄封装 core 的 `parse_report_nonnegative_int`。
- **证据**:`git show 65870e47:web/routes/reports.py:85-101` vs b08162cd web 层零命中。

### 13.F2 🔧 报表行计算从 web 路由内联下沉到 viewmodel/exporter

- **旧债**:`reports.py:129-148,416-419`(65870e47)内联利用率换算/汇总求和。
- **已修复**:下沉到 `scheduler_reports_workbench.py:324,343` 与 `exporters/xlsx.py:60`;`reports.py` 收缩为 42 行纯路由。

### 13.F3 🔧 首页超期统计补齐方案/资源/批次全过滤

- **旧债**:`reports.py:150-160`(65870e47)取超期数时只 `engine.overdue_batches(latest_ver)`,丢弃 resource/batch/方案上下文。
- **已修复**:`reports_page_support.py:144-151` 补齐 plan_role/scenario_id/resource_type/resource_id/batch_id 全过滤。

### 13.F4 🔧 三处 P4 静默兜底改 loud(灵魂线落实)

- **旧债**:基准三处坏数据静默兜底——`_pause_duration_label`(`try: float(value or 0.0) except: 0.0`)、`_utilization_percent`(导出 `except: return value` 原样泄漏)、`_delay_text`(裸 `float()`)。
- **已修复**:全改走 `parse_report_float`/`parse_optional_report_float`,空值才给 0、非空非法直接 `raise ValidationError`。
- **证据**:`execution_review.py:377-384`、`exporters/xlsx.py:60-67`、`delay_diagnosis_presentation.py:78-83`。

### 13.F5 🔧 dispatch 现场记录入口 硬编码 URL → 计算值

- **旧债**:resource_dispatch 现场记录入口曾是硬编码字面量 `"/scheduler/resource-dispatch/execution/__OP_ID__/actual"`(不带 query 上下文)。
- **已修复**:改为 `_actual_record_url_template(filters)` 计算值,新实现 `scheduler_resource_dispatch_query.py:125-129`。

### 13.F6 🔧 甘特工作台链接死面包屑被接上消费端

- **旧债**:基准 gantt spec 发出 `resource_type/resource_id/batch_id`,但 gantt 路由(65870e47)根本不读这些键,链接参数全程被丢弃(基准报告 web-all P6 同源)。
- **已修复**:`link_query.py:31-38` 改 `gantt_filter`+`gantt_batch`,`scheduler_gantt.py:214,223,343-349` 新增对 `gantt_resource/gantt_batch` 的读取,面包屑被接上消费端。

### 13.F7 🔧 资源归一真收口(证实基准报告"第 N 套私有资源实现"已解决)

- **已收口**:`report_context_filters.normalize_report_resource_filter`(:119)做完报表特有别名合并(scope_*/machine_id/operator_id)后,在 **:148 委派给规范收口点 `normalize_schedule_resource_filter`**,不重复校验。报表全部入口经此一点:report_engine `:146/167/279/383`、web `request_resource_context.py:39`、`reports_request_support.py:54`;SQL 侧 `schedule_resource_sql_filters` 也 delegate 到同一 collar。
- **派工 team 轴非 P5**:resource_dispatch 不走此 collar 是因为有 team(班组)第三轴——collar 的 `SUPPORTED={machine,operator}` 表达不了,靠 SQL `(o.team_id=? OR m.team_id=?)` 双 join(基准报告 §90 LB-B 同源的承重不对称,b08162cd 未触碰)。刻意两轨并存,不是绕收口点。

---

## 第二部分 · 新引入的债(N1–N14)

### 承重级(高优先)

### 13.N1 【P5 · high · load_bearing=TRUE】⚠️execution_review 放行护栏依赖的 plan-guard 字段投影被切成 3 套手维 key 列表(本轮新增 2 份)

**位置**
- `git show b08162cd:web/viewmodels/scheduler_reports_workbench.py:40-53`(新增)
- `git show b08162cd:web/routes/domains/scheduler/scheduler_navigation_publish.py:12-21,72-85`(新增)
- 对照既有 `git show b08162cd:web/routes/domains/scheduler/scheduler_resource_dispatch.py:63-73`(基准已存在)

**引用链**
- 唯一应有收口点是 `schedule_result_view_context.py:277 plan_role_filter_fields`(一次性产出 requested_plan_role/effective_plan_role/plan_role_status/is_comparison/is_scenario_preview/is_superseded_by_newer_version/can_dispatch/can_write_feedback 全集)。
- 但 `build_workbench_plan_context`(`scheduler_workbench_links.py:183`)的入参**根本不承载这些 guard 字段**,只接受 plan_role/is_preview/can_write_feedback。
- 于是三处各自在 builder 输出后手工"补挂":reports_workbench 从 resolution 命名 `requested_role`/`selected_role` 映射(:42-48);navigation_publish 走 `plan_role_filter_fields` 取 8 键(:13-21);resource_dispatch 从 filter 命名 `requested_plan_role` 直拷 6 键(:64-72)。
- 下游 `_is_formal_adopted_context`(`scheduler_workbench_links.py:271-287`)正是读这些补挂字段(requested_plan_role/effective_plan_role/is_comparison/is_superseded_by_newer_version/scenario_id)来判 execution_review 是否放行。

**为何算债**:收口点 `build_workbench_plan_context` 不承载 guard 字段,导致"把方案护栏字段投进工作台上下文"有 **3 份私有实现**,且源键命名两套(`requested_role` vs `requested_plan_role`)、键集合三样(reports/resource 各 6 键无 plan_role_status,navigation 8 键)。**execution_review「只复盘正式采用方案」这条灵魂护栏的正确性被拆散到 3 张手维列表里**——任何一处漏拷 `is_superseded_by_newer_version`/`is_comparison`,旧正式版本就会被 `_is_formal_adopted_context` 判成 True 而放行写链接,正是 commit message 自己强调要防的"旧正式版本冒充现行正式采用方案"。本轮把这个脆弱模式从 1 处扩散到 3 处。

**爆炸半径**:报表中心/超期/利用率/停机/计划现场实际全部入口卡 + 行级动作,加甘特/周计划/分析/资源派工导航上下文,全依赖手拷字段的完整性;漏一键即 execution_review 写侧护栏静默失效。

**处置建议**:把 guard 字段投影收口进 `build_workbench_plan_context`(让收口点承载这些字段,从 `plan_role_filter_fields` 单一来源产出),删除三处手维拷贝。这是把"护栏正确性"从 3 张易漂移的手维列表收回单一权威点。**这是本提交最该回收的承重语义债。**

**复核结论**:✅ 证据仍准(已亲核三处 def 在 b08162cd 并存:`reports_workbench.py:40`/`navigation_publish.py:72`/`resource_dispatch.py:63`)。

### 13.N2 【呈现失真 · medium · P1 气味】筛选后的关键链把"周窗口子集"喂进"要求整版输入"的算法,以整版 makespan 对外且无 scope 标记

**位置**:`git show b08162cd:core/services/scheduler/gantt_service.py:335,340,375-377` + `gantt_service_support.py:57`

**引用链**
- `scheduler_gantt.py:347-349` `gantt_resource` 存在时 `resource_type=view; resource_id=gantt_resource`(含 :346 batch_id)→ `get_gantt_tasks` → `gantt_service.py:335` plan_detail_filter_kwargs → :340 `list_plan_detail_rows_between_for_resolution(**detail_filters, start_time=wr.start_str, end_time=wr.end_exclusive_str)`(**既按周窗口又按资源/批次过滤的 rows**)→ :375 `critical_chain_for_plan_detail_filter(rows, detail_filters)` → `gantt_service_support.py:57 compute_critical_chain_from_rows(rows)`。
- 无 filter 时(:376 None)才回落 provider,对全版 `list_by_version_with_details(version)` 计算。
- `compute_critical_chain` 文档不变量明示"输入:某一 version 的**全量排程(不按周截断)**"(`gantt_critical_chain.py:347`)。

**为何算债**:新路径喂的是窗口+过滤子集,算出的 ids/edges/makespan_end/edge_type_stats 只描述该子集,却经同一 contract 以 `available:True`、相同 `makespan_end`/关键链 UI 键对外,**无任何 scope=filtered 标记**区分。用户筛到单台设备/单批次时看到的"关键链"和"makespan"其实是子集内部链,被当成整版计划呈现。基准报告(`_load_bearing.json` 的甘特条目)只论两路归一一致、未察觉窗口/整版输入分叉,**此为漏网**。

**爆炸半径**:只读显示正确性——只要 gantt 带任一 resource/batch 过滤,关键链/makespan 数值即偏离整版计划真值且无提示;不损坏数据。

**处置建议**:在 contract 输出加 `scope: "filtered" | "full"` 标记,filtered 时 UI 明示"当前为筛选范围内的局部关键链"。或确认这是渲染刻意设计(若是,补注释说明为何 filtered 也叫 available)。

**复核结论**:⚠️ 中等置信(可能为渲染刻意设计但缺 scope 标记使其失真),建议 owner 确认设计意图。

### 13.N3 【P2 · medium · load_bearing=TRUE】⚠️navigation_context 的 execution_review 护栏靠 endpoint/path 字面量匹配且零注释(整文件新增)

**位置**:`git show b08162cd:web/navigation_context.py:42-47`(`_is_execution_review_request`)+ `:80-82`(`plan_role = ROLE_ADOPTED if is_execution_review else ...` / `scenario_id = "" if is_execution_review`)

**引用链**:`render_bridge.init_ui_mode` 把 `build_*_navigation_links` 注入 Jinja globals(`render_bridge.py:73-91`)→ 每页渲染调 `navigation_context.current_workbench_navigation_context()` → 命中 execution_review 分支强制 adopted/清空 scenario_id。判定靠 `endpoint == "reports.execution_review_page"` 或 `path == "/reports/execution-review"` 字面量匹配。

**为何算债**:这是 commit 自述的灵魂护栏("旧正式版本不能再被显示成现行正式采用方案"),属承重逻辑;但落地方式是路由名/路径**字面量匹配**,且全程无一行注释说明"为何复盘页必须剥离 plan_role/scenario_id"。`navigation_context.py` 整个文件是 b08162cd 新增——**这是本提交新引入的最脆弱承重点**:一旦未来有人重命名该路由或"顺手"删掉这个 if 特例,护栏静默失效、scenario_id 重新渗入复盘页导航,本地无任何阻止信号。

**爆炸半径**:全站导航 chrome;复盘页一旦泄漏 scenario_id,正式方案复盘会被模拟方案身份污染,直接违背本次收口目标。

**🔧 该补注释**(贴在 `navigation_context.py:80` 上方):
```python
# 故意:复盘页(execution_review)强制 plan_role=adopted、scenario_id="",剥离 request 的方案身份。
# 这是护栏——计划和现场实际只复盘正式采用方案,放开会让模拟预览/旧正式版本冒充现行正式复盘。
# 勿删此 if 特例,勿因重命名路由而让 _is_execution_review_request 失配(它靠 endpoint/path 字面量)。
```

**复核结论**:✅ 证据仍准(navigation_context.py:42-47,80-82 已核,整文件 grep `#` 护栏注释零命中)。

### 13.N5 【P2 · low · 护栏削弱】navigation_publish 把 builder 已 gate 的 can_write_feedback 覆盖回未门控值

**位置**:`git show b08162cd:web/routes/domains/scheduler/scheduler_navigation_publish.py:79-84`

**引用链**:`_publish_context` 先以 `can_write_feedback=guard_fields.get("can_write_feedback")` 调 `build_workbench_plan_context`——builder 内 `_feedback_guard_context`(`scheduler_workbench_links.py:145-157`)把它 gate 成 `can_write and formal_adopted`;随后 :83 `context.update(guard_fields)` 又用未 gate 的原始值(来自 `plan_role_filter_fields`,恒为 bool 故必被纳入)覆盖回去,**撤销了 builder 的门控**。

**为何算债**:写侧护栏(只有 formal_adopted 才可写现场记录)在 builder 里建好,又被发布层无注释地拆掉一半。当前低危——写链接放行实际走 resource_dispatch 的 `can_emit_feedback_write_urls`(读 filters,非此 nav context),故该覆盖暂未被消费;但 nav context 的 can_write_feedback 已是"非门控真值",一旦未来有人据此渲染写按钮即破。

**爆炸半径**:当前零(未被消费);潜伏——未来据 nav context 渲染写按钮会绕过门控。

**处置建议**:`:83 context.update(guard_fields)` 前剔除 `can_write_feedback`,或改用 builder gate 后的值。属潜伏护栏债,优先级中。

**复核结论**:✅ 证据仍准。

### 低危残渣(N4 / N6–N14)

### 13.N4 【P3 · medium】导航上下文双构建路径:fallback 直接信任未经 PlanIdentity 解析的 raw plan_role/scenario_id

**位置**:`git show b08162cd:web/navigation_context.py:76-98`(override 路径 :77-78 用真实 plan_resolution;fallback 路径 :80-98 用 `_request_arg("plan_role")`/`_request_arg("scenario_id")`,:87 `plan_role or ROLE_ADOPTED`)

**为何算债**:页面 context 已发布时走 override(经真实 PlanIdentity);未发布(报错页/其它 scheduler 页)走 fallback,只把 `request.args` 的 plan_role/scenario_id 原样塞进导航链接,**不向 schedule_plan_query_service 求证**。除 execution-review 外的页面若带 `?plan_role=adopted&version=<已被取代的旧版>`,fallback 生成的导航链接仍按 adopted 透传——这正是 commit 想消灭的"显示层自欺",只在 publish 路径和 exec-review 特例堵住,**generic fallback 仍是漏的**。两套路径对"当前方案身份"各执一词。

**爆炸半径**:非复盘页的跨页回跳链接 query 参数;下游页面会按透传的 plan_role 重新取数,可能在旧版本上误标 adopted。

**处置建议**:fallback 路径也经 `resolve_plan_view` 求证,或明示 fallback 链接不带未验证的 plan_role。属半截收口,中优先。

**复核结论**:✅ 证据仍准。

### 13.N6 【P5 · low】parse_report_nonnegative_int 手搓正则绕过 strict_parse 收口点(刚收口就开后门)

**位置**:`git show b08162cd:core/services/report/report_number_parsing.py:9,54-70,73-90`

**引用链**:`report_engine._export_nonnegative_int`(:71)→ `parse_report_nonnegative_int` → `_parse_plain_report_int`(自带 `_INT_TEXT_PATTERN=re.compile(r"^[+-]?\d+$")`,自行判 bool/int/str);web `reports_export_support.py:45` 也用它。**对照同文件 3 个兄弟函数**:`parse_report_int`(:48 委派 `parse_required_int`)、`parse_report_float`/`parse_optional_report_float`(委派 `parse_required_float`)——**唯独它例外**。

**为何算债**:已知收口点是 `parse_finite_int`/`parse_required_int`(`core/shared/strict_parse.py:46,81`)。`_parse_plain_report_int` 是第二套私有整数解析,且**语义漂移**——收口点走 `float(value)` 接受 `"2000.0"` 这类浮点文本,私有版正则只认纯整数会拒掉。本可用 `parse_required_int(value, min_value=0)` 表达"非负"。无注释说明为何不复用,也无 parity 测试钉死差异。同文件已亲核 :25/:49 兄弟都委派,唯它手搓。

**爆炸半径**:导出行数档位决策(direct/stream/reject)与 web 导出表单整数参数;收口点语义若调整,此副本不跟随。

**处置建议**:改用 `parse_required_int(value, min_value=0)`,删除 `_INT_TEXT_PATTERN` 与 `_parse_plain_report_int`。属真债清理册第四档(语义需对齐:确认是否真要拒 `"2000.0"`)。

**复核结论**:✅ 已亲核(report_number_parsing.py:9 有 `_INT_TEXT_PATTERN`,:25/:49 兄弟委派 `parse_required_*`)。

### 13.N7 【P6 · low】plan_id 死面包屑被合同字段表正式承认却全链零消费(坐实基准 web-all P6)

**位置**:`git show b08162cd:web/viewmodels/scheduler_workbench_link_query.py:118,154`(`_append_param(query,"plan_id",...)`);注入点 `scheduler_reports_workbench.py:73`、`navigation_context.py:86`、`reports_page_support.py:98,135`;合同字段表 `scheduler_navigation_links.py:12 _REPORT_CONTEXT_FIELD_NAMES`、`reports_export_support.py:14`

**引用链**:`build_report_context(plan_id=)` → `build_workbench_plan_context(plan_id=)`(`scheduler_workbench_links.py:229 "plan_id":_text(plan_id) or None`)→ `query_for_target` → 拼进所有目标页 URL(含 execution_review,`link_query.py:154`)。**反向核查**:`git grep plan_id b08162cd -- core/ data/` 仅命中无关的 `_plan_idempotency_keys`;web 层无 `args.get("plan_id")` 作为解析键——版本身份解析全程用 version+plan_role+scenario_id(`resolve_plan_view`),plan_id 从不参与取数。

**为何算债**:收口收的是"统一参数合同",plan_id 被**正式写进合同字段表**并落进每条链接 query,但没有任何页面用它定位方案——是一个"被合同正式承认却永不消费"的承重感面包屑,读者会误以为 plan_id 是身份主键。这坐实了基准报告 web-all 的 plan_id P6,且这次收口**把它制度化了**(进了字段表)。

**爆炸半径**:所有工作台/报表链接 URL 都多挂一个无效 plan_id 参数;误导后续维护者按 plan_id 做方案解析。

**处置建议**:从 `_REPORT_CONTEXT_FIELD_NAMES` 与 link_query 移除 plan_id,或明确文档化它是"保留字段未启用"。注意:基准报告记过 `back_to`(回跳头牌参数)也 threaded 但零渲染,但 design doc:225 写明 back_to/plan_id 是"保留为返回上下文未必渲染"——**back_to 是有意延期(在途,非债),plan_id 是真死面包屑**(无任何消费者且非延期渲染目标)。

**复核结论**:✅ 证据仍准(双信源互证:本轮 + 上轮失败 workflow 的深度调查均独立得出)。

### 13.N8 【P6 · low】filter_plan_rows_for_report_context 出生即死(实际过滤在 SQL 层)

**位置**:`git show b08162cd:core/services/report/report_context_filters.py:160-187`(含 helper `_plan_row_matches_batch`:160、`_plan_row_matches_resource`:164)

**引用链**:全仓 grep `filter_plan_rows_for_report_context` 仅命中定义 + `tests/regression_report_context_filters_contract.py`(:66/75/81)。孪生函数 `filter_downtime_rows_for_report_context`(:274)被 `report_engine.py:406` 真用;但计划行的 resource/batch 过滤**实际由 repo SQL 完成**(`schedule_resource_sql_filters.append_detail_filters` → `report_engine._list_plan_rows_between` 传 resource_type/resource_id/batch_id 下钻),Python 侧这套行匹配无人调用。

**为何算债**:新文件里一段 40 行完整实现 + helper,只有合同测试供养(给"存活"假信号),无任何生产路径触达。维护者会误以为报表计划行在此处 Python 过滤,实际走 SQL,误导理解。

**爆炸半径**:运行期为零(死);维护成本 + 测试覆盖率虚高 + 对"过滤发生在哪层"的误导。

**处置建议**:删除该函数 + helper + 退对应合同测试断言。属真债清理册第二档。

**复核结论**:✅ 证据仍准。

### 13.N9 【P3 · low】execution_review 三档标签(display/identity/export)被压扁成同值,旧键+模板分支+导出回退沦为死分支未清

**位置**:`git show b08162cd:core/services/report/execution_review.py:337-348`(`_resource_pair_payload` 现 `return {"display_label": display, "identity_label": display, "export_label": display}` 三键恒等)、:287-292、:304-305、:311-312

**引用链**:模板 `templates/reports/execution_review.html:131,132,135,136` 的 `{% if ..._identity_label and ..._identity_label != ..._label %}` 守卫现恒为 False → `text-meta` 副行永不渲染;导出 `exporters/xlsx.py:410-415` 的 `row.get("..._export_label") or row.get("..._label")` 中 `or` 永不回退,且 `_export_label` 名实不符。

**为何算债**:半截简化——三档身份系统被掏空成单值,但键名、模板 `!=` 分支、导出 `or` 回退三处消费方全部留存为 no-op,API 仍对外宣称有 identity/export 变体却零信息差。后续若要恢复真实身份渲染,无法区分这是有意压扁还是 bug。

**爆炸半径**:模板一段死分支 + 导出一段死回退 + 每资源 3 个重复键;阅读/演进误导,低运行期风险。

**处置建议**:若确定不再需要三档,删除 identity/export 键 + 模板 `!=` 分支 + 导出 `or` 回退,只留单 `_label`;若要保留三档能力,恢复真实拼装。属真债清理册第二档。

**复核结论**:✅ 证据仍准。

### 13.N10 【P5 · medium】_normalize_critical_chain_result 被逐字复制成第二份(support vs provider)

**位置**:`git show b08162cd:core/services/scheduler/gantt_service_support.py:32-50` vs `gantt_critical_chain_provider.py:104-128`(基准即存在,UNCHANGED)

**引用链**:`gantt_service.py:21` import `critical_chain_for_plan_detail_filter` → :375 有 detail_filters 时走 support 路径 → `gantt_service_support.py:54-58` → :32 `_normalize_critical_chain_result`;另一份在 provider 走无 filter 路径(`gantt_service.py:377`)。两路汇入同一 `build_gantt_contract` → `gantt_contract.py:19 _public_critical_chain` 白名单复核。两文件都已 `from .gantt_critical_chain import ...`,存在天然公共落点。

**为何算债**:b08162cd 抽 support 模块时,本可 import provider 已有的同名 staticmethod 或抽公共 helper,却又写了一份逐字段语义相同的副本(provider 版与 support 版 diff 后无差异)。**这正是基准报告 §91 第三档记过的 `_normalize_critical_chain_result` 重复(当时标 git status `A` 未提交、需问在途作者)——现在 b08162cd 把它提交了,坐实为 P5**。归一调用本身承重(raw `compute_critical_chain_from_rows` 缺 available/edge_type_stats 默认),但第二份物理副本不提供额外保证。

**爆炸半径**:任何人给关键链 reason_code/edge_type_stats schema 加键,只改一处 → filtered(support)与 unfiltered(provider)两路 payload 字段不一致,且需第三处 `gantt_contract.py:19` 白名单同步。

**处置建议**:抽公共 helper 或让 support 复用 provider 的 staticmethod(两文件都已 import gantt_critical_chain)。属真债清理册第三档。

**复核结论**:✅ 证据仍准(与基准 §91 第三档闭环:那条"未提交待问作者"的债已落地为已提交 P5)。

### 13.N11–N14 死代码/半截残渣(简列)

| 编号 | 病理 | 位置(git show b08162cd:) | 一句话 |
|---|---|---|---|
| **N11** | P6/low | `web/viewmodels/scheduler_navigation_links.py:66` | `_has_navigation_date_range` 新建即死,全仓零引用 |
| **N12** | P6/low | `web/viewmodels/scheduler_navigation_links.py:74-78,160` | `_target_url` 死分支:9 条 spec 第 3 字段全非空字面量,`plain_url or _target_url(...)` 中 plain_url 恒真 |
| **N13** | P6/low | `web/viewmodels/scheduler_reports_workbench.py:141-154` | `_context_summary` 死函数(私有副本,真实现在 `scheduler_workbench_links.py:254`) |
| **N14** | P3/low | `web/request_resource_context.py:20-28` + `reports_request_support.py:53-61` + `reports_export_support.py:13-29` | 资源 6 参数名清单三处各抄一遍(收口点没绕,维护性半截) |

> N11–N13 属真债清理册第一/二档(grep 实证零引用,可直删);N14 属第三档(把 6 别名清单收口到单一常量供三处 import)。

---

## 第三部分 · 承重护栏新状态(更新 §90)

### 13.G1 execution_review「只复盘正式采用方案」纵深三层 —— 保留,四文件零注释

交叉核验官对 4 个承载文件逐一 grep `#` 注释 + `故意/刻意/不对称/不收/forbidden`——**四处全部零解释性注释**(命中的全是 UI 文案、错误消息、变量名 `_EXECUTION_REVIEW_FORBIDDEN_EXTRA_PARAMS`)。当前硬钉 ROLE_ADOPTED 行(execution_review 服务层):`:112,123`(取数分支)、`:153`(`_resolve_plan`)、`:166-167`(返回 dict);签名 `execution_review(version, *, date_from, date_to, batch_id, resource_type, resource_id)` 结构性无 plan_role/scenario_id 形参。落点另两层:路由 `reports_page_support.py:367,388`、导航 `navigation_context.py:80-82`。

→ **这是基准 §90 LB-A 族的现状确认 + 扩展**:基准记了 web 路由/service 签名/写侧反馈三层,现增加 **navigation_context 这第四个承载点**(b08162cd 新增,见 13.N3),且它靠路由名字面量匹配,最脆弱。§90 应补 navigation_context 这一处 + 13.N3 的注释文案。

### 13.G2 新 collar schedule_resource_filter 只支持 machine/operator,对 team/empty-id 一律 raise(loud)—— 新增无注释

**证据**:`git show b08162cd:core/models/schedule_resource_filter.py:8 SUPPORTED={machine,operator}`、:19-24 column_name 对 team 返 `''`、:54/60/66 三处 `raise ValidationError`。基准报告 §90 LB-B 同源(`column_name('team')==''` 而 `has_filter('team')==True` 的陷阱),precondition 要求"先扩 collar 再统一"。**文件零注释说明 team 排除与 empty-id 拒绝是刻意的、不可裸扩。** dispatch 的 team 双 join(`schedule_plan_query_repo.py:452-462`)在 b08162cd 中 0 改动,仍是 collar 表达不了、必须两轨并存的承重逻辑。

### 13.G3 ✅【正向】is_superseded → "历史正式方案(已被新版本替代)"标签 —— b08162cd 新增的反自欺护栏

**证据**:`git show b08162cd:core/services/scheduler/schedule_plan_identity_builder.py:76-77`(`_is_superseded_version`:version<latest)、:61-62(label 分支)、:166(`build_plan_identity` 接线);基准 65870e47 的 `_identity_user_label` 无此分支。

→ **这是本提交针对"显示层自欺"的灵魂线正向补强**:旧正式版本现在会被明确标成"历史正式方案(已被新版本替代)",而非冒充"现行正式采用方案"。**值得记一笔正面**——b08162cd 不只是减债,还主动加固了一道反自欺护栏。建议补注释说明它守的不变量(防旧正式冒充现行),让未来 LLM 知道这个标签是护栏不是装饰。

---

## §13 小结

| 维度 | 结论 |
|---|---|
| 净效果 | **减债 > 增债**:堵掉 web 私有数值解析、3 处 P4 静默兜底、硬编码 URL;代价是 2 笔承重语义债 + 一批低危残渣 |
| 最该回收 | **N1**(护栏字段散 3 抄,收口进 build_workbench_plan_context)+ **N2**(关键链子集冒充整版,补 scope 标记) |
| 最高杠杆免疫 | **N3** navigation_context 护栏补注释(13.N3 文案)+ §90 execution_review 族补注释(基准已给文案) |
| 正向亮点 | **G3** 新增 is_superseded 反自欺护栏(灵魂线正向补强) |
| 元更正 | **13.0** 原报告幻觉 P1 经版本史考古证伪,已诚实更正 |
| 未修复存量 | `gantt_critical_chain.py:84` 静默丢坏时间行(基准甘特 P4)b08162cd 未碰 |

---

## 13.5 · 工作树 in-flight 漂移说明(复核基线钉死 + 超前治理记录)

> 本节由全面核查(19 节级 subagent + 全局对账)新增,解决一个被抓出的**基线漂移**问题:报告各节"证据仍准/未改动"的复核结论,基线是提交 `b08162cd`;但当前工作树有 **staged 未提交**的 in-flight 改动,使部分被引文件已偏离 `b08162cd`。

### 复核基线声明

**本报告全部 `file:line` 与"复核为准/证据仍准"结论,基线 = 提交 `b08162cd`(当前 HEAD)。** 工作树另有 13 个生产文件处于 staged-未提交状态(见下),不属"现状提交"范畴,但其中一条改动**直接命中并超前治理了本报告记录的一笔债**,如实记录于此,避免读者拿"未改动"的复核结论去指导一个已在治理中的债。

### 工作树相对 `b08162cd` 漂移的 13 个生产文件(git diff 实证)

| 文件 | 改动量 | 性质 |
|---|---|---|
| `core/services/scheduler/schedule_plan_identity_builder.py` | +13/-20 | **治理 5.4 P4 债**(见下) |
| `core/models/schedule_plan_identity.py` | +4 | 新增 `result_summary_parse_failed/_reason` 两键(坏数据可见标记) |
| `core/models/schedule_plan_resolution.py` | +2 | 透传上述两键 |
| `web/routes/reports_plan_template_fields.py` | +2 | 消费 `result_summary_parse_failed` |
| `web/routes/dashboard.py` | +134/-35 | 独立重构(值班台取数下沉,与本报告债无直接关系) |
| `web/viewmodels/dashboard_workbench.py` | +49/-19 | guard 字段集扩展(is_scenario_preview/is_comparison/is_superseded_by_newer_version) |
| 其余 7 文件(navigation_publish/resource_dispatch/workbench_links/dashboard_workbench_cards 等) | 各 +2~8 | guard 字段投影/透传微调 |

### ⚠️ 超前治理:5.4 / LB-B4 的 P4 静默兜底债,工作树中**已被治理**

- **基准 `b08162cd` 状态(本报告 5.4 与 §90 LB-B4 记录的)**:`schedule_plan_identity_builder.py:24-29` 的 `_bool_from_summary` 用 `except (TypeError, ValueError): return False` 静默吞坏 `result_summary` JSON。
- **工作树现状(git diff 实证)**:`_bool_from_summary` 已删,替换为 `_parsed_summary_flag_is_true(parsed, key, *, fail_closed=False)`(基于 `parse_result_summary_payload`),在 `:141` 以 `fail_closed=True` 调用(坏 JSON 在 is_simulation 闸上 fail-closed = 判为模拟 = 安全方向);并在 `to_dict` 新增 `result_summary_parse_failed/result_summary_parse_reason` 两键,把"summary 解析失败"沿 identity→resolution→template_fields 全链路**显式暴露**。
- **裁定**:这**正是 5.4 处置建议"坏数据可见的非致命标记"所要求的**,方向与灵魂线"坏数据不准静默兜底、宁可暴露错误"一致。**5.4 / LB-B4 的"✅证据仍准(对 b08162cd)"成立,但读者应知该债在工作树中已进入治理(待提交后可改标 🔧)。**
- 注:5.4 的其余安全论证(`_BLOCKED_RESULT_STATUSES` Gate1 先于 summary gate、危险动作闸 can_write_feedback)在工作树中仍全部成立,不受影响。
