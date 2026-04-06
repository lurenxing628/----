## Phase4 / Batch4-1 留痕：scheduler_analysis Route 边界清理（下沉到 ViewModel）

- 时间：2026-02-28 21:11
- 目标：将 `web/routes/scheduler_analysis.py` 中的“趋势/attempts/trace/条形计算/JSON 解析”等数据加工从 Route 下沉到 ViewModel，Route 仅保留参数解析 + QueryService 调用 + 模板渲染组装；同时保持 `templates/scheduler/analysis.html` 的变量契约不变，避免 UI 行为漂移。
- Schema 变更：无
- 开发文档回填：未触发（未新增/删除 Route；未变更模板列名/用户可见文案）

### 影响域（实际改动文件）

- `web/routes/scheduler_analysis.py`
  - 精简为薄 Route：仅解析 `version` 参数、读取 `versions/raw_hist/selected_item`，其余交给 ViewModel 计算。
- `web/viewmodels/scheduler_analysis_vm.py`
  - 新增 `build_analysis_context(...)` 及若干纯函数（趋势抽取/折线图/目标键推导/attempts 排序与 bar_pct 等），承接原先 Route 的数据加工逻辑。
  - 统一 JSON 解析为“失败即空 dict”的安全策略，避免单条坏数据导致页面 500。
- `templates/scheduler/analysis.html`
  - 仅做契约核对：无需改动（继续使用 `selected/selected_summary/selected_metrics/prev_metrics/objective_key/attempts/trace_chart/trend_rows/trend_charts`）。

### 结果与证据

- **Web Smoke（Phase0~6）**
  - `python tests/smoke_web_phase0_6.py`：OK；产物：`evidence/Phase0_to_Phase6/web_smoke_report.md`
- **Architecture Fitness**
  - `python -m pytest tests/test_architecture_fitness.py -v`：9 passed
- **Conformance**
  - `python tests/generate_conformance_report.py`：OK；产物：`evidence/Conformance/conformance_report.md`

### 下一步（按计划）

- 继续 Phase4：处理 `web/routes/system_logs.py` + `templates/system/logs.html` 的边界与契约；随后再评估高复杂度 Excel confirm 路由的最小拆分策略。

