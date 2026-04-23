# 静默回退修复实现 Final Review
- Date: 2026-04-01
- Overview: Workspace review
- Status: completed
- Overall decision: conditionally_accepted

## Review Scope
# 静默回退修复实现 Final Review

**审查日期**: 2026-04-01  
**审查范围**: 基于 audit/2026-04/20260401_core_静默回退_baseline_reconciliation.md 声明的修复批次  
**审查目标**: 验证修复是否真正解决了审计识别的问题，确认不存在新的静默回退隐患

### 修复批次声明的 4 个改进方向
1. Route / supplier / persistence 可观测性加固
2. Warning / summary pipeline 加固
3. Resource-pool 降级可观测性
4. Weighted-optimizer falsy-weight 修复

### 审查策略
- 逐文件读取关键修改点
- 沿调用链验证 warning 是否真正能传递到 result_summary
- 检查回归测试是否充分覆盖
- 检查 Pylance 诊断问题是否引入了新 bug

## Review Summary
<!-- LIMCODE_REVIEW_SUMMARY_START -->
- Current status: completed
- Reviewed modules: core/services/process/route_parser.py, core/services/process/part_service.py, core/services/process/supplier_service.py, core/services/scheduler/schedule_summary.py, core/services/scheduler/schedule_service.py, core/services/scheduler/resource_pool_builder.py, core/services/scheduler/schedule_optimizer.py, core/services/scheduler/schedule_optimizer_steps.py
- Current progress: 3 milestones recorded; latest: M3
- Total milestones: 3
- Completed milestones: 3
- Total findings: 5
- Findings by severity: high 0 / medium 1 / low 4
- Latest conclusion: Conditionally accepted. All 4 declared fix areas verified through source code and regression tests. Route/supplier/persistence chain: silent 1.0-day fallback now has warning + status degradation across all 3 layers. Warning pipeline: algo_warnings independent path ensures warnings survive summary merge failure. Resource pool: degradation observable in result_summary. Optimizer: 0.0 weights preserved. Residual: _build_overdue_items except:pass (F-003, medium), _extract_freeze_warnings broad except (F-004, low), Pylance type annotations (F-001/F-002/F-005, low). No high-severity findings. No new silent fallback introduced.
- Recommended next action: Phase 3: fix _build_overdue_items except:pass, improve _extract_freeze_warnings to per-item handling, address Pylance type annotations. Then proceed to Phase 4 strict mode.
- Overall decision: conditionally_accepted
<!-- LIMCODE_REVIEW_SUMMARY_END -->

## Review Findings
<!-- LIMCODE_REVIEW_FINDINGS_START -->
- [low] maintainability: SupplierService Pylance type annotation mismatch
  - ID: F-001
  - Description: supplier_service.py L146/L160 str|None vs str parameter type. Runtime safe.
  - Related Milestones: M1

- [low] maintainability: schedule_service.py Pylance diagnostics
  - ID: F-002
  - Description: schedule_service.py L308/L451 Pylance type narrowing issues. Runtime safe.
  - Related Milestones: M2

- [medium] maintainability: _build_overdue_items append failure still silent
  - ID: F-003
  - Description: _build_overdue_items L303-305 except:pass still swallows summary.warnings.append failure.
  - Related Milestones: M2
  - Recommendation: Add logger fallback in except block per Phase 3 plan.

- [low] maintainability: _extract_freeze_warnings broad except
  - ID: F-004
  - Description: _extract_freeze_warnings L346-347 broad except resets to []. Low risk since input pre-sanitized.
  - Related Milestones: M2

- [low] test: Test file Pylance type mismatch
  - ID: F-005
  - Description: regression_part_service_external_default_days_fallback.py L49: ExternalGroup type mismatch between test stub and route_parser import. Runtime safe.
  - Related Milestones: M3
<!-- LIMCODE_REVIEW_FINDINGS_END -->

## Review Milestones
<!-- LIMCODE_REVIEW_MILESTONES_START -->
### M1 · Route / Supplier / Persistence Chain
- Status: completed
- Recorded At: 2026-04-01T17:02:11.480Z
- Summary:
All 4 critical points fixed: RouteParser.parse warning added, _build_supplier_map or-1.0 split, _save_template_no_tx uses _coerce_external_default_days, SupplierService write-side logging added. Tests verified.
- Conclusion: All 4 critical points fixed: RouteParser.parse warning added, _build_supplier_map or-1.0 split, _save_template_no_tx uses _coerce_external_default_days, SupplierService write-side logging added. Tests verified.
- Findings:
  - [low] maintainability: SupplierService Pylance type annotation mismatch

### M2 · Warning Pipeline + Resource Pool + Optimizer
- Status: completed
- Recorded At: 2026-04-01T17:02:22.097Z
- Summary:
Warning pipeline: algo_warnings independent path confirmed. Resource pool: meta fields and algo.resource_pool structure added. Optimizer: _cfg_float preserves 0.0 weights. Residual: _build_overdue_items pass, _extract_freeze_warnings broad except.
- Conclusion: Warning pipeline: algo_warnings independent path confirmed. Resource pool: meta fields and algo.resource_pool structure added. Optimizer: _cfg_float preserves 0.0 weights. Residual: _build_overdue_items pass, _extract_freeze_warnings broad except.
- Findings:
  - [low] maintainability: schedule_service.py Pylance diagnostics
  - [medium] maintainability: _build_overdue_items append failure still silent
  - [low] maintainability: _extract_freeze_warnings broad except

### M3 · Regression Tests + Test Diagnostic
- Status: completed
- Recorded At: 2026-04-01T17:02:31.687Z
- Summary:
6 regression tests verified covering all 4 fix areas. Test assertions are well-targeted: checking status, warning text, persisted values, and pipeline transparency. One Pylance type mismatch in test file (not runtime).
- Conclusion: 6 regression tests verified covering all 4 fix areas. Test assertions are well-targeted: checking status, warning text, persisted values, and pipeline transparency. One Pylance type mismatch in test file (not runtime).
- Findings:
  - [low] test: Test file Pylance type mismatch
<!-- LIMCODE_REVIEW_MILESTONES_END -->

<!-- LIMCODE_REVIEW_METADATA_START -->
{
  "formatVersion": 3,
  "reviewRunId": "review-mngamtly-ohmlve",
  "createdAt": "2026-04-01T00:00:00.000Z",
  "finalizedAt": "2026-04-01T17:02:43.265Z",
  "status": "completed",
  "overallDecision": "conditionally_accepted",
  "latestConclusion": "Conditionally accepted. All 4 declared fix areas verified through source code and regression tests. Route/supplier/persistence chain: silent 1.0-day fallback now has warning + status degradation across all 3 layers. Warning pipeline: algo_warnings independent path ensures warnings survive summary merge failure. Resource pool: degradation observable in result_summary. Optimizer: 0.0 weights preserved. Residual: _build_overdue_items except:pass (F-003, medium), _extract_freeze_warnings broad except (F-004, low), Pylance type annotations (F-001/F-002/F-005, low). No high-severity findings. No new silent fallback introduced.",
  "recommendedNextAction": "Phase 3: fix _build_overdue_items except:pass, improve _extract_freeze_warnings to per-item handling, address Pylance type annotations. Then proceed to Phase 4 strict mode.",
  "reviewedModules": [
    "core/services/process/route_parser.py",
    "core/services/process/part_service.py",
    "core/services/process/supplier_service.py",
    "core/services/scheduler/schedule_summary.py",
    "core/services/scheduler/schedule_service.py",
    "core/services/scheduler/resource_pool_builder.py",
    "core/services/scheduler/schedule_optimizer.py",
    "core/services/scheduler/schedule_optimizer_steps.py"
  ],
  "milestones": [
    {
      "id": "M1",
      "title": "Route / Supplier / Persistence Chain",
      "summary": "All 4 critical points fixed: RouteParser.parse warning added, _build_supplier_map or-1.0 split, _save_template_no_tx uses _coerce_external_default_days, SupplierService write-side logging added. Tests verified.",
      "status": "completed",
      "conclusion": "All 4 critical points fixed: RouteParser.parse warning added, _build_supplier_map or-1.0 split, _save_template_no_tx uses _coerce_external_default_days, SupplierService write-side logging added. Tests verified.",
      "evidenceFiles": [],
      "reviewedModules": [],
      "recommendedNextAction": null,
      "recordedAt": "2026-04-01T17:02:11.480Z",
      "findingIds": [
        "F-001"
      ]
    },
    {
      "id": "M2",
      "title": "Warning Pipeline + Resource Pool + Optimizer",
      "summary": "Warning pipeline: algo_warnings independent path confirmed. Resource pool: meta fields and algo.resource_pool structure added. Optimizer: _cfg_float preserves 0.0 weights. Residual: _build_overdue_items pass, _extract_freeze_warnings broad except.",
      "status": "completed",
      "conclusion": "Warning pipeline: algo_warnings independent path confirmed. Resource pool: meta fields and algo.resource_pool structure added. Optimizer: _cfg_float preserves 0.0 weights. Residual: _build_overdue_items pass, _extract_freeze_warnings broad except.",
      "evidenceFiles": [],
      "reviewedModules": [],
      "recommendedNextAction": null,
      "recordedAt": "2026-04-01T17:02:22.097Z",
      "findingIds": [
        "F-002",
        "F-003",
        "F-004"
      ]
    },
    {
      "id": "M3",
      "title": "Regression Tests + Test Diagnostic",
      "summary": "6 regression tests verified covering all 4 fix areas. Test assertions are well-targeted: checking status, warning text, persisted values, and pipeline transparency. One Pylance type mismatch in test file (not runtime).",
      "status": "completed",
      "conclusion": "6 regression tests verified covering all 4 fix areas. Test assertions are well-targeted: checking status, warning text, persisted values, and pipeline transparency. One Pylance type mismatch in test file (not runtime).",
      "evidenceFiles": [],
      "reviewedModules": [],
      "recommendedNextAction": null,
      "recordedAt": "2026-04-01T17:02:31.687Z",
      "findingIds": [
        "F-005"
      ]
    }
  ],
  "findings": [
    {
      "id": "F-001",
      "severity": "low",
      "category": "maintainability",
      "title": "SupplierService Pylance type annotation mismatch",
      "description": "supplier_service.py L146/L160 str|None vs str parameter type. Runtime safe.",
      "evidenceFiles": [],
      "relatedMilestoneIds": [
        "M1"
      ],
      "recommendation": null
    },
    {
      "id": "F-002",
      "severity": "low",
      "category": "maintainability",
      "title": "schedule_service.py Pylance diagnostics",
      "description": "schedule_service.py L308/L451 Pylance type narrowing issues. Runtime safe.",
      "evidenceFiles": [],
      "relatedMilestoneIds": [
        "M2"
      ],
      "recommendation": null
    },
    {
      "id": "F-003",
      "severity": "medium",
      "category": "maintainability",
      "title": "_build_overdue_items append failure still silent",
      "description": "_build_overdue_items L303-305 except:pass still swallows summary.warnings.append failure.",
      "evidenceFiles": [],
      "relatedMilestoneIds": [
        "M2"
      ],
      "recommendation": "Add logger fallback in except block per Phase 3 plan."
    },
    {
      "id": "F-004",
      "severity": "low",
      "category": "maintainability",
      "title": "_extract_freeze_warnings broad except",
      "description": "_extract_freeze_warnings L346-347 broad except resets to []. Low risk since input pre-sanitized.",
      "evidenceFiles": [],
      "relatedMilestoneIds": [
        "M2"
      ],
      "recommendation": null
    },
    {
      "id": "F-005",
      "severity": "low",
      "category": "test",
      "title": "Test file Pylance type mismatch",
      "description": "regression_part_service_external_default_days_fallback.py L49: ExternalGroup type mismatch between test stub and route_parser import. Runtime safe.",
      "evidenceFiles": [],
      "relatedMilestoneIds": [
        "M3"
      ],
      "recommendation": null
    }
  ]
}
<!-- LIMCODE_REVIEW_METADATA_END -->
