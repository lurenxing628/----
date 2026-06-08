# 红队第2轮3号 · 复攻3 门禁可执行性核查

> 视角:每批门禁里点名的测试文件/符号是否真实存在(rg 抽查);「21 项 fitness / 语义雷达 / v18·v19 CHECK」是否每批可机器判定。只读不改。基线 HEAD c2aa7501。

## 核查结论速览(真问题优先)

经 rg 回盘抽查,**计划点名的门禁绝大多数真实可定位且数字准确**(尤其 fitness 21 项、ReadyQueueContractError=16、v19 CHECK 两列、启动探针 :349),诚实度高。但发现 **4 个门禁可执行性缺口**(2 个真硬伤 + 2 个简称/口径瑕疵),逐条如下。

---

## 问题 1(真硬伤·中)· 跨 ROOT/Batch-B/C 所有 parse-helper 删点 + 收口债

**问题**:`tests/gate_meta/test_architecture_fitness.py:229 test_no_new_local_parse_helpers` 不只查「新增」,还有第二条断言 `:254-256`:
```python
stale_entries = sorted(LOCAL_PARSE_HELPER_ALLOWLIST - found_allowlist)
assert not stale_entries, "局部解析函数白名单存在失效项..."
```
白名单实盘 3 项(`:75-79`):`_sched_utils.py:_safe_int` / `batch_service.py:_safe_float` / `system_config_service.py:_get_int`。

**为什么会炸**:计划全篇大量「删 parse helper / 收口委托到真相源」动作——R09 收编 Optional 副本、R28 收口 parse_finite_float、R49 删 parse_dispatch_rule、R11/R63 去重 _normalize、R34 纯删——只要被删/被收口的函数名命中 `LOCAL_PARSE_HELPER_NAMES`(`:63`)且在白名单里,删后该白名单项即「失效」→ `stale_entries` 非空 → **fitness 第 11 项(test_no_new_local_parse_helpers)由绿转红**,但全篇门禁只写「fitness 21 项全绿」,**零处提示删函数须同 PR 退白名单条目**。这是「合规动作误触自身门禁」缺口,机器判定时表现为莫名其妙的红。

**修正建议**:在 ROOT/Batch-A 前置安全网补一条总纲:凡删除或收编命中 `LOCAL_PARSE_HELPER_NAMES` 的函数,须同提交核对并退场 `LOCAL_PARSE_HELPER_ALLOWLIST` 对应条目(按符号 rg 该 3 项现状,确认是否落入本轮删点)。

## 问题 2(真硬伤·中)· 语义雷达门禁「无新漂移」无法机器判定红/绿

**问题**:`.codestable/semantics/run_drift_scan.py` 脚本头注释自述「**只读、不改代码、不直接 fail。drift exit code: 0/1 都属正常(1=有 findings)**」。即该脚本 exit 0 与 exit 1 都不代表门禁红;它只产 `evidence/SemanticDebt/drift/drift-baseline.{json,md}`,**需人工对比基线**才能判「有无新漂移」。

**为什么会炸**:每批门禁都写「语义雷达 `.codestable/semantics/` 无新漂移」作为 go-no-go 判据,但该判据**没有机器红/绿出口**——CI 跑 run_drift_scan 永远「绿」(exit 0/1 都正常),漏掉新漂移不会拦批。此外脚本依赖 `.venv-semantic/bin/drift`(已确认存在)+ Python 3.14,缺失则 return 2(不可判定)。`run_semantic_guards.py` 倒是真 pytest(可红),但它跑的是 3 个固定守卫(test_config_field_properties / test_plan_role_properties / test_semantic_snapshots),不等价于「无新 drift」。

**修正建议**:把「无新漂移」门禁拆成可机器判定的两半——(a)`run_semantic_guards.py` 必须 exit 0(property+snapshot,真能红);(b)drift 须显式对比 `drift-baseline.json` findings 数 vs HEAD 基线 findings 数,差值 >0 才算「新漂移」并人工裁断。否则该判据形同虚设。

## 问题 3(口径瑕疵·低)· ROOT「regression_execution_review_identity_guardrail(R56)绿」用简称且 fd 不可见

**问题**:文件**确实存在**(`tests/operation_execution/test_execution_review_identity_guard.py`,9 个 def,经注册表 `tools/test_registry_groups_scheduler.py:289` 引用),门禁可机器判定 ✓。但 `fd` 按文件名搜不到(因其为 regression_ 前缀长名,执行者若按计划裸名 `fd regression_execution_review_identity` 会误判「文件不存在」)。同类:计划写「spec_sync」简称,真实文件是 `tests/config/test_scheduler_config_spec_sync_contract.py`(注册表 :56 引用)。

**为什么会绊**:执行者抽查门禁存在性时按计划简称 rg/fd 会落空,误以为门禁缺失而绕过。非分析硬伤,是检索口径瑕疵。

**修正建议**:门禁清单统一写全路径名(regression_execution_review_identity_guardrail.py / regression_scheduler_config_spec_sync_contract.py),并标注它们经 test_registry 注册,须用 `rg <name> tools/test_registry*` 而非 `fd` 核存在。

## 问题 4(口径瑕疵·低)· 「v18/v19 DB CHECK 不破」——v18 无 CHECK,CHECK 仅在 v19

**问题**:计划每批门禁均写「v18/v19 DB CHECK 不破」。实盘 `rg CHECK core/infrastructure/migrations/v18.py` **零命中**——source_table='schedule' / effective_plan_role='adopted' 两 CHECK 全在 `v19.py:14-19`。v18 不含任何 CHECK 列。

**为什么会绊**:门禁措辞把 v18 与 CHECK 绑定,执行者验证「v18 CHECK」会查无对象;真正可机器判定的 CHECK 门禁载体是 `v19.py` + `tests/migration_db/test_migrations.py` / `tests/migration_db/test_migration_schema_contract.py`(已确认存在,可跑红)。

**修正建议**:门禁正名为「v19 DB CHECK 不破(source_table/effective_plan_role 两列),经 regression_migrations + regression_migration_schema_contract 机器验证;v18 仅作 schema 前置无 CHECK」。

---

## 已核实为真·可机器判定(无伤,备查)

- fitness **21 项**精确(`grep -c "def test_"`=21),全为 AST/正则结构断言,机器可判;含分层方向(test_routes_do_not_execute_sql_directly 等前 6 项即「分层 0 违规」载体)。
- `ReadyQueueContractError`=**16**(`tests/scheduler_graph/test_ready_queue.py`,`rg -c`=16)——计划 RT3-P03 纠正后实盘值正确,A1 子门覆盖数对得上。
- v19 CHECK 两列实证(`v19.py:14/15/18/19`),与 LB01/LB02 注释 1:1 引用前提成立。
- 启动探针 `migration_operation_execution_contract.py:349 event_time:"not-a-date"` 精确命中(爆点 #8 锚点真实)。
- `test_sgs_graph_ready.py` 当前 MISSING——但计划 G39 明写「走 A 先新建」,是诚实待建非缺口。
