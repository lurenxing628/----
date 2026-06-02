## 03 分区:scheduler-gantt(甘特调整闭环 `gantt_*`)

**分区健康一句话:** 有残渣但整体偏干净——调整闭环(publish/draft/scenario/validation/projection)是全分区最成熟的一块(严格 `strict_parse`、`ValidationError` 主动暴露、快照 revision/异常工序多重承重护栏、`DegradationCollector` 统一透出降级,完全贴合"坏数据不准静默兜底"的灵魂暗线);水下残渣仅三处且均**非承重**(`load_bearing=false`):1 个已提交的零消费死方法(名字还撒谎)、1 个被复制成第二份的私有归一函数、1 个只读关键链覆盖层的轻度静默丢行盲点。无 P1/P2/P3。

> 复核口径:本次普查所有 file:line 已回到【当前】分支 `codex/aps-three-gap-directions` 代码逐条 grep/Read 复核。三条债的**主证据位置全部仍精确**;两处**非位置性的状态变化**已在对应条目的"复核结论"中如实标注(债 2 的文件已从未提交转为已提交;债 3 的一处兄弟范式交叉引用行号 +4)。

---

### 债 1 ── `get_latest_version_or_1` 零生产消费的死方法,且名字与实现自相矛盾

- **病理标签:** `P6`(死代码/死面包屑) · **严重度:** low · **load_bearing:** false
- **位置:** `core/services/scheduler/gantt_service.py:60-62`

```
60	    def get_latest_version_or_1(self) -> int:
61	        v = int(self.history_repo.get_latest_version() or 0)
62	        return v if v > 0 else 0
```

- **引用链:**
  - 定义点 `gantt_service.py:60` `def get_latest_version_or_1`。
  - 全仓 `grep 'get_latest_version_or_1('` 仅两处命中:① 定义点本身 `gantt_service.py:60`;② `tests/regression_scheduler_week_plan_summary_observability.py:59` 的 `_GanttServiceStub.get_latest_version_or_1`——那是 stub **定义**(当前实现 `return 3`,见该文件 :55-60)而非对真实方法的调用,通读该测试该 stub 方法从不被 invoke。
  - 真实周计划路由 `web/routes/domains/scheduler/scheduler_week_plan.py:278/284/377` 只调用 `svc.resolve_week_range`(:278)与 `svc.get_week_plan_rows`(:284、:377),从不碰此方法(已 grep 确认该路由文件内无 `get_latest_version_or_1` 命中)。
  - 函数体语义:`v = int(history_repo.get_latest_version() or 0); return v if v > 0 else 0`——名字承诺 `or_1`,实际无历史时返回 **0**,而非 1。

- **为何算债:** 定义后零真实 caller(Flask 路由/registry 已逐一排除,确为静态非盲区),纯死代码。更坏的是测试 stub 镜像了它,制造出"`GanttService` 对外 API 仍在用此方法"的假象(P6 典型的"散布多处造成看起来在用")。名字 `or_1` 与返回 `0` 的矛盾会误导未来读者,以为空态有 `version=1` 的兜底。注意同类正确实现就在隔壁 `resolve_version`(:64-70)——它走 `resolve_version_or_latest` 统一解析,根本不需要这个裸方法。

- **爆炸半径:** 删方法(`gantt_service.py:60-62`)+ 删测试 stub 的该方法(`regression_scheduler_week_plan_summary_observability.py:59-60`),**无生产影响(零 caller)**。唯一风险是若未来有人凭名字以为它返回 1 来写新代码——删掉反而消除误导。

- **处置建议 + 收口点:** 直接删除死方法及其测试 stub 镜像。版本解析的**统一收口点已存在**——`gantt_service.py:64 resolve_version` → `core/services/scheduler/version_resolution.py` 的 `resolve_version_or_latest` / `require_selected_version`。任何"取最新版本"的需求都应走这条已成熟的解析链,不再保留这个名实不符的裸 getter。

- **复核结论:** ✅ 证据仍准。`gantt_service.py:60-62` 行号与函数体逐字一致;测试 stub 仍在 `:59`(stub body 现为 `return 3`,不影响"从不被调用"的结论)。周计划路由仍只调用 `resolve_week_range`/`get_week_plan_rows`,死方法定性不变。

---

### 债 2 ── 关键链结果归一函数 `_normalize_critical_chain_result` 被复制成第二份私有实现

- **病理标签:** `P5`(第 N 套私有实现) · **严重度:** low · **load_bearing:** false · **对抗验证:** `real_debt`(已被反驳/确权为真债)
- **位置:** `core/services/scheduler/gantt_service_support.py:32-51`(第二份);对照原版 `core/services/scheduler/gantt_critical_chain_provider.py:104-128`

```
# support 版 gantt_service_support.py:32-51
32	def _normalize_critical_chain_result(raw: Any) -> Dict[str, Any]:
...
48	        "available": bool(is_available),
50	        "reason_code": reason_code or ("unknown" if not is_available else ""),

# provider 版 gantt_critical_chain_provider.py:104-128(@staticmethod，3be4757f/2a6534ab 期已提交)
104	    def _normalize_critical_chain_result(raw: Any) -> Dict[str, Any]:
...
125	            "available": is_available,
127	            "reason_code": reason_code or ("unknown" if not is_available else ""),
```

- **引用链:**
  - 两份同名函数经 diff 语义逐字相同:`available` 布尔判定(support `is_available = available if isinstance(available, bool) else True` / provider 等价 `if isinstance(...): is_available = available else: is_available = True`)、`available` 时清空 `reason`/`reason_code`、`edge_type_stats` 默认四键 `{"process":0,"machine":0,"operator":0,"unknown":0}`、`edge_count` 的 `int(... or 0)` 兜底、`reason_code or 'unknown'` 兜底——完全一致。support 的 `_text(x)=str(value or "").strip()`(:10-11)即 provider 内联的 `str(x or "").strip()`,无差异。唯一字面差异:support 输出 `bool(is_available)`、provider 输出裸 `is_available`——但 `is_available` 必为 bool(要么通过 `isinstance(bool)` 校验、要么硬编码 `True`),`bool()` 是 no-op,**输出无差**。
  - 两份都活,汇入同一出口:`gantt_service.py:375` `critical_chain = critical_chain_for_plan_detail_filter(rows, detail_filters)`(support 路径,有 `detail_filters` 时)→ 内部 `gantt_service_support.py:58` 调 support 版归一;`gantt_service.py:377` `self._get_critical_chain_provider().get_critical_chain(...)`(provider 路径,无 filter 时)→ 内部调 provider 版归一。二者都流入 `gantt_service.py:389` `build_gantt_contract(...)` → `gantt_contract.py:19 _public_critical_chain` 再统一按 `:16 _ALLOWED_CRITICAL_REASON_CODES` 白名单复核 `reason_code`(:33)并映射中文标签——下游对两路产物一视同仁。
  - 两文件都已 `from .gantt_critical_chain import ...`(support.py:7、provider.py:10),存在**天然的公共 helper 落点**。

- **为何算债:** 同一概念(关键链结果归一)的第 2 套私有实现,两份逐字同义但物理分离,已具备语义漂移温床:任何一处改 `reason_code` 兜底规则或新增字段,另一处不会同步,前端契约会在 filtered/unfiltered 两条路径下不一致。属 P5"绕过已有实现重写"。重复本身**不护任何不变量**——归一调用对 support 路径确实承重(裸 `compute_critical_chain_from_rows` 缺 `available`/`edge_type_stats` 默认,`collect_gantt_degradation_events` 与 `_public_critical_chain` 依赖这些键),但**一份共享实现即可满足**,第二份物理副本不提供任何额外保证。

- **爆炸半径:** 若改:把 support 路径改为复用 provider 的归一(或抽到 `gantt_critical_chain` 公共函数),让两路共用单份。风险低但需同时覆盖 filtered/unfiltered 两条路径的快照测试。

- **处置建议 + 收口点(对抗验证给出的唯一安全做法):**
  - **收口到单份共享实现:** 把 `_normalize_critical_chain_result` 抽到两文件共享的 `core/services/scheduler/gantt_critical_chain.py`(两文件均已 import 该模块,落点天然),让 support 与 provider 两路都改调它(或 support `import` provider 的版本)。**保留归一调用本身**。
  - **绝不可** 把 `critical_chain_for_plan_detail_filter`(`gantt_service_support.py:54-58`)简化为直接 `return compute_critical_chain_from_rows` 的 raw——那会丢掉 `available` 默认 / `edge_type_stats` 四键 / `reason_code` 兜底,使坏数据/空结果以缺字段形态流入 `_public_critical_chain`(违反灵魂暗线"坏数据不准静默兜底",且可能让 `collect_gantt_degradation_events`(`gantt_service_support.py:61-80`,依赖 `available is False`)漏报降级)。
  - **统一后必跑:** `tests/regression_gantt_contract_snapshot.py`、`tests/regression_gantt_critical_chain_unavailable.py`、`tests/regression_gantt_critical_chain_provider.py`,验证 filtered/unfiltered 两路契约逐字不变。

- **复核结论:** ✅ 证据位置仍精确(support `:32-51`、provider `:104-128`、call sites `gantt_service.py:375/377/389` 全部逐字一致;两份归一语义复核仍逐字段相同)。**⚠️ 一处状态变化已落实:** 普查时 `gantt_service_support.py` 为新增**未提交**(git status `A`),对抗验证曾据此保留"疑为在途中间态,落手前先与在途作者确认"的前置。当前该文件已在提交 `b08162cd 完成报表工作台回跳验收` 中**提交入库**,工作区干净。**结论:在途疑虑消除,这是已固化进提交历史的 P5 真债,可按上述收口方案推进(无需再等在途作者),反而更应尽快统一以免两份在后续 feature 中各自漂移。**

---

### 债 3 ── 关键链 `_build_nodes` 静默丢弃坏时间行却仍报 `available:True`,无 partial/缺口信号

- **病理标签:** `P4`(静默兜底死角) · **严重度:** low · **load_bearing:** false(但内含一处**事实上承重的过滤行**,见下方醒目提示) · **对抗验证:** `real_debt`(已被反驳/确权为真债)
- **位置:** `core/services/scheduler/gantt_critical_chain.py:84`

```
79	def _build_nodes(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
80	    nodes: Dict[str, Dict[str, Any]] = {}
81	    for r in rows:
82	        st = _parse_dt(r.get("start_time"))
83	        et = _parse_dt(r.get("end_time"))
84	        if not st or not et or not (st < et):
85	            continue          # ← 静默跳过坏时间行,无任何 collector/counter/flag
```

- **引用链:**
  - `_build_nodes`(`gantt_critical_chain.py:79`)对 `if not st or not et or not (st < et): continue`(:84-85)**静默**跳过坏时间行。
  - 链路:`provider.get_critical_chain` → `compute_critical_chain`(`gantt_critical_chain.py:344`)→ `_load_rows`(:67-68 `schedule_repo.list_by_version_with_details(version)`,取**全版本不按周截断**)→ `_compute_critical_chain_from_loaded_rows`(:312)→ 内部调 `_build_nodes`(:313)丢行后,在 :328-334 仍返回带 `edge_type_stats`/`edge_count` 的**正常结果**(无 partial/dropped 字段),经归一包成 `available:True`。
  - 全文件 `grep -niE 'partial|dropped|skipped|degraded'`:**零命中**——丢了多少行无任何记录。
  - **对照同分区已有的"丢行但留痕"范式:**
    - `gantt_service.py:402-404`:overdue 标记有 `overdue_markers_degraded`/`overdue_markers_partial`/`overdue_markers_message` 三个透出字段。
    - `gantt_tasks.py:195-196`:`build_tasks` 对同款坏时间行(`if not st or not et or not (st < et):`)走 `_record_bad_time_row(collector, scope="gantt.tasks", row=...)` 入 `DegradationCollector`;并在 `:355` 当 `bad_time_row_skipped > 0` 时给出 `empty_reason`。这是**已确立的"丢行 + 留痕"政策**。
    - 本模块边级 `_eligible_process_edge`(:144,raise 在 :151)/`_eligible_resource_edge`(:155,raise 在 :160)对缺时间字段直接 `raise ValueError("...时间字段缺失。")`,且回归测试 `tests/regression_gantt_critical_chain_unavailable.py:215-248`(`test_critical_chain_edge_time_errors_do_not_drop_edges_silently`)断言"关键链边时间异常不应静默当成没有前驱边"(:248)。**证明节点级 `:84` 的静默是已立政策下的缺口,而非被接受的设计。**

- **为何算债:** 项目灵魂是"坏数据不准静默兜底、宁可暴露"。关键链已有 `available:False + reason` 的异常级降级通道,却对"部分行坏时间被剔除"这种**数据缺口零信号**:用户看到一条 `available:True` 的关键链,以为它是完整的,实际真正的瓶颈工序可能因时间损坏被悄悄排除,链路结论被污染而无人知。这是吞掉了本应让用户看见的数据缺口——同分区的 overdue 标记和 tasks 构建都已经留痕,唯独关键链丢行无声。

- **爆炸半径:** 若改:`_build_nodes` 计丢弃行数,经 reason / 新增 `partial`+`dropped_count` 字段透到契约。`Schedule` 表时间由持久化层上游 `NOT NULL` 校验(见下),正常态几乎不触发,改动主要是补防御性可观测;但 candidate/scenario 明细路径数据来源更松。属只读解释性覆盖层上的轻度盲点,非高危。

- **处置建议 + 收口点(对抗验证确权:是真债,可安全收口为兄弟范式,但不是裸删):**
  1. **必须保留 `:84` 的过滤条件本身**(见下方醒目提示)。正确做法是"丢行 + 留痕":照搬 `gantt_tasks` 的 `_record_bad_time_row` / `DegradationCollector`(收口到 `core/services/common/degradation`,与 tasks/calendar 共用同一 collector 出口),并新增 `critical_chain_partial` + `dropped_count`。
  2. **任何新增信号键必须同时穿过三道 whitelist 归一化**,否则在归一层被静默剥离 =换个地方自欺:① `gantt_service_support.py:32-51 _normalize_critical_chain_result`;② `gantt_critical_chain_provider.py:104-128 _normalize_critical_chain_result`;③ `gantt_contract.py:19-40 _public_critical_chain`。(注意:这三道里前两道正是债 2 的重复体——先收口债 2 成单份,再加 partial 键,可少改一处。)
  3. **优先级评估(先堵源头再补读侧):** 采纳/候选源为引擎写入且 `NOT NULL`(`schema.sql:240-241` Schedule、`:338-339` ScheduleCandidateRows、`:538-539` ScheduleAdjustmentScenarioRow 均 `start_time/end_time DATETIME NOT NULL`),`st < et` 几乎恒成立,丢行分支接近死代码;真正能产坏时间的是**人工 scenario 调整**路径——更应在 scenario 调整的**写入校验源头**堵 `st < et`,而非只在只读关键链读侧补 partial 标志。先确认写入源头是否已校验,再决定读侧补防御的投入。

> **🔧 醒目提示——`:84` 过滤行是事实上的承重护栏,需补"我是故意的"注释:**
> 虽然本 finding 的 `load_bearing=false`(缺的是 partial 信号),但**过滤行 `:84` 本身承重、绝不可裸删**:删掉它会让 `start/end=None` 流入 `_build_process_prev` 排序(`:114 items.sort(key=lambda x: (..., x.get("start"), ...))`)与 `_sink_id` 的 `max` 比较(`:262 max(nodes.values(), key=lambda x: (x.get("end"), ...))`)→ Py3.8 下 `None` 与 `datetime` 比较抛 `TypeError` → 被 `:340`/`:358` 的 `try/except` 接住 → 整条关键链因一行坏数据降为 `available:False`(过度激进、功能回归)。这一行是"丢一行坏数据仍出有用链"的刻意韧性。建议落注释:
> ```python
> # 我是故意的(承重):此过滤刻意"丢坏时间行仍出链",不可裸删。
> # 删除会让 None 流入 :114 排序与 :262 max 比较→Py3.8 TypeError→被 :340/:358 接住→
> # 整链降为 available:False(一行坏数据毁全链,功能回归)。
> # 已知缺口:丢行未留痕,违反"坏数据不准静默兜底"——收口方向是 +DegradationCollector
> # 与 critical_chain_partial/dropped_count,而非删此行。详见普查报告 03 分区债 3。
> ```

- **复核结论:** ✅ 主证据仍精确。`gantt_critical_chain.py:84` 过滤行逐字一致;全文件仍无 `partial/dropped/skipped/degraded`;`_compute_critical_chain_from_loaded_rows`(:312-334)丢行后返回正常结果不变;承重的排序/max 点 `:114`/`:262` 逐字一致;`gantt_contract.py:19/33` 白名单复核、`gantt_service.py:402-404` overdue 兄弟范式、`schema.sql:240-241/338-339/538-539` NOT NULL、`tests/regression_gantt_critical_chain_unavailable.py:215-248` 断言全部精确命中。**⚠️ 唯一行号偏移:** 兄弟范式交叉引用的 `gantt_tasks.py` 已较普查时 +4 行——`_record_bad_time_row` 守卫由原 `:192` 移至 **`:195-196`**、`bad_time_row_skipped` 判定由原 `:351` 移至 **`:355`**(模式与定性不变,仅行号位移)。该偏移仅影响"对照范式"的指针,不影响本债主证据 `:84`,定性维持 P4 真债。
