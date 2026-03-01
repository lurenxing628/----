## Phase3 / Batch3-Equ1 留痕：Equipment 停机计划状态枚举闭环（active/cancelled）

- 时间：2026-02-28 21:07
- 目标：把 `MachineDowntime.status` 的值域（`active/cancelled`）从“裸字符串”落地为 `core/models/enums.py` 枚举，并在 Model/Service/文档中统一口径，避免后续漂移与误判。
- Schema 变更：无
- 开发文档回填：已回填（新增枚举联动：补充 `MachineDowntimes.status` 值域说明）

### 影响域（实际改动文件）

- `core/models/enums.py`
  - 新增 `MachineDowntimeStatus`：`active` / `cancelled`
- `core/models/machine_downtime.py`
  - `status` 默认值与 `from_row()` 的默认兜底改为引用 `MachineDowntimeStatus.ACTIVE.value`（字符串语义不变）。
- `core/services/equipment/machine_downtime_service.py`
  - 创建停机记录时写入 `status` 改为 `MachineDowntimeStatus.ACTIVE.value`
  - `cancel()` 幂等判断改为与 `MachineDowntimeStatus.ACTIVE.value` 比较
  - 批量范围创建中对设备筛选的 `"active"` 改为 `MachineStatus.ACTIVE.value`（设备长期状态口径收敛）
- `开发文档/系统速查表.md`
  - 增加 `MachineDowntimes.status`：`active/cancelled` 的枚举说明

### 结果与证据

- **回归（Model 枚举/大小写规范化）**
  - `python tests/regression_model_enums_case_insensitive.py`：OK
- **QueryService（停机 active 过滤契约）**
  - `python -m pytest tests/test_query_services.py::test_machine_downtime_query_service_list_active_machine_ids_at -v`：PASS
- **Smoke（设备停机创建/取消链路）**
  - `python tests/smoke_phase4.py`：OK；产物：`evidence/Phase4/smoke_phase4_report.md`
- **Architecture Fitness**
  - `python -m pytest tests/test_architecture_fitness.py -v`：9 passed
- **Conformance**
  - `python tests/generate_conformance_report.py`：OK；产物：`evidence/Conformance/conformance_report.md`

### 下一步（按计划）

- Phase3（Process→Personnel→Equipment）已完成，进入 **Phase4（Route 边界 + 模板/前端契约核查）**：优先 `web/routes/scheduler_analysis.py` + `web/viewmodels/scheduler_analysis_vm.py` + `templates/scheduler/analysis.html`。

