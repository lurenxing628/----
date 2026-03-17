# 复杂排产 Excel Cases 全流程验证报告

- 生成时间：2026-03-17 14:16:56
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
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case01_1_5bb7dk6v`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case01_1_5bb7dk6v\aps.db`
- 输入：`D:\Github\APS Test\evidence\ComplexExcelCases\Case01\run_01\input`
- 输出：`D:\Github\APS Test\evidence\ComplexExcelCases\Case01\run_01\output`
- start_dt：`2026-03-18 08:00:00`
- 结果文件：`Case01\run_01\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=300/300 failed=0 overdue=3 time_cost_ms=212 objective=min_overdue budget_s=5
  - best_score：[0.0, 3.0, 36.14608254611111, 529.6551357075, 0.0]
  - metrics：overdue_count=3 tardiness_h=36.1461 makespan_h=529.6551 changeover=0 machine_util_avg=0.293169 operator_util_avg=0.21669 machine_load_cv=0.507854 operator_load_cv=0.396094
- **sanity：通过**

## Case02 - 外协组 merged + separate 混用

- 说明：连续外协形成外协组，部分组设为 merged(total_days)，部分保持 separate(ext_days)。

### run_01
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case02_1_3fe0lizm`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case02_1_3fe0lizm\aps.db`
- 输入：`D:\Github\APS Test\evidence\ComplexExcelCases\Case02\run_01\input`
- 输出：`D:\Github\APS Test\evidence\ComplexExcelCases\Case02\run_01\output`
- start_dt：`2026-03-18 08:00:00`
- 结果文件：`Case02\run_01\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=254/254 failed=0 overdue=1 time_cost_ms=168 objective=min_overdue budget_s=5
  - best_score：[0.0, 1.0, 35.22857142833333, 387.78321678305554, 0.0]
  - metrics：overdue_count=1 tardiness_h=35.2286 makespan_h=387.7832 changeover=0 machine_util_avg=0.191205 operator_util_avg=0.12747 machine_load_cv=0.741477 operator_load_cv=0.453953
- **sanity：通过**

## Case03 - auto-assign+技能/主操+SGS 派工（greedy vs improve）

- 说明：内部工序缺省资源，开启 auto-assign；人机表含技能/主操；启用 SGS 派工并对比 greedy/improve。

### run_01
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case03_1_393sj6f6`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case03_1_393sj6f6\aps.db`
- 输入：`D:\Github\APS Test\evidence\ComplexExcelCases\Case03\run_01\input`
- 输出：`D:\Github\APS Test\evidence\ComplexExcelCases\Case03\run_01\output`
- start_dt：`2026-03-18 08:00:00`
- 结果文件：`Case03\run_01\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=342/342 failed=0 overdue=2 time_cost_ms=22474 objective=min_tardiness budget_s=5
  - best_score：[0.0, 48.637826385833336, 2.0, 727.0382081688889, 0.0]
  - metrics：overdue_count=2 tardiness_h=48.6378 makespan_h=727.0382 changeover=0 machine_util_avg=0.278562 operator_util_avg=0.215253 machine_load_cv=0.907865 operator_load_cv=0.240447
- 排产：algo=improve version=2 result_status=success ops=342/342 failed=0 overdue=3 time_cost_ms=7955 objective=min_tardiness budget_s=15
  - best_score：[0.0, 204.80469960250002, 3.0, 797.6541961577777, 0.0]
  - metrics：overdue_count=3 tardiness_h=204.8047 makespan_h=797.6542 changeover=0 machine_util_avg=0.239642 operator_util_avg=0.185178 machine_load_cv=0.849865 operator_load_cv=0.514622
- **sanity：通过**

## Case04 - 冻结窗口插单回归

- 说明：先排产得到 V1；再导入特急插单，开启 freeze_window，验证窗口内排程不被破坏。

### run_01
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case04_1_piqc38xx`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case04_1_piqc38xx\aps.db`
- 输入：`D:\Github\APS Test\evidence\ComplexExcelCases\Case04\run_01\input`
- 输出：`D:\Github\APS Test\evidence\ComplexExcelCases\Case04\run_01\output`
- start_dt：`2026-03-18 08:00:00`
- 结果文件：`Case04\run_01\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=42/42 failed=0 overdue=0 time_cost_ms=57 objective=min_overdue budget_s=5
  - best_score：[0.0, 0.0, 0.0, 199.88716357416666, 0.0]
  - metrics：overdue_count=0 tardiness_h=0.0 makespan_h=199.8872 changeover=0 machine_util_avg=0.276142 operator_util_avg=0.146193 machine_load_cv=0.737307 operator_load_cv=0.894122
- 排产：algo=greedy+freeze version=2 result_status=success ops=77/77 failed=0 overdue=5 time_cost_ms=61 objective=min_overdue budget_s=5
  - best_score：[0.0, 5.0, 346.52610143611105, 339.41221233305555, 0.0]
  - metrics：overdue_count=5 tardiness_h=346.5261 makespan_h=339.4122 changeover=0 machine_util_avg=0.289121 operator_util_avg=0.153064 machine_load_cv=0.603648 operator_load_cv=0.596338
- **sanity：通过**

## Case05 - 资源极稀疏+密集停机+禁排日多

- 说明：极稀疏的人机资质+高比例停机+大量 allow_normal=no/holiday，验证不会出现全失败/冲突/死循环，且结果不离谱。

### run_01
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case05_1_baxj0a34`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case05_1_baxj0a34\aps.db`
- 输入：`D:\Github\APS Test\evidence\ComplexExcelCases\Case05\run_01\input`
- 输出：`D:\Github\APS Test\evidence\ComplexExcelCases\Case05\run_01\output`
- start_dt：`2026-03-18 08:00:00`
- 结果文件：`Case05\run_01\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=528/528 failed=0 overdue=44 time_cost_ms=372 objective=min_overdue budget_s=5
  - best_score：[0.0, 44.0, 112925.69190254445, 4898.9265, 0.0]
  - metrics：overdue_count=44 tardiness_h=112925.6919 makespan_h=4898.9265 changeover=0 machine_util_avg=0.357761 operator_util_avg=0.306652 machine_load_cv=0.593189 operator_load_cv=0.981019
- **sanity：通过**

## Case06 - 超紧交期+高负荷+多外协merged

- 说明：due_date 极短（1~5天）+高负荷+多段连续外协并大量 merged(total_days)，验证超期/外协一致性/导出报表可用。

### run_01
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case06_1_afyjf_pc`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case06_1_afyjf_pc\aps.db`
- 输入：`D:\Github\APS Test\evidence\ComplexExcelCases\Case06\run_01\input`
- 输出：`D:\Github\APS Test\evidence\ComplexExcelCases\Case06\run_01\output`
- start_dt：`2026-03-18 08:00:00`
- 结果文件：`Case06\run_01\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=744/744 failed=0 overdue=62 time_cost_ms=796 objective=min_overdue budget_s=5
  - best_score：[0.0, 62.0, 96553.15880059167, 2694.6924000000004, 0.0]
  - metrics：overdue_count=62 tardiness_h=96553.1588 makespan_h=2694.6924 changeover=0 machine_util_avg=0.181336 operator_util_avg=0.123638 machine_load_cv=0.98004 operator_load_cv=0.342681
- **sanity：通过**

