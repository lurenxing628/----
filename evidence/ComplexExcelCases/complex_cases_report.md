# 复杂排产 Excel Cases 全流程验证报告

- 生成时间：2026-02-28 01:04:14
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
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case01_1__jzh6x6j`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case01_1__jzh6x6j\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case01\run_01\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case01\run_01\output`
- start_dt：`2026-03-01 08:00:00`
- 结果文件：`Case01\run_01\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=300/300 failed=0 overdue=2 time_cost_ms=93 objective=min_overdue budget_s=5
  - best_score：[0.0, 2.0, 45.789756419166665, 268.46817692944444, 0.0]
  - metrics：overdue_count=2 tardiness_h=45.7898 makespan_h=268.4682 changeover=0 machine_util_avg=0.575806 operator_util_avg=0.215927 machine_load_cv=0.015272 operator_load_cv=0.627071
- **sanity：通过**

## Case02 - 外协组 merged + separate 混用

- 说明：连续外协形成外协组，部分组设为 merged(total_days)，部分保持 separate(ext_days)。

### run_01
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case02_1_swofdnsx`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case02_1_swofdnsx\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case02\run_01\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case02\run_01\output`
- start_dt：`2026-03-01 08:00:00`
- 结果文件：`Case02\run_01\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=284/284 failed=0 overdue=1 time_cost_ms=450 objective=min_overdue budget_s=5
  - best_score：[0.0, 1.0, 9.475025252777778, 507.95322939888894, 0.0]
  - metrics：overdue_count=1 tardiness_h=9.475 makespan_h=507.9532 changeover=0 machine_util_avg=0.119404 operator_util_avg=0.079603 machine_load_cv=0.937524 operator_load_cv=0.609355
- **sanity：通过**

## Case03 - auto-assign+技能/主操+SGS 派工（greedy vs improve）

- 说明：内部工序缺省资源，开启 auto-assign；人机表含技能/主操；启用 SGS 派工并对比 greedy/improve。

### run_01
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case03_1_nwjdmtrj`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case03_1_nwjdmtrj\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case03\run_01\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case03\run_01\output`
- start_dt：`2026-03-01 08:00:00`
- 结果文件：`Case03\run_01\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=348/348 failed=0 overdue=5 time_cost_ms=40718 objective=min_tardiness budget_s=5
  - best_score：[0.0, 394.876789615, 5.0, 679.6703967444445, 0.0]
  - metrics：overdue_count=5 tardiness_h=394.8768 makespan_h=679.6704 changeover=0 machine_util_avg=0.288243 operator_util_avg=0.222733 machine_load_cv=0.941882 operator_load_cv=0.237345
- 排产：algo=improve version=2 result_status=success ops=348/348 failed=0 overdue=10 time_cost_ms=15273 objective=min_tardiness budget_s=15
  - best_score：[0.0, 451.16129387888884, 10.0, 698.2861331983333, 0.0]
  - metrics：overdue_count=10 tardiness_h=451.1613 makespan_h=698.2861 changeover=0 machine_util_avg=0.264607 operator_util_avg=0.204469 machine_load_cv=0.889852 operator_load_cv=0.433118
- **sanity：通过**

## Case04 - 冻结窗口插单回归

- 说明：先排产得到 V1；再导入特急插单，开启 freeze_window，验证窗口内排程不被破坏。

### run_01
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case04_1_d45va8uz`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case04_1_d45va8uz\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case04\run_01\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case04\run_01\output`
- start_dt：`2026-03-01 08:00:00`
- 结果文件：`Case04\run_01\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=42/42 failed=0 overdue=0 time_cost_ms=93 objective=min_overdue budget_s=5
  - best_score：[0.0, 0.0, 0.0, 199.88716357416666, 0.0]
  - metrics：overdue_count=0 tardiness_h=0.0 makespan_h=199.8872 changeover=0 machine_util_avg=0.329505 operator_util_avg=0.174444 machine_load_cv=0.554272 operator_load_cv=0.766379
- 排产：algo=greedy+freeze version=2 result_status=success ops=77/77 failed=0 overdue=5 time_cost_ms=100 objective=min_overdue budget_s=5
  - best_score：[0.0, 5.0, 466.5274903249999, 363.93162194166666, 0.0]
  - metrics：overdue_count=5 tardiness_h=466.5275 makespan_h=363.9316 changeover=0 machine_util_avg=0.30328 operator_util_avg=0.16056 machine_load_cv=0.547944 operator_load_cv=0.534275
- **sanity：通过**

## Case05 - 资源极稀疏+密集停机+禁排日多

- 说明：极稀疏的人机资质+高比例停机+大量 allow_normal=no/holiday，验证不会出现全失败/冲突/死循环，且结果不离谱。

### run_01
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case05_1_ou5jjhcd`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case05_1_ou5jjhcd\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case05\run_01\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case05\run_01\output`
- start_dt：`2026-03-01 08:00:00`
- 结果文件：`Case05\run_01\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=444/444 failed=0 overdue=37 time_cost_ms=146 objective=min_overdue budget_s=5
  - best_score：[0.0, 37.0, 23253.559991448055, 1634.1392115969443, 0.0]
  - metrics：overdue_count=37 tardiness_h=23253.56 makespan_h=1634.1392 changeover=0 machine_util_avg=0.835731 operator_util_avg=0.835731 machine_load_cv=0.0 operator_load_cv=0.0
- **sanity：通过**

## Case06 - 超紧交期+高负荷+多外协merged

- 说明：due_date 极短（1~5天）+高负荷+多段连续外协并大量 merged(total_days)，验证超期/外协一致性/导出报表可用。

### run_01
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case06_1_9cw46q_a`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case06_1_9cw46q_a\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case06\run_01\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case06\run_01\output`
- start_dt：`2026-03-01 08:00:00`
- 结果文件：`Case06\run_01\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=756/756 failed=0 overdue=63 time_cost_ms=1823 objective=min_overdue budget_s=5
  - best_score：[0.0, 63.0, 98379.07245251581, 2713.8667641916663, 0.0]
  - metrics：overdue_count=63 tardiness_h=98379.0725 makespan_h=2713.8668 changeover=0 machine_util_avg=0.176166 operator_util_avg=0.120113 machine_load_cv=1.01049 operator_load_cv=0.349773
- **sanity：通过**

