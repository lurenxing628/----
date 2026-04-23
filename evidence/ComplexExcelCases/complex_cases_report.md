# 复杂排产 Excel Cases 全流程验证报告

- 生成时间：2026-04-22 09:03:14
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
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case01_1_7i73_kb7`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case01_1_7i73_kb7\aps.db`
- 输入：`D:\Github\APS Test\evidence\ComplexExcelCases\Case01\run_01\input`
- 输出：`D:\Github\APS Test\evidence\ComplexExcelCases\Case01\run_01\output`
- start_dt：`2026-04-23 08:00:00`
- 结果文件：`Case01\run_01\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=230/230 failed=0 overdue=1 time_cost_ms=173 objective=min_overdue budget_s=5
  - best_score：[0.0, 1.0, 62.462171393055556, 62.462171393055556, 294.42427059694444, 0.0]
  - metrics：overdue_count=1 tardiness_h=62.4622 makespan_h=294.4243 changeover=0 machine_util_avg=0.404286 operator_util_avg=0.29882 machine_load_cv=0.350737 operator_load_cv=0.338514
- **sanity：通过**

## Case02 - 外协组 merged + separate 混用

- 说明：连续外协形成外协组，部分组设为 merged(total_days)，部分保持 separate(ext_days)。

### run_01
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case02_1_wkpw2llk`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case02_1_wkpw2llk\aps.db`
- 输入：`D:\Github\APS Test\evidence\ComplexExcelCases\Case02\run_01\input`
- 输出：`D:\Github\APS Test\evidence\ComplexExcelCases\Case02\run_01\output`
- start_dt：`2026-04-23 08:00:00`
- 结果文件：`Case02\run_01\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=268/268 failed=0 overdue=2 time_cost_ms=205 objective=min_overdue budget_s=5
  - best_score：[0.0, 2.0, 20.042803392222222, 20.042803392222222, 435.6298568505556, 0.0]
  - metrics：overdue_count=2 tardiness_h=20.0428 makespan_h=435.6299 changeover=0 machine_util_avg=0.142509 operator_util_avg=0.095006 machine_load_cv=0.802725 operator_load_cv=0.411401
- **sanity：通过**

## Case03 - auto-assign+技能/主操+SGS 派工（greedy vs improve）

- 说明：内部工序缺省资源，开启 auto-assign；人机表含技能/主操；启用 SGS 派工并对比 greedy/improve。

### run_01
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case03_1_y_r81slg`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case03_1_y_r81slg\aps.db`
- 输入：`D:\Github\APS Test\evidence\ComplexExcelCases\Case03\run_01\input`
- 输出：`D:\Github\APS Test\evidence\ComplexExcelCases\Case03\run_01\output`
- start_dt：`2026-04-23 08:00:00`
- 结果文件：`Case03\run_01\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=342/342 failed=0 overdue=8 time_cost_ms=21770 objective=min_tardiness budget_s=5
  - best_score：[0.0, 773.8153582586111, 8.0, 922.9502285311111, 773.401415571389, 0.0]
  - metrics：overdue_count=8 tardiness_h=773.8154 makespan_h=773.4014 changeover=0 machine_util_avg=0.265187 operator_util_avg=0.204917 machine_load_cv=0.877727 operator_load_cv=0.208573
- 排产：algo=improve version=2 result_status=success ops=342/342 failed=0 overdue=6 time_cost_ms=14837 objective=min_tardiness budget_s=15
  - best_score：[0.0, 188.39836573527782, 6.0, 188.39836573527782, 775.4782608697222, 0.0]
  - metrics：overdue_count=6 tardiness_h=188.3984 makespan_h=775.4783 changeover=0 machine_util_avg=0.26678 operator_util_avg=0.206148 machine_load_cv=0.767165 operator_load_cv=0.263545
- **sanity：通过**

## Case04 - 冻结窗口插单回归

- 说明：先排产得到 V1；再导入特急插单，开启 freeze_window，验证窗口内排程不被破坏。

### run_01
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case04_1_6lv5gaz8`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case04_1_6lv5gaz8\aps.db`
- 输入：`D:\Github\APS Test\evidence\ComplexExcelCases\Case04\run_01\input`
- 输出：`D:\Github\APS Test\evidence\ComplexExcelCases\Case04\run_01\output`
- start_dt：`2026-04-23 08:00:00`
- 结果文件：`Case04\run_01\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=42/42 failed=0 overdue=0 time_cost_ms=68 objective=min_overdue budget_s=5
  - best_score：[0.0, 0.0, 0.0, 0.0, 172.19045423694442, 0.0]
  - metrics：overdue_count=0 tardiness_h=0.0 makespan_h=172.1905 changeover=0 machine_util_avg=0.295361 operator_util_avg=0.14768 machine_load_cv=0.740013 operator_load_cv=0.703396
- 排产：algo=greedy+freeze version=2 result_status=success ops=77/77 failed=0 overdue=5 time_cost_ms=77 objective=min_overdue budget_s=5
  - best_score：[0.0, 5.0, 618.5444162933334, 206.18147209777777, 293.3108872702778, 0.0]
  - metrics：overdue_count=5 tardiness_h=206.1815 makespan_h=293.3109 changeover=0 machine_util_avg=0.369757 operator_util_avg=0.184879 machine_load_cv=0.626805 operator_load_cv=0.668645
- **sanity：通过**

## Case05 - 资源极稀疏+密集停机+禁排日多

- 说明：极稀疏的人机资质+高比例停机+大量 allow_normal=no/holiday，验证不会出现全失败/冲突/死循环，且结果不离谱。

### run_01
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case05_1_8_wzx3dl`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case05_1_8_wzx3dl\aps.db`
- 输入：`D:\Github\APS Test\evidence\ComplexExcelCases\Case05\run_01\input`
- 输出：`D:\Github\APS Test\evidence\ComplexExcelCases\Case05\run_01\output`
- start_dt：`2026-04-23 08:00:00`
- 结果文件：`Case05\run_01\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=528/528 failed=0 overdue=44 time_cost_ms=453 objective=min_overdue budget_s=5
  - best_score：[0.0, 44.0, 126970.15380366526, 111952.00559766553, 4874.9265, 0.0]
  - metrics：overdue_count=44 tardiness_h=111952.0056 makespan_h=4874.9265 changeover=0 machine_util_avg=0.363794 operator_util_avg=0.311823 machine_load_cv=0.546564 operator_load_cv=0.947341
- **sanity：通过**

## Case06 - 超紧交期+高负荷+多外协merged

- 说明：due_date 极短（1~5天）+高负荷+多段连续外协并大量 merged(total_days)，验证超期/外协一致性/导出报表可用。

### run_01
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case06_1_zzuxdq7o`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case06_1_zzuxdq7o\aps.db`
- 输入：`D:\Github\APS Test\evidence\ComplexExcelCases\Case06\run_01\input`
- 输出：`D:\Github\APS Test\evidence\ComplexExcelCases\Case06\run_01\output`
- start_dt：`2026-04-23 08:00:00`
- 结果文件：`Case06\run_01\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=744/744 failed=0 overdue=62 time_cost_ms=927 objective=min_overdue budget_s=5
  - best_score：[0.0, 62.0, 116740.520593997, 97337.90749712226, 2786.2844, 0.0]
  - metrics：overdue_count=62 tardiness_h=97337.9075 makespan_h=2786.2844 changeover=0 machine_util_avg=0.17618 operator_util_avg=0.120123 machine_load_cv=0.961925 operator_load_cv=0.327125
- **sanity：通过**

