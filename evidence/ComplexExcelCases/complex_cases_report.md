# 复杂排产 Excel Cases 全流程验证报告

- 生成时间：2026-05-04 00:32:04
- repeat：1
- seed：1000

## Sanity 检查项（自动判定“离谱结果”）

- **Schedule 覆盖率**：`Schedule(version)` 行数必须等于所选批次 `BatchOperations` 总数（不允许漏排/少排）。
- **时间合法性**：每条任务必须满足 `start_time < end_time`，且不得早于本次 `start_dt`。
- **资源完整性**：internal 工序必须具备 `machine_id` + `operator_id`。
- **资源不重叠**：同一设备/同一人员的任务区间不得重叠（允许端点相接）。
- **停机避让**：internal 任务不得与 `MachineDowntimes(status=active)` 区间重叠。
- **外协 merged 一致性**：同一批次同一外协组（merge_mode=merged）组内工序必须共享同一 `(start,end)`。
- **跨度合理性**：若出现 `max_end > start_dt + 365d` 视为异常。
- **页面可访问性**：抽检 `/scheduler/gantt/data`、`/scheduler/week-plan/export`、`/reports/*` 返回 200。
- **留痕键名**：抽检关键 `OperationLogs` 记录的 `detail` 键名是否齐全（Excel import + 排产 schedule）。

## Case01 - 资源耦合+停机+日历约束

- 说明：高耦合人机+多段停机+日历效率/禁排，验证避让与跨日推进。

### run_01
- 临时目录：`/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps_complex_case01_1_mfhha2rk`
- DB：`/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps_complex_case01_1_mfhha2rk/aps.db`
- 输入：`/Users/lurenxing/Documents/GitHub/----/evidence/ComplexExcelCases/Case01/run_01/input`
- 输出：`/Users/lurenxing/Documents/GitHub/----/evidence/ComplexExcelCases/Case01/run_01/output`
- start_dt：`2026-05-05 08:00:00`
- 结果文件：`Case01/run_01/result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=210/210 failed=0 overdue=0 time_cost_ms=59 objective=min_overdue budget_s=5
  - best_score：[0.0, 0.0, 0.0, 0.0, 339.1010833963889, 0.0]
  - metrics：overdue_count=0 tardiness_h=0.0 makespan_h=339.1011 changeover=0 machine_util_avg=0.273927 operator_util_avg=0.202468 machine_load_cv=0.476499 operator_load_cv=0.46274
- **sanity：通过**

## Case02 - 外协组 merged + separate 混用

- 说明：连续外协形成外协组，部分组设为 merged(total_days)，部分保持 separate(ext_days)。

### run_01
- 临时目录：`/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps_complex_case02_1_ls8a8c1v`
- DB：`/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps_complex_case02_1_ls8a8c1v/aps.db`
- 输入：`/Users/lurenxing/Documents/GitHub/----/evidence/ComplexExcelCases/Case02/run_01/input`
- 输出：`/Users/lurenxing/Documents/GitHub/----/evidence/ComplexExcelCases/Case02/run_01/output`
- start_dt：`2026-05-05 08:00:00`
- 结果文件：`Case02/run_01/result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=284/284 failed=0 overdue=0 time_cost_ms=93 objective=min_overdue budget_s=5
  - best_score：[0.0, 0.0, 0.0, 0.0, 483.6298568505556, 0.0]
  - metrics：overdue_count=0 tardiness_h=0.0 makespan_h=483.6299 changeover=0 machine_util_avg=0.146531 operator_util_avg=0.097687 machine_load_cv=0.732207 operator_load_cv=0.426854
- **sanity：通过**

## Case03 - auto-assign+技能/主操+SGS 派工（greedy vs improve）

- 说明：内部工序缺省资源，开启 auto-assign；人机表含技能/主操；启用 SGS 派工并对比 greedy/improve。

### run_01
- 临时目录：`/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps_complex_case03_1_r_w9p083`
- DB：`/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps_complex_case03_1_r_w9p083/aps.db`
- 输入：`/Users/lurenxing/Documents/GitHub/----/evidence/ComplexExcelCases/Case03/run_01/input`
- 输出：`/Users/lurenxing/Documents/GitHub/----/evidence/ComplexExcelCases/Case03/run_01/output`
- start_dt：`2026-05-05 08:00:00`
- 结果文件：`Case03/run_01/result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=348/348 failed=0 overdue=8 time_cost_ms=18363 objective=min_tardiness budget_s=5
  - best_score：[0.0, 532.6589074650001, 8.0, 644.7882949961112, 698.035757628889, 0.0]
  - metrics：overdue_count=8 tardiness_h=532.6589 makespan_h=698.0358 changeover=0 machine_util_avg=0.25344 operator_util_avg=0.19584 machine_load_cv=1.03589 operator_load_cv=0.29332
- 排产：algo=improve version=2 result_status=success ops=348/348 failed=0 overdue=5 time_cost_ms=12147 objective=min_tardiness budget_s=15
  - best_score：[0.0, 103.26840349583333, 5.0, 122.02659897555554, 751.0382081688889, 0.0]
  - metrics：overdue_count=5 tardiness_h=103.2684 makespan_h=751.0382 changeover=0 machine_util_avg=0.238401 operator_util_avg=0.184219 machine_load_cv=0.813518 operator_load_cv=0.382359
- **sanity：通过**

## Case04 - 冻结窗口插单回归

- 说明：先排产得到 V1；再导入特急插单，开启 freeze_window，验证窗口内排程不被破坏。

### run_01
- 临时目录：`/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps_complex_case04_1_e7suhq23`
- DB：`/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps_complex_case04_1_e7suhq23/aps.db`
- 输入：`/Users/lurenxing/Documents/GitHub/----/evidence/ComplexExcelCases/Case04/run_01/input`
- 输出：`/Users/lurenxing/Documents/GitHub/----/evidence/ComplexExcelCases/Case04/run_01/output`
- start_dt：`2026-05-05 08:00:00`
- 结果文件：`Case04/run_01/result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=35/35 failed=0 overdue=0 time_cost_ms=12 objective=min_overdue budget_s=5
  - best_score：[0.0, 0.0, 0.0, 0.0, 175.3088031513889, 0.0]
  - metrics：overdue_count=0 tardiness_h=0.0 makespan_h=175.3088 changeover=0 machine_util_avg=0.258419 operator_util_avg=0.13681 machine_load_cv=1.112002 operator_load_cv=1.103273
- 排产：algo=greedy+freeze version=2 result_status=success ops=70/70 failed=0 overdue=5 time_cost_ms=17 objective=min_overdue budget_s=5
  - best_score：[0.0, 5.0, 1330.1382157283335, 443.3794052427778, 245.6823742313889, 0.0]
  - metrics：overdue_count=5 tardiness_h=443.3794 makespan_h=245.6824 changeover=0 machine_util_avg=0.377087 operator_util_avg=0.188544 machine_load_cv=0.727651 operator_load_cv=0.514249
- **sanity：通过**

## Case05 - 资源极稀疏+密集停机+禁排日多

- 说明：极稀疏的人机资质+高比例停机+大量 allow_normal=no/holiday，验证不会出现全失败/冲突/死循环，且结果不离谱。

### run_01
- 临时目录：`/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps_complex_case05_1_v5oz31sh`
- DB：`/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps_complex_case05_1_v5oz31sh/aps.db`
- 输入：`/Users/lurenxing/Documents/GitHub/----/evidence/ComplexExcelCases/Case05/run_01/input`
- 输出：`/Users/lurenxing/Documents/GitHub/----/evidence/ComplexExcelCases/Case05/run_01/output`
- start_dt：`2026-05-05 08:00:00`
- 结果文件：`Case05/run_01/result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=444/444 failed=0 overdue=37 time_cost_ms=113 objective=min_overdue budget_s=5
  - best_score：[0.0, 37.0, 99953.37375459333, 87521.72011488053, 4419.5037999999995, 0.0]
  - metrics：overdue_count=37 tardiness_h=87521.7201 makespan_h=4419.5038 changeover=0 machine_util_avg=0.365339 operator_util_avg=0.313148 machine_load_cv=0.506816 operator_load_cv=0.882395
- **sanity：通过**

## Case06 - 超紧交期+高负荷+多外协merged

- 说明：due_date 极短（1~5天）+高负荷+多段连续外协并大量 merged(total_days)，验证超期/外协一致性/导出报表可用。

### run_01
- 临时目录：`/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps_complex_case06_1_j_ib2oyw`
- DB：`/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps_complex_case06_1_j_ib2oyw/aps.db`
- 输入：`/Users/lurenxing/Documents/GitHub/----/evidence/ComplexExcelCases/Case06/run_01/input`
- 输出：`/Users/lurenxing/Documents/GitHub/----/evidence/ComplexExcelCases/Case06/run_01/output`
- start_dt：`2026-05-05 08:00:00`
- 结果文件：`Case06/run_01/result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=756/756 failed=0 overdue=63 time_cost_ms=358 objective=min_overdue budget_s=5
  - best_score：[0.0, 63.0, 117014.94801877029, 98878.47113857223, 2717.2628, 0.0]
  - metrics：overdue_count=63 tardiness_h=98878.4711 makespan_h=2717.2628 changeover=0 machine_util_avg=0.187917 operator_util_avg=0.128125 machine_load_cv=0.925565 operator_load_cv=0.303759
- **sanity：通过**

