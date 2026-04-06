## Phase4 / Batch4-2 留痕：system_logs Route 边界清理（detail JSON 解析下沉）

- 时间：2026-02-28 21:14
- 目标：将 `web/routes/system_logs.py` 中对 `OperationLogs.detail` 的 JSON 解析与 view rows 构造下沉到 ViewModel，Route 仅保留参数解析/Service 调用/分页/渲染，模板契约保持不变。
- Schema 变更：无
- 开发文档回填：未触发（未新增/删除 Route；未变更模板列名/用户可见文案）

### 影响域（实际改动文件）

- `web/viewmodels/system_logs_vm.py`
  - 新增 `build_operation_log_view_rows(items)`：`to_dict()` + 安全解析 `detail_obj`（仅 dict 才展开；失败回退为 None）。
- `web/routes/system_logs.py`
  - `logs_page()` 改为直接调用 `build_operation_log_view_rows()`，移除 Route 内的 `json.loads` 循环。
- `templates/system/logs.html`
  - 仅做契约核对：继续使用 `r.detail_obj`/`r.detail` 的回退展示逻辑，无需改动。

### 结果与证据

- **Web Smoke（Phase0~6）**
  - `python tests/smoke_web_phase0_6.py`：OK；产物：`evidence/Phase0_to_Phase6/web_smoke_report.md`
- **Architecture Fitness**
  - `python -m pytest tests/test_architecture_fitness.py -v`：9 passed
- **Conformance**
  - `python tests/generate_conformance_report.py`：OK；产物：`evidence/Conformance/conformance_report.md`

### 下一步（按计划）

- 继续 Phase4：评估并拆分高复杂度 Excel confirm 路由（优先“confirm 中的数据清洗/差异计算/统计”下沉到对应 Service/Executor，Route 保持薄层）。

