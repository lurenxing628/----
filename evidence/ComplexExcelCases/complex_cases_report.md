# 复杂排产 Excel Cases 全流程验证报告

- 生成时间：2026-01-28 21:48:12
- repeat：20
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
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case01_1_phvhxiwp`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case01_1_phvhxiwp\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case01\run_01\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case01\run_01\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case01\run_01\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=230/230 failed=0 overdue=4 time_cost_ms=648 objective=min_overdue budget_s=5
  - best_score：[0.0, 4.0, 122.24396825388888, 290.350612245, 0.0]
  - metrics：overdue_count=4 tardiness_h=122.244 makespan_h=290.3506 changeover=0 machine_util_avg=0.978898 operator_util_avg=0.367087 machine_load_cv=0.015881 operator_load_cv=0.787037
- **sanity：通过**

### run_02
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case01_2_6eu7ohkn`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case01_2_6eu7ohkn\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case01\run_02\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case01\run_02\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case01\run_02\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=270/270 failed=0 overdue=5 time_cost_ms=687 objective=min_overdue budget_s=5
  - best_score：[0.0, 5.0, 112.1093939711111, 293.83583227444444, 0.0]
  - metrics：overdue_count=5 tardiness_h=112.1094 makespan_h=293.8358 changeover=0 machine_util_avg=0.987854 operator_util_avg=0.423366 machine_load_cv=0.009012 operator_load_cv=0.540501
- **sanity：通过**

### run_03
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case01_3_92f5v809`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case01_3_92f5v809\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case01\run_03\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case01\run_03\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case01\run_03\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=260/260 failed=0 overdue=8 time_cost_ms=696 objective=min_overdue budget_s=5
  - best_score：[0.0, 8.0, 446.7290354091666, 336.5239560444444, 0.0]
  - metrics：overdue_count=8 tardiness_h=446.729 makespan_h=336.524 changeover=0 machine_util_avg=0.998303 operator_util_avg=0.399321 machine_load_cv=0.0017 operator_load_cv=0.586586
- **sanity：通过**

### run_04
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case01_4_stm3zyok`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case01_4_stm3zyok\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case01\run_04\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case01\run_04\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case01\run_04\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=280/280 failed=0 overdue=7 time_cost_ms=733 objective=min_overdue budget_s=5
  - best_score：[0.0, 7.0, 231.46952339166666, 314.4813738441666, 0.0]
  - metrics：overdue_count=7 tardiness_h=231.4695 makespan_h=314.4814 changeover=0 machine_util_avg=0.548587 operator_util_avg=0.235109 machine_load_cv=0.030454 operator_load_cv=0.708548
- **sanity：通过**

### run_05
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case01_5_1ntfzyl2`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case01_5_1ntfzyl2\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case01\run_05\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case01\run_05\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case01\run_05\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=280/280 failed=0 overdue=3 time_cost_ms=928 objective=min_overdue budget_s=5
  - best_score：[0.0, 3.0, 152.66139671333332, 315.60865191138885, 0.0]
  - metrics：overdue_count=3 tardiness_h=152.6614 makespan_h=315.6087 changeover=0 machine_util_avg=0.974986 operator_util_avg=0.36562 machine_load_cv=0.018153 operator_load_cv=0.728934
- **sanity：通过**

### run_06
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case01_6_sws8p0kb`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case01_6_sws8p0kb\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case01\run_06\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case01\run_06\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case01\run_06\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=300/300 failed=0 overdue=5 time_cost_ms=895 objective=min_overdue budget_s=5
  - best_score：[0.0, 5.0, 258.8794865113889, 295.5471839797222, 0.0]
  - metrics：overdue_count=5 tardiness_h=258.8795 makespan_h=295.5472 changeover=0 machine_util_avg=0.983758 operator_util_avg=0.421611 machine_load_cv=0.020325 operator_load_cv=0.474268
- **sanity：通过**

### run_07
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case01_7_e8nmwfwd`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case01_7_e8nmwfwd\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case01\run_07\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case01\run_07\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case01\run_07\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=250/250 failed=0 overdue=6 time_cost_ms=661 objective=min_overdue budget_s=5
  - best_score：[0.0, 6.0, 243.59861167638888, 315.3818737272222, 0.0]
  - metrics：overdue_count=6 tardiness_h=243.5986 makespan_h=315.3819 changeover=0 machine_util_avg=0.992835 operator_util_avg=0.496417 machine_load_cv=0.007789 operator_load_cv=0.617748
- **sanity：通过**

### run_08
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case01_8_i4mfu5jk`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case01_8_i4mfu5jk\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case01\run_08\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case01\run_08\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case01\run_08\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=300/300 failed=0 overdue=7 time_cost_ms=663 objective=min_overdue budget_s=5
  - best_score：[0.0, 7.0, 346.13646879416666, 315.1899665552778, 0.0]
  - metrics：overdue_count=7 tardiness_h=346.1365 makespan_h=315.19 changeover=0 machine_util_avg=0.610757 operator_util_avg=0.261753 machine_load_cv=0.020303 operator_load_cv=0.543051
- **sanity：通过**

### run_09
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case01_9_1we_tlog`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case01_9_1we_tlog\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case01\run_09\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case01\run_09\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case01\run_09\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=270/270 failed=0 overdue=9 time_cost_ms=879 objective=min_overdue budget_s=5
  - best_score：[0.0, 9.0, 322.1225000002778, 341.6446451613889, 0.0]
  - metrics：overdue_count=9 tardiness_h=322.1225 makespan_h=341.6446 changeover=0 machine_util_avg=0.995513 operator_util_avg=0.373317 machine_load_cv=0.0038 operator_load_cv=1.033294
- **sanity：通过**

### run_10
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case01_10_ypn7pcee`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case01_10_ypn7pcee\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case01\run_10\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case01\run_10\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case01\run_10\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=270/270 failed=0 overdue=2 time_cost_ms=741 objective=min_overdue budget_s=5
  - best_score：[0.0, 2.0, 98.81138805277779, 316.2381143430556, 0.0]
  - metrics：overdue_count=2 tardiness_h=98.8114 makespan_h=316.2381 changeover=0 machine_util_avg=0.98151 operator_util_avg=0.420647 machine_load_cv=0.013523 operator_load_cv=0.866174
- **sanity：通过**

### run_11
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case01_11_o4u9bd84`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case01_11_o4u9bd84\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case01\run_11\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case01\run_11\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case01\run_11\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=280/280 failed=0 overdue=7 time_cost_ms=665 objective=min_overdue budget_s=5
  - best_score：[0.0, 7.0, 250.7666132138889, 316.58170346972224, 0.0]
  - metrics：overdue_count=7 tardiness_h=250.7666 makespan_h=316.5817 changeover=0 machine_util_avg=0.996466 operator_util_avg=0.597879 machine_load_cv=0.003379 operator_load_cv=0.416259
- **sanity：通过**

### run_12
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case01_12_i2sugyw2`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case01_12_i2sugyw2\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case01\run_12\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case01\run_12\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case01\run_12\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=270/270 failed=0 overdue=7 time_cost_ms=600 objective=min_overdue budget_s=5
  - best_score：[0.0, 7.0, 189.67100514166668, 312.74092373777773, 0.0]
  - metrics：overdue_count=7 tardiness_h=189.671 makespan_h=312.7409 changeover=0 machine_util_avg=0.349914 operator_util_avg=0.209948 machine_load_cv=0.459434 operator_load_cv=0.663176
- **sanity：通过**

### run_13
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case01_13_yeakdhzh`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case01_13_yeakdhzh\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case01\run_13\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case01\run_13\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case01\run_13\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=280/280 failed=0 overdue=5 time_cost_ms=605 objective=min_overdue budget_s=5
  - best_score：[0.0, 5.0, 224.5826622972222, 318.0479400752778, 0.0]
  - metrics：overdue_count=5 tardiness_h=224.5827 makespan_h=318.0479 changeover=0 machine_util_avg=0.995341 operator_util_avg=0.663561 machine_load_cv=0.004681 operator_load_cv=0.220841
- **sanity：通过**

### run_14
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case01_14_jswymkmr`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case01_14_jswymkmr\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case01\run_14\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case01\run_14\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case01\run_14\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=230/230 failed=0 overdue=5 time_cost_ms=566 objective=min_overdue budget_s=5
  - best_score：[0.0, 5.0, 441.0927197811111, 460.0940170941667, 0.0]
  - metrics：overdue_count=5 tardiness_h=441.0927 makespan_h=460.094 changeover=0 machine_util_avg=0.772971 operator_util_avg=0.257657 machine_load_cv=0.0 operator_load_cv=0.31937
- **sanity：通过**

### run_15
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case01_15_7alidrf1`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case01_15_7alidrf1\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case01\run_15\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case01\run_15\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case01\run_15\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=290/290 failed=0 overdue=7 time_cost_ms=836 objective=min_overdue budget_s=5
  - best_score：[0.0, 7.0, 236.8508885447222, 294.6427329194444, 0.0]
  - metrics：overdue_count=7 tardiness_h=236.8509 makespan_h=294.6427 changeover=0 machine_util_avg=0.987857 operator_util_avg=0.423367 machine_load_cv=0.011283 operator_load_cv=0.666707
- **sanity：通过**

### run_16
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case01_16_ap7ic6ty`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case01_16_ap7ic6ty\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case01\run_16\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case01\run_16\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case01\run_16\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=310/310 failed=0 overdue=8 time_cost_ms=758 objective=min_overdue budget_s=5
  - best_score：[0.0, 8.0, 377.0495415691667, 340.39020979027777, 0.0]
  - metrics：overdue_count=8 tardiness_h=377.0495 makespan_h=340.3902 changeover=0 machine_util_avg=0.996012 operator_util_avg=0.498006 machine_load_cv=0.004004 operator_load_cv=0.165181
- **sanity：通过**

### run_17
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case01_17_qlt2ea4m`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case01_17_qlt2ea4m\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case01\run_17\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case01\run_17\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case01\run_17\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=280/280 failed=0 overdue=4 time_cost_ms=641 objective=min_overdue budget_s=5
  - best_score：[0.0, 4.0, 134.14353077027778, 314.7981613888889, 0.0]
  - metrics：overdue_count=4 tardiness_h=134.1435 makespan_h=314.7982 changeover=0 machine_util_avg=0.831292 operator_util_avg=0.332517 machine_load_cv=0.194744 operator_load_cv=0.378542
- **sanity：通过**

### run_18
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case01_18__sw_tq_d`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case01_18__sw_tq_d\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case01\run_18\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case01\run_18\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case01\run_18\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=280/280 failed=0 overdue=7 time_cost_ms=627 objective=min_overdue budget_s=5
  - best_score：[0.0, 7.0, 218.72612941472224, 316.66397984916665, 0.0]
  - metrics：overdue_count=7 tardiness_h=218.7261 makespan_h=316.664 changeover=0 machine_util_avg=0.324405 operator_util_avg=0.121652 machine_load_cv=0.460265 operator_load_cv=0.878257
- **sanity：通过**

### run_19
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case01_19_wzc4pdj9`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case01_19_wzc4pdj9\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case01\run_19\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case01\run_19\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case01\run_19\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=280/280 failed=0 overdue=9 time_cost_ms=743 objective=min_overdue budget_s=5
  - best_score：[0.0, 9.0, 453.3421016375, 319.4420398011111, 0.0]
  - metrics：overdue_count=9 tardiness_h=453.3421 makespan_h=319.442 changeover=0 machine_util_avg=0.424627 operator_util_avg=0.159235 machine_load_cv=0.020132 operator_load_cv=0.237615
- **sanity：通过**

### run_20
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case01_20_c3m515d4`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case01_20_c3m515d4\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case01\run_20\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case01\run_20\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case01\run_20\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=330/330 failed=0 overdue=5 time_cost_ms=1199 objective=min_overdue budget_s=5
  - best_score：[0.0, 5.0, 292.42561034194443, 342.15409457916667, 0.0]
  - metrics：overdue_count=5 tardiness_h=292.4256 makespan_h=342.1541 changeover=0 machine_util_avg=0.995167 operator_util_avg=0.331722 machine_load_cv=0.004856 operator_load_cv=0.454461
- **sanity：通过**

## Case02 - 外协组 merged + separate 混用

- 说明：连续外协形成外协组，部分组设为 merged(total_days)，部分保持 separate(ext_days)。

### run_01
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case02_1_csx21vll`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case02_1_csx21vll\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case02\run_01\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case02\run_01\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case02\run_01\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=268/268 failed=0 overdue=2 time_cost_ms=3953 objective=min_overdue budget_s=5
  - best_score：[0.0, 2.0, 20.04335894777778, 435.6298568505556, 0.0]
  - metrics：overdue_count=2 tardiness_h=20.0434 makespan_h=435.6299 changeover=0 machine_util_avg=0.158494 operator_util_avg=0.105663 machine_load_cv=0.788833 operator_load_cv=0.386509
- **sanity：通过**

### run_02
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case02_2_hw4eb4k_`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case02_2_hw4eb4k_\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case02\run_02\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case02\run_02\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case02\run_02\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=246/246 failed=0 overdue=5 time_cost_ms=3010 objective=min_overdue budget_s=5
  - best_score：[0.0, 5.0, 107.65077148694445, 653.3127413127778, 0.0]
  - metrics：overdue_count=5 tardiness_h=107.6508 makespan_h=653.3127 changeover=0 machine_util_avg=0.108588 operator_util_avg=0.070263 machine_load_cv=1.716437 operator_load_cv=0.895757
- **sanity：通过**

### run_03
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case02_3_w4rnrl5q`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case02_3_w4rnrl5q\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case02\run_03\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case02\run_03\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case02\run_03\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=216/216 failed=0 overdue=0 time_cost_ms=3115 objective=min_overdue budget_s=5
  - best_score：[0.0, 0.0, 0.0, 363.9882629108333, 0.0]
  - metrics：overdue_count=0 tardiness_h=0.0 makespan_h=363.9883 changeover=0 machine_util_avg=0.197848 operator_util_avg=0.164873 machine_load_cv=0.744065 operator_load_cv=0.616061
- **sanity：通过**

### run_04
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case02_4__6mxmrmi`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case02_4__6mxmrmi\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case02\run_04\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case02\run_04\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case02\run_04\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=226/226 failed=0 overdue=1 time_cost_ms=3451 objective=min_overdue budget_s=5
  - best_score：[0.0, 1.0, 12.797965638888888, 432.28213744944446, 0.0]
  - metrics：overdue_count=1 tardiness_h=12.798 makespan_h=432.2821 changeover=0 machine_util_avg=0.164119 operator_util_avg=0.109413 machine_load_cv=0.82899 operator_load_cv=0.868152
- **sanity：通过**

### run_05
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case02_5_w44ig43n`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case02_5_w44ig43n\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case02\run_05\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case02\run_05\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case02\run_05\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=270/270 failed=0 overdue=6 time_cost_ms=3625 objective=min_overdue budget_s=5
  - best_score：[0.0, 6.0, 214.86251494277778, 601.6823658269444, 0.0]
  - metrics：overdue_count=6 tardiness_h=214.8625 makespan_h=601.6824 changeover=0 machine_util_avg=0.104499 operator_util_avg=0.06386 machine_load_cv=1.608841 operator_load_cv=0.827236
- **sanity：通过**

### run_06
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case02_6_jnlqv9rg`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case02_6_jnlqv9rg\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case02\run_06\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case02\run_06\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case02\run_06\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=254/254 failed=0 overdue=0 time_cost_ms=4084 objective=min_overdue budget_s=5
  - best_score：[0.0, 0.0, 0.0, 316.1579617833333, 0.0]
  - metrics：overdue_count=0 tardiness_h=0.0 makespan_h=316.158 changeover=0 machine_util_avg=0.218669 operator_util_avg=0.157927 machine_load_cv=0.76711 operator_load_cv=0.481154
- **sanity：通过**

### run_07
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case02_7_v2vpw39e`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case02_7_v2vpw39e\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case02\run_07\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case02\run_07\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case02\run_07\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=236/236 failed=0 overdue=0 time_cost_ms=4244 objective=min_overdue budget_s=5
  - best_score：[0.0, 0.0, 0.0, 294.28469750888894, 0.0]
  - metrics：overdue_count=0 tardiness_h=0.0 makespan_h=294.2847 changeover=0 machine_util_avg=0.170415 operator_util_avg=0.150366 machine_load_cv=0.785275 operator_load_cv=0.648113
- **sanity：通过**

### run_08
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case02_8_azwj68ke`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case02_8_azwj68ke\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case02\run_08\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case02\run_08\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case02\run_08\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=274/274 failed=0 overdue=0 time_cost_ms=4568 objective=min_overdue budget_s=5
  - best_score：[0.0, 0.0, 0.0, 338.2621231977778, 0.0]
  - metrics：overdue_count=0 tardiness_h=0.0 makespan_h=338.2621 changeover=0 machine_util_avg=0.195374 operator_util_avg=0.146531 machine_load_cv=0.682222 operator_load_cv=0.491724
- **sanity：通过**

### run_09
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case02_9_143jz40x`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case02_9_143jz40x\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case02\run_09\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case02\run_09\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case02\run_09\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=234/234 failed=0 overdue=10 time_cost_ms=3514 objective=min_overdue budget_s=5
  - best_score：[0.0, 10.0, 554.4986326938889, 773.7497181508334, 0.0]
  - metrics：overdue_count=10 tardiness_h=554.4986 makespan_h=773.7497 changeover=0 machine_util_avg=0.103884 operator_util_avg=0.075027 machine_load_cv=1.534964 operator_load_cv=0.875648
- **sanity：通过**

### run_10
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case02_10_baykhjmm`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case02_10_baykhjmm\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case02\run_10\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case02\run_10\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case02\run_10\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=206/206 failed=0 overdue=0 time_cost_ms=3011 objective=min_overdue budget_s=5
  - best_score：[0.0, 0.0, 0.0, 288.71727748666666, 0.0]
  - metrics：overdue_count=0 tardiness_h=0.0 makespan_h=288.7173 changeover=0 machine_util_avg=0.143125 operator_util_avg=0.126287 machine_load_cv=0.98572 operator_load_cv=0.750649
- **sanity：通过**

### run_11
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case02_11_ih8x63xf`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case02_11_ih8x63xf\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case02\run_11\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case02\run_11\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case02\run_11\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=236/236 failed=0 overdue=0 time_cost_ms=3043 objective=min_overdue budget_s=5
  - best_score：[0.0, 0.0, 0.0, 293.7529817222222, 0.0]
  - metrics：overdue_count=0 tardiness_h=0.0 makespan_h=293.753 changeover=0 machine_util_avg=0.279827 operator_util_avg=0.181064 machine_load_cv=0.394363 operator_load_cv=0.467069
- **sanity：通过**

### run_12
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case02_12_4vzul5jq`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case02_12_4vzul5jq\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case02\run_12\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case02\run_12\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case02\run_12\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=266/266 failed=0 overdue=0 time_cost_ms=4653 objective=min_overdue budget_s=5
  - best_score：[0.0, 0.0, 0.0, 293.2997954063889, 0.0]
  - metrics：overdue_count=0 tardiness_h=0.0 makespan_h=293.2998 changeover=0 machine_util_avg=0.22987 operator_util_avg=0.175783 machine_load_cv=0.633866 operator_load_cv=0.456421
- **sanity：通过**

### run_13
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case02_13_c0beek97`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case02_13_c0beek97\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case02\run_13\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case02\run_13\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case02\run_13\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=282/282 failed=0 overdue=2 time_cost_ms=4480 objective=min_overdue budget_s=5
  - best_score：[0.0, 2.0, 24.342068848333334, 363.7718940938889, 0.0]
  - metrics：overdue_count=2 tardiness_h=24.3421 makespan_h=363.7719 changeover=0 machine_util_avg=0.286077 operator_util_avg=0.174825 machine_load_cv=0.566962 operator_load_cv=0.419166
- **sanity：通过**

### run_14
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case02_14_x6h5rxgf`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case02_14_x6h5rxgf\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case02\run_14\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case02\run_14\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case02\run_14\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=238/238 failed=0 overdue=0 time_cost_ms=3469 objective=min_overdue budget_s=5
  - best_score：[0.0, 0.0, 0.0, 196.13645621166668, 0.0]
  - metrics：overdue_count=0 tardiness_h=0.0 makespan_h=196.1365 changeover=0 machine_util_avg=0.247522 operator_util_avg=0.192517 machine_load_cv=0.778593 operator_load_cv=0.683912
- **sanity：通过**

### run_15
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case02_15_nin4jqgy`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case02_15_nin4jqgy\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case02\run_15\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case02\run_15\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case02\run_15\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=244/244 failed=0 overdue=0 time_cost_ms=4095 objective=min_overdue budget_s=5
  - best_score：[0.0, 0.0, 0.0, 338.5684055958333, 0.0]
  - metrics：overdue_count=0 tardiness_h=0.0 makespan_h=338.5684 changeover=0 machine_util_avg=0.173288 operator_util_avg=0.125153 machine_load_cv=0.654557 operator_load_cv=0.563481
- **sanity：通过**

### run_16
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case02_16_44ap3qki`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case02_16_44ap3qki\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case02\run_16\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case02\run_16\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case02\run_16\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=248/248 failed=0 overdue=0 time_cost_ms=3898 objective=min_overdue budget_s=5
  - best_score：[0.0, 0.0, 0.0, 294.1458563536111, 0.0]
  - metrics：overdue_count=0 tardiness_h=0.0 makespan_h=294.1459 changeover=0 machine_util_avg=0.201864 operator_util_avg=0.16822 machine_load_cv=0.839267 operator_load_cv=0.602353
- **sanity：通过**

### run_17
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case02_17_y0hc08m9`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case02_17_y0hc08m9\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case02\run_17\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case02\run_17\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case02\run_17\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=266/266 failed=0 overdue=0 time_cost_ms=3955 objective=min_overdue budget_s=5
  - best_score：[0.0, 0.0, 0.0, 338.85368314833335, 0.0]
  - metrics：overdue_count=0 tardiness_h=0.0 makespan_h=338.8537 changeover=0 machine_util_avg=0.191956 operator_util_avg=0.149299 machine_load_cv=0.629712 operator_load_cv=0.525354
- **sanity：通过**

### run_18
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case02_18_h0gqv3y0`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case02_18_h0gqv3y0\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case02\run_18\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case02\run_18\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case02\run_18\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=278/278 failed=0 overdue=2 time_cost_ms=5168 objective=min_overdue budget_s=5
  - best_score：[0.0, 2.0, 25.88124311861111, 294.59419665666667, 0.0]
  - metrics：overdue_count=2 tardiness_h=25.8812 makespan_h=294.5942 changeover=0 machine_util_avg=0.199195 operator_util_avg=0.15493 machine_load_cv=0.776169 operator_load_cv=0.437152
- **sanity：通过**

### run_19
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case02_19_4b9o1r0v`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case02_19_4b9o1r0v\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case02\run_19\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case02\run_19\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case02\run_19\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=248/248 failed=0 overdue=0 time_cost_ms=3451 objective=min_overdue budget_s=5
  - best_score：[0.0, 0.0, 0.0, 435.7119437938889, 0.0]
  - metrics：overdue_count=0 tardiness_h=0.0 makespan_h=435.7119 changeover=0 machine_util_avg=0.140925 operator_util_avg=0.101779 machine_load_cv=0.75876 operator_load_cv=0.472992
- **sanity：通过**

### run_20
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case02_20_ovg3ig80`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case02_20_ovg3ig80\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case02\run_20\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case02\run_20\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case02\run_20\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=266/266 failed=0 overdue=0 time_cost_ms=4328 objective=min_overdue budget_s=5
  - best_score：[0.0, 0.0, 0.0, 342.95081967194443, 0.0]
  - metrics：overdue_count=0 tardiness_h=0.0 makespan_h=342.9508 changeover=0 machine_util_avg=0.114731 operator_util_avg=0.094484 machine_load_cv=0.827593 operator_load_cv=0.463823
- **sanity：通过**

## Case03 - auto-assign+技能/主操+SGS 派工（greedy vs improve）

- 说明：内部工序缺省资源，开启 auto-assign；人机表含技能/主操；启用 SGS 派工并对比 greedy/improve。

### run_01
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case03_1_lriai24u`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case03_1_lriai24u\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case03\run_01\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case03\run_01\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case03\run_01\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=342/342 failed=0 overdue=6 time_cost_ms=9545 objective=min_tardiness budget_s=5
  - best_score：[0.0, 297.2902676077778, 6.0, 775.6238624875, 0.0]
  - metrics：overdue_count=6 tardiness_h=297.2903 makespan_h=775.6239 changeover=0 machine_util_avg=0.272029 operator_util_avg=0.210204 machine_load_cv=0.867058 operator_load_cv=0.252329
- 排产：algo=improve version=2 result_status=success ops=342/342 failed=0 overdue=13 time_cost_ms=19301 objective=min_tardiness budget_s=15
  - best_score：[0.0, 907.8732386, 13.0, 795.0556117291667, 0.0]
  - metrics：overdue_count=13 tardiness_h=907.8732 makespan_h=795.0556 changeover=0 machine_util_avg=0.277561 operator_util_avg=0.214479 machine_load_cv=0.734708 operator_load_cv=0.362383
- **sanity：通过**

### run_02
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case03_2_7bq7tg1i`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case03_2_7bq7tg1i\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case03\run_02\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case03\run_02\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case03\run_02\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=330/330 failed=0 overdue=0 time_cost_ms=8298 objective=min_tardiness budget_s=5
  - best_score：[0.0, 0.0, 0.0, 629.8348623852777, 0.0]
  - metrics：overdue_count=0 tardiness_h=0.0 makespan_h=629.8349 changeover=0 machine_util_avg=0.257889 operator_util_avg=0.196487 machine_load_cv=0.874441 operator_load_cv=0.322321
- 排产：algo=improve version=2 result_status=success ops=330/330 failed=0 overdue=0 time_cost_ms=17870 objective=min_tardiness budget_s=15
  - best_score：[0.0, 0.0, 0.0, 604.5725977075, 0.0]
  - metrics：overdue_count=0 tardiness_h=0.0 makespan_h=604.5726 changeover=0 machine_util_avg=0.352866 operator_util_avg=0.26885 machine_load_cv=0.82485 operator_load_cv=0.401306
- **sanity：通过**

### run_03
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case03_3_0pw0uypa`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case03_3_0pw0uypa\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case03\run_03\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case03\run_03\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case03\run_03\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=354/354 failed=0 overdue=1 time_cost_ms=11037 objective=min_tardiness budget_s=5
  - best_score：[0.0, 8.146944444444445, 1.0, 774.6746746747222, 0.0]
  - metrics：overdue_count=1 tardiness_h=8.1469 makespan_h=774.6747 changeover=0 machine_util_avg=0.26883 operator_util_avg=0.210389 machine_load_cv=0.965871 operator_load_cv=0.330021
- 排产：algo=improve version=2 result_status=success ops=354/354 failed=0 overdue=15 time_cost_ms=21198 objective=min_tardiness budget_s=15
  - best_score：[0.0, 901.1075596766667, 15.0, 774.6346346344444, 0.0]
  - metrics：overdue_count=15 tardiness_h=901.1076 makespan_h=774.6346 changeover=0 machine_util_avg=0.287251 operator_util_avg=0.224805 machine_load_cv=0.898675 operator_load_cv=0.485122
- **sanity：通过**

### run_04
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case03_4_jbzzpwyl`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case03_4_jbzzpwyl\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case03\run_04\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case03\run_04\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case03\run_04\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=360/360 failed=0 overdue=0 time_cost_ms=9824 objective=min_tardiness budget_s=5
  - best_score：[0.0, 0.0, 0.0, 628.6159600997222, 0.0]
  - metrics：overdue_count=0 tardiness_h=0.0 makespan_h=628.616 changeover=0 machine_util_avg=0.340755 operator_util_avg=0.263311 machine_load_cv=0.772192 operator_load_cv=0.440937
- 排产：algo=improve version=2 result_status=success ops=360/360 failed=0 overdue=7 time_cost_ms=21256 objective=min_tardiness budget_s=15
  - best_score：[0.0, 151.49582653055558, 7.0, 631.2500561247223, 0.0]
  - metrics：overdue_count=7 tardiness_h=151.4958 makespan_h=631.2501 changeover=0 machine_util_avg=0.32444 operator_util_avg=0.250704 machine_load_cv=0.760473 operator_load_cv=0.545895
- **sanity：通过**

### run_05
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case03_5_104kd9gh`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case03_5_104kd9gh\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case03\run_05\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case03\run_05\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case03\run_05\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=348/348 failed=0 overdue=37 time_cost_ms=10634 objective=min_tardiness budget_s=5
  - best_score：[0.0, 6569.937929902223, 37.0, 1279.9979253111112, 0.0]
  - metrics：overdue_count=37 tardiness_h=6569.9379 makespan_h=1279.9979 changeover=0 machine_util_avg=0.163721 operator_util_avg=0.109148 machine_load_cv=1.559351 operator_load_cv=0.644863
- 排产：algo=improve version=2 result_status=success ops=348/348 failed=0 overdue=47 time_cost_ms=18678 objective=min_tardiness budget_s=15
  - best_score：[0.0, 9405.961263521109, 47.0, 1152.5444191344445, 0.0]
  - metrics：overdue_count=47 tardiness_h=9405.9613 makespan_h=1152.5444 changeover=0 machine_util_avg=0.209758 operator_util_avg=0.139839 machine_load_cv=1.214433 operator_load_cv=0.540708
- **sanity：通过**

### run_06
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case03_6_ezr0w7a0`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case03_6_ezr0w7a0\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case03\run_06\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case03\run_06\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case03\run_06\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=330/330 failed=0 overdue=0 time_cost_ms=8918 objective=min_tardiness budget_s=5
  - best_score：[0.0, 0.0, 0.0, 461.0615539858333, 0.0]
  - metrics：overdue_count=0 tardiness_h=0.0 makespan_h=461.0616 changeover=0 machine_util_avg=0.298201 operator_util_avg=0.220409 machine_load_cv=0.626885 operator_load_cv=0.341594
- 排产：algo=improve version=2 result_status=success ops=330/330 failed=0 overdue=0 time_cost_ms=17311 objective=min_tardiness budget_s=15
  - best_score：[0.0, 0.0, 0.0, 462.3814328961111, 0.0]
  - metrics：overdue_count=0 tardiness_h=0.0 makespan_h=462.3814 changeover=0 machine_util_avg=0.292627 operator_util_avg=0.21629 machine_load_cv=0.714344 operator_load_cv=0.498278
- **sanity：通过**

### run_07
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case03_7_vcxmt1dg`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case03_7_vcxmt1dg\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case03\run_07\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case03\run_07\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case03\run_07\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=390/390 failed=0 overdue=0 time_cost_ms=10693 objective=min_tardiness budget_s=5
  - best_score：[0.0, 0.0, 0.0, 606.9858156027778, 0.0]
  - metrics：overdue_count=0 tardiness_h=0.0 makespan_h=606.9858 changeover=0 machine_util_avg=0.39551 operator_util_avg=0.269666 machine_load_cv=0.639602 operator_load_cv=0.323436
- 排产：algo=improve version=2 result_status=success ops=390/390 failed=0 overdue=0 time_cost_ms=25838 objective=min_tardiness budget_s=15
  - best_score：[0.0, 0.0, 0.0, 627.3475177305555, 0.0]
  - metrics：overdue_count=0 tardiness_h=0.0 makespan_h=627.3475 changeover=0 machine_util_avg=0.388171 operator_util_avg=0.264662 machine_load_cv=0.661507 operator_load_cv=0.5379
- **sanity：通过**

### run_08
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case03_8_amy8sj66`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case03_8_amy8sj66\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case03\run_08\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case03\run_08\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case03\run_08\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=348/348 failed=0 overdue=0 time_cost_ms=10651 objective=min_tardiness budget_s=5
  - best_score：[0.0, 0.0, 0.0, 624.9084507041666, 0.0]
  - metrics：overdue_count=0 tardiness_h=0.0 makespan_h=624.9085 changeover=0 machine_util_avg=0.363239 operator_util_avg=0.259457 machine_load_cv=0.754595 operator_load_cv=0.323868
- 排产：algo=improve version=2 result_status=success ops=348/348 failed=0 overdue=3 time_cost_ms=19237 objective=min_tardiness budget_s=15
  - best_score：[0.0, 226.42749724333333, 3.0, 605.3655801341667, 0.0]
  - metrics：overdue_count=3 tardiness_h=226.4275 makespan_h=605.3656 changeover=0 machine_util_avg=0.380406 operator_util_avg=0.271718 machine_load_cv=0.827315 operator_load_cv=0.611952
- **sanity：通过**

### run_09
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case03_9_x1rbc75r`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case03_9_x1rbc75r\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case03\run_09\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case03\run_09\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case03\run_09\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=318/318 failed=0 overdue=0 time_cost_ms=8842 objective=min_tardiness budget_s=5
  - best_score：[0.0, 0.0, 0.0, 775.6279674758334, 0.0]
  - metrics：overdue_count=0 tardiness_h=0.0 makespan_h=775.628 changeover=0 machine_util_avg=0.264704 operator_util_avg=0.192512 machine_load_cv=0.993596 operator_load_cv=0.444309
- 排产：algo=improve version=2 result_status=success ops=318/318 failed=0 overdue=5 time_cost_ms=16754 objective=min_tardiness budget_s=15
  - best_score：[0.0, 201.5371711188889, 5.0, 867.0845990391666, 0.0]
  - metrics：overdue_count=5 tardiness_h=201.5372 makespan_h=867.0846 changeover=0 machine_util_avg=0.249029 operator_util_avg=0.181112 machine_load_cv=0.964965 operator_load_cv=0.630776
- **sanity：通过**

### run_10
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case03_10_y5wtddbx`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case03_10_y5wtddbx\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case03\run_10\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case03\run_10\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case03\run_10\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=336/336 failed=0 overdue=28 time_cost_ms=7902 objective=min_tardiness budget_s=5
  - best_score：[0.0, 7369.037641866666, 28.0, 1373.83, 0.0]
  - metrics：overdue_count=28 tardiness_h=7369.0376 makespan_h=1373.83 changeover=0 machine_util_avg=0.135852 operator_util_avg=0.092626 machine_load_cv=1.306615 operator_load_cv=0.554264
- 排产：algo=improve version=2 result_status=success ops=336/336 failed=0 overdue=34 time_cost_ms=17053 objective=min_tardiness budget_s=15
  - best_score：[0.0, 11574.79646110583, 34.0, 1369.6884483583333, 0.0]
  - metrics：overdue_count=34 tardiness_h=11574.7965 makespan_h=1369.6884 changeover=0 machine_util_avg=0.148059 operator_util_avg=0.100949 machine_load_cv=1.486266 operator_load_cv=0.771689
- **sanity：通过**

### run_11
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case03_11___xzmchx`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case03_11___xzmchx\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case03\run_11\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case03\run_11\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case03\run_11\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=336/336 failed=0 overdue=0 time_cost_ms=8083 objective=min_tardiness budget_s=5
  - best_score：[0.0, 0.0, 0.0, 775.9417040358334, 0.0]
  - metrics：overdue_count=0 tardiness_h=0.0 makespan_h=775.9417 changeover=0 machine_util_avg=0.323991 operator_util_avg=0.204626 machine_load_cv=0.904336 operator_load_cv=0.287134
- 排产：algo=improve version=2 result_status=success ops=336/336 failed=0 overdue=7 time_cost_ms=18275 objective=min_tardiness budget_s=15
  - best_score：[0.0, 176.3045422563889, 7.0, 823.8587443947222, 0.0]
  - metrics：overdue_count=7 tardiness_h=176.3045 makespan_h=823.8587 changeover=0 machine_util_avg=0.303804 operator_util_avg=0.191876 machine_load_cv=0.9077 operator_load_cv=0.47488
- **sanity：通过**

### run_12
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case03_12_8_w67x5p`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case03_12_8_w67x5p\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case03\run_12\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case03\run_12\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case03\run_12\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=276/276 failed=0 overdue=28 time_cost_ms=7903 objective=min_tardiness budget_s=5
  - best_score：[0.0, 3292.266223475278, 28.0, 1033.6692708333333, 0.0]
  - metrics：overdue_count=28 tardiness_h=3292.2662 makespan_h=1033.6693 changeover=0 machine_util_avg=0.18791 operator_util_avg=0.136662 machine_load_cv=1.171316 operator_load_cv=0.461103
- 排产：algo=improve version=2 result_status=success ops=276/276 failed=0 overdue=26 time_cost_ms=15171 objective=min_tardiness budget_s=15
  - best_score：[0.0, 4275.029708220556, 26.0, 962.9023354563889, 0.0]
  - metrics：overdue_count=26 tardiness_h=4275.0297 makespan_h=962.9023 changeover=0 machine_util_avg=0.194219 operator_util_avg=0.14125 machine_load_cv=1.129842 operator_load_cv=0.636606
- **sanity：通过**

### run_13
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case03_13_7bwc7pvp`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case03_13_7bwc7pvp\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case03\run_13\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case03\run_13\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case03\run_13\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=348/348 failed=0 overdue=0 time_cost_ms=10680 objective=min_tardiness budget_s=5
  - best_score：[0.0, 0.0, 0.0, 627.0893081761111, 0.0]
  - metrics：overdue_count=0 tardiness_h=0.0 makespan_h=627.0893 changeover=0 machine_util_avg=0.268301 operator_util_avg=0.229972 machine_load_cv=0.897549 operator_load_cv=0.18864
- 排产：algo=improve version=2 result_status=success ops=348/348 failed=0 overdue=2 time_cost_ms=19468 objective=min_tardiness budget_s=15
  - best_score：[0.0, 46.31446442833334, 2.0, 768.2805755394445, 0.0]
  - metrics：overdue_count=2 tardiness_h=46.3145 makespan_h=768.2806 changeover=0 machine_util_avg=0.244559 operator_util_avg=0.209622 machine_load_cv=0.843233 operator_load_cv=0.302996
- **sanity：通过**

### run_14
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case03_14_3hznfg2r`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case03_14_3hznfg2r\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case03\run_14\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case03\run_14\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case03\run_14\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=372/372 failed=0 overdue=11 time_cost_ms=10513 objective=min_tardiness budget_s=5
  - best_score：[0.0, 711.4373276675, 11.0, 1013.5717439294444, 0.0]
  - metrics：overdue_count=11 tardiness_h=711.4373 makespan_h=1013.5717 changeover=0 machine_util_avg=0.224011 operator_util_avg=0.160008 machine_load_cv=1.195927 operator_load_cv=0.404387
- 排产：algo=improve version=2 result_status=success ops=372/372 failed=0 overdue=19 time_cost_ms=22312 objective=min_tardiness budget_s=15
  - best_score：[0.0, 3434.008598651945, 19.0, 1037.871428571389, 0.0]
  - metrics：overdue_count=19 tardiness_h=3434.0086 makespan_h=1037.8714 changeover=0 machine_util_avg=0.210103 operator_util_avg=0.150074 machine_load_cv=1.235682 operator_load_cv=0.541187
- **sanity：通过**

### run_15
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case03_15_i39ctoic`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case03_15_i39ctoic\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case03\run_15\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case03\run_15\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case03\run_15\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=330/330 failed=0 overdue=49 time_cost_ms=8369 objective=min_tardiness budget_s=5
  - best_score：[0.0, 20511.96609149917, 49.0, 1710.104, 0.0]
  - metrics：overdue_count=49 tardiness_h=20511.9661 makespan_h=1710.104 changeover=0 machine_util_avg=0.119431 operator_util_avg=0.086256 machine_load_cv=1.985264 operator_load_cv=0.912576
- 排产：algo=improve version=2 result_status=success ops=330/330 failed=0 overdue=50 time_cost_ms=15561 objective=min_tardiness budget_s=15
  - best_score：[0.0, 24205.850519859174, 50.0, 1708.6640000000002, 0.0]
  - metrics：overdue_count=50 tardiness_h=24205.8505 makespan_h=1708.664 changeover=0 machine_util_avg=0.120107 operator_util_avg=0.086744 machine_load_cv=1.813312 operator_load_cv=0.817783
- **sanity：通过**

### run_16
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case03_16_xwvr1cuv`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case03_16_xwvr1cuv\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case03\run_16\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case03\run_16\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case03\run_16\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=348/348 failed=0 overdue=0 time_cost_ms=8501 objective=min_tardiness budget_s=5
  - best_score：[0.0, 0.0, 0.0, 535.5340659341667, 0.0]
  - metrics：overdue_count=0 tardiness_h=0.0 makespan_h=535.5341 changeover=0 machine_util_avg=0.328856 operator_util_avg=0.254116 machine_load_cv=0.792461 operator_load_cv=0.360563
- 排产：algo=improve version=2 result_status=success ops=348/348 failed=0 overdue=0 time_cost_ms=19509 objective=min_tardiness budget_s=15
  - best_score：[0.0, 0.0, 0.0, 535.5340659341667, 0.0]
  - metrics：overdue_count=0 tardiness_h=0.0 makespan_h=535.5341 changeover=0 machine_util_avg=0.328782 operator_util_avg=0.254059 machine_load_cv=0.785266 operator_load_cv=0.46301
- **sanity：通过**

### run_17
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case03_17_da1cvap8`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case03_17_da1cvap8\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case03\run_17\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case03\run_17\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case03\run_17\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=348/348 failed=0 overdue=0 time_cost_ms=8928 objective=min_tardiness budget_s=5
  - best_score：[0.0, 0.0, 0.0, 463.6797235022222, 0.0]
  - metrics：overdue_count=0 tardiness_h=0.0 makespan_h=463.6797 changeover=0 machine_util_avg=0.380096 operator_util_avg=0.307697 machine_load_cv=0.578713 operator_load_cv=0.260818
- 排产：algo=improve version=2 result_status=success ops=348/348 failed=0 overdue=1 time_cost_ms=19437 objective=min_tardiness budget_s=15
  - best_score：[0.0, 12.48459396361111, 1.0, 630.6774595266668, 0.0]
  - metrics：overdue_count=1 tardiness_h=12.4846 makespan_h=630.6775 changeover=0 machine_util_avg=0.272709 operator_util_avg=0.220765 machine_load_cv=0.612305 operator_load_cv=0.395028
- **sanity：通过**

### run_18
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case03_18_9xly_ez1`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case03_18_9xly_ez1\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case03\run_18\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case03\run_18\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case03\run_18\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=300/300 failed=0 overdue=0 time_cost_ms=8052 objective=min_tardiness budget_s=5
  - best_score：[0.0, 0.0, 0.0, 702.2869565216666, 0.0]
  - metrics：overdue_count=0 tardiness_h=0.0 makespan_h=702.287 changeover=0 machine_util_avg=0.253556 operator_util_avg=0.165362 machine_load_cv=0.798791 operator_load_cv=0.375913
- 排产：algo=improve version=2 result_status=success ops=300/300 failed=0 overdue=1 time_cost_ms=22039 objective=min_tardiness budget_s=15
  - best_score：[0.0, 61.01190045388889, 1.0, 654.9968594502778, 0.0]
  - metrics：overdue_count=1 tardiness_h=61.0119 makespan_h=654.9969 changeover=0 machine_util_avg=0.28844 operator_util_avg=0.188113 machine_load_cv=0.97851 operator_load_cv=0.60479
- **sanity：通过**

### run_19
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case03_19_n75fb30f`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case03_19_n75fb30f\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case03\run_19\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case03\run_19\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case03\run_19\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=348/348 failed=0 overdue=0 time_cost_ms=8089 objective=min_tardiness budget_s=5
  - best_score：[0.0, 0.0, 0.0, 703.90310559, 0.0]
  - metrics：overdue_count=0 tardiness_h=0.0 makespan_h=703.9031 changeover=0 machine_util_avg=0.321257 operator_util_avg=0.22488 machine_load_cv=0.702519 operator_load_cv=0.211656
- 排产：algo=improve version=2 result_status=success ops=348/348 failed=0 overdue=1 time_cost_ms=19500 objective=min_tardiness budget_s=15
  - best_score：[0.0, 15.489253134166667, 1.0, 775.0931677019445, 0.0]
  - metrics：overdue_count=1 tardiness_h=15.4893 makespan_h=775.0932 changeover=0 machine_util_avg=0.299804 operator_util_avg=0.209863 machine_load_cv=0.702202 operator_load_cv=0.343961
- **sanity：通过**

### run_20
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case03_20_h_a2y2za`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case03_20_h_a2y2za\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case03\run_20\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case03\run_20\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case03\run_20\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=330/330 failed=0 overdue=0 time_cost_ms=9020 objective=min_tardiness budget_s=5
  - best_score：[0.0, 0.0, 0.0, 606.5593220338889, 0.0]
  - metrics：overdue_count=0 tardiness_h=0.0 makespan_h=606.5593 changeover=0 machine_util_avg=0.27018 operator_util_avg=0.24174 machine_load_cv=0.851394 operator_load_cv=0.312172
- 排产：algo=improve version=2 result_status=success ops=330/330 failed=0 overdue=0 time_cost_ms=18306 objective=min_tardiness budget_s=15
  - best_score：[0.0, 0.0, 0.0, 605.531779661111, 0.0]
  - metrics：overdue_count=0 tardiness_h=0.0 makespan_h=605.5318 changeover=0 machine_util_avg=0.244283 operator_util_avg=0.218569 machine_load_cv=0.826511 operator_load_cv=0.454658
- **sanity：通过**

## Case04 - 冻结窗口插单回归

- 说明：先排产得到 V1；再导入特急插单，开启 freeze_window，验证窗口内排程不被破坏。

### run_01
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case04_1_7n0z43p7`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case04_1_7n0z43p7\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case04\run_01\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case04\run_01\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case04\run_01\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=42/42 failed=0 overdue=0 time_cost_ms=363 objective=min_overdue budget_s=5
  - best_score：[0.0, 0.0, 0.0, 174.06912677222223, 0.0]
  - metrics：overdue_count=0 tardiness_h=0.0 makespan_h=174.0691 changeover=0 machine_util_avg=0.282895 operator_util_avg=0.141447 machine_load_cv=0.779913 operator_load_cv=0.714921
- 排产：algo=greedy+freeze version=2 result_status=success ops=77/77 failed=0 overdue=5 time_cost_ms=386 objective=min_overdue budget_s=5
  - best_score：[0.0, 5.0, 210.89645704472224, 317.3170887838889, 0.0]
  - metrics：overdue_count=5 tardiness_h=210.8965 makespan_h=317.3171 changeover=0 machine_util_avg=0.335621 operator_util_avg=0.16781 machine_load_cv=0.70463 operator_load_cv=0.693611
- **sanity：通过**

### run_02
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case04_2_msvp_z6h`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case04_2_msvp_z6h\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case04\run_02\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case04\run_02\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case04\run_02\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=35/35 failed=0 overdue=0 time_cost_ms=506 objective=min_overdue budget_s=5
  - best_score：[0.0, 0.0, 0.0, 170.92427441833334, 0.0]
  - metrics：overdue_count=0 tardiness_h=0.0 makespan_h=170.9243 changeover=0 machine_util_avg=0.309136 operator_util_avg=0.200029 machine_load_cv=0.718542 operator_load_cv=0.729558
- 排产：algo=greedy+freeze version=2 result_status=success ops=70/70 failed=0 overdue=5 time_cost_ms=544 objective=min_overdue budget_s=5
  - best_score：[0.0, 5.0, 132.3731183008333, 265.8939742091667, 0.0]
  - metrics：overdue_count=5 tardiness_h=132.3731 makespan_h=265.894 changeover=0 machine_util_avg=0.358035 operator_util_avg=0.23167 machine_load_cv=0.461847 operator_load_cv=0.551094
- **sanity：通过**

### run_03
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case04_3_g6ocit_1`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case04_3_g6ocit_1\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case04\run_03\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case04\run_03\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case04\run_03\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=35/35 failed=0 overdue=0 time_cost_ms=328 objective=min_overdue budget_s=5
  - best_score：[0.0, 0.0, 0.0, 291.9570432441667, 0.0]
  - metrics：overdue_count=0 tardiness_h=0.0 makespan_h=291.957 changeover=0 machine_util_avg=0.219723 operator_util_avg=0.151059 machine_load_cv=0.652985 operator_load_cv=0.920116
- 排产：algo=greedy+freeze version=2 result_status=success ops=70/70 failed=0 overdue=6 time_cost_ms=408 objective=min_overdue budget_s=5
  - best_score：[0.0, 6.0, 364.85712197583337, 318.89140182833336, 0.0]
  - metrics：overdue_count=6 tardiness_h=364.8571 makespan_h=318.8914 changeover=0 machine_util_avg=0.283737 operator_util_avg=0.195069 machine_load_cv=0.419503 operator_load_cv=0.526196
- **sanity：通过**

### run_04
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case04_4_1xr7c7i3`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case04_4_1xr7c7i3\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case04\run_04\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case04\run_04\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case04\run_04\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=35/35 failed=0 overdue=0 time_cost_ms=339 objective=min_overdue budget_s=5
  - best_score：[0.0, 0.0, 0.0, 175.65588203555555, 0.0]
  - metrics：overdue_count=0 tardiness_h=0.0 makespan_h=175.6559 changeover=0 machine_util_avg=0.332599 operator_util_avg=0.195647 machine_load_cv=0.59612 operator_load_cv=0.742624
- 排产：algo=greedy+freeze version=2 result_status=success ops=70/70 failed=0 overdue=5 time_cost_ms=464 objective=min_overdue budget_s=5
  - best_score：[0.0, 5.0, 322.5559296122222, 271.3211681302778, 0.0]
  - metrics：overdue_count=5 tardiness_h=322.5559 makespan_h=271.3212 changeover=0 machine_util_avg=0.418726 operator_util_avg=0.246309 machine_load_cv=0.398334 operator_load_cv=0.372295
- **sanity：通过**

### run_05
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case04_5_mme3m5gw`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case04_5_mme3m5gw\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case04\run_05\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case04\run_05\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case04\run_05\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=35/35 failed=0 overdue=0 time_cost_ms=308 objective=min_overdue budget_s=5
  - best_score：[0.0, 0.0, 0.0, 175.5596239427778, 0.0]
  - metrics：overdue_count=0 tardiness_h=0.0 makespan_h=175.5596 changeover=0 machine_util_avg=0.20887 operator_util_avg=0.116039 machine_load_cv=0.858483 operator_load_cv=0.957485
- 排产：algo=greedy+freeze version=2 result_status=success ops=70/70 failed=0 overdue=5 time_cost_ms=440 objective=min_overdue budget_s=5
  - best_score：[0.0, 5.0, 128.26520762166666, 271.2102821905556, 0.0]
  - metrics：overdue_count=5 tardiness_h=128.2652 makespan_h=271.2103 changeover=0 machine_util_avg=0.311192 operator_util_avg=0.172885 machine_load_cv=0.538686 operator_load_cv=0.661653
- **sanity：通过**

### run_06
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case04_6_uyb1ame9`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case04_6_uyb1ame9\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case04\run_06\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case04\run_06\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case04\run_06\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=42/42 failed=0 overdue=0 time_cost_ms=402 objective=min_overdue budget_s=5
  - best_score：[0.0, 0.0, 0.0, 148.80770112027776, 0.0]
  - metrics：overdue_count=0 tardiness_h=0.0 makespan_h=148.8077 changeover=0 machine_util_avg=0.287315 operator_util_avg=0.215486 machine_load_cv=0.77412 operator_load_cv=0.957962
- 排产：algo=greedy+freeze version=2 result_status=success ops=77/77 failed=0 overdue=3 time_cost_ms=415 objective=min_overdue budget_s=5
  - best_score：[0.0, 3.0, 63.637361883333334, 175.33459890833333, 0.0]
  - metrics：overdue_count=3 tardiness_h=63.6374 makespan_h=175.3346 changeover=0 machine_util_avg=0.435047 operator_util_avg=0.326285 machine_load_cv=0.489853 operator_load_cv=0.568869
- **sanity：通过**

### run_07
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case04_7_1bqkg2v_`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case04_7_1bqkg2v_\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case04\run_07\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case04\run_07\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case04\run_07\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=35/35 failed=0 overdue=0 time_cost_ms=346 objective=min_overdue budget_s=5
  - best_score：[0.0, 0.0, 0.0, 127.81616384333333, 0.0]
  - metrics：overdue_count=0 tardiness_h=0.0 makespan_h=127.8162 changeover=0 machine_util_avg=0.34226 operator_util_avg=0.221463 machine_load_cv=0.747569 operator_load_cv=0.81551
- 排产：algo=greedy+freeze version=2 result_status=success ops=70/70 failed=0 overdue=5 time_cost_ms=487 objective=min_overdue budget_s=5
  - best_score：[0.0, 5.0, 231.1736758363889, 199.6165190486111, 0.0]
  - metrics：overdue_count=5 tardiness_h=231.1737 makespan_h=199.6165 changeover=0 machine_util_avg=0.420724 operator_util_avg=0.272233 machine_load_cv=0.333771 operator_load_cv=0.355355
- **sanity：通过**

### run_08
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case04_8_jnz623cz`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case04_8_jnz623cz\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case04\run_08\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case04\run_08\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case04\run_08\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=42/42 failed=0 overdue=0 time_cost_ms=441 objective=min_overdue budget_s=5
  - best_score：[0.0, 0.0, 0.0, 270.8984401183333, 0.0]
  - metrics：overdue_count=0 tardiness_h=0.0 makespan_h=270.8984 changeover=0 machine_util_avg=0.384763 operator_util_avg=0.216429 machine_load_cv=0.349658 operator_load_cv=0.539916
- 排产：algo=greedy+freeze version=2 result_status=success ops=77/77 failed=0 overdue=6 time_cost_ms=441 objective=min_overdue budget_s=5
  - best_score：[0.0, 6.0, 547.7996441022223, 360.2720508636111, 0.0]
  - metrics：overdue_count=6 tardiness_h=547.7996 makespan_h=360.2721 changeover=0 machine_util_avg=0.434447 operator_util_avg=0.244376 machine_load_cv=0.228112 operator_load_cv=0.380142
- **sanity：通过**

### run_09
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case04_9_zo4rymho`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case04_9_zo4rymho\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case04\run_09\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case04\run_09\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case04\run_09\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=42/42 failed=0 overdue=0 time_cost_ms=336 objective=min_overdue budget_s=5
  - best_score：[0.0, 0.0, 0.0, 289.9113688619445, 0.0]
  - metrics：overdue_count=0 tardiness_h=0.0 makespan_h=289.9114 changeover=0 machine_util_avg=0.292946 operator_util_avg=0.136708 machine_load_cv=0.535784 operator_load_cv=0.733966
- 排产：algo=greedy+freeze version=2 result_status=success ops=77/77 failed=0 overdue=5 time_cost_ms=307 objective=min_overdue budget_s=5
  - best_score：[0.0, 5.0, 449.7138524313889, 366.5472910838889, 0.0]
  - metrics：overdue_count=5 tardiness_h=449.7139 makespan_h=366.5473 changeover=0 machine_util_avg=0.407153 operator_util_avg=0.190005 machine_load_cv=0.560807 operator_load_cv=0.529164
- **sanity：通过**

### run_10
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case04_10_nss3026r`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case04_10_nss3026r\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case04\run_10\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case04\run_10\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case04\run_10\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=42/42 failed=0 overdue=0 time_cost_ms=324 objective=min_overdue budget_s=5
  - best_score：[0.0, 0.0, 0.0, 149.19017759777776, 0.0]
  - metrics：overdue_count=0 tardiness_h=0.0 makespan_h=149.1902 changeover=0 machine_util_avg=0.312063 operator_util_avg=0.16521 machine_load_cv=0.764162 operator_load_cv=0.85135
- 排产：algo=greedy+freeze version=2 result_status=success ops=77/77 failed=0 overdue=5 time_cost_ms=335 objective=min_overdue budget_s=5
  - best_score：[0.0, 5.0, 419.7657819844444, 291.61073508972225, 0.0]
  - metrics：overdue_count=5 tardiness_h=419.7658 makespan_h=291.6107 changeover=0 machine_util_avg=0.367237 operator_util_avg=0.19442 machine_load_cv=0.615048 operator_load_cv=0.557774
- **sanity：通过**

### run_11
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case04_11_0swuuven`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case04_11_0swuuven\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case04\run_11\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case04\run_11\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case04\run_11\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=42/42 failed=0 overdue=0 time_cost_ms=389 objective=min_overdue budget_s=5
  - best_score：[0.0, 0.0, 0.0, 170.86105365833333, 0.0]
  - metrics：overdue_count=0 tardiness_h=0.0 makespan_h=170.8611 changeover=0 machine_util_avg=0.34493 operator_util_avg=0.18261 machine_load_cv=0.539122 operator_load_cv=0.721855
- 排产：algo=greedy+freeze version=2 result_status=success ops=77/77 failed=0 overdue=5 time_cost_ms=404 objective=min_overdue budget_s=5
  - best_score：[0.0, 5.0, 112.70147786333334, 339.4772749555555, 0.0]
  - metrics：overdue_count=5 tardiness_h=112.7015 makespan_h=339.4773 changeover=0 machine_util_avg=0.271271 operator_util_avg=0.143614 machine_load_cv=0.357043 operator_load_cv=0.355886
- **sanity：通过**

### run_12
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case04_12_khcde8sp`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case04_12_khcde8sp\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case04\run_12\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case04\run_12\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case04\run_12\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=42/42 failed=0 overdue=0 time_cost_ms=406 objective=min_overdue budget_s=5
  - best_score：[0.0, 0.0, 0.0, 268.33531965027777, 0.0]
  - metrics：overdue_count=0 tardiness_h=0.0 makespan_h=268.3353 changeover=0 machine_util_avg=0.224862 operator_util_avg=0.137416 machine_load_cv=0.698321 operator_load_cv=0.875028
- 排产：algo=greedy+freeze version=2 result_status=success ops=77/77 failed=0 overdue=5 time_cost_ms=461 objective=min_overdue budget_s=5
  - best_score：[0.0, 5.0, 303.0931453208333, 336.688847525, 0.0]
  - metrics：overdue_count=5 tardiness_h=303.0931 makespan_h=336.6888 changeover=0 machine_util_avg=0.25109 operator_util_avg=0.153444 machine_load_cv=0.675777 operator_load_cv=0.48239
- **sanity：通过**

### run_13
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case04_13_pw71rwiv`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case04_13_pw71rwiv\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case04\run_13\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case04\run_13\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case04\run_13\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=42/42 failed=0 overdue=0 time_cost_ms=430 objective=min_overdue budget_s=5
  - best_score：[0.0, 0.0, 0.0, 196.2249915011111, 0.0]
  - metrics：overdue_count=0 tardiness_h=0.0 makespan_h=196.225 changeover=0 machine_util_avg=0.292818 operator_util_avg=0.172246 machine_load_cv=0.706627 operator_load_cv=0.619265
- 排产：algo=greedy+freeze version=2 result_status=success ops=77/77 failed=0 overdue=5 time_cost_ms=533 objective=min_overdue budget_s=5
  - best_score：[0.0, 5.0, 495.67213521194446, 362.45230934055553, 0.0]
  - metrics：overdue_count=5 tardiness_h=495.6721 makespan_h=362.4523 changeover=0 machine_util_avg=0.307231 operator_util_avg=0.180724 machine_load_cv=0.692334 operator_load_cv=0.548918
- **sanity：通过**

### run_14
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case04_14_5b7k0ta0`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case04_14_5b7k0ta0\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case04\run_14\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case04\run_14\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case04\run_14\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=35/35 failed=0 overdue=0 time_cost_ms=308 objective=min_overdue budget_s=5
  - best_score：[0.0, 0.0, 0.0, 171.56189152583335, 0.0]
  - metrics：overdue_count=0 tardiness_h=0.0 makespan_h=171.5619 changeover=0 machine_util_avg=0.245448 operator_util_avg=0.158819 machine_load_cv=0.7939 operator_load_cv=0.926546
- 排产：algo=greedy+freeze version=2 result_status=success ops=70/70 failed=0 overdue=5 time_cost_ms=377 objective=min_overdue budget_s=5
  - best_score：[0.0, 5.0, 297.9338070930556, 267.8840606697222, 0.0]
  - metrics：overdue_count=5 tardiness_h=297.9338 makespan_h=267.8841 changeover=0 machine_util_avg=0.293701 operator_util_avg=0.190042 machine_load_cv=0.610499 operator_load_cv=0.450069
- **sanity：通过**

### run_15
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case04_15_c33qigmr`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case04_15_c33qigmr\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case04\run_15\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case04\run_15\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case04\run_15\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=42/42 failed=0 overdue=0 time_cost_ms=403 objective=min_overdue budget_s=5
  - best_score：[0.0, 0.0, 0.0, 124.26634577055556, 0.0]
  - metrics：overdue_count=0 tardiness_h=0.0 makespan_h=124.2663 changeover=0 machine_util_avg=0.270654 operator_util_avg=0.175129 machine_load_cv=0.914301 operator_load_cv=1.022578
- 排产：algo=greedy+freeze version=2 result_status=success ops=77/77 failed=0 overdue=3 time_cost_ms=668 objective=min_overdue budget_s=5
  - best_score：[0.0, 3.0, 105.05197024833333, 171.5053935958333, 0.0]
  - metrics：overdue_count=3 tardiness_h=105.052 makespan_h=171.5054 changeover=0 machine_util_avg=0.457666 operator_util_avg=0.296137 machine_load_cv=0.42329 operator_load_cv=0.470764
- **sanity：通过**

### run_16
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case04_16_ws1mogux`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case04_16_ws1mogux\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case04\run_16\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case04\run_16\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case04\run_16\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=35/35 failed=0 overdue=0 time_cost_ms=425 objective=min_overdue budget_s=5
  - best_score：[0.0, 0.0, 0.0, 192.37378592, 0.0]
  - metrics：overdue_count=0 tardiness_h=0.0 makespan_h=192.3738 changeover=0 machine_util_avg=0.304086 operator_util_avg=0.209059 machine_load_cv=0.653115 operator_load_cv=0.875577
- 排产：algo=greedy+freeze version=2 result_status=success ops=70/70 failed=0 overdue=5 time_cost_ms=448 objective=min_overdue budget_s=5
  - best_score：[0.0, 5.0, 93.56150050166667, 267.04350504055554, 0.0]
  - metrics：overdue_count=5 tardiness_h=93.5615 makespan_h=267.0435 changeover=0 machine_util_avg=0.297517 operator_util_avg=0.204543 machine_load_cv=0.611907 operator_load_cv=0.581564
- **sanity：通过**

### run_17
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case04_17_vrkgtifb`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case04_17_vrkgtifb\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case04\run_17\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case04\run_17\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case04\run_17\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=42/42 failed=0 overdue=0 time_cost_ms=387 objective=min_overdue budget_s=5
  - best_score：[0.0, 0.0, 0.0, 169.62165031916666, 0.0]
  - metrics：overdue_count=0 tardiness_h=0.0 makespan_h=169.6217 changeover=0 machine_util_avg=0.305324 operator_util_avg=0.161642 machine_load_cv=0.761007 operator_load_cv=0.692682
- 排产：algo=greedy+freeze version=2 result_status=success ops=77/77 failed=0 overdue=5 time_cost_ms=435 objective=min_overdue budget_s=5
  - best_score：[0.0, 5.0, 395.3782804272222, 295.0660450297222, 0.0]
  - metrics：overdue_count=5 tardiness_h=395.3783 makespan_h=295.066 changeover=0 machine_util_avg=0.449399 operator_util_avg=0.237917 machine_load_cv=0.443014 operator_load_cv=0.466631
- **sanity：通过**

### run_18
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case04_18_2jp22ss0`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case04_18_2jp22ss0\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case04\run_18\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case04\run_18\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case04\run_18\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=42/42 failed=0 overdue=0 time_cost_ms=439 objective=min_overdue budget_s=5
  - best_score：[0.0, 0.0, 0.0, 192.5793439336111, 0.0]
  - metrics：overdue_count=0 tardiness_h=0.0 makespan_h=192.5793 changeover=0 machine_util_avg=0.305894 operator_util_avg=0.169941 machine_load_cv=0.698887 operator_load_cv=0.691091
- 排产：algo=greedy+freeze version=2 result_status=success ops=77/77 failed=0 overdue=7 time_cost_ms=434 objective=min_overdue budget_s=5
  - best_score：[0.0, 7.0, 444.61052283722216, 317.9700682725, 0.0]
  - metrics：overdue_count=7 tardiness_h=444.6105 makespan_h=317.9701 changeover=0 machine_util_avg=0.315141 operator_util_avg=0.175078 machine_load_cv=0.66883 operator_load_cv=0.435264
- **sanity：通过**

### run_19
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case04_19_jqyxii1v`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case04_19_jqyxii1v\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case04\run_19\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case04\run_19\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case04\run_19\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=42/42 failed=0 overdue=0 time_cost_ms=438 objective=min_overdue budget_s=5
  - best_score：[0.0, 0.0, 0.0, 409.25238056, 0.0]
  - metrics：overdue_count=0 tardiness_h=0.0 makespan_h=409.2524 changeover=0 machine_util_avg=0.280942 operator_util_avg=0.15803 machine_load_cv=0.484247 operator_load_cv=0.628628
- 排产：algo=greedy+freeze version=2 result_status=success ops=77/77 failed=0 overdue=5 time_cost_ms=418 objective=min_overdue budget_s=5
  - best_score：[0.0, 5.0, 609.6755799619444, 461.62216493444447, 0.0]
  - metrics：overdue_count=5 tardiness_h=609.6756 makespan_h=461.6222 changeover=0 machine_util_avg=0.332722 operator_util_avg=0.187156 machine_load_cv=0.708097 operator_load_cv=0.52257
- **sanity：通过**

### run_20
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case04_20_umqwx5th`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case04_20_umqwx5th\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case04\run_20\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case04\run_20\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case04\run_20\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=35/35 failed=0 overdue=0 time_cost_ms=277 objective=min_overdue budget_s=5
  - best_score：[0.0, 0.0, 0.0, 195.2218763538889, 0.0]
  - metrics：overdue_count=0 tardiness_h=0.0 makespan_h=195.2219 changeover=0 machine_util_avg=0.262967 operator_util_avg=0.147919 machine_load_cv=0.918446 operator_load_cv=0.829763
- 排产：algo=greedy+freeze version=2 result_status=success ops=70/70 failed=0 overdue=5 time_cost_ms=389 objective=min_overdue budget_s=5
  - best_score：[0.0, 5.0, 566.0916986116667, 319.0055708108333, 0.0]
  - metrics：overdue_count=5 tardiness_h=566.0917 makespan_h=319.0056 changeover=0 machine_util_avg=0.340079 operator_util_avg=0.191294 machine_load_cv=0.61212 operator_load_cv=0.419324
- **sanity：通过**

## Case05 - 资源极稀疏+密集停机+禁排日多

- 说明：极稀疏的人机资质+高比例停机+大量 allow_normal=no/holiday，验证不会出现全失败/冲突/死循环，且结果不离谱。

### run_01
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case05_1_uorvc7zg`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case05_1_uorvc7zg\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case05\run_01\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case05\run_01\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case05\run_01\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=528/528 failed=0 overdue=41 time_cost_ms=1063 objective=min_overdue budget_s=5
  - best_score：[0.0, 41.0, 29024.20435143223, 1800.65323496, 0.0]
  - metrics：overdue_count=41 tardiness_h=29024.2044 makespan_h=1800.6532 changeover=0 machine_util_avg=0.922726 operator_util_avg=0.922726 machine_load_cv=0.0 operator_load_cv=0.0
- **sanity：通过**

### run_02
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case05_2_pk6ilgv7`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case05_2_pk6ilgv7\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case05\run_02\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case05\run_02\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case05\run_02\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=480/480 failed=0 overdue=39 time_cost_ms=794 objective=min_overdue budget_s=5
  - best_score：[0.0, 39.0, 25884.800268164992, 1971.1602697088888, 0.0]
  - metrics：overdue_count=39 tardiness_h=25884.8003 makespan_h=1971.1603 changeover=0 machine_util_avg=0.9792 operator_util_avg=0.9792 machine_load_cv=0.0 operator_load_cv=0.0
- **sanity：通过**

### run_03
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case05_3_z74ezhuv`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case05_3_z74ezhuv\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case05\run_03\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case05\run_03\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case05\run_03\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=492/492 failed=0 overdue=39 time_cost_ms=1047 objective=min_overdue budget_s=5
  - best_score：[0.0, 39.0, 17210.1820370025, 1182.6959826277778, 0.0]
  - metrics：overdue_count=39 tardiness_h=17210.182 makespan_h=1182.696 changeover=0 machine_util_avg=0.974377 operator_util_avg=0.974377 machine_load_cv=0.0 operator_load_cv=0.0
- **sanity：通过**

### run_04
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case05_4_qf6q_k01`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case05_4_qf6q_k01\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case05\run_04\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case05\run_04\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case05\run_04\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=528/528 failed=0 overdue=44 time_cost_ms=1306 objective=min_overdue budget_s=5
  - best_score：[0.0, 44.0, 23496.777402287502, 1444.0714285713889, 0.0]
  - metrics：overdue_count=44 tardiness_h=23496.7774 makespan_h=1444.0714 changeover=0 machine_util_avg=0.961094 operator_util_avg=0.480547 machine_load_cv=0.0 operator_load_cv=0.01172
- **sanity：通过**

### run_05
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case05_5_iq145ykv`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case05_5_iq145ykv\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case05\run_05\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case05\run_05\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case05\run_05\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=432/432 failed=0 overdue=33 time_cost_ms=1059 objective=min_overdue budget_s=5
  - best_score：[0.0, 33.0, 13094.77777259083, 1111.6141935494443, 0.0]
  - metrics：overdue_count=33 tardiness_h=13094.7778 makespan_h=1111.6142 changeover=0 machine_util_avg=0.930489 operator_util_avg=0.465245 machine_load_cv=0.0 operator_load_cv=0.010102
- **sanity：通过**

### run_06
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case05_6_9vxgymq2`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case05_6_9vxgymq2\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case05\run_06\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case05\run_06\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case05\run_06\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=492/492 failed=0 overdue=36 time_cost_ms=1019 objective=min_overdue budget_s=5
  - best_score：[0.0, 36.0, 24434.644554862218, 1778.7960683758333, 0.0]
  - metrics：overdue_count=36 tardiness_h=24434.6446 makespan_h=1778.7961 changeover=0 machine_util_avg=0.834208 operator_util_avg=0.834208 machine_load_cv=0.0 operator_load_cv=0.0
- **sanity：通过**

### run_07
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case05_7_6gttvib8`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case05_7_6gttvib8\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case05\run_07\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case05\run_07\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case05\run_07\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=456/456 failed=0 overdue=36 time_cost_ms=798 objective=min_overdue budget_s=5
  - best_score：[0.0, 36.0, 10530.446336202778, 1322.021995453611, 0.0]
  - metrics：overdue_count=36 tardiness_h=10530.4463 makespan_h=1322.022 changeover=0 machine_util_avg=1.0 operator_util_avg=1.0 machine_load_cv=0.0 operator_load_cv=0.0
- **sanity：通过**

### run_08
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case05_8_jqpttynp`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case05_8_jqpttynp\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case05\run_08\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case05\run_08\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case05\run_08\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=492/492 failed=0 overdue=36 time_cost_ms=1230 objective=min_overdue budget_s=5
  - best_score：[0.0, 36.0, 26038.269503451396, 1781.2348087927776, 0.0]
  - metrics：overdue_count=36 tardiness_h=26038.2695 makespan_h=1781.2348 changeover=0 machine_util_avg=0.989154 operator_util_avg=0.989154 machine_load_cv=0.0 operator_load_cv=0.0
- **sanity：通过**

### run_09
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case05_9_h0_9phoz`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case05_9_h0_9phoz\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case05\run_09\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case05\run_09\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case05\run_09\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=564/564 failed=0 overdue=44 time_cost_ms=1041 objective=min_overdue budget_s=5
  - best_score：[0.0, 44.0, 30965.286989537773, 2019.5646387833333, 0.0]
  - metrics：overdue_count=44 tardiness_h=30965.287 makespan_h=2019.5646 changeover=0 machine_util_avg=0.976299 operator_util_avg=0.976299 machine_load_cv=0.0 operator_load_cv=0.0
- **sanity：通过**

### run_10
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case05_10_mk4smsgi`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case05_10_mk4smsgi\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case05\run_10\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case05\run_10\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case05\run_10\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=504/504 failed=0 overdue=37 time_cost_ms=994 objective=min_overdue budget_s=5
  - best_score：[0.0, 37.0, 21850.523138352775, 1325.2726762819445, 0.0]
  - metrics：overdue_count=37 tardiness_h=21850.5231 makespan_h=1325.2727 changeover=0 machine_util_avg=0.931233 operator_util_avg=0.931233 machine_load_cv=0.0 operator_load_cv=0.0
- **sanity：通过**

### run_11
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case05_11_dco9zntg`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case05_11_dco9zntg\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case05\run_11\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case05\run_11\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case05\run_11\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=492/492 failed=0 overdue=37 time_cost_ms=1412 objective=min_overdue budget_s=5
  - best_score：[0.0, 37.0, 18326.14318050306, 1542.7568069302777, 0.0]
  - metrics：overdue_count=37 tardiness_h=18326.1432 makespan_h=1542.7568 changeover=0 machine_util_avg=0.873221 operator_util_avg=0.436611 machine_load_cv=0.0 operator_load_cv=0.010274
- **sanity：通过**

### run_12
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case05_12_20nlvpke`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case05_12_20nlvpke\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case05\run_12\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case05\run_12\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case05\run_12\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=480/480 failed=0 overdue=38 time_cost_ms=883 objective=min_overdue budget_s=5
  - best_score：[0.0, 38.0, 15114.232758425831, 1183.0562567475001, 0.0]
  - metrics：overdue_count=38 tardiness_h=15114.2328 makespan_h=1183.0563 changeover=0 machine_util_avg=0.974329 operator_util_avg=0.974329 machine_load_cv=0.0 operator_load_cv=0.0
- **sanity：通过**

### run_13
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case05_13_kyowfhri`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case05_13_kyowfhri\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case05\run_13\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case05\run_13\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case05\run_13\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=468/468 failed=0 overdue=38 time_cost_ms=914 objective=min_overdue budget_s=5
  - best_score：[0.0, 38.0, 14645.411442008612, 1202.713186275, 0.0]
  - metrics：overdue_count=38 tardiness_h=14645.4114 makespan_h=1202.7132 changeover=0 machine_util_avg=1.0 operator_util_avg=1.0 machine_load_cv=0.0 operator_load_cv=0.0
- **sanity：通过**

### run_14
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case05_14_hn0ay01e`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case05_14_hn0ay01e\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case05\run_14\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case05\run_14\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case05\run_14\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=432/432 failed=0 overdue=34 time_cost_ms=691 objective=min_overdue budget_s=5
  - best_score：[0.0, 34.0, 15139.351398361388, 1464.6128519825002, 0.0]
  - metrics：overdue_count=34 tardiness_h=15139.3514 makespan_h=1464.6129 changeover=0 machine_util_avg=0.98633 operator_util_avg=0.98633 machine_load_cv=0.0 operator_load_cv=0.0
- **sanity：通过**

### run_15
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case05_15_q5clomhz`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case05_15_q5clomhz\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case05\run_15\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case05\run_15\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case05\run_15\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=456/456 failed=0 overdue=38 time_cost_ms=988 objective=min_overdue budget_s=5
  - best_score：[0.0, 38.0, 19950.004974767224, 1303.0923982172221, 0.0]
  - metrics：overdue_count=38 tardiness_h=19950.005 makespan_h=1303.0924 changeover=0 machine_util_avg=0.862191 operator_util_avg=0.862191 machine_load_cv=0.0 operator_load_cv=0.0
- **sanity：通过**

### run_16
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case05_16_twvo7ghr`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case05_16_twvo7ghr\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case05\run_16\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case05\run_16\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case05\run_16\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=444/444 failed=0 overdue=32 time_cost_ms=747 objective=min_overdue budget_s=5
  - best_score：[0.0, 32.0, 15726.29455268, 1374.7800593311113, 0.0]
  - metrics：overdue_count=32 tardiness_h=15726.2946 makespan_h=1374.7801 changeover=0 machine_util_avg=1.0 operator_util_avg=1.0 machine_load_cv=0.0 operator_load_cv=0.0
- **sanity：通过**

### run_17
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case05_17_wjz2_d_l`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case05_17_wjz2_d_l\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case05\run_17\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case05\run_17\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case05\run_17\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=444/444 failed=0 overdue=33 time_cost_ms=862 objective=min_overdue budget_s=5
  - best_score：[0.0, 33.0, 17029.724291591392, 1469.7681970069443, 0.0]
  - metrics：overdue_count=33 tardiness_h=17029.7243 makespan_h=1469.7682 changeover=0 machine_util_avg=0.980466 operator_util_avg=0.980466 machine_load_cv=0.0 operator_load_cv=0.0
- **sanity：通过**

### run_18
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case05_18_p2_14_nj`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case05_18_p2_14_nj\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case05\run_18\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case05\run_18\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case05\run_18\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=492/492 failed=0 overdue=35 time_cost_ms=952 objective=min_overdue budget_s=5
  - best_score：[0.0, 35.0, 11543.467358365, 1274.5622895625002, 0.0]
  - metrics：overdue_count=35 tardiness_h=11543.4674 makespan_h=1274.5623 changeover=0 machine_util_avg=0.982299 operator_util_avg=0.982299 machine_load_cv=0.0 operator_load_cv=0.0
- **sanity：通过**

### run_19
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case05_19_qvce_0tf`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case05_19_qvce_0tf\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case05\run_19\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case05\run_19\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case05\run_19\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=492/492 failed=0 overdue=41 time_cost_ms=927 objective=min_overdue budget_s=5
  - best_score：[0.0, 41.0, 21200.757554464166, 1445.7043275716665, 0.0]
  - metrics：overdue_count=41 tardiness_h=21200.7576 makespan_h=1445.7043 changeover=0 machine_util_avg=1.0 operator_util_avg=1.0 machine_load_cv=0.0 operator_load_cv=0.0
- **sanity：通过**

### run_20
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case05_20_phfc9awa`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case05_20_phfc9awa\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case05\run_20\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case05\run_20\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case05\run_20\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=516/516 failed=0 overdue=39 time_cost_ms=1460 objective=min_overdue budget_s=5
  - best_score：[0.0, 39.0, 14769.65334376556, 1375.9773284322223, 0.0]
  - metrics：overdue_count=39 tardiness_h=14769.6533 makespan_h=1375.9773 changeover=0 machine_util_avg=0.980171 operator_util_avg=0.490086 machine_load_cv=0.0 operator_load_cv=0.201344
- **sanity：通过**

## Case06 - 超紧交期+高负荷+多外协merged

- 说明：due_date 极短（1~5天）+高负荷+多段连续外协并大量 merged(total_days)，验证超期/外协一致性/导出报表可用。

### run_01
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case06_1_1rq7f6w7`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case06_1_1rq7f6w7\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case06\run_01\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case06\run_01\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case06\run_01\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=744/744 failed=0 overdue=62 time_cost_ms=11211 objective=min_overdue budget_s=5
  - best_score：[0.0, 62.0, 97286.15771046527, 2786.2844, 0.0]
  - metrics：overdue_count=62 tardiness_h=97286.1577 makespan_h=2786.2844 changeover=0 machine_util_avg=0.176833 operator_util_avg=0.120568 machine_load_cv=0.969704 operator_load_cv=0.330373
- **sanity：通过**

### run_02
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case06_2_2tu1kkfs`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case06_2_2tu1kkfs\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case06\run_02\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case06\run_02\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case06\run_02\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=684/684 failed=0 overdue=57 time_cost_ms=12770 objective=min_overdue budget_s=5
  - best_score：[0.0, 57.0, 53285.67866719834, 1615.9000750183332, 0.0]
  - metrics：overdue_count=57 tardiness_h=53285.6787 makespan_h=1615.9001 changeover=0 machine_util_avg=0.310813 operator_util_avg=0.24865 machine_load_cv=0.274985 operator_load_cv=0.121776
- **sanity：通过**

### run_03
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case06_3_wp9maot6`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case06_3_wp9maot6\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case06\run_03\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case06\run_03\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case06\run_03\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=720/720 failed=0 overdue=60 time_cost_ms=9492 objective=min_overdue budget_s=5
  - best_score：[0.0, 60.0, 87043.52031195944, 2667.926, 0.0]
  - metrics：overdue_count=60 tardiness_h=87043.5203 makespan_h=2667.926 changeover=0 machine_util_avg=0.209087 operator_util_avg=0.125452 machine_load_cv=0.926131 operator_load_cv=0.353196
- **sanity：通过**

### run_04
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case06_4_xsb9seoi`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case06_4_xsb9seoi\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case06\run_04\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case06\run_04\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case06\run_04\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=780/780 failed=0 overdue=65 time_cost_ms=13940 objective=min_overdue budget_s=5
  - best_score：[0.0, 65.0, 52887.55321240833, 1351.1182574213888, 0.0]
  - metrics：overdue_count=65 tardiness_h=52887.5532 makespan_h=1351.1183 changeover=0 machine_util_avg=0.38531 operator_util_avg=0.268042 machine_load_cv=0.461299 operator_load_cv=0.191884
- **sanity：通过**

### run_05
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case06_5_58m5gbaf`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case06_5_58m5gbaf\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case06\run_05\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case06\run_05\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case06\run_05\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=708/708 failed=0 overdue=59 time_cost_ms=11421 objective=min_overdue budget_s=5
  - best_score：[0.0, 59.0, 68374.4143815578, 2022.337590018611, 0.0]
  - metrics：overdue_count=59 tardiness_h=68374.4144 makespan_h=2022.3376 changeover=0 machine_util_avg=0.299481 operator_util_avg=0.182293 machine_load_cv=0.574859 operator_load_cv=0.249058
- **sanity：通过**

### run_06
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case06_6_mos9r33g`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case06_6_mos9r33g\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case06\run_06\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case06\run_06\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case06\run_06\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=732/732 failed=0 overdue=61 time_cost_ms=15010 objective=min_overdue budget_s=5
  - best_score：[0.0, 61.0, 56984.49355472332, 1681.0602179866667, 0.0]
  - metrics：overdue_count=61 tardiness_h=56984.4936 makespan_h=1681.0602 changeover=0 machine_util_avg=0.33069 operator_util_avg=0.270565 machine_load_cv=0.33771 operator_load_cv=0.136038
- **sanity：通过**

### run_07
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case06_7_ic28up9b`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case06_7_ic28up9b\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case06\run_07\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case06\run_07\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case06\run_07\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=696/696 failed=0 overdue=58 time_cost_ms=11620 objective=min_overdue budget_s=5
  - best_score：[0.0, 58.0, 61862.92741291306, 1855.491966068889, 0.0]
  - metrics：overdue_count=58 tardiness_h=61862.9274 makespan_h=1855.492 changeover=0 machine_util_avg=0.287996 operator_util_avg=0.196361 machine_load_cv=0.620198 operator_load_cv=0.134976
- **sanity：通过**

### run_08
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case06_8_fc1_7kfs`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case06_8_fc1_7kfs\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case06\run_08\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case06\run_08\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case06\run_08\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=708/708 failed=0 overdue=59 time_cost_ms=13950 objective=min_overdue budget_s=5
  - best_score：[0.0, 59.0, 52845.123523851405, 1514.5102672961111, 0.0]
  - metrics：overdue_count=59 tardiness_h=52845.1235 makespan_h=1514.5103 changeover=0 machine_util_avg=0.301367 operator_util_avg=0.271231 machine_load_cv=0.396244 operator_load_cv=0.135488
- **sanity：通过**

### run_09
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case06_9_5qappln8`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case06_9_5qappln8\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case06\run_09\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case06\run_09\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case06\run_09\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=780/780 failed=0 overdue=65 time_cost_ms=13029 objective=min_overdue budget_s=5
  - best_score：[0.0, 65.0, 73282.95720611056, 1944.7305335233332, 0.0]
  - metrics：overdue_count=65 tardiness_h=73282.9572 makespan_h=1944.7305 changeover=0 machine_util_avg=0.315048 operator_util_avg=0.200485 machine_load_cv=0.521765 operator_load_cv=0.120081
- **sanity：通过**

### run_10
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case06_10_knmzymst`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case06_10_knmzymst\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case06\run_10\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case06\run_10\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case06\run_10\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=780/780 failed=0 overdue=65 time_cost_ms=14656 objective=min_overdue budget_s=5
  - best_score：[0.0, 65.0, 52471.59489666862, 1447.5902171397222, 0.0]
  - metrics：overdue_count=65 tardiness_h=52471.5949 makespan_h=1447.5902 changeover=0 machine_util_avg=0.379373 operator_util_avg=0.270981 machine_load_cv=0.47694 operator_load_cv=0.178441
- **sanity：通过**

### run_11
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case06_11_z0u1m09h`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case06_11_z0u1m09h\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case06\run_11\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case06\run_11\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case06\run_11\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=708/708 failed=0 overdue=59 time_cost_ms=12878 objective=min_overdue budget_s=5
  - best_score：[0.0, 59.0, 44772.63374308499, 1324.2358787249998, 0.0]
  - metrics：overdue_count=59 tardiness_h=44772.6337 makespan_h=1324.2359 changeover=0 machine_util_avg=0.322932 operator_util_avg=0.25273 machine_load_cv=0.443651 operator_load_cv=0.189241
- **sanity：通过**

### run_12
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case06_12_mgxom8x_`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case06_12_mgxom8x_\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case06\run_12\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case06\run_12\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case06\run_12\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=780/780 failed=0 overdue=65 time_cost_ms=13772 objective=min_overdue budget_s=5
  - best_score：[0.0, 65.0, 69246.9124002025, 1849.7165129694442, 0.0]
  - metrics：overdue_count=65 tardiness_h=69246.9124 makespan_h=1849.7165 changeover=0 machine_util_avg=0.299221 operator_util_avg=0.208154 machine_load_cv=0.667442 operator_load_cv=0.098036
- **sanity：通过**

### run_13
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case06_13_9to6v960`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case06_13_9to6v960\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case06\run_13\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case06\run_13\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case06\run_13\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=768/768 failed=0 overdue=64 time_cost_ms=12417 objective=min_overdue budget_s=5
  - best_score：[0.0, 64.0, 106296.16335172055, 2981.9132, 0.0]
  - metrics：overdue_count=64 tardiness_h=106296.1634 makespan_h=2981.9132 changeover=0 machine_util_avg=0.20896 operator_util_avg=0.123476 machine_load_cv=0.893459 operator_load_cv=0.256678
- **sanity：通过**

### run_14
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case06_14_9tgza81t`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case06_14_9tgza81t\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case06\run_14\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case06\run_14\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case06\run_14\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=684/684 failed=0 overdue=57 time_cost_ms=11655 objective=min_overdue budget_s=5
  - best_score：[0.0, 57.0, 53043.69950911861, 2040.2894768583333, 0.0]
  - metrics：overdue_count=57 tardiness_h=53043.6995 makespan_h=2040.2895 changeover=0 machine_util_avg=0.247528 operator_util_avg=0.161432 machine_load_cv=0.66164 operator_load_cv=0.218313
- **sanity：通过**

### run_15
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case06_15_v6i6vayk`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case06_15_v6i6vayk\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case06\run_15\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case06\run_15\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case06\run_15\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=660/660 failed=0 overdue=55 time_cost_ms=10947 objective=min_overdue budget_s=5
  - best_score：[0.0, 55.0, 51068.358830911944, 1612.3996899430554, 0.0]
  - metrics：overdue_count=55 tardiness_h=51068.3588 makespan_h=1612.3997 changeover=0 machine_util_avg=0.291651 operator_util_avg=0.22221 machine_load_cv=0.544415 operator_load_cv=0.21667
- **sanity：通过**

### run_16
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case06_16_pre_kgsz`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case06_16_pre_kgsz\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case06\run_16\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case06\run_16\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case06\run_16\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=720/720 failed=0 overdue=60 time_cost_ms=14963 objective=min_overdue budget_s=5
  - best_score：[0.0, 60.0, 56047.15007291528, 1494.3898786236111, 0.0]
  - metrics：overdue_count=60 tardiness_h=56047.1501 makespan_h=1494.3899 changeover=0 machine_util_avg=0.318763 operator_util_avg=0.246317 machine_load_cv=0.499667 operator_load_cv=0.210529
- **sanity：通过**

### run_17
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case06_17_axalnc_j`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case06_17_axalnc_j\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case06\run_17\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case06\run_17\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case06\run_17\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=756/756 failed=0 overdue=63 time_cost_ms=16332 objective=min_overdue budget_s=5
  - best_score：[0.0, 63.0, 58798.33183357971, 1608.2620472869446, 0.0]
  - metrics：overdue_count=63 tardiness_h=58798.3318 makespan_h=1608.262 changeover=0 machine_util_avg=0.30358 operator_util_avg=0.224385 machine_load_cv=0.578264 operator_load_cv=0.132771
- **sanity：通过**

### run_18
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case06_18_cysrfsbs`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case06_18_cysrfsbs\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case06\run_18\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case06\run_18\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case06\run_18\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=804/804 failed=0 overdue=67 time_cost_ms=16067 objective=min_overdue budget_s=5
  - best_score：[0.0, 67.0, 75991.02929295221, 1998.7317651958333, 0.0]
  - metrics：overdue_count=67 tardiness_h=75991.0293 makespan_h=1998.7318 changeover=0 machine_util_avg=0.422569 operator_util_avg=0.2497 machine_load_cv=0.303632 operator_load_cv=0.127786
- **sanity：通过**

### run_19
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case06_19_b5arnhy3`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case06_19_b5arnhy3\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case06\run_19\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case06\run_19\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case06\run_19\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=792/792 failed=0 overdue=66 time_cost_ms=17554 objective=min_overdue budget_s=5
  - best_score：[0.0, 66.0, 73662.71822381942, 2112.2470359091667, 0.0]
  - metrics：overdue_count=66 tardiness_h=73662.7182 makespan_h=2112.247 changeover=0 machine_util_avg=0.266985 operator_util_avg=0.185729 machine_load_cv=0.565413 operator_load_cv=0.280143
- **sanity：通过**

### run_20
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case06_20_zz50gu4i`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case06_20_zz50gu4i\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case06\run_20\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case06\run_20\output`
- start_dt：`2026-01-29 08:00:00`
- 结果文件：`Case06\run_20\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=768/768 failed=0 overdue=64 time_cost_ms=16460 objective=min_overdue budget_s=5
  - best_score：[0.0, 64.0, 61831.1435714867, 1614.2395020188887, 0.0]
  - metrics：overdue_count=64 tardiness_h=61831.1436 makespan_h=1614.2395 changeover=0 machine_util_avg=0.357031 operator_util_avg=0.248369 machine_load_cv=0.567704 operator_load_cv=0.274422
- **sanity：通过**

