## Phase2 / Batch2-4 留痕：Personnel Operators Excel 导入链路闭环

- 时间：2026-02-28 20:33
- 目标：选定 **Personnel/Operators** 作为示范域，完成 “Service + Route + Template 组件契约” 的端到端闭环；并将 `active/inactive` 等散落枚举值收敛到 `core/models/enums.py`，避免后续口径漂移。
- Schema 变更：无
- 开发文档回填：未触发（未新增/删除 Route；未变更模板列名；用户可见文案与行为保持一致）

### 影响域（实际改动文件）

- `core/services/personnel/operator_excel_import_service.py`
  - 导入校验中 `status in ("active","inactive")` 改为引用 `OperatorStatus.ACTIVE/INACTIVE.value`（字符串输出保持不变）。
- `web/routes/personnel_excel_operators.py`
  - 预览阶段的行级校验同样改为引用 `OperatorStatus.*.value`，确保 Route/Service 口径一致。
  - 模板兜底生成的示例行状态值改为 `OperatorStatus.ACTIVE.value`（Excel 内容保持 `"active"`）。

### 结果与证据

- **Complex Excel E2E（覆盖本链路：上传预览 → 确认导入）**
  - `python tests/run_complex_excel_cases_e2e.py --cases Case01 --repeat 1`
  - 报告：`evidence/ComplexExcelCases/complex_cases_report.md`
  - 结果：Case01 `sanity：通过`
- **Architecture Fitness**
  - `python -m pytest tests/test_architecture_fitness.py -v`：9 passed
- **Conformance**
  - `python tests/generate_conformance_report.py`：OK；产物：`evidence/Conformance/conformance_report.md`

### 下一步（按计划）

- Phase2 的 Excel 导入链路小闭环已完成：进入 **Phase3（Domain Services 闭环）**，按 `process → personnel → equipment` 依次清理服务缺口与跨层边界问题。

