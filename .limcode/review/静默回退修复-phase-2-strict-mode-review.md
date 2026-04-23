# 静默回退修复 Phase 2 Strict Mode Review
- Date: 2026-04-01
- Overview: Workspace review
- Status: completed
- Overall decision: conditionally_accepted

## Review Scope
# 静默回退修复 Phase 2 Review — Strict Mode + 补充修改

**审查日期**: 2026-04-01  
**审查范围**: 用户第二轮大量修改，重点包括 strict mode 贯通实现、ExternalGroupService CFM-063 修复、batch_template_ops 提取、web routes 变更  
**审查目标**: 深入引用链和函数变量，验证 strict mode 是否端到端生效，确认无新的静默回退

## Review Summary
<!-- LIMCODE_REVIEW_SUMMARY_START -->
- Current status: completed
- Reviewed modules: core/services/process/route_parser.py, core/services/process/part_service.py, core/services/process/external_group_service.py, core/services/scheduler/batch_service.py, core/services/scheduler/batch_template_ops.py, core/services/scheduler/batch_excel_import.py, web/routes/process_parts.py, web/routes/process_excel_routes.py, web/routes/scheduler_batches.py, web/routes/scheduler_excel_batches.py, templates/process/list.html, templates/process/detail.html, templates/scheduler/batches_manage.html, templates/scheduler/batch_detail.html, templates/components/excel_import.html
- Current progress: 2 milestones recorded; latest: M2
- Total milestones: 2
- Completed milestones: 2
- Total findings: 4
- Findings by severity: high 1 / medium 1 / low 2
- Latest conclusion: Conditionally accepted. Strict mode implementation is comprehensive across main UI paths (process parts, process Excel routes, scheduler batches create/generate-ops). Transaction safety verified. One high-severity finding: ExternalGroupService._apply_separate_mode compatible path (CFM-063) still has completely silent 1.0 day fallback with no logger/counter — this must be fixed before merge. One medium finding: batch Excel import path lacks strict_mode propagation (can be deferred). Regression tests for strict mode are thorough (4 tests covering route_parser, PartService, ExternalGroupService, and BatchService rejection paths).
- Recommended next action: MUST FIX before merge: Add logger.warning to ExternalGroupService._apply_separate_mode compatible fallback path (L131-138). SHOULD FIX: Propagate strict_mode to batch_excel_import.py and scheduler_excel_batches.py.
- Overall decision: conditionally_accepted
<!-- LIMCODE_REVIEW_SUMMARY_END -->

## Review Findings
<!-- LIMCODE_REVIEW_FINDINGS_START -->
- [high] javascript: CFM-063 ExternalGroupService compatible mode still completely silent
  - ID: F-006
  - Description: ExternalGroupService._apply_separate_mode L131-138: when strict_mode=False, dv=None/<=0 still silently falls back to 1.0 with NO logger.warning, NO counter, NO trace. The service has self.logger available but never calls it in the compatible fallback path. This is the original CFM-063 critical finding that was rated 'fatal' in the audit.
  - Related Milestones: M1
  - Recommendation: Add self.logger.warning() call before dv=1.0 in the compatible path. Example: if self.logger: self.logger.warning(f'...seq={seq} ext_days fallback to 1.0...')

- [low] javascript: route_parser strict mode logic verified correct
  - ID: F-008
  - Description: route_parser.parse() strict_mode verified correct. Unknown op type -> errors (not warnings). Missing supplier -> errors. Supplier with issue_messages -> errors via _strict_supplier_issue_messages. op.default_days NOT set when strict errors occur. ParseStatus.FAILED triggers BusinessError in _parse_route_or_raise. Transaction safety confirmed.
  - Related Milestones: M1

- [medium] javascript: Batch Excel import path lacks strict_mode propagation
  - ID: F-007
  - Description: batch_excel_import.py L79 calls create_batch_from_template_no_tx without strict_mode. scheduler_excel_batches.py route has no strict_mode support. The batch Excel import always runs in compatible mode regardless of any UI setting.
  - Related Milestones: M2
  - Recommendation: Add strict_mode parameter to import_from_preview_rows and batch_excel_import, and add checkbox to scheduler_excel_batches.py route. May be deferred but should be tracked.

- [low] javascript: _invoke_template_resolver introspection is defensive and correct
  - ID: F-009
  - Description: BatchService._invoke_template_resolver uses inspect.signature to check if resolver supports strict_mode, falling back to calling without it. This is appropriately defensive for backward compatibility with custom resolvers.
  - Related Milestones: M2
<!-- LIMCODE_REVIEW_FINDINGS_END -->

## Review Milestones
<!-- LIMCODE_REVIEW_MILESTONES_START -->
### M1 · Strict Mode Chain: RouteParser + PartService + ExternalGroupService
- Status: completed
- Recorded At: 2026-04-01T18:48:11.684Z
- Summary:
RouteParser strict mode: 3 rejection paths verified (unknown op type, missing supplier, invalid supplier days). PartService strict mode: pre-parse before create, reparse_and_save pass-through. ExternalGroupService: strict_mode gate added but compatible path still SILENT (F-006 HIGH). Transaction safety verified.
- Conclusion: RouteParser strict mode: 3 rejection paths verified (unknown op type, missing supplier, invalid supplier days). PartService strict mode: pre-parse before create, reparse_and_save pass-through. ExternalGroupService: strict_mode gate added but compatible path still SILENT (F-006 HIGH). Transaction safety verified.
- Findings:
  - [high] javascript: CFM-063 ExternalGroupService compatible mode still completely silent
  - [low] javascript: route_parser strict mode logic verified correct

### M2 · Strict Mode Caller Propagation: Web Routes + BatchService + batch_template_ops + Excel Import
- Status: completed
- Recorded At: 2026-04-01T18:48:25.563Z
- Summary:
Web routes: process_parts.py, process_excel_routes.py, scheduler_batches.py all pass strict_mode from form checkbox. BatchService: strict_mode propagated through create_batch_from_template -> _load_template_ops_with_fallback -> _invoke_template_resolver. batch_template_ops.py: clean extraction with strict_mode pass-through. Gap: batch_excel_import.py and scheduler_excel_batches.py lack strict_mode (F-007). Templates: checkbox and hidden field propagation verified in 5 templates.
- Conclusion: Web routes: process_parts.py, process_excel_routes.py, scheduler_batches.py all pass strict_mode from form checkbox. BatchService: strict_mode propagated through create_batch_from_template -> _load_template_ops_with_fallback -> _invoke_template_resolver. batch_template_ops.py: clean extraction with strict_mode pass-through. Gap: batch_excel_import.py and scheduler_excel_batches.py lack strict_mode (F-007). Templates: checkbox and hidden field propagation verified in 5 templates.
- Findings:
  - [medium] javascript: Batch Excel import path lacks strict_mode propagation
  - [low] javascript: _invoke_template_resolver introspection is defensive and correct
<!-- LIMCODE_REVIEW_MILESTONES_END -->

<!-- LIMCODE_REVIEW_METADATA_START -->
{
  "formatVersion": 3,
  "reviewRunId": "review-mngeeyjm-lj96zp",
  "createdAt": "2026-04-01T00:00:00.000Z",
  "finalizedAt": "2026-04-01T18:48:36.996Z",
  "status": "completed",
  "overallDecision": "conditionally_accepted",
  "latestConclusion": "Conditionally accepted. Strict mode implementation is comprehensive across main UI paths (process parts, process Excel routes, scheduler batches create/generate-ops). Transaction safety verified. One high-severity finding: ExternalGroupService._apply_separate_mode compatible path (CFM-063) still has completely silent 1.0 day fallback with no logger/counter — this must be fixed before merge. One medium finding: batch Excel import path lacks strict_mode propagation (can be deferred). Regression tests for strict mode are thorough (4 tests covering route_parser, PartService, ExternalGroupService, and BatchService rejection paths).",
  "recommendedNextAction": "MUST FIX before merge: Add logger.warning to ExternalGroupService._apply_separate_mode compatible fallback path (L131-138). SHOULD FIX: Propagate strict_mode to batch_excel_import.py and scheduler_excel_batches.py.",
  "reviewedModules": [
    "core/services/process/route_parser.py",
    "core/services/process/part_service.py",
    "core/services/process/external_group_service.py",
    "core/services/scheduler/batch_service.py",
    "core/services/scheduler/batch_template_ops.py",
    "core/services/scheduler/batch_excel_import.py",
    "web/routes/process_parts.py",
    "web/routes/process_excel_routes.py",
    "web/routes/scheduler_batches.py",
    "web/routes/scheduler_excel_batches.py",
    "templates/process/list.html",
    "templates/process/detail.html",
    "templates/scheduler/batches_manage.html",
    "templates/scheduler/batch_detail.html",
    "templates/components/excel_import.html"
  ],
  "milestones": [
    {
      "id": "M1",
      "title": "Strict Mode Chain: RouteParser + PartService + ExternalGroupService",
      "summary": "RouteParser strict mode: 3 rejection paths verified (unknown op type, missing supplier, invalid supplier days). PartService strict mode: pre-parse before create, reparse_and_save pass-through. ExternalGroupService: strict_mode gate added but compatible path still SILENT (F-006 HIGH). Transaction safety verified.",
      "status": "completed",
      "conclusion": "RouteParser strict mode: 3 rejection paths verified (unknown op type, missing supplier, invalid supplier days). PartService strict mode: pre-parse before create, reparse_and_save pass-through. ExternalGroupService: strict_mode gate added but compatible path still SILENT (F-006 HIGH). Transaction safety verified.",
      "evidenceFiles": [],
      "reviewedModules": [],
      "recommendedNextAction": null,
      "recordedAt": "2026-04-01T18:48:11.684Z",
      "findingIds": [
        "F-006",
        "F-008"
      ]
    },
    {
      "id": "M2",
      "title": "Strict Mode Caller Propagation: Web Routes + BatchService + batch_template_ops + Excel Import",
      "summary": "Web routes: process_parts.py, process_excel_routes.py, scheduler_batches.py all pass strict_mode from form checkbox. BatchService: strict_mode propagated through create_batch_from_template -> _load_template_ops_with_fallback -> _invoke_template_resolver. batch_template_ops.py: clean extraction with strict_mode pass-through. Gap: batch_excel_import.py and scheduler_excel_batches.py lack strict_mode (F-007). Templates: checkbox and hidden field propagation verified in 5 templates.",
      "status": "completed",
      "conclusion": "Web routes: process_parts.py, process_excel_routes.py, scheduler_batches.py all pass strict_mode from form checkbox. BatchService: strict_mode propagated through create_batch_from_template -> _load_template_ops_with_fallback -> _invoke_template_resolver. batch_template_ops.py: clean extraction with strict_mode pass-through. Gap: batch_excel_import.py and scheduler_excel_batches.py lack strict_mode (F-007). Templates: checkbox and hidden field propagation verified in 5 templates.",
      "evidenceFiles": [],
      "reviewedModules": [],
      "recommendedNextAction": null,
      "recordedAt": "2026-04-01T18:48:25.563Z",
      "findingIds": [
        "F-007",
        "F-009"
      ]
    }
  ],
  "findings": [
    {
      "id": "F-006",
      "severity": "high",
      "category": "javascript",
      "title": "CFM-063 ExternalGroupService compatible mode still completely silent",
      "description": "ExternalGroupService._apply_separate_mode L131-138: when strict_mode=False, dv=None/<=0 still silently falls back to 1.0 with NO logger.warning, NO counter, NO trace. The service has self.logger available but never calls it in the compatible fallback path. This is the original CFM-063 critical finding that was rated 'fatal' in the audit.",
      "evidenceFiles": [],
      "relatedMilestoneIds": [
        "M1"
      ],
      "recommendation": "Add self.logger.warning() call before dv=1.0 in the compatible path. Example: if self.logger: self.logger.warning(f'...seq={seq} ext_days fallback to 1.0...')"
    },
    {
      "id": "F-008",
      "severity": "low",
      "category": "javascript",
      "title": "route_parser strict mode logic verified correct",
      "description": "route_parser.parse() strict_mode verified correct. Unknown op type -> errors (not warnings). Missing supplier -> errors. Supplier with issue_messages -> errors via _strict_supplier_issue_messages. op.default_days NOT set when strict errors occur. ParseStatus.FAILED triggers BusinessError in _parse_route_or_raise. Transaction safety confirmed.",
      "evidenceFiles": [],
      "relatedMilestoneIds": [
        "M1"
      ],
      "recommendation": null
    },
    {
      "id": "F-007",
      "severity": "medium",
      "category": "javascript",
      "title": "Batch Excel import path lacks strict_mode propagation",
      "description": "batch_excel_import.py L79 calls create_batch_from_template_no_tx without strict_mode. scheduler_excel_batches.py route has no strict_mode support. The batch Excel import always runs in compatible mode regardless of any UI setting.",
      "evidenceFiles": [],
      "relatedMilestoneIds": [
        "M2"
      ],
      "recommendation": "Add strict_mode parameter to import_from_preview_rows and batch_excel_import, and add checkbox to scheduler_excel_batches.py route. May be deferred but should be tracked."
    },
    {
      "id": "F-009",
      "severity": "low",
      "category": "javascript",
      "title": "_invoke_template_resolver introspection is defensive and correct",
      "description": "BatchService._invoke_template_resolver uses inspect.signature to check if resolver supports strict_mode, falling back to calling without it. This is appropriately defensive for backward compatibility with custom resolvers.",
      "evidenceFiles": [],
      "relatedMilestoneIds": [
        "M2"
      ],
      "recommendation": null
    }
  ]
}
<!-- LIMCODE_REVIEW_METADATA_END -->
