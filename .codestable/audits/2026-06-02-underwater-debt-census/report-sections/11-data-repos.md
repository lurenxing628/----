## 11. 分区:data-repos(数据仓储 `data/repositories/`)

**分区健康一句话**:结构干净、承重链条全对,唯一的真债是 PR7a「plan-role 查询迁移」留下的一束版本-only 死读方法(P3,被孪生 `schedule_plan_query_repo` 完整取代、仅靠类型契约测试续命),外加 6 处零引用死方法/死簇(P6)和 1 处不可达的库存静默兜底死角(P4);无 P1(执行事件常量是 schema CHECK 三重锁定的领域真值)、无 P2、无 P5(资源筛选统一走 `normalize_schedule_resource_filter`,明细 JOIN 统一走 `build_schedule_detail_sql`)。

**关于承重护栏(load_bearing)**:本分区 7 条债 **全部 `load_bearing=false`** —— 没有任何一条是「故意的护栏但缺注释」。需要特别说明的是:本分区真正承重的语义护栏(防候选/情景方案冒充 adopted 的 `source_table`+`candidate_id`+`scenario_id` 校验、`_require_candidate_id`/`_require_scenario_id`/未知 source `raise ValueError`)全部活在 **孪生 `schedule_plan_query_repo`** 里,而非活在被本次普查标记为债的那束旧方法里。换言之,F1 要删的旧方法恰恰是「更不安全、plan-role 盲」的版本,删除它不削弱任何不变量。因此本分区无需补任何「我是故意的」注释。

**复核范围**:逐条回到当前代码(多个文件处于 git modified/added 状态),用 grep 全仓(排除 `__pycache__`)+ Read 复核每个 `file:line` 与每条引用链。结论:**7 条全部 ✅ 证据仍准,0 条行号已变,0 条疑似已修复**。

---

### 11.1 【P3 · medium · load_bearing=false】schedule_repo 版本-only 查询方法群:plan-role 迁移残渣,仅类型契约测试续命

**位置**(`data/repositories/schedule_repo.py`):
- `get_version_time_span` — **:36** ✅
- `list_overlapping_with_details` — **:114** ✅
- `list_dispatch_rows_with_resource_context` — **:128**(`scope_type` 过滤体 :137-158)✅

**引用链(已逐条复核)**:

1. **迁移来源**:PR7a(commit `a8ee4934`「给候选方案补上保存位置和统一查询入口」)新建 `data/repositories/schedule_plan_query_repo.py`,其三个孪生方法仍在原位:
   - `get_plan_time_span` — **:257** ✅
   - `list_detail_rows_between` — **:311** ✅
   - `list_dispatch_rows` — **:430**(`scope_type` 过滤体 :447-463)✅
   孪生带 `source_table`+`candidate_id`+`scenario_id` 的 plan-role 感知;`schedule_plan_query_repo.py:447-463` 的 operator/machine/team `scope_type` 分支与 `schedule_repo.py:137-158` **逐行相同**(已对照确认,仅 where_clauses 初值因孪生多了 source 维度而不同)。

2. **生产链全部走孪生,不碰旧方法**:
   - `core/services/scheduler/schedule_plan_query_service.py:399` → `self.repo.list_dispatch_rows(...)`(孪生);其对外方法 `list_plan_dispatch_rows_for_resolution`(:387)被三个活消费者调用:`resource_dispatch_service.py:424`、`resource_dispatch_execution_service.py:95` 与 `:142`(最新提交 `65870e47` 正在扩建此 dispatch lane)。✅
   - `core/services/scheduler/gantt_critical_chain.py:68` → `schedule_repo.list_by_version_with_details(...)`(**另一个活方法**,不是被标记的 `list_overlapping_with_details`)。✅
   - 时间跨度查询活路径走 `gantt_plan_query`→孪生 `get_plan_time_span`,不碰 `schedule_repo.get_version_time_span`。✅

3. **三个旧方法的全仓引用 = 零生产 + 仅测试/契约续命**(grep 实证):
   - `list_overlapping_with_details`:仅 `tests/test_schedule_repository_detail_queries.py:168` + `tests/regression_schedule_service_facade_delegation.py:36`(类型断言) + `tests/regression_gantt_critical_chain_unavailable.py:59`(monkeypatch 桩)。**生产零调用**。
   - `list_dispatch_rows_with_resource_context`:仅 `tests/test_schedule_repository_detail_queries.py:198/218/225/240/247/254/268/274/288` + `tests/regression_schedule_service_facade_delegation.py:39`(类型断言)。**生产零调用**。
   - `get_version_time_span`(裸名,排除 `_dates`):仅 `tests/benchmark_fjsp.py:503` + `tests/regression_schedule_service_facade_delegation.py:31`(类型断言)。**生产零调用**。

4. **「续命」机制本体已复核**:`tests/regression_schedule_service_facade_delegation.py:30-41` 是一个 `get_type_hints(...)["return"] == ...` 的**纯返回类型契约**测试,从不执行 SQL/行为。它在同一个 assert 块里同时覆盖 **2 个仍活的方法**:`:33` `list_version_rows_by_op_ids_start_range`(→ `freeze_window` 活路径)、`:37` `list_by_version_with_details`(→ `gantt_critical_chain.py:68` 活路径)。这证明该测试是「dict 行命名返回类型」契约,**不是**「保留这 3 个 API」的设计意图。

5. **无效脚手架反证**:`tests/regression_gantt_critical_chain_unavailable.py:59` 把 `list_overlapping_with_details` monkeypatch 成 `[]`,但 **:60** 才是把生产真正调用的 `list_by_version_with_details` 设为 `_repo_raise`(:56-57 定义 `raise RuntimeError("repo boom")`)。:59 桩的方法生产根本不调,是无效残留脚手架。✅

**为何算债**:同一职责存在两套实现 —— plan-role 感知版(活)与版本-only 版(死)。迁移把生产切到孪生后,旧三方法没删,仅靠一个断言返回类型的契约测试制造「还在用」假象。roadmap(`aps-frontend-workbench` / `aps-three-gap` / `gantt-result`)均无重新接线计划;`.codestable/checkup/latest/codemap/dynamic_refs.json` 三名皆无;`core/web/data` 无按字符串 `getattr/setattr` 动态派发。属典型 P3 半截迁移残渣。

**爆炸半径**:删除三个旧方法需同步改动 4 处(对抗验证已确权的删除前置条件):
1. `tests/regression_schedule_service_facade_delegation.py` 删 **:31 / :36 / :38-41** 三条类型断言,**保留 :33 / :37**(两个仍活方法的断言)。
2. `tests/test_schedule_repository_detail_queries.py` 删 `list_overlapping_with_details`(~:168)与 `list_dispatch_rows_with_resource_context`(:198-288)用例,**保留 `list_by_version_with_details`(~:188)**。
3. `tests/regression_gantt_critical_chain_unavailable.py:59` 删那行无效 monkeypatch,**保留 :60**(生产真实路径)。
4. `tests/benchmark_fjsp.py:503` 改调孪生 `SchedulePlanQueryService.get_plan_time_span_for_resolution(version, ROLE_ADOPTED)`(benchmark 为非生产 harness,低风险但须改以免基准脚本报错)。
> 误判风险已对抗排除:契约测试**暗示**可能存在「保留非 plan-role 通用读 API」的隐性意图,但因其同时覆盖 2 个真活方法,证明它是返回类型契约而非保留意图;且安全方向相反(删旧方法是去掉更不安全的 plan-role 盲路径)。对抗结论:`real_debt`,可删。

**处置建议 + 收口点**:删除 `schedule_repo.py` 的 `get_version_time_span`(:36)/`list_overlapping_with_details`(:114)/`list_dispatch_rows_with_resource_context`(:128)三方法,按上述 4 步同步测试与 benchmark。**统一收口点 = `schedule_plan_query_repo`(孪生)+ `SchedulePlanQueryService`**(已是生产唯一入口)。注意 `list_by_version`(:29)/`list_version_rows_by_op_ids_start_range`(:71)/`list_by_version_with_details`(:160)是同文件仍被生产调用的活方法,**不在删除范围**。

**复核结论**:✅ 证据仍准。三个 `def` 行号(36/114/128)与孪生行号(257/311/430)、契约测试行号(31/33/36/37/38-41)、monkeypatch 行号(59 vs 60)、生产消费者(399 / 424 / 95 / 142 / 68)全部与 JSON 逐字吻合,无漂移。

---

### 11.2 【P6 · low · load_bearing=false】schedule_repo.list_between 纯死方法:全仓零引用(含测试)

**位置**:`data/repositories/schedule_repo.py:61` ✅

**引用链(已复核)**:grep `list_between` 全仓 `.py`(排除 `__pycache__`)= **仅 :61 的 `def` 一行**,无任何调用,连测试都没有。与 11.1 的 P3 群不同,它甚至不是被孪生取代 —— 是个从未被任何上层接线过的通用区间查询(`SELECT ... FROM Schedule WHERE start_time >= ? AND end_time <= ?`,可选 version)。

**为何算债**:定义后零消费的死代码,占 `schedule_repo` 一个公开方法位。

**爆炸半径**:零。无任何引用点需同步。

**处置建议 + 收口点**:可直接删除 `schedule_repo.py:61-69` 整个方法。无收口对象(若将来真需要区间查询,应走孪生 `list_detail_rows_between`,带 plan-role 维度)。

**复核结论**:✅ 证据仍准,行号 :61 不变。

---

### 11.3 【P6 · low · load_bearing=false】batch_operation_repo 两个死查询方法:get_by_op_code + list_by_status

**位置**(`data/repositories/batch_operation_repo.py`):
- `get_by_op_code` — **:25** ✅
- `list_by_status` — **:50** ✅

**引用链(已复核)**:`BatchOperationRepository` 经 `repository_bundle.op_repo` / `batch_service.batch_op_repo` / `resource_dispatch_actual_record_service.batch_operation_repo` 实例化。grep `get_by_op_code` 与 `list_by_status` 全仓 `.py` = **各自仅 :25 / :50 的 `def` 一行**,0 调用(含测试、模板、动态 getattr)。同文件实际被调的活方法是 `get`(:13)/`list_by_batch`(:37)/`create`(:63)/`update`(:92)/`delete`(:148)/`delete_by_batch`(:151)。

**为何算债**:两个定义后零消费的死方法。`op_code` 在 schema 里是 UNIQUE 业务键,曾打算按 `op_code` 取行但从未接线;`list_by_status` 同理无人按状态批量取批次工序。

**爆炸半径**:零。

**处置建议 + 收口点**:可直接删除 `batch_operation_repo.py:25-35`(get_by_op_code)与 `:50-61`(list_by_status)。无收口对象。

**复核结论**:✅ 证据仍准,行号 :25 / :50 不变。

---

### 11.4 【P6 · low · load_bearing=false】operator_machine_repo.list_links_with_machine_names 死方法:连 facade 都没暴露它

**位置**:`data/repositories/operator_machine_repo.py:82` ✅

**引用链(已复核)**:该 repo 的查询 facade `core/services/personnel/operator_machine_query_service.py` 逐一代理了 `list_simple_rows`/`list_with_names_by_machine`/`list_with_names_by_operator`/`list_links_with_operator_info`/`list_simple_rows_for_machine_operator_sets` —— **唯独漏了 `list_links_with_machine_names`**。grep 全仓 = **仅 :82 的 `def` 一行**,0 调用。
> 对照其活的近亲 `list_links_with_operator_info`(`operator_machine_repo.py:92`):该方法活路径完整 —— facade `operator_machine_query_service.py:105` 代理它,生产 `web/routes/equipment_pages.py:142` 调用,测试 `tests/test_query_services.py:194/222` 覆盖。命名对称(`machine_names` vs `operator_info`)正是 `list_links_with_machine_names` 最易被误认为「在用」的原因,故特别标注。

**为何算债**:一个被 facade 兄弟方法淹没、看似在用实则零消费的死查询。

**爆炸半径**:零。

**处置建议 + 收口点**:可直接删除 `operator_machine_repo.py:82-90`。无收口对象(若将来需要带 machine 名的关联,应在 facade `operator_machine_query_service` 增代理后再启用)。

**复核结论**:✅ 证据仍准,行号 :82 不变;近亲活方法 `list_links_with_operator_info` 的活路径(facade :105 / equipment_pages :142)也已确认。

---

### 11.5 【P6 · low · load_bearing=false】list_as_dicts 三连复制死簇(op_type / operator / part)

**位置**:
- `data/repositories/op_type_repo.py:73` ✅
- `data/repositories/operator_repo.py:85` ✅
- `data/repositories/part_repo.py:71` ✅

**引用链(已复核)**:codemap `dup_bodies` 簇 `0bd22fccb1ac5d3b` 标记三处同体。grep `list_as_dicts` 全仓 `.py`(含 templates/web 字符串引用)= **仅这三条 `def` 行**,0 调用。三个都是 `self.fetchall(...)` 一行的轻量字典列表查询(各取本表少量列),疑似早期给某页面/算法联动用,后被 `list() -> model` 路径取代。

**为何算债**:复制三份的死方法,`dup_bodies` 已识别为同体簇,且全簇零消费。

**爆炸半径**:零。三处可一并删。

**处置建议 + 收口点**:一并删除 `op_type_repo.py:73-74`、`operator_repo.py:85-86`、`part_repo.py:71-72`。无收口对象(各表已有返回 model 的 `list()` 活方法作为唯一查询路径)。

**复核结论**:✅ 证据仍准,三处行号 73 / 85 / 71 均不变。

---

### 11.6 【P6 · low · load_bearing=false】part_repo.list_unparsed 死方法

**位置**:`data/repositories/part_repo.py:32` ✅

**引用链(已复核)**:grep `list_unparsed` 全仓 `.py` = **仅 :32 的 `def` 一行**,0 调用(含测试)。内部转调 `self.list(route_parsed='no')`(:33),曾用于「未解析工艺路线」筛选,现无人调。

**为何算债**:定义后零消费的死方法。

**爆炸半径**:零。

**处置建议 + 收口点**:可直接删除 `part_repo.py:32-33`。无收口对象(其底座 `list(route_parsed=...)` 是活方法,任何调用方可直接传参)。

**复核结论**:✅ 证据仍准,行号 :32 不变。

---

### 11.7 【P4 · low · load_bearing=false】material_repo.update 库存数量 except 静默保留原值(不可达防御死角)

**位置**:`data/repositories/material_repo.py:68-72` ✅(`try` :68 → `float(val)` :69 → `except Exception:` :70 → 注释「留给服务层校验;这里保持原值」:71 → `val = updates.get("stock_qty")` :72)

**引用链(已复核)**:`stock_qty` 不可转 `float` 时,except 捕获后把**原始坏值**重新赋回 `val` 继续 `set_parts.append`/写库(:74-75)。唯一生产调用方 `core/services/material/material_service.py` 的 `update`(:85)在传入前已于 **:100** `updates["stock_qty"] = self._norm_float(stock_qty, field="库存数量", min_v=0.0)` 强校验(`_norm_float` 定义于同文件 :32);`create` 路径同样在 :65 经 `_norm_float` 校验。坏 `stock_qty` 在 service 层就被 `ValidationError` 拦下,**repo 的 except 分支在当前生产路径不可达**。

**为何算债**:形式上违反灵魂暗线「坏数据不静默兜底」—— 若有旁路绕过 service 直调 repo,坏 `stock_qty` 会被悄悄写进 `Materials.stock_qty`(REAL 列)而非报错。但当前唯一生产入口已上游校验,属**不可达防御死角**,危害极低(当前无任何实际错误被吞)。

**爆炸半径**:极小。改成抛错风险极小(service 已挡上游);保留则是无害死代码。

**处置建议 + 收口点**:两个方向皆可,**推荐方向一**以贴合灵魂暗线 ——
- **方向一(贴合灵魂)**:把 :70-72 的 `except` 改为不吞坏值、直接 `raise`(例如 `raise ValueError(f"库存数量无法解析为数值: {val!r}")`),让 repo 层与 service 层共同守「坏数据不静默」。收口到现有错误语义:与 `material_service._norm_float` 抛 `ValidationError` 的上游护栏对齐,形成「双保险」而非「下游兜底」。
- **方向二(若坚持单点校验)**:删除 :64-72 的整段 `stock_qty` 转换 try/except,在注释里写明「`stock_qty` 数值化是 service 层 `_norm_float` 单一职责,repo 只接收已净化值」,把校验收口点明确钉在 `material_service.py:100`。
> 注意:无论哪个方向,**不要保留现状的「except 后塞回原始坏值」**,这是唯一与灵魂暗线相悖的形态。

**复核结论**:✅ 证据仍准。`material_repo.py:68-72` 的 except-保留原值结构不变;上游护栏 `material_service.py:100`(`_norm_float`, `field="库存数量"`)与 JSON 描述逐字吻合(JSON 原写 `material_service.update:100`,当前文件路径为 `core/services/material/material_service.py`,行号 :100 精确命中)。

---

### 本分区复核汇总

| 编号 | 病理 | 严重度 | load_bearing | 位置 | 复核 |
|---|---|---|---|---|---|
| 11.1 | P3 | medium | false | schedule_repo.py:36/114/128 | ✅ 证据仍准 |
| 11.2 | P6 | low | false | schedule_repo.py:61 | ✅ 证据仍准 |
| 11.3 | P6 | low | false | batch_operation_repo.py:25/50 | ✅ 证据仍准 |
| 11.4 | P6 | low | false | operator_machine_repo.py:82 | ✅ 证据仍准 |
| 11.5 | P6 | low | false | op_type_repo.py:73 / operator_repo.py:85 / part_repo.py:71 | ✅ 证据仍准 |
| 11.6 | P6 | low | false | part_repo.py:32 | ✅ 证据仍准 |
| 11.7 | P4 | low | false | material_repo.py:68-72 | ✅ 证据仍准 |

**7 条全部 ✅ 证据仍准 / 0 条行号已变 / 0 条疑似已修复。** 本分区无 `load_bearing=true` 条目,无需补「我是故意的」注释;真正承重的 plan-role 护栏全在活孪生 `schedule_plan_query_repo` 里,F1 删的是更不安全的旧路径。建议优先收口 11.1(P3 残渣,medium),其余 6 条均为可直接删/低风险定点修(P6 死代码 + P4 不可达死角)。
