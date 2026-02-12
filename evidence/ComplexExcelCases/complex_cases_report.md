# 复杂排产 Excel Cases 全流程验证报告

- 生成时间：2026-02-13 02:32:00
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
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case01_1_5czqbdq8`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case01_1_5czqbdq8\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case01\run_01\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case01\run_01\output`
- start_dt：`2026-02-14 08:00:00`
- 结果文件：`Case01\run_01\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=230/230 failed=0 overdue=1 time_cost_ms=869 objective=min_overdue budget_s=5
  - best_score：[0.0, 1.0, 81.77410493833332, 291.6859259258334, 0.0]
  - metrics：overdue_count=1 tardiness_h=81.7741 makespan_h=291.6859 changeover=0 machine_util_avg=0.365667 operator_util_avg=0.137125 machine_load_cv=0.005617 operator_load_cv=0.749607
- **sanity：通过**

## Case02 - 外协组 merged + separate 混用

- 说明：连续外协形成外协组，部分组设为 merged(total_days)，部分保持 separate(ext_days)。

### run_01
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case02_1_vmkoeted`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case02_1_vmkoeted\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case02\run_01\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case02\run_01\output`
- start_dt：`2026-02-14 08:00:00`
- 结果文件：`Case02\run_01\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=254/254 failed=0 overdue=2 time_cost_ms=8004 objective=min_overdue budget_s=5
  - best_score：[0.0, 2.0, 141.38233641277776, 340.1062355661111, 0.0]
  - metrics：overdue_count=2 tardiness_h=141.3823 makespan_h=340.1062 changeover=0 machine_util_avg=0.161322 operator_util_avg=0.107548 machine_load_cv=0.639608 operator_load_cv=0.515159
- **sanity：通过**

## Case03 - auto-assign+技能/主操+SGS 派工（greedy vs improve）

- 说明：内部工序缺省资源，开启 auto-assign；人机表含技能/主操；启用 SGS 派工并对比 greedy/improve。

### run_01
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case03_1_cgaooi8u`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case03_1_cgaooi8u\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case03\run_01\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case03\run_01\output`
- start_dt：`2026-02-14 08:00:00`
- 结果文件：`Case03\run_01\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=342/342 failed=0 overdue=7 time_cost_ms=1699201 objective=min_tardiness budget_s=5
  - best_score：[0.0, 532.6017410647223, 7.0, 696.8511749347222, 0.0]
  - metrics：overdue_count=7 tardiness_h=532.6017 makespan_h=696.8512 changeover=0 machine_util_avg=0.263937 operator_util_avg=0.203951 machine_load_cv=0.918827 operator_load_cv=0.291662
- 排产：algo=improve version=2 result_status=success ops=342/342 failed=0 overdue=12 time_cost_ms=19933 objective=min_tardiness budget_s=15
  - best_score：[0.0, 894.1588344427778, 12.0, 696.8511749347222, 0.0]
  - metrics：overdue_count=12 tardiness_h=894.1588 makespan_h=696.8512 changeover=0 machine_util_avg=0.259444 operator_util_avg=0.200479 machine_load_cv=0.973394 operator_load_cv=0.503502
- **sanity：通过**

## Case04 - 冻结窗口插单回归

- 说明：先排产得到 V1；再导入特急插单，开启 freeze_window，验证窗口内排程不被破坏。

### run_01
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case04_1_dbb1dmvw`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case04_1_dbb1dmvw\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case04\run_01\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case04\run_01\output`
- start_dt：`2026-02-14 08:00:00`
- 结果文件：`Case04\run_01\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=42/42 failed=0 overdue=0 time_cost_ms=1211 objective=min_overdue budget_s=5
  - best_score：[0.0, 0.0, 0.0, 172.19045423694442, 0.0]
  - metrics：overdue_count=0 tardiness_h=0.0 makespan_h=172.1905 changeover=0 machine_util_avg=0.326334 operator_util_avg=0.163167 machine_load_cv=0.633659 operator_load_cv=0.758213
- 排产：algo=greedy+freeze version=2 result_status=success ops=77/77 failed=0 overdue=5 time_cost_ms=1095 objective=min_overdue budget_s=5
  - best_score：[0.0, 5.0, 348.04368519888885, 270.46270659416666, 0.0]
  - metrics：overdue_count=5 tardiness_h=348.0437 makespan_h=270.4627 changeover=0 machine_util_avg=0.407578 operator_util_avg=0.203789 machine_load_cv=0.553797 operator_load_cv=0.618709
- **sanity：通过**

## Case05 - 资源极稀疏+密集停机+禁排日多

- 说明：极稀疏的人机资质+高比例停机+大量 allow_normal=no/holiday，验证不会出现全失败/冲突/死循环，且结果不离谱。

### run_01
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case05_1_7r3bthg1`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case05_1_7r3bthg1\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case05\run_01\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case05\run_01\output`
- start_dt：`2026-02-14 08:00:00`
- 结果文件：`Case05\run_01\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=444/444 failed=0 overdue=37 time_cost_ms=2059 objective=min_overdue budget_s=5
  - best_score：[0.0, 37.0, 23222.635979476945, 1634.1392115969443, 0.0]
  - metrics：overdue_count=37 tardiness_h=23222.636 makespan_h=1634.1392 changeover=0 machine_util_avg=0.882442 operator_util_avg=0.882442 machine_load_cv=0.0 operator_load_cv=0.0
- **sanity：通过**

## Case06 - 超紧交期+高负荷+多外协merged

- 说明：due_date 极短（1~5天）+高负荷+多段连续外协并大量 merged(total_days)，验证超期/外协一致性/导出报表可用。

### run_01
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case06_1_yn7w50dr`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case06_1_yn7w50dr\aps.db`
- 输入：`D:\Github\APS Test\evidence/ComplexExcelCases\Case06\run_01\input`
- 输出：`D:\Github\APS Test\evidence/ComplexExcelCases\Case06\run_01\output`
- start_dt：`2026-02-14 08:00:00`
- 结果文件：`Case06\run_01\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=756/756 failed=0 overdue=63 time_cost_ms=30271 objective=min_overdue budget_s=5
  - best_score：[0.0, 63.0, 100859.18652295943, 2714.157533990278, 0.0]
  - metrics：overdue_count=63 tardiness_h=100859.1865 makespan_h=2714.1575 changeover=0 machine_util_avg=0.177739 operator_util_avg=0.121185 machine_load_cv=0.985062 operator_load_cv=0.339861
- **sanity：通过**

