## Phase4 / Batch4-3 留痕：零件工序工时 Excel confirm 下沉到 Service

- 时间：2026-02-28 21:28
- 目标：将 `web/routes/process_excel_part_operation_hours.py` 的 confirm 中“逐行落库/导入级事务壳/统计与 errors_sample”下沉到 Service；Route 仅保留参数解析、preview 重算（防篡改）、错误拒绝、留痕与 flash/redirect，并保持模板变量契约不变。
- Schema 变更：无
- 开发文档回填：未触发（未新增/删除 Route；未变更 Excel 模板列名/用户可见文案）

### 判定标准（本阶段口径）

- 禁止留在 Route：事务协调、逐行落库、业务写入错误聚合/统计。
- 允许留在 Route：表单参数解析、文件读取、preview 重算、渲染/跳转与用户提示。

### 影响域（实际改动文件）

- `core/services/process/part_operation_hours_excel_import_service.py`
  - 新增 `PartOperationHoursExcelImportService.apply_preview_rows(...)`：导入级事务壳 + 逐行调用 `PartService.update_internal_hours` + 统计（new/update/skip/error）+ `errors_sample`。
  - 为避免 `process` 反向依赖 `scheduler` 触发 Service 包循环依赖门禁，落库阶段直接使用 preview 已校验/标准化后的数据，去除跨包工具依赖。
  - 将原单方法拆分为 `_apply_one/_apply_non_write_row/_parse_write_row`，满足复杂度门禁（≤15）。
- `web/routes/process_excel_part_operation_hours.py`
  - `excel_part_op_hours_confirm()` 改为调用上述 Service，移除 Route 内写入循环与事务壳（保留 preview 重算 + error_rows 拒绝导入）。
- `templates/process/excel_import_part_operation_hours.html`
  - 仅做契约核对：无需改动（继续使用 `preview_rows/raw_rows_json/mode/filename`）。

### 结果与证据

- **Web Smoke（Phase0~6）**
  - `python tests/smoke_web_phase0_6.py`：OK；产物：`evidence/Phase0_to_Phase6/web_smoke_report.md`
- **Architecture Fitness**
  - `python -m pytest -q tests/test_architecture_fitness.py`：9 passed
- **Conformance**
  - `python tests/generate_conformance_report.py`：OK；产物：`evidence/Conformance/conformance_report.md`

### 下一步（按计划）

- Phase4 的优先项（`scheduler_analysis`、`system_logs`、高复杂度 excel confirm）已闭环，进入 Phase5：Repository/SQL 一致性治理（优先 `batch_material_service` 分层修复）。

