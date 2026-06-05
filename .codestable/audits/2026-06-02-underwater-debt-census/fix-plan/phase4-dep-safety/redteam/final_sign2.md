# Layer4 终检签收复检2（sign2）

> 只读不改。独立重 walk 整个批次序列（ROOT→A→B→C→D），三焦点：①无新爆点引入 ②owner 闸门全部「只标不修」零终态泄漏 ③门禁每批可机器执行（测试名真实存在）。所有锚点 2026-06-05 rg 实盘回盘，路径以 _layer2_residual.md 权威表为准。

## 一、独立重 walk 批次序列（无新爆点核验）

**脊梁四步序未被任何批次违反**：承重先钉(ROOT)→guard 收口(C)→SCC 串行→facade 最晚(D)。13 H 硬边方向、ROOT 零入边 source、R26 晚于 R29/R33/R52 三桶（E07/E08/E09）均守。重 walk 每批的「前置安全网+不可碰清单+收口反例」逐条对 6 硬阻断爆点(#1/#7/#19/#20/#21/#22/#23)闭合，未发现计划引入「修法本身即炸」的新爆点——所有删改点都挂了「按符号 rg / 同原子 / 收口反例 / 活近亲 grep」四重网。

**实盘回盘验证（按符号 rg，弃裸行号）全部坐实**：
- GF1：`reject_integer_float` 全仓零命中✓；`parse_required_int` 真在 `core/shared/strict_parse.py:81`（文件 130 行无 :46）✓——「新建 kwarg 非现有参数」定性正确。
- R52：双 ready_queue.py 坐实——impl `core/algorithms/greedy/dispatch/ready_queue.py:103 get_ready_operation_ids`✓ / 垫片 `core/services/scheduler/graph/ready_queue.py`=11 行✓；`ReadyQueueContractError`=16✓（非旧值 15）。
- R42：dashboard `:92 "plan_id"` 键✓（文件 136 行，与「:191 去 dashboard 删会越界」一致）。
- R54：collar `build_workbench_plan_context` 真宿主 `web/viewmodels/scheduler_workbench_links.py:187`✓；`routes/domains/scheduler/` 下既无 workbench_links 也无 analysis_links✓（宿主订正成立）。
- R09 family：viewmodel:33/service:24/persistence:13 三份 `-> Optional[int]`✓；STRICT-4（auto_assign:114/feedback_support:161/public_errors:167）三份 `-> int`✓；scope.py 真符号 `parse_positive_execution_int:9`✓（非 `_positive_int`，与残留表口径一致）。
- R13：`_fact_from_state:40` + 实参 `latest_events.get(scope):123` + 孤儿 `_latest_events_by_scope:163`✓（退场四处同原子成立）。
- R19：`positive_op_ids:28` + `return sorted:40`✓。
- R22：`normalize_plan_role:65` def + `:74` 调用点（"绝不删"）✓，真宿主 `core/services/scheduler/schedule_result_view_context.py`。
- R64/R65：`_has_navigation_date_range:66`/`_target_url:74`/`_has_navigation_context:47`(用于:71/114/142/175)/`TARGET_PAGE_PATHS:7`(用于:177)/孤儿 import `urlencode:4`/`query_for_target:6`✓；文件 205 行✓（三批四单元串行块前提成立）。
- R67：`_REPORT_CONTEXT_FIELD_NAMES:11` + `preserved_report_context_fields:186`✓（同 nav_links 文件）。
- R14：`_resolve_strict_plan:134`（`schedule_delay_diagnosis_service.py`）✓。
- R05：`schedule_repo.py` team 双 join `((o.team_id=?) OR (m.team_id=?))` + `include_team_context=True`✓；`normalize_schedule_resource_filter` 在 `core/models/schedule_resource_filter.py`（model 层，:65-66 双 raise✓）——「model→data 禁反向 import」警告坐实。

**唯一登记备查项（非新爆点、计划已自登）**：R49 §189/§584 称 `parse_dispatch_rule` 被「greedy 多文件消费」，实盘全仓仅 `dispatch_rules.py:28`(def)+1 测试，零 greedy 消费者——但 §613 已显式登记为「幻觉消费图非硬伤，串行结论保守无害」。不构成新爆点。

## 二、owner 闸门「只标不修」零终态泄漏核验

§3 owner 表实盘 38 条（O01-O38，`rg -c "^| O[0-9]"`=38✓，与计划自检一致）。逐条审「选项/建议/归属」三列：

- **全部带「选项」列给 2-3 个候选 + 「建议」列给倾向 + 「归属单元/批」列**，无一给出 patch 级终态修法。「建议」措辞统一为「待 owner / A（理由）/ B（理由）」式倾向，未越界为「就这么改」。
- **owner_pending 单元后置 Batch-C/D，裁前不锁 patch / 不分配执行批次**：§3 表末「计数」行 + §0.1 铁律 5 + 每批 go-no-go「裁前不进批/STOP」三处冗余声明，闭环。
- **重点复核易泄漏的几条均合规**：
  - O24 R69「owner_pending=false 但只给 loud raise vs 降级方向」——给方向不给 except 域具体写法，合规（爆点 #15 的「loud 只动 except 域」是约束不是终态）。
  - O11/O12/O13 R54 collar F门-1/2/3——给「plan_resolution 入参 vs 局部源 / 同批 vs 分批 / fail-CLOSED vs fail-open」选项，建议「选项 I」仍是选项编号非现成 diff。
  - O01 R09「A 保 C 严格 / B 放宽 A/B」——纯语义取向选项。
  - O18 R67「①②必收 / ③④全收或全不收 / 第4处保现状」——是收编范围裁断不是拼接代码终态。
- **零终态泄漏确认**：未发现任何 owner_pending 债被偷偷给定最终 patch、被提前分配执行批次、或「建议」列写成可直接照抄的修改步骤。⏸ 标记与 11 标红债 owner_pending 全程保留。

## 三、门禁每批可机器执行（测试名真实存在）

§1.1 ⚠门禁可执行性总纲(1)-(4) 四条 + 各批「批后门禁」均实盘抽查：

- **6 个门禁载体测试/脚本全部 EXIST**：`tests/test_architecture_fitness.py`✓、`tests/regression_execution_review_identity_guardrail.py`✓（R56，fd 搜不到经 test_registry 注册，总纲(3) 正确）、`tests/regression_scheduler_config_spec_sync_contract.py`✓、`tests/regression_migrations.py`✓、`tests/regression_migration_schema_contract.py`✓、`tests/regression_number_utils_facade_delegates_strict_parse.py`✓（R29 真续命点）。
- **总纲(1) stale_entries 第二断言坐实**：`test_architecture_fitness.py:229 def` + `:254 stale_entries = LOCAL_PARSE_HELPER_ALLOWLIST - found_allowlist` + `:256 assert`✓；白名单 `:75` 三项。「本轮删点全不在 LOCAL_PARSE_HELPER_NAMES」属防御性总纲，可机器自检。
- **总纲(2) 语义雷达拆两半正确**：`run_drift_scan.py:2-4` 头注释逐字坐实「只读、不直接 fail、exit 0/1 都正常」✓——CI 跑它永远绿，正名为(a)`run_semantic_guards.py` exit 0 机器门 +(b) drift findings 对比 baseline 人工裁断，两脚本均 EXIST✓。
- **总纲(4) v19 DB CHECK 正名正确**：CHECK 在 v19 非 v18，经 regression_migrations + regression_migration_schema_contract 机器验，两测试均 EXIST✓。
- **R52 合同数 16 可机器核**：`rg -c ReadyQueueContractError`=16✓，go-no-go「31 用例全量分流」有真实测试支撑。
- **G16 sp06 退场点**：`tests/regression_sp06_no_duplicate_defs.py` EXIST✓（漏退→FileNotFoundError loud）。

每批 go-no-go 判据均可落到「fitness 21 项绿 + 0 分层违规 + run_semantic_guards exit 0 + v19 CHECK 不破 + 本批专项 parity 绿」的机器可判组合，无「凭感觉」门禁。

## 四、签收结论

**PASS**。独立重 walk 五批序列无新爆点引入（脊梁四步序、13 H 边方向、6 硬阻断爆点闭合全守）；38 owner 闸门全部「只标不修」零终态泄漏；门禁每批可机器执行（6 载体测试 + 2 语义脚本 + stale_entries/drift/v19-CHECK 总纲全部实盘坐实）。所有抽查锚点按符号 rg 回盘与计划一致。唯一 R49 幻觉消费图已计划自登备查、不影响安全。
