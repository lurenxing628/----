# 复杂排产 Excel Cases 全流程验证报告

- 生成时间：2026-04-11 23:38:40
- repeat：1
- seed：1000
- cases：Case01

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
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case01_1_nzay523u`
- DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_complex_case01_1_nzay523u\aps.db`
- 输入：`D:\Github\APS Test\evidence\ComplexExcelCases\Case01\run_01\input`
- 输出：`D:\Github\APS Test\evidence\ComplexExcelCases\Case01\run_01\output`
- start_dt：`2026-04-12 08:00:00`
- 结果文件：`Case01\run_01\result.json`（相对 --out 目录）

- 排产：algo=greedy version=1 result_status=success ops=300/300 failed=0 overdue=2 time_cost_ms=242 objective=min_overdue budget_s=5
  - best_score：[0.0, 2.0, 44.03919455583333, 44.03919455583333, 529.6446593255555, 0.0]
  - metrics：overdue_count=2 tardiness_h=44.0392 makespan_h=529.6447 changeover=0 machine_util_avg=0.268305 operator_util_avg=0.198313 machine_load_cv=0.518882 operator_load_cv=0.381049
- **sanity：通过**

