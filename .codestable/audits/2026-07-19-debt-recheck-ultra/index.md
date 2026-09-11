# 2026-07-19 账本外债务 UltraCode 对抗复核终稿（debt-recheck-ultra）

## 背景与方法

- 输入：2026-07-18 UltraCode 全库扫债的 28 条候选（9 条初判成立 + 19 条初判驳回），配对数据 `/tmp/debt_pairs_repaired.json`（已修复过一次 journal 完成序错配）。
- 方法：Workflow `debt-recheck-ultra`（runId `wf_3568fdcf-d41`），共两轮：
  - 第 1 轮 50 agents / 37.9 分钟（P4 补扫 sched 范围 finder 因上游 API 断流失败）；
  - 第 2 轮（续跑）60 agents / 28.2 分钟 / 0 失败，补上 sched 范围。
- 每条"成立"项走双镜头（镜头A 代码事实怀疑者 / 镜头B 设计意图与已知裁决辩护者）+ 分歧仲裁 judge；每条"驳回"项走误杀审计（KillAudit）；另做 P4 静默兜底限额补扫（3 scope，grep-first 硬预算）+ 逐候选对抗核实（GapVerify）。
- 两轮仲裁在 3 条边缘项上结论相反，终稿由主代理亲自抽查决定性证据后裁定（见"两轮冲突仲裁"节）。

## 终局结论

**账本外真债 = 10 条（0 high / 4 medium / 6 low）。scheduler 核心区（core/services/scheduler + core/algorithm_runtime + core/algorithm_contracts）P4 补扫 4 候选全数驳回，干净。**

| # | ID | 位置 | 问题 | 级别 | 处置 |
|---|----|------|------|------|------|
| 1 | U01 | core/services/scheduler/contracts/schedule_summary_types.py:19 | SummaryBuildContext 核心字段（cfg/batches/operations/results/summary/best_metrics 等）全标 Any，合同层类型合同为零。**归因修正：存量债非 A1 新造**（c2243cd0 逐字节平移），38 字段中 17 个有具体类型 | medium | 出实施计划（难项） |
| 2 | U02 | core/services/process/unit_excel/parser.py:268-282 | `_parse_route_map` 对重复工序号静默取第一个、空名段静默丢弃，零诊断。实测复现："1车2铣2磨"→"1车2铣"，磨的工时并入铣（template_builder.py:270），违反 diagnostics_visible 契约；05-21 治理只盖了 _to_float/_parse_step_seq | medium | 本轮修复 |
| 3 | U03 | core/algorithms/greedy/run_context.py:53 | schedule_internal 用 \*args/\*\*kwargs 透传并 pop strict_mode，签名失配 TypeError 被 batch_order.py:148 except Exception 吞成"单工序失败"继续跑。A3 apply-notes:97-100 已把同类"TypeError 被主循环折算"判为缺陷（DispatchContextContractError 先例），但修复只盖缺 callback，签名漂移仍被吞（误杀翻案） | medium | 出实施计划（难项） |
| 4 | U04 | core/algorithms/greedy/run_context.py:16 | 四个 callback 槽全标 Callable[..., Any] + 万能透传，调用链工具全盲：实测 symbol_locator 对 _schedule_internal / ScheduleRunContext.schedule_internal 的 confident 边均为 0；方法不进死代码基线只因 tests 直接调用兜住（误杀翻案） | medium | 出实施计划（难项，与 U03 同修） |
| 5 | U05 | core/services/report/downtime_impact.py:42-44 | 停机影响报表对空 machine_id 停机行静默 continue 不留降级痕迹，而同函数 :47-49 对坏时间行走 record_report_bad_time_row——同契约遗漏；报表停机工时少算且 report_degraded=false | low | 本轮修复 |
| 6 | U06 | core/algorithm_runtime/internal_slot.py:82 + core/algorithms/greedy/dispatch/sgs.py:171-177 | 均值预扫 _append_proc_sample 吞 ValueError 跳样本零计数零留痕；sgs.py:165-168 仅"全部样本为空"才计数兜底 1.0，部分跳样本致均值偏移时查无此事。（镜头A 修正危害面：坏 op 进评分仍会在 sgs_scoring.py:280-283 响亮崩，残留只是预扫无观测） | low | 本轮修复 |
| 7 | U07 | core/services/scheduler/summary/summary_runtime_state.py:24 | due_exclusive 第 3 份私有实现（收口点 core/algorithm_contracts/date_parsers.py:46，另一份 core/services/common/overdue_calculations.py:21）；A3 design 只限 algorithms 圈内，summary 属范围外沉默非知情保留 | low | 本轮修复 |
| 8 | U08 | core/services/scheduler/schedule_service.py:113 | fmt_dt 一字节函数 4 份逐字节相同私造（_sched_display_utils.py:28 公共落点已有 5 处调用；另 gantt_critical_chain.py:31、gantt_range.py:22） | low | 本轮修复 |
| 9 | U09 | core/services/scheduler/schedule_plan_query_service.py:7 | 死 import ValidationError（原判"3 个死 import"缩窄为 1/3：ROLE_BASELINE_BEST/ROLE_CRITICAL_BEST 是测试转口 re-export，约 15 个测试经本模块导入，删即断测） | low | 本轮修复 |
| 10 | U10 | core/algorithms/greedy/seed.py:7 | 死 import INTERNAL（5f1770d9 引入时曾真实使用，92ad5b31 删用途后变死；A3 机械搬运路径） | low | 本轮修复 |

## 原 9 条"成立"的复核结果：维持 6 / 推翻 3

维持（即上表 U01/U02 外的 U06/U07/U08/U09 + U01；U02 来自补扫）。推翻 3 条：

1. **core/services/scheduler/resource_dispatch_execution_enrichment.py:1（A1 兼容壳零调用方）**——两轮一致推翻。A1 裁决无条件保留全部旧路径（refactor-design.md:43、apply-notes.md:51、scan.md:49、checklist.yaml:54 点名此文件），零调用方即设计终态；边界测试是设计要求的锁，非"保命自引用"。
2. **core/services/scheduler/execution/execution_fact_provider.py:84（_positive_op_ids 死包装）**——第 2 轮推翻，主代理抽查证实：`debt_status_2026-07-17.json:362-365` 已把该别名记录在 R19 "positive_op_ids 三处漂移未收口"条目内（含"execution_fact_provider.py:70 _positive_op_ids 仍 :82 return out"原文），**属账本内旧债非账本外新发现**；且委托形态系 f6be38f9（R19 收口）有意裁决、配契约测试 test_operation_execution_scope_read_contract.py:301-303；"A1 新增"归因不实（c2243cd0^ 时包装已存在）。
3. **core/algorithms/greedy/run_context.py:87（ensure_run_context 零引用）**——第 2 轮推翻，主代理抽查 A3 设计原文证实："起点 7329 个 callable 通过路径映射全部有对应项，**零旧 callable 丢失**"，且明文只批准 dispatch_batch_order/sgs→ensure_run_context 两条边换为 ensure_dispatch_context——"定义留存 + 零调用"正是设计逐项枚举并验收的批准终态；双近似入口漂移另经 2026-07-13 legacy-dispatch-adapter issue 复核（方案C统一被显式否决、方案B经用户拍板）。

## 原 19 条"驳回"的误杀审计：维持 17 / 误杀 2（两轮缓存一致）

误杀翻案即 U03/U04（见上表）。维持的 17 条中值得记录的注记：

- batch_order.py:146 裸 except 的驳回维持（2026-06-24 深审 F-10 已专审此 catch-all 并登记残留"缺结构化根因"在账），但它作为**吞错通道**在 U03 的"形态B"路径中部分复活——修法在透传层加签名校验响亮失败，不动 except 本身。
- dispatch_context.py:26 log_exception、auto_assign 双签名、config 双栈系列、A2/A3 re-export 壳系列等驳回全部维持，引用逐项核实为真。

## P4 静默兜底补扫：确认 2 / 驳回 14（两轮并集）

确认：U02（第 1 轮，附实测复现）+ U05（第 2 轮）。驳回 14 条全部是"危害链断裂"或"已有裁决"——坏数据在更上游即被响亮拦住（strict_parse.parse_required_int、写入层 ValidationError、schema NOT NULL、契约测试锁定等）。值得留档的边缘注记：

- **core/algorithm_contracts/priority_constants.py:28-31**（normalize_priority 未知值兜 normal）：应用内全部写入路径 fail-loud，仅手改 sqlite/篡改备份等界外场景可触发，GapVerify 注记"属纵深防御缺口而非现实吞错，最多值得登记低优先级账本项"——本轮不立案，留此注记备查。
- scheduler 核心区 4 候选（resource_pool_builder/priority_constants/run_state/config_snapshot）全数驳回：核心排产区无新增 P4 债。

## 两轮冲突仲裁（主代理终审记录）

第 2 轮续跑未走缓存（Recheck/Judge/P4Gap/GapVerify 流水线整体重跑），3 条边缘项两轮仲裁相反：

| 项 | 轮1 | 轮2 | 终审 | 决定性证据（主代理亲查） |
|----|-----|-----|------|--------------------------|
| SummaryBuildContext (U01) | 推翻 | 成立 med | **成立 med** | 代码事实两轮无争议；"不改字段"只是 A1 move-only 执行约束，未裁决"合同层可长期零类型"；账本无此条。按存量债保守立案，归因修正 |
| _positive_op_ids | 成立 low | 推翻 | **推翻** | debt_status_2026-07-17.json:362-365 已在 R19 条目记录该别名（grep 实证） |
| ensure_run_context | 成立 low | 推翻 | **推翻** | A3 设计"零旧 callable 丢失"+ 两条边替换白名单原文（sed 实证） |

另 schedule_plan_query（U09）从"推翻"改记"成立但缩窄至 1/3"，两轮实质一致，纯记账口径挪位。

## 处置

- 本轮直接修复：U02/U05/U06/U07/U08/U09/U10（7 条，逐条配针对性测试，.venv 日常门禁全绿后在本文件补记"处置结果"）。
- 出实施计划（Plan subagent）：U01（合同层类型化）、U03+U04（透传层签名校验响亮失败 + 调用链盲区，一对同修）。
- 账本：新增 U01-U10 至 `docs/_panorama_data/debt_status_2026-07-19.json`，债务全景图/项目全景图同步重生。

## 处置结果（2026-07-19 当日）

7 条直接修复全部落地，`.venv/bin/python scripts/run_daily_quality_gate.py` 全绿（2166 并行 + 301 串行 + 5 聚焦 passed）：

| ID | 修复 | 测试 |
|----|------|------|
| U02 | `_parse_route_map` 改 finditer 全覆盖：重复工序号出 `route_duplicate_step_seq`（含 kept/dropped 名称）、前导/空名/尾部片段出 `route_segment_dropped`；`PartContext.route_diagnostics` 新字段经 `builder_diagnostics.record_route_diagnostics` 聚合进 `diagnostics.counters/samples`（转换行为不变，只加留痕） | tests/excel_data_io/test_unit_excel_route_map_degradations_visible.py（2 个，锁"1车2铣2磨"与干净路线） |
| U05 | `_index_downtime_rows` 空 machine_id 行走新 `record_report_missing_machine_row`；`missing_machine_row_skipped` 入 `STABLE_DEGRADATION_CODES`；payload 出 `report_missing_machine_skipped_count` + 可读提示；导出摘要逐项出现 | tests/calendar_maintenance/test_downtime_impact_missing_machine_degradation.py（2 个） |
| U06 | `_append_proc_sample` 增 ctx 参数，跳样本时 `increment("dispatch_key_avg_proc_hours_sample_skipped_count")` 进 fallback_counts 审计链；全空兜底计数不变 | tests/algorithm/test_sgs_proc_sample_skip_counter.py（3 个：部分跳/全跳/全好） |
| U07 | summary 私有 `due_exclusive` 删除，改 import `core.algorithm_contracts.date_parsers.due_exclusive`；注入点与再导出保持 | 既有 guard/consistency 两契约测试绿 |
| U08 | gantt_critical_chain/gantt_range 私有 `_fmt_dt` 删除改 import 公共 `fmt_dt`；`schedule_service._format_dt` 改为委托（方法保留——10+ 测试假 svc 消费的鸭子协议面，不可删） | 既有影响面测试绿 |
| U09 | 删死 import `ValidationError`；ROLE_* 转口 re-export 加"勿删"护栏注释 | 既有转口消费测试绿 |
| U10 | 删死 import `INTERNAL` | 既有测试绿 |

修复过程中门禁另抓到 3 个本轮引入的问题，均按正路修复（未绕门禁）：新降级 code 登记进稳定册（core/shared/degradation.py）；template_builder.py 504 行超限 → 按职责拆出 `builder_diagnostics.py`（430 行）；`report_degradation_summary_rows` 复杂度 17 → 拆 `_summary_count`/`_bad_time_summary_rows`。

账本终态：90 条 = 23 fixed / 3 in_progress / 63 planned / 1 n_a。

难项计划已落盘（draft，实施前需用户拍板决策点）：
- U01 → `.codestable/refactors/2026-07-19-summary-build-context-typing/plan-draft.md`（逐字段考证：19 已具体不动 / 7 可安全补类型分两批 / 13 保守；4 个决策点 D1-D4）
- U03+U04 → `.codestable/issues/2026-07-19-dispatch-callback-binding-contract/plan-draft.md`（推荐方案 B bind 校验主干 + C Protocol 配套 + A 由契约测试承接；S1-S7 分步；诚实结论：槽位 confident 边因提取器结构性行为不可恢复）

## 运行档案

- Workflow 脚本：会话目录 `workflows/scripts/debt-recheck-ultra-wf_3568fdcf-d41.js`；journal：`subagents/workflows/wf_3568fdcf-d41/journal.jsonl`。
- 用量：轮1 50 agents / 3.89M subagent tokens / 800 tool uses；轮2 60 agents / 3.07M / 703。
- 已知豁免清单（复核时内嵌）：resolve_plan fallback_to_adopted、GraphReadyV2 空交期降级、LB01-LB08/R54/R56/R58、dispatch_context.py:26 计数器（92ad5b31）、batch_order/sgs except 结构（2026-07-13 issue）、死代码基线 86 项、A1/A2/A3 兼容壳裁决。
