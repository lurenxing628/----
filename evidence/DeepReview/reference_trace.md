# 引用链追踪报告（深度 Review 辅助）

> 说明：本报告基于 AST 提取“定义”，并用文本搜索定位“调用点/被调用者”。
> 由于 Python 动态特性与启发式匹配限制，可能存在漏报/误报，仅作为审查线索。
> 建议：对每条调用关系回到源码上下文手工核对。

## core/services/scheduler/run/schedule_candidate_runner.py（Service 层）

### `_CandidateTrialConfigService.__init__()` [私有]
- 位置：第 98-104 行
- 参数：base_cfg_svc, cfg
- 返回类型：Constant(value=None, kind=None)

### `_CandidateTrialConfigService.__getattr__()` [私有]
- 位置：第 106-107 行
- 参数：name
- 返回类型：Name(id='Any', ctx=Load())

### `run_candidate_comparison()` [公开]
- 位置：第 110-162 行
- 参数：无
- 返回类型：Name(id='CandidateComparisonOutcome', ctx=Load())
- **调用者**（1 处）：
  - `core/services/scheduler/run/schedule_orchestrator.py:243` [Service] `candidate_comparison = run_candidate_comparison(`
- **被调用者**（12 个）：`ensure_schedule_config_snapshot`, `generate_candidate_specs`, `_resolve_total_budget`, `now`, `_run_candidate_plans`, `select_candidate_plan`, `_comparison_outcome`, `make_cached_graph_preparation_fn`, `math.isfinite`, `float`, `bool`, `int`

### `_run_candidate_plans()` [私有]
- 位置：第 165-198 行
- 参数：specs
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_run_candidate_with_failure_capture()` [私有]
- 位置：第 201-230 行
- 参数：spec
- 返回类型：Name(id='CandidatePlan', ctx=Load())

### `_next_baseline_results()` [私有]
- 位置：第 233-236 行
- 参数：current, plan
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_comparison_outcome()` [私有]
- 位置：第 239-260 行
- 参数：无
- 返回类型：Name(id='CandidateComparisonOutcome', ctx=Load())

### `_count_candidates()` [私有]
- 位置：第 263-264 行
- 参数：candidates, status
- 返回类型：Name(id='int', ctx=Load())

### `_skipped_candidate_labels()` [私有]
- 位置：第 267-272 行
- 参数：candidates
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_baseline_missing_or_failed()` [私有]
- 位置：第 275-281 行
- 参数：candidates
- 返回类型：Name(id='bool', ctx=Load())

### `_run_single_candidate()` [私有]
- 位置：第 284-310 行
- 参数：spec
- 返回类型：Name(id='CandidatePlan', ctx=Load())

### `_run_candidate_optimization()` [私有]
- 位置：第 313-345 行
- 参数：spec
- 返回类型：Name(id='_CandidateRunArtifacts', ctx=Load())

### `_candidate_plan_from_artifacts()` [私有]
- 位置：第 348-386 行
- 参数：spec
- 返回类型：Name(id='CandidatePlan', ctx=Load())

### `_skipped_plan()` [私有]
- 位置：第 389-401 行
- 参数：spec
- 返回类型：Name(id='CandidatePlan', ctx=Load())

### `_failed_plan()` [私有]
- 位置：第 404-417 行
- 参数：spec, exc
- 返回类型：Name(id='CandidatePlan', ctx=Load())

---
- 分析函数/方法数：15
- 找到调用关系：1 处
- 跨层边界风险：0 项
