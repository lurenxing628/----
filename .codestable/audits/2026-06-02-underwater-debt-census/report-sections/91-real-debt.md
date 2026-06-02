## 91 · 真债清理册【按收口难度排序】

> 53 条 `load_bearing=false` 的可安全收的债,按收口难度分六档。**核心原则:收口到已存在的统一点,绝不新发明**(新发明 = 再失忆一次)。每条给 file:line + 动作 + 收口目标。
>
> ⚠️ 时间基准:位置取自普查 HEAD `65870e47`。`b08162cd` 工作台收口主要动了 report/gantt 相关文件,本清单多数条目(data-repos / core-algorithms / core-models / infra-shared)未受影响,行号仍准;涉及 report/gantt/web 的条目动手前请重新 grep 定位。

---

### 第一档 · grep 实证零引用,可直删(零爆炸半径)

> 这些是纯死代码,全仓(含测试)零引用。删除无生产路径受影响。

| # | 位置 | 动作 |
|---|---|---|
| 1 | `data/repositories/schedule_repo.py:61` `list_between` | 直接删,零同步 |
| 2 | `data/repositories/batch_operation_repo.py:25,50` `get_by_op_code`+`list_by_status` | 直接删两个方法 |
| 3 | `data/repositories/operator_machine_repo.py:82` `list_links_with_machine_names` | 直接删(连 facade 都没暴露) |
| 4 | `data/repositories/op_type_repo.py:73` + `operator_repo.py:85` + `part_repo.py:71` `list_as_dicts` 三连复制 | 三处一并删 |
| 5 | `data/repositories/part_repo.py:32` `list_unparsed` | 直接删 |
| 6 | `core/shared/value_policies.py:9` `WRITE_INTERNAL_ONLY`(+common:11,29 re-export+__all__) | 删 3 处(定义+re-export+白名单) |
| 7 | `core/models/scheduler_public_errors.py:163-164` `_safe_identifier` 死别名 | 删函数+删误导性注释 |
| 8 | `core/models/schedule_config_runtime_coercion.py:83-98` `_record_blank_choice_degradation` 死参数 `raw_value` | 删形参+改两调用点(:155,:210) |
| 9 | `core/algorithms/dispatch_rules.py:25` + `evaluation.py:40-41` + `ortools_bottleneck.py:24-25` 5 处死模块别名 | 删 5 处别名 |
| 10 | `core/algorithms/dispatch_rules.py:112` `mean_positive` 死函数 | 删(生产用内联均值) |
| 11 | `core/algorithms/greedy/dispatch/batch_order.py:74` `_ = scheduled_count` 死空操作 | 删 1 行 |
| 12 | `core/services/scheduler/dispatch/__init__.py` 空包(无关提交误建) | 删目录 |

### 第二档 · 删 + 同步退 1-2 处测试/桩

> 死代码,但有测试在续命,删时需同步退测试断言。

| # | 位置 | 动作 |
|---|---|---|
| 13 | `core/services/scheduler/gantt_service.py:60-62` `get_latest_version_or_1`(死且名字撒谎) | 删方法 + 删测试 stub |
| 14 | `core/services/scheduler/execution_fact_provider.py:20-21,42-43,96` ExecutionFact 两死字段 `last_event_schedule_version/id` | 删字段 + 不再调 `list_latest_events_by_op_ids`(其本身也仅此一调用,连带死) |
| 15 | `data/repositories/operation_execution_event_repo.py:260-265` `list_latest_exception_events_by_op_ids` | 删 + 退 1 行测试断言 |
| 16 | `core/services/scheduler/run/schedule_graph_dispatch_context.py:461-475` `build_first_wave_ready_nodes` test-only 包装器 | 先把测试 import 改指真 impl(`resource_matching_context`),再删 |
| 17 | `core/shared/compat_parse.py:198` compat 整条 date 分支(`parse_compat_date`+3 日期策略+`VALUE_D...`) | 删 + 退 2 处测试断言 |
| 18 | `core/services/scheduler/run/schedule_payload_contract.py:90-95` `count/has_actionable_schedule_rows`+`_iter_actionable_results` | 删函数+两处 re-export+__all__,同步删 SP05 拓扑断言 |
| 19 | `core/services/scheduler/run/schedule_candidate_runner.py:216` candidate FAILED 态下游计数/UI 脚手架 | **窄 except:216 必须留(承重)**,只收下游不可达计数+viewmodel 死分支 |
| 20 | `web/viewmodels/scheduler_resource_dispatch_execution.py:24,226-227,361-362` `feedback_write_enabled` 休眠开关 + 生产不可达"保护未开启"提示 | 删开关+死提示分支 |
| 21 | `data/repositories/operation_execution_state_builder.py:33-39,76-79` `_REPORTED_STATUS_BY_EVENT_TYPE` 兜底表(被 schema CHECK 架空) | 删表,:77 简化为直用 reported_status |
| 22 | `core/services/scheduler/operation_execution_feedback_support.py:64` + `feedback_service.py:12,455` `_REPORTED_STATUS_BY_ACTION` 的 `EXECUTION_EVENT_EXCEPTION` 死键 | 删键+删死导入 |

### 第三档 · 收口到已存在统一点(改 import/re-export,语义已实证等价)

> 这些有现成的收口点,只需把私有副本/死 shim 指过去。**不新发明。**

| # | 死/重复项 | **收口到(已存在)** | 注意 |
|---|---|---|---|
| 23 | `schedule_plan_role._normalize_role` 与 `schedule_plan_query_service:28-30` 双字节副本 | `core/models/schedule_plan_role._normalize_role` | query_service 直接 import,今日行为一致 |
| 24 | `scheduler_navigation_publish.py:28-29` `selected_plan_role` | `core/services/scheduler/schedule_result_view_context.selected_plan_role` | 照搬 `gantt_plan_query.py:46` 已有 re-export;core 版对 None 更稳 |
| 25 | `gantt_service_support.py:32-51` `_normalize_critical_chain_result` 第二份 | `gantt_critical_chain`(两文件都已 import 它) | ⚠️ git status 标 `A`(未提交),**落手前问在途作者** |
| 26 | `gantt_plan_query.py:42,46,32,59` 死兼容 shim(resolve_plan/selected_plan_role/default_plan_resolution_dict/_has_explicit_gantt_range) | `schedule_result_view_context`(已是真身) | 删 4 符号+1 测试;**文件整体不可删**(还有 4 个活的 range 辅助);删 default_plan_resolution_dict 前先迁移其遗留错误文案包装 |
| 27 | `core/services/scheduler/operation_execution_labels.py:1-36` 纯转出垫片 | `core.models.operation_execution_labels` | 重指 5 个导入方 + 清 doc-gate KEY_PYTHON_FILES |
| 28 | `core/services/common/{compat_parse,field_parse,value_policies}.py` 三个零消费 facade 残渣 | `core.shared.*` 直连 | 先把 2 个行为测试 import 改指 core.shared,再删身份断言+删文件 |
| 29 | `core/services/scheduler/analysis/schedule_diagnostic_contract.py:13-79` 孪生副本 | web 侧 LIVE helper 已是活路径 | **删 core 这份(零消费),绝不能反删 web twin**;先调和 PR-9 roadmap |
| 30 | `core/services/scheduler/graph/ready_queue.py:1-12`+`get_ready_operation_ids` | `sgs_graph._prepare_graph_ready_state`(已取代) | 删测试文件+2 处枚举断言+roadmap 备忘 |
| 31 | `core/algorithms/greedy/config_adapter.py`(整模块 28 行) | 本分区收口点 `ensure_schedule_config_snapshot`(已内联取代) | 整模块删(仅查重测试列了路径) |
| 32 | `data/repositories/schedule_repo.py:114,128,36` 版本-only 查询方法群 | `schedule_plan_query_repo` 的 plan-role 感知孪生方法 | plan-role 迁移残渣,仅测试/类型契约续命 |

### 第四档 · 语义需逐处对齐(收口但不能裸替换)

> 有收口点,但私有副本与收口点**语义有细微差异**,替换前需逐处对齐,否则会改变行为。

| # | 死/重复项 | 收口到 | 对齐要点 |
|---|---|---|---|
| 33 | `execution_fact_provider.py:66` / `feedback_support.py:226` / `operation_execution_*` datetime 解析 3 份 | `core/shared/strict_parse.parse_required/optional_datetime` | provider/state_builder 的 None 是合法"无时间"语义,要分清 required vs optional,别把缺时间误判成错误 |
| 34 | `execution_fact_provider.py:51` / `event_repo.py:63` positive-op-id 过滤 | `execution_snapshot.positive_op_ids`(public 已排序) | 指纹依赖排序版;换前确认无下游依赖原入参顺序 |
| 35 | `batch_service.py:56-65` `_safe_float` 静默吞错 | `core/shared/number_utils.parse_finite_float` | 上游模型已 `parse_optional_float` 校验,替换后更合灵魂线;须同步移除 fitness allowlist 条目 |
| 36 | `enum_display.py:13-79` + `process_bp.py` 中文枚举标签第二套(**已语义漂移**) | `enum_normalizers` 收口点 | operator 停用→"停用/休假" vs "停用";ready 未知值静默贴"未齐套"——对齐前先定哪个语义对 |
| 37 | `parse_dispatch_rule`(dispatch_rules.py:28) / `parse_strategy`(sort_strategies.py:161) 宽容解析器 | 已被 `_require_choice+Enum()` 严格收口取代 | 生产零引用且语义与灵魂相悖(宽容回落 vs 严格抛错),删前确认无测试依赖宽容行为 |

### 第五档 · P4 软兜底(改 raise / 补可观测,不裸删)

> 静默兜底死角。多数不可裸删(删了会 500 谎报),正确动作是改成 loud 暴露或补降级信号。

| # | 位置 | 动作 |
|---|---|---|
| 38 | `core/infrastructure/backup.py:333` integrity_check 失败只 warning 不阻断 | **改 raise**(对齐 :340 else 分支)——真吞缺口,未校验库不该升正式备份;收尾收 `system_backup.py:107` 裸 500 |
| 39 | `core/services/scheduler/resource_dispatch_execution_service.py:131-141` schedule 缺失静默兜成"正式采用方案/可写"卡 | **改 `raise AppError(NOT_FOUND)`**;**不可裸删**(否则 142 行 AttributeError→500 谎报写失败) |
| 40 | `core/services/scheduler/gantt_critical_chain.py:84` 静默丢坏时间行仍报 available:True | 保留过滤 + **补 `dropped_count`/`partial`** 穿三道白名单(support/provider/contract);不可裸删 |
| 41 | `data/repositories/material_repo.py:68-72` `update` 库存 except 静默保留原值 | 不可达防御,当前无错被吞,低优先;补注释或改 loud |

### 第六档 · 需先协调(depends / roadmap 明示延期)

> 这些**现在不该动**——要么 owner 未裁断,要么 roadmap 明示延期,动了属抢跑。

| # | 项 | 状态 | 待办 |
|---|---|---|---|
| 42 | 5 个 config/summary shim(`config_service.py` 等) | depends | **先迁 2 个在用离线脚本**(tools/capture_networkx_phase0_baseline、audit probes)+ 53 测试到深路径 + 改 SP05,再删 |
| 43 | 空 delayed 包 `calendar/`+`batch/` | SP05 强制存在 | 删目录+改 SP05:310-315 元组(机械简单但需同提交) |
| 44 | `core/services/common/number_utils.py:23` 全量拷贝 | depends | 是有意 delegation-facade(2026-06-01 KEEP/high 裁定);薄壳化须**先重写 monkeypatch 测试**为身份断言 → 收口 `core.shared.number_utils` |
| 45 | 顶层 9 个 `scheduler_*.py` wrapper | roadmap 明示延期 | `p1-scheduler-debt-cleanup:522`"先保留避免冲击启动链"——**现在动属抢跑** |
| 46 | `_positive_int` 可空簇(`resource_dispatch_execution_service.py:23` 等 3 处逐字节复制) | ⚠️ **唯一"该收却无现成统一点"的债** | parse_finite_int 对垃圾 raise、契约不符;需**新建 canonical** `parse_optional_positive_int`(垃圾→None)——这是本报告唯一需要新增收口点的债,需 owner 裁断是否值得 |

---

### ⚠️ 唯一需要"新发明"的债(其余全部收口到已存在点)

第六档 #46 的 `_positive_int` 可空簇是个特例:它在执行车道三处逐字节复制(`resource_dispatch_execution_service.py:23` 等),逻辑是"垃圾值→None"。但已有的收口点 `parse_finite_int` 对垃圾值是 **raise**,契约不匹配——所以不能直接收口过去。

这是本次普查 53 条真债里**唯一一条"该收却无现成统一点"的债**。处置需 owner 裁断:是新建一个 canonical `parse_optional_positive_int`(垃圾→None),还是让这三处改用 `parse_finite_int` 的 raise 语义并在调用方补 try。报告不替你决定——但标出来,免得未来有人随手把它"统一"到契约不符的 `parse_finite_int` 上,把"宽容跳过"悄悄变成"抛错中断"。

### 收口难度总览

| 档 | 条数 | 性质 | 风险 |
|---|---:|---|---|
| 一档 直删 | 12 | 零引用死代码 | 零 |
| 二档 删+退测试 | 10 | 测试续命死代码 | 低 |
| 三档 收口到已存在点 | 10 | 私有副本/死 shim | 低(语义已等价) |
| 四档 语义对齐后收口 | 5 | 语义微差 | 中(需逐处对齐) |
| 五档 改 raise/补可观测 | 4 | P4 软兜底 | 中(不可裸删) |
| 六档 需先协调 | 6 | depends/延期 | 暂不动 |
| **合计** | **47** | | |

> 注:53 条真债中,6 条已并入上述"族"(如 enum 标签、datetime 三份各算多处),按可执行动作去重后约 47 个清理项。
