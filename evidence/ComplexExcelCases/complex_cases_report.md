# 复杂排产 Excel Cases 全流程验证报告

- 生成时间：2026-03-16 11:02:36
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
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case01_1_3vpyy9fy`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case01_1_3vpyy9fy\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case01\run_01\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case01\run_01\output`
- start_dt：`2026-03-17 08:00:00`
- 结果文件：`Case01\run_01\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=210/210 failed=0 overdue=1 time_cost_ms=46 objective=min_overdue budget_s=5
  - best_score：[0.0, 1.0, 33.551619870277776, 243.40302375833332, 0.0]
  - metrics：overdue_count=1 tardiness_h=33.5516 makespan_h=243.403 changeover=0 machine_util_avg=0.581238 operator_util_avg=0.217964 machine_load_cv=0.474625 operator_load_cv=0.980026
- **sanity：通过**

## Case02 - 外协组 merged + separate 混用

- 说明：连续外协形成外协组，部分组设为 merged(total_days)，部分保持 separate(ext_days)。

### run_01
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case02_1_0qe5oor7`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case02_1_0qe5oor7\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case02\run_01\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case02\run_01\output`
- start_dt：`2026-03-17 08:00:00`
- 结果文件：`Case02\run_01\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=284/284 failed=0 overdue=0 time_cost_ms=186 objective=min_overdue budget_s=5
  - best_score：[0.0, 0.0, 0.0, 483.6298568505556, 0.0]
  - metrics：overdue_count=0 tardiness_h=0.0 makespan_h=483.6299 changeover=0 machine_util_avg=0.146531 operator_util_avg=0.097687 machine_load_cv=0.732207 operator_load_cv=0.426854
- **sanity：通过**

## Case03 - auto-assign+技能/主操+SGS 派工（greedy vs improve）

- 说明：内部工序缺省资源，开启 auto-assign；人机表含技能/主操；启用 SGS 派工并对比 greedy/improve。

### run_01
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case03_1_0j4od3rb`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case03_1_0j4od3rb\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case03\run_01\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case03\run_01\output`
- start_dt：`2026-03-17 08:00:00`
- 结果文件：`Case03\run_01\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=348/348 failed=0 overdue=4 time_cost_ms=25033 objective=min_tardiness budget_s=5
  - best_score：[0.0, 114.76245725527777, 4.0, 697.5092886141667, 0.0]
  - metrics：overdue_count=4 tardiness_h=114.7625 makespan_h=697.5093 changeover=0 machine_util_avg=0.279053 operator_util_avg=0.215632 machine_load_cv=0.977184 operator_load_cv=0.25986
- 排产：algo=improve version=2 result_status=success ops=348/348 failed=0 overdue=4 time_cost_ms=8226 objective=min_tardiness budget_s=15
  - best_score：[0.0, 143.20041753638887, 4.0, 751.0382081688889, 0.0]
  - metrics：overdue_count=4 tardiness_h=143.2004 makespan_h=751.0382 changeover=0 machine_util_avg=0.271199 operator_util_avg=0.209563 machine_load_cv=0.863771 operator_load_cv=0.496785
- **sanity：通过**

## Case04 - 冻结窗口插单回归

- 说明：先排产得到 V1；再导入特急插单，开启 freeze_window，验证窗口内排程不被破坏。

### run_01
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case04_1_rp_czzti`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case04_1_rp_czzti\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case04\run_01\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case04\run_01\output`
- start_dt：`2026-03-17 08:00:00`
- 结果文件：`Case04\run_01\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=35/35 failed=0 overdue=0 time_cost_ms=56 objective=min_overdue budget_s=5
  - best_score：[0.0, 0.0, 0.0, 175.3088031513889, 0.0]
  - metrics：overdue_count=0 tardiness_h=0.0 makespan_h=175.3088 changeover=0 machine_util_avg=0.258419 operator_util_avg=0.13681 machine_load_cv=1.112002 operator_load_cv=1.103273
- 排产：algo=greedy+freeze version=2 result_status=success ops=70/70 failed=0 overdue=5 time_cost_ms=67 objective=min_overdue budget_s=5
  - best_score：[0.0, 5.0, 443.3794052427778, 245.6823742313889, 0.0]
  - metrics：overdue_count=5 tardiness_h=443.3794 makespan_h=245.6824 changeover=0 machine_util_avg=0.377087 operator_util_avg=0.188544 machine_load_cv=0.727651 operator_load_cv=0.514249
- **sanity：通过**

## Case05 - 资源极稀疏+密集停机+禁排日多

- 说明：极稀疏的人机资质+高比例停机+大量 allow_normal=no/holiday，验证不会出现全失败/冲突/死循环，且结果不离谱。

### run_01
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case05_1_9rgezh88`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case05_1_9rgezh88\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case05\run_01\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case05\run_01\output`
- start_dt：`2026-03-17 08:00:00`
- 结果文件：`Case05\run_01\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=444/444 failed=0 overdue=37 time_cost_ms=72 objective=min_overdue budget_s=5
  - best_score：[0.0, 37.0, 24351.027113286935, 1682.1392115969443, 0.0]
  - metrics：overdue_count=37 tardiness_h=24351.0271 makespan_h=1682.1392 changeover=0 machine_util_avg=0.900141 operator_util_avg=0.900141 machine_load_cv=0.0 operator_load_cv=0.0
- **sanity：通过**

## Case06 - 超紧交期+高负荷+多外协merged

- 说明：due_date 极短（1~5天）+高负荷+多段连续外协并大量 merged(total_days)，验证超期/外协一致性/导出报表可用。

### run_01
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case06_1_e9xq_55d`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case06_1_e9xq_55d\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case06\run_01\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case06\run_01\output`
- start_dt：`2026-03-17 08:00:00`
- 结果文件：`Case06\run_01\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=756/756 failed=0 overdue=63 time_cost_ms=828 objective=min_overdue budget_s=5
  - best_score：[0.0, 63.0, 98878.47113857223, 2717.2628, 0.0]
  - metrics：overdue_count=63 tardiness_h=98878.4711 makespan_h=2717.2628 changeover=0 machine_util_avg=0.187917 operator_util_avg=0.128125 machine_load_cv=0.925565 operator_load_cv=0.303759
- **sanity：通过**

