# 复杂排产 Excel Cases 全流程验证报告

- 生成时间：2026-02-01 18:06:11
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
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case01_1_5d6t3oqo`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case01_1_5d6t3oqo\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case01\run_01\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case01\run_01\output`
- start_dt：`2026-02-02 08:00:00`
- 结果文件：`Case01\run_01\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=210/210 failed=0 overdue=1 time_cost_ms=441 objective=min_overdue budget_s=5
  - best_score：[0.0, 1.0, 33.55189764805556, 245.68488120944443, 0.0]
  - metrics：overdue_count=1 tardiness_h=33.5519 makespan_h=245.6849 changeover=0 machine_util_avg=0.345395 operator_util_avg=0.129523 machine_load_cv=0.064029 operator_load_cv=0.212542
- **sanity：通过**

## Case02 - 外协组 merged + separate 混用

- 说明：连续外协形成外协组，部分组设为 merged(total_days)，部分保持 separate(ext_days)。

### run_01
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case02_1_8nb01wb_`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case02_1_8nb01wb_\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case02\run_01\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case02\run_01\output`
- start_dt：`2026-02-02 08:00:00`
- 结果文件：`Case02\run_01\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=284/284 failed=0 overdue=0 time_cost_ms=5937 objective=min_overdue budget_s=5
  - best_score：[0.0, 0.0, 0.0, 531.40311804, 0.0]
  - metrics：overdue_count=0 tardiness_h=0.0 makespan_h=531.4031 changeover=0 machine_util_avg=0.149374 operator_util_avg=0.099583 machine_load_cv=0.811044 operator_load_cv=0.509399
- **sanity：通过**

## Case03 - auto-assign+技能/主操+SGS 派工（greedy vs improve）

- 说明：内部工序缺省资源，开启 auto-assign；人机表含技能/主操；启用 SGS 派工并对比 greedy/improve。

### run_01
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case03_1_ciuvrol6`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case03_1_ciuvrol6\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case03\run_01\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case03\run_01\output`
- start_dt：`2026-02-02 08:00:00`
- 结果文件：`Case03\run_01\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=348/348 failed=0 overdue=3 time_cost_ms=13035 objective=min_tardiness budget_s=5
  - best_score：[0.0, 79.6751949436111, 3.0, 701.6887080366666, 0.0]
  - metrics：overdue_count=3 tardiness_h=79.6752 makespan_h=701.6887 changeover=0 machine_util_avg=0.279398 operator_util_avg=0.215898 machine_load_cv=0.957671 operator_load_cv=0.235612
- 排产：algo=improve version=2 result_status=success ops=348/348 failed=0 overdue=7 time_cost_ms=29287 objective=min_tardiness budget_s=15
  - best_score：[0.0, 774.3012602952779, 7.0, 773.401415571389, 0.0]
  - metrics：overdue_count=7 tardiness_h=774.3013 makespan_h=773.4014 changeover=0 machine_util_avg=0.269569 operator_util_avg=0.208304 machine_load_cv=0.913329 operator_load_cv=0.47182
- **sanity：通过**

## Case04 - 冻结窗口插单回归

- 说明：先排产得到 V1；再导入特急插单，开启 freeze_window，验证窗口内排程不被破坏。

### run_01
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case04_1_ar6aqvsf`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case04_1_ar6aqvsf\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case04\run_01\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case04\run_01\output`
- start_dt：`2026-02-02 08:00:00`
- 结果文件：`Case04\run_01\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=35/35 failed=0 overdue=0 time_cost_ms=437 objective=min_overdue budget_s=5
  - best_score：[0.0, 0.0, 0.0, 174.33218000583335, 0.0]
  - metrics：overdue_count=0 tardiness_h=0.0 makespan_h=174.3322 changeover=0 machine_util_avg=0.268716 operator_util_avg=0.142262 machine_load_cv=0.887643 operator_load_cv=0.81818
- 排产：algo=greedy+freeze version=2 result_status=success ops=70/70 failed=0 overdue=5 time_cost_ms=621 objective=min_overdue budget_s=5
  - best_score：[0.0, 5.0, 437.2635610488889, 244.68579086055556, 0.0]
  - metrics：overdue_count=5 tardiness_h=437.2636 makespan_h=244.6858 changeover=0 machine_util_avg=0.362092 operator_util_avg=0.181046 machine_load_cv=0.683475 operator_load_cv=0.587574
- **sanity：通过**

## Case05 - 资源极稀疏+密集停机+禁排日多

- 说明：极稀疏的人机资质+高比例停机+大量 allow_normal=no/holiday，验证不会出现全失败/冲突/死循环，且结果不离谱。

### run_01
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case05_1_6tspbq61`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case05_1_6tspbq61\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case05\run_01\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case05\run_01\output`
- start_dt：`2026-02-02 08:00:00`
- 结果文件：`Case05\run_01\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=444/444 failed=0 overdue=36 time_cost_ms=1031 objective=min_overdue budget_s=5
  - best_score：[0.0, 36.0, 23376.890249711665, 1682.2939841088887, 0.0]
  - metrics：overdue_count=36 tardiness_h=23376.8902 makespan_h=1682.294 changeover=0 machine_util_avg=0.936024 operator_util_avg=0.936024 machine_load_cv=0.0 operator_load_cv=0.0
- **sanity：通过**

## Case06 - 超紧交期+高负荷+多外协merged

- 说明：due_date 极短（1~5天）+高负荷+多段连续外协并大量 merged(total_days)，验证超期/外协一致性/导出报表可用。

### run_01
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case06_1_phdvq9nf`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case06_1_phdvq9nf\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case06\run_01\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case06\run_01\output`
- start_dt：`2026-02-02 08:00:00`
- 结果文件：`Case06\run_01\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=756/756 failed=0 overdue=63 time_cost_ms=16887 objective=min_overdue budget_s=5
  - best_score：[0.0, 63.0, 102180.7909259897, 2858.2844, 0.0]
  - metrics：overdue_count=63 tardiness_h=102180.7909 makespan_h=2858.2844 changeover=0 machine_util_avg=0.180474 operator_util_avg=0.12305 machine_load_cv=1.005109 operator_load_cv=0.351881
- **sanity：通过**

