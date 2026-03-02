# 复杂排产 Excel Cases 全流程验证报告

- 生成时间：2026-03-02 12:35:54
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
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case01_1_d8ub1h3o`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case01_1_d8ub1h3o\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case01\run_01\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case01\run_01\output`
- start_dt：`2026-03-03 08:00:00`
- 结果文件：`Case01\run_01\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=210/210 failed=0 overdue=1 time_cost_ms=62 objective=min_overdue budget_s=5
  - best_score：[0.0, 1.0, 33.55189764805556, 243.40302375833332, 0.0]
  - metrics：overdue_count=1 tardiness_h=33.5519 makespan_h=243.403 changeover=0 machine_util_avg=0.581238 operator_util_avg=0.217964 machine_load_cv=0.474625 operator_load_cv=0.980026
- **sanity：通过**

## Case02 - 外协组 merged + separate 混用

- 说明：连续外协形成外协组，部分组设为 merged(total_days)，部分保持 separate(ext_days)。

### run_01
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case02_1_mxc306so`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case02_1_mxc306so\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case02\run_01\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case02\run_01\output`
- start_dt：`2026-03-03 08:00:00`
- 结果文件：`Case02\run_01\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=284/284 failed=0 overdue=0 time_cost_ms=429 objective=min_overdue budget_s=5
  - best_score：[0.0, 0.0, 0.0, 483.6298568505556, 0.0]
  - metrics：overdue_count=0 tardiness_h=0.0 makespan_h=483.6299 changeover=0 machine_util_avg=0.146531 operator_util_avg=0.097687 machine_load_cv=0.732207 operator_load_cv=0.426854
- **sanity：通过**

## Case03 - auto-assign+技能/主操+SGS 派工（greedy vs improve）

- 说明：内部工序缺省资源，开启 auto-assign；人机表含技能/主操；启用 SGS 派工并对比 greedy/improve。

### run_01
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case03_1_5lsenlyi`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case03_1_5lsenlyi\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case03\run_01\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case03\run_01\output`
- start_dt：`2026-03-03 08:00:00`
- 结果文件：`Case03\run_01\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=348/348 failed=0 overdue=6 time_cost_ms=38699 objective=min_tardiness budget_s=5
  - best_score：[0.0, 262.72959771305557, 6.0, 673.7912317327778, 0.0]
  - metrics：overdue_count=6 tardiness_h=262.7296 makespan_h=673.7912 changeover=0 machine_util_avg=0.288596 operator_util_avg=0.223006 machine_load_cv=0.916753 operator_load_cv=0.237158
- 排产：algo=improve version=2 result_status=success ops=348/348 failed=0 overdue=11 time_cost_ms=15581 objective=min_tardiness budget_s=15
  - best_score：[0.0, 747.7821852597222, 11.0, 679.0772484038889, 0.0]
  - metrics：overdue_count=11 tardiness_h=747.7822 makespan_h=679.0772 changeover=0 machine_util_avg=0.301988 operator_util_avg=0.233355 machine_load_cv=0.962707 operator_load_cv=0.430594
- **sanity：通过**

## Case04 - 冻结窗口插单回归

- 说明：先排产得到 V1；再导入特急插单，开启 freeze_window，验证窗口内排程不被破坏。

### run_01
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case04_1_7cmxv18e`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case04_1_7cmxv18e\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case04\run_01\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case04\run_01\output`
- start_dt：`2026-03-03 08:00:00`
- 结果文件：`Case04\run_01\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=35/35 failed=0 overdue=0 time_cost_ms=82 objective=min_overdue budget_s=5
  - best_score：[0.0, 0.0, 0.0, 175.3088031513889, 0.0]
  - metrics：overdue_count=0 tardiness_h=0.0 makespan_h=175.3088 changeover=0 machine_util_avg=0.258419 operator_util_avg=0.13681 machine_load_cv=1.112002 operator_load_cv=1.103273
- 排产：algo=greedy+freeze version=2 result_status=success ops=70/70 failed=0 overdue=5 time_cost_ms=97 objective=min_overdue budget_s=5
  - best_score：[0.0, 5.0, 443.3807941316666, 245.6823742313889, 0.0]
  - metrics：overdue_count=5 tardiness_h=443.3808 makespan_h=245.6824 changeover=0 machine_util_avg=0.377087 operator_util_avg=0.188544 machine_load_cv=0.727651 operator_load_cv=0.514249
- **sanity：通过**

## Case05 - 资源极稀疏+密集停机+禁排日多

- 说明：极稀疏的人机资质+高比例停机+大量 allow_normal=no/holiday，验证不会出现全失败/冲突/死循环，且结果不离谱。

### run_01
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case05_1_t_yxifl5`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case05_1_t_yxifl5\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case05\run_01\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case05\run_01\output`
- start_dt：`2026-03-03 08:00:00`
- 结果文件：`Case05\run_01\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=444/444 failed=0 overdue=37 time_cost_ms=141 objective=min_overdue budget_s=5
  - best_score：[0.0, 37.0, 24351.037391064725, 1682.1392115969443, 0.0]
  - metrics：overdue_count=37 tardiness_h=24351.0374 makespan_h=1682.1392 changeover=0 machine_util_avg=0.900141 operator_util_avg=0.900141 machine_load_cv=0.0 operator_load_cv=0.0
- **sanity：通过**

## Case06 - 超紧交期+高负荷+多外协merged

- 说明：due_date 极短（1~5天）+高负荷+多段连续外协并大量 merged(total_days)，验证超期/外协一致性/导出报表可用。

### run_01
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case06_1__h7i_urv`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case06_1__h7i_urv\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case06\run_01\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case06\run_01\output`
- start_dt：`2026-03-03 08:00:00`
- 结果文件：`Case06\run_01\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=756/756 failed=0 overdue=63 time_cost_ms=1748 objective=min_overdue budget_s=5
  - best_score：[0.0, 63.0, 98878.48863857219, 2717.2628, 0.0]
  - metrics：overdue_count=63 tardiness_h=98878.4886 makespan_h=2717.2628 changeover=0 machine_util_avg=0.187917 operator_util_avg=0.128125 machine_load_cv=0.925565 operator_load_cv=0.303759
- **sanity：通过**

