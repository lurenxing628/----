---
doc_type: issue-fix
issue: 2026-05-25-route-parser-supplier-global-scope
path: fast-track
fix_date: 2026-05-25
status: completed
severity: P1
tags:
  - process
  - route-parser
  - supplier
---

# Route Parser Supplier Global Scope Fix Note

## 问题

`RouteParser.parse(..., strict_mode=True)` 会在逐个工序解析前，把所有 `supplier_global_issues` 直接加入 `errors`。

这会导致一个无关供应商的坏 `op_type_id` 卡死当前路线。比如当前路线只有内部工序 `数铣`，但供应商表里有一行指向已不存在工种的脏数据，strict 模式仍会失败。

## 根因

供应商映射加载阶段只产出全局错误文字，没有保留这条错误对应的 `op_type_id`。

路线解析阶段也没有等到当前路线的外协工序识别完成，就把这些全局错误升级成 strict 失败。

## 修复

- `SupplierConstraintResolver` 增加 `SupplierGlobalIssue`，记录 `op_type_id` 和错误文案。
- `RouteParser` 延后处理 `supplier_global_issues`。
- 当前路线已经识别出外协工序后，只把“当前路线外协工序实际引用到的 `op_type_id`”对应的供应商映射问题升级成 strict error。
- 无关供应商映射问题仍作为 warning 透出，不吞错、不静默。

## 验证

- `python tests/regression_route_parser_strict_mode_rejects_supplier_fallback.py`
- `python tests/regression_route_parser_missing_supplier_warning.py`
- `python tests/regression_route_parser_preserve_errors_when_no_matches.py`
- `pytest -q tests/regression_supplier_effective_selection_contract.py tests/regression_part_service_create_strict_mode_atomic.py tests/regression_batch_service_strict_mode_template_autoparse.py`
- `python -m py_compile core/services/process/route_parser.py core/services/process/route_parser_constraints.py tests/regression_route_parser_strict_mode_rejects_supplier_fallback.py`

## 结果

- 内部工序路线不再被无关供应商脏映射卡成 strict 失败。
- 当前路线外协工序缺供应商时，strict 仍然失败。
- 当前路线引用到的外协供应商映射加载失败时，strict 仍然失败。
- 无关供应商脏映射仍显示为 warning，方便用户发现并清理数据。
