# 复杂排产 Excel Cases 全流程验证报告

- 生成时间：2026-03-08 23:40:53
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
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case01_1_t44j7ncf`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case01_1_t44j7ncf\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case01\run_01\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case01\run_01\output`
- start_dt：`2026-03-09 08:00:00`
- 结果文件：`Case01\run_01\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=210/210 failed=0 overdue=1 time_cost_ms=57 objective=min_overdue budget_s=5
  - best_score：[0.0, 1.0, 33.55189764805556, 245.68488120944443, 0.0]
  - metrics：overdue_count=1 tardiness_h=33.5519 makespan_h=245.6849 changeover=0 machine_util_avg=0.345395 operator_util_avg=0.129523 machine_load_cv=0.064029 operator_load_cv=0.212542
- **sanity：通过**

## Case02 - 外协组 merged + separate 混用

- 说明：连续外协形成外协组，部分组设为 merged(total_days)，部分保持 separate(ext_days)。

### run_01
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case02_1_e8o87z1o`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case02_1_e8o87z1o\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case02\run_01\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case02\run_01\output`
- start_dt：`2026-03-09 08:00:00`
- 结果文件：`Case02\run_01\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=284/284 failed=0 overdue=0 time_cost_ms=418 objective=min_overdue budget_s=5
  - best_score：[0.0, 0.0, 0.0, 435.6298568505556, 0.0]
  - metrics：overdue_count=0 tardiness_h=0.0 makespan_h=435.6299 changeover=0 machine_util_avg=0.177614 operator_util_avg=0.11841 machine_load_cv=0.702917 operator_load_cv=0.528731
- **sanity：通过**

## Case03 - auto-assign+技能/主操+SGS 派工（greedy vs improve）

- 说明：内部工序缺省资源，开启 auto-assign；人机表含技能/主操；启用 SGS 派工并对比 greedy/improve。

### run_01
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case03_1_ny6oiryd`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case03_1_ny6oiryd\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case03\run_01\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case03\run_01\output`
- start_dt：`2026-03-09 08:00:00`
- 结果文件：`Case03\run_01\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=348/348 failed=0 overdue=5 time_cost_ms=36857 objective=min_tardiness budget_s=5
  - best_score：[0.0, 153.7147247158333, 5.0, 679.9368421052778, 0.0]
  - metrics：overdue_count=5 tardiness_h=153.7147 makespan_h=679.9368 changeover=0 machine_util_avg=0.272194 operator_util_avg=0.210332 machine_load_cv=1.049244 operator_load_cv=0.262182
- 排产：algo=improve version=2 result_status=success ops=348/348 failed=0 overdue=8 time_cost_ms=15620 objective=min_tardiness budget_s=15
  - best_score：[0.0, 497.09647817527775, 8.0, 679.9368421052778, 0.0]
  - metrics：overdue_count=8 tardiness_h=497.0965 makespan_h=679.9368 changeover=0 machine_util_avg=0.269818 operator_util_avg=0.208496 machine_load_cv=0.94282 operator_load_cv=0.425031
- **sanity：通过**

## Case04 - 冻结窗口插单回归

- 说明：先排产得到 V1；再导入特急插单，开启 freeze_window，验证窗口内排程不被破坏。

### run_01
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case04_1_jw1jw4jq`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case04_1_jw1jw4jq\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case04\run_01\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case04\run_01\output`
- start_dt：`2026-03-09 08:00:00`
- 结果文件：`Case04\run_01\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=35/35 failed=0 overdue=0 time_cost_ms=64 objective=min_overdue budget_s=5
  - best_score：[0.0, 0.0, 0.0, 175.3088031513889, 0.0]
  - metrics：overdue_count=0 tardiness_h=0.0 makespan_h=175.3088 changeover=0 machine_util_avg=0.227996 operator_util_avg=0.120704 machine_load_cv=1.042749 operator_load_cv=0.788031
- 排产：algo=greedy+freeze version=2 result_status=success ops=70/70 failed=0 overdue=5 time_cost_ms=87 objective=min_overdue budget_s=5
  - best_score：[0.0, 5.0, 443.3807941316666, 337.16525287166667, 0.0]
  - metrics：overdue_count=5 tardiness_h=443.3808 makespan_h=337.1653 changeover=0 machine_util_avg=0.306296 operator_util_avg=0.153148 machine_load_cv=0.556543 operator_load_cv=0.758684
- **sanity：通过**

## Case05 - 资源极稀疏+密集停机+禁排日多

- 说明：极稀疏的人机资质+高比例停机+大量 allow_normal=no/holiday，验证不会出现全失败/冲突/死循环，且结果不离谱。

### run_01
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case05_1_8_jbjegj`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case05_1_8_jbjegj\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case05\run_01\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case05\run_01\output`
- start_dt：`2026-03-09 08:00:00`
- 结果文件：`Case05\run_01\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=444/444 failed=0 overdue=36 time_cost_ms=111 objective=min_overdue budget_s=5
  - best_score：[0.0, 36.0, 23642.856636555836, 1682.1392115969443, 0.0]
  - metrics：overdue_count=36 tardiness_h=23642.8566 makespan_h=1682.1392 changeover=0 machine_util_avg=0.937368 operator_util_avg=0.937368 machine_load_cv=0.0 operator_load_cv=0.0
- **sanity：通过**

## Case06 - 超紧交期+高负荷+多外协merged

- 说明：due_date 极短（1~5天）+高负荷+多段连续外协并大量 merged(total_days)，验证超期/外协一致性/导出报表可用。

### run_01
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case06_1_2fwmfaph`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case06_1_2fwmfaph\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case06\run_01\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case06\run_01\output`
- start_dt：`2026-03-09 08:00:00`
- 结果文件：`Case06\run_01\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=756/756 failed=0 overdue=63 time_cost_ms=1581 objective=min_overdue budget_s=5
  - best_score：[0.0, 63.0, 97701.98462981552, 2717.1868, 0.0]
  - metrics：overdue_count=63 tardiness_h=97701.9846 makespan_h=2717.1868 changeover=0 machine_util_avg=0.182762 operator_util_avg=0.124611 machine_load_cv=0.9847 operator_load_cv=0.346182
- **sanity：通过**

