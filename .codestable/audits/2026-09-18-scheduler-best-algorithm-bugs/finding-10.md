---
doc_type: audit-finding
audit: 2026-09-18-scheduler-best-algorithm-bugs
finding_id: quality-10
nature: quality
severity: P2
confidence: high
suggested_action: cs-decide
status: fixed
---

# Finding 10：派工规则把日历小时和工作小时混着除，跨周末错判紧急度，默认 k 下 ATC 退化成近 EDD

## 速答

`build_dispatch_key` 的 slack / time_left 是墙钟小时差，而 p / avg_p 来自 `estimate.total_hours` 与 `_average_proc_hours`，是纯工作小时；CR = 日历小时 / 工作小时，ATC 指数 = 日历 slack / (k × 工作小时 avg)。

## 关键证据

- `core/algorithm_contracts/dispatch_rules.py:143-145,158-173`；`core/algorithms/greedy/dispatch/sgs_scoring.py:274-275`；`sgs.py:169-190`。
- 实测（`/tmp/aps-audit-20260918/S5/probe_calendar_units.py`，8h 班 Mon–Fri）：A 周五 16:00 完工、交期周一（工作余量 8h，日历 80h）；B 周一 12:00 完工、交期周二（工作余量 12h，日历 36h）。slack 与 ATC 都先排 B。默认 k=2、avg=6 时交期 3 天外的指数项 exp(-72/12)=0.0025，5 天外 4.5e-5。

## 影响

所有 SGS 规则在跨休息日时系统性错判紧急度；09-14 梯子里 k=8/16 反而更好，部分是在补偿单位错配。

## 修复方向

slack / time_left 改用日历"工作小时差"（新增 `working_hours_between` 并接入解码内备忘）；连续 24h 日历下键值必须与改前完全相同以保护 SMTWT 结论；需重跑质量矩阵与端到端。裁决记入 `.codestable/compound/2026-09-18-decision-dispatch-rule-working-hour-slack-and-priority-weight.md`。

## 处理结果

2026-09-18 同日落地（分支 `fix/dispatch-semantics` 提交 `ba5f6498` 已合并进主工作区）：日历层新增带符号工作小时差 `working_hours_between`（`calendar_engine.py`，底层 `calendar_working_hours.py` 按人员/优先级类缓存前缀和，随策略缓存清空），列入原生时序方法清单并接入解码内备忘（`calendar_timing_memo.py`，键含 operator）；评分层统一折算在 `core/algorithms/greedy/dispatch/sgs_due_span.py`，内部/外协/窗口受阻三条路径都走它；`DispatchInputs` 新增工作小时口径字段，ATC 指数、CR、SLACK 改用它们。合同测试 `tests/algorithm/test_sgs_working_hour_slack_dispatch.py`、`tests/calendar_maintenance/test_calendar_working_hours_between.py`、`tests/resource_dispatch/test_dispatch_rules_working_hour_priority_contract.py`（连续日历键值与改前相同）。基准：SMTWT 逐行相同；质量矩阵 improve 结果 7 平 1 好，但 medium_shift_pool 单次贪心基线拖期 1031 → 1044（换型 25 → 23）；端到端 20 例选中 19 平 1 差（shift_pool/min_tardiness 1419.5 → 1444.5，逐项开关归因到本项的 cr 规则）。`tests/fixtures/optimizer_quality_matrix_baseline.json` 正式历史基线因此需要在干净工作区实测后重新生成。

盲审复核（同日）发现远交期问题并已修：ERP 常用的 2099-12-31 一类"无交期"哨兵会让工作小时前缀按（人员, 优先级类）逐日游走到交期（存根策略首次 0.3s、10 人 × 2 类 3.8s，真实 DB 路径每日每人一次查库），超过 36500 天的交期更会在评分热路径抛 `ValidationError` 让整次解码失败。修法：`due_span_inputs` 只在排产视野内计工作小时——视野取本次排产的排他截止时刻 `end_dt_exclusive`，没有截止日期时取预计开工后 366 天（`FAR_DUE_LOOKAHEAD`），视野之外按墙钟延续；两段之和对交期单调，slack 与 time_left 共用同一视野，视野内的交期口径不变。合同测试 `tests/algorithm/test_sgs_working_hour_slack_dispatch.py` 新增三条：远交期（含超百年）不越视野且值可手算、无截止日期只看一年、预计时刻已过视野只按墙钟。
