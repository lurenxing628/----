# 复杂排产 Excel Cases 全流程验证报告

- 生成时间：2026-04-02 17:01:06
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
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case01_1_p95o1ksi`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case01_1_p95o1ksi\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case01\run_01\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case01\run_01\output`
- start_dt：`2026-04-03 08:00:00`
- 结果文件：`Case01\run_01\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=230/230 failed=0 overdue=2 time_cost_ms=141 objective=min_overdue budget_s=5
  - best_score：[0.0, 2.0, 71.09025490305555, 291.2729709897222, 0.0]
  - metrics：overdue_count=2 tardiness_h=71.0903 makespan_h=291.273 changeover=0 machine_util_avg=0.350086 operator_util_avg=0.258759 machine_load_cv=0.482181 operator_load_cv=0.379944
- **sanity：通过**

## Case02 - 外协组 merged + separate 混用

- 说明：连续外协形成外协组，部分组设为 merged(total_days)，部分保持 separate(ext_days)。

### run_01
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case02_1_yy2y7sxy`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case02_1_yy2y7sxy\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case02\run_01\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case02\run_01\output`
- start_dt：`2026-04-03 08:00:00`
- 结果文件：`Case02\run_01\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=268/268 failed=0 overdue=2 time_cost_ms=181 objective=min_overdue budget_s=5
  - best_score：[0.0, 2.0, 68.04280339222223, 435.1247443763889, 0.0]
  - metrics：overdue_count=2 tardiness_h=68.0428 makespan_h=435.1247 changeover=0 machine_util_avg=0.139529 operator_util_avg=0.09302 machine_load_cv=0.838323 operator_load_cv=0.404863
- **sanity：通过**

## Case03 - auto-assign+技能/主操+SGS 派工（greedy vs improve）

- 说明：内部工序缺省资源，开启 auto-assign；人机表含技能/主操；启用 SGS 派工并对比 greedy/improve。

### run_01
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case03_1_dpl6kgpa`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case03_1_dpl6kgpa\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case03\run_01\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case03\run_01\output`
- start_dt：`2026-04-03 08:00:00`
- 结果文件：`Case03\run_01\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=342/342 failed=0 overdue=9 time_cost_ms=25912 objective=min_tardiness budget_s=5
  - best_score：[0.0, 388.11778429916666, 9.0, 769.4071146247221, 0.0]
  - metrics：overdue_count=9 tardiness_h=388.1178 makespan_h=769.4071 changeover=0 machine_util_avg=0.290923 operator_util_avg=0.224804 machine_load_cv=0.788309 operator_load_cv=0.224622
- 排产：algo=improve version=2 result_status=success ops=342/342 failed=0 overdue=11 time_cost_ms=15208 objective=min_tardiness budget_s=15
  - best_score：[0.0, 478.932511115, 11.0, 774.5344241199999, 0.0]
  - metrics：overdue_count=11 tardiness_h=478.9325 makespan_h=774.5344 changeover=0 machine_util_avg=0.262401 operator_util_avg=0.202764 machine_load_cv=0.744878 operator_load_cv=0.412192
- **sanity：通过**

## Case04 - 冻结窗口插单回归

- 说明：先排产得到 V1；再导入特急插单，开启 freeze_window，验证窗口内排程不被破坏。

### run_01
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case04_1_czi13rx7`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case04_1_czi13rx7\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case04\run_01\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case04\run_01\output`
- start_dt：`2026-04-03 08:00:00`
- 结果文件：`Case04\run_01\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=42/42 failed=0 overdue=0 time_cost_ms=54 objective=min_overdue budget_s=5
  - best_score：[0.0, 0.0, 0.0, 172.19045423694442, 0.0]
  - metrics：overdue_count=0 tardiness_h=0.0 makespan_h=172.1905 changeover=0 machine_util_avg=0.295361 operator_util_avg=0.14768 machine_load_cv=0.880598 operator_load_cv=0.729992
- 排产：algo=greedy+freeze version=2 result_status=success ops=77/77 failed=0 overdue=5 time_cost_ms=68 objective=min_overdue budget_s=5
  - best_score：[0.0, 5.0, 252.04229630999998, 318.46270659416666, 0.0]
  - metrics：overdue_count=5 tardiness_h=252.0423 makespan_h=318.4627 changeover=0 machine_util_avg=0.368539 operator_util_avg=0.184269 machine_load_cv=0.674922 operator_load_cv=0.640323
- **sanity：通过**

## Case05 - 资源极稀疏+密集停机+禁排日多

- 说明：极稀疏的人机资质+高比例停机+大量 allow_normal=no/holiday，验证不会出现全失败/冲突/死循环，且结果不离谱。

### run_01
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case05_1_4bln256e`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case05_1_4bln256e\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case05\run_01\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case05\run_01\output`
- start_dt：`2026-04-03 08:00:00`
- 结果文件：`Case05\run_01\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=444/444 failed=0 overdue=37 time_cost_ms=335 objective=min_overdue budget_s=5
  - best_score：[0.0, 37.0, 87835.36788375251, 4515.5037999999995, 0.0]
  - metrics：overdue_count=37 tardiness_h=87835.3679 makespan_h=4515.5038 changeover=0 machine_util_avg=0.338462 operator_util_avg=0.29011 machine_load_cv=0.582238 operator_load_cv=0.940445
- **sanity：通过**

## Case06 - 超紧交期+高负荷+多外协merged

- 说明：due_date 极短（1~5天）+高负荷+多段连续外协并大量 merged(total_days)，验证超期/外协一致性/导出报表可用。

### run_01
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case06_1_jofbqwab`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case06_1_jofbqwab\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case06\run_01\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case06\run_01\output`
- start_dt：`2026-04-03 08:00:00`
- 结果文件：`Case06\run_01\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=756/756 failed=0 overdue=63 time_cost_ms=848 objective=min_overdue budget_s=5
  - best_score：[0.0, 63.0, 100689.70921420834, 2762.2844, 0.0]
  - metrics：overdue_count=63 tardiness_h=100689.7092 makespan_h=2762.2844 changeover=0 machine_util_avg=0.177315 operator_util_avg=0.120897 machine_load_cv=0.991574 operator_load_cv=0.34221
- **sanity：通过**

