# 静默回退修复实现 Review
- Date: 2026-04-01
- Overview: 全面审查静默回退修复批次的代码变更，验证是否解决了审计报告识别的关键问题，确认不存在新的静默回退隐患。
- Status: in_progress

## Review Scope
# 静默回退修复实现 Review

**审查日期**: 2026-04-01  
**审查范围**: 基于 `audit/2026-04/20260401_core_静默回退_baseline_reconciliation.md` 声明的修复批次  
**审查目标**: 验证修复是否真正解决了审计识别的问题，而非引入新的静默回退

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
- Current status: in_progress
- Reviewed modules: core/services/process/route_parser.py, core/services/process/part_service.py, core/services/process/supplier_service.py
- Current progress: 1 milestones recorded; latest: M1
- Total milestones: 1
- Completed milestones: 1
- Total findings: 1
- Findings by severity: high 0 / medium 0 / low 1
- Latest conclusion: ## 审查结果 ### 1. `RouteParser.parse()` — 无供应商映射时补 warning ✅ 已修复 **源码确认**（L224-226）： ```python else: op.default_days = 1.0 warnings.append(f'工种"{op_type_name}"未找到供应商配置，已按默认 1.0 天初始化外协周期') ``` - 之前：完全静默（CFM-065 致命级问题） - 现在：显式 warning，且因为 `warnings` 列表有内容，状态会自动降为 `ParseStatus.PARTIAL`（L238-242 逻辑） - **验证通过**：warning 文案清晰，状态降级逻辑正确 ### 2. `RouteParser._build_supplier_map()` — 拆开 `or 1.0` 逻辑 ✅ 已修复 **源码确认**（L315-333）： - 使用 `missing = object()` sentinel 精确区分"属性不存在"、"值为 None/空串"、"值无法解析"、"值 <= 0" 四种情况 - 每种情况都生成明确的 `issue_messages`，而不是一律静默写 1.0 - `op_types_repo.get()` 异常现在有 logger.warning（L299-305） **关键改进**：原来 `float(getattr(supplier, "default_days", 1.0) or 1.0)` 会把 `0.0` 也收敛为 `1.0`，现在改为 `parsed_default_days <= 0` 时给出明确诊断信息。 **残留问题**：`default_days = 0.0` 仍然被回退为 1.0 天并产生 issue，但 issue 消息文案中 `<= 0` 的处理是否合理取决于业务语义 — 如果业务允许 0 天周期，则此处仍是错误回退。当前实现视 0 为无效值是审慎的。 ### 3. `PartService._coerce_external_default_days()` — 新增方法 ✅ 改进显著 **源码确认**（L81-118）： - 提取为独立方法，返回 `(ext_days, used_fallback)` 元组 - 覆盖了 None/空串/解析失败/非有限/<=0 全部场景 - 每种场景都有 warning（同时写 warnings 列表和 logger） - 返回值中 `used_fallback=True` 标志可让调用方感知 ### 4. `_save_template_no_tx()` — 使用 `_coerce_external_default_days()` ✅ 已修复 **源码确认**（L340-342）： ```python ext_days, used_fallback = self._coerce_external_default_days(op, warnings=parse_result.warnings) if used_fallback and parse_result.status != ParseStatus.FAILED: parse_result.status = ParseStatus.PARTIAL ``` - 之前：`float(op.default_days or 1.0)` 完全静默洗白（审计报告新发现 NEW-001） - 现在：有明确 warning + 状态降级 - **关键发现**：parse_result.warnings 是共享列表引用，写入会保留到上层 ### 5. `SupplierService` 写侧 — 新增 `_normalize_default_days` + `_log_default_days_fallback` ✅ 已修复 **源码确认**： - `_normalize_default_days()`（L28-39）：返回 `(value, fallback_reason)` 元组，区分 None/blank/invalid - `_log_default_days_fallback()`（L41-50）：logger.warning 记录 - `_validate_fields()`（L81-83）：当 fallback 发生时调用日志记录 - `create()`（L155）：`float(sdays if sdays is not None else 1.0)` — 仍有冗余防御 - `update()`（L184）：同上 **残留问题**：`create()` 和 `update()` 中的 `float(sdays if sdays is not None else 1.0)` 存在微小风险 — 如果 `_validate_fields()` 因为 `allow_partial=True` 返回 `sdays=None`，`float(sdays if sdays is not None else 1.0)` 会再次写入 1.0。但在 `create()` 路径中 `allow_partial=False`，所以 `sdays` 一定不是 None（会在 validate 中被默认化）。在 `update()` 中 `sdays=None` 表示"用户未传入该字段"，条件 `if default_days is not None:` 会保护住不会写入。**此路径安全**。 ### Pylance 诊断确认 `supplier_service.py` 有两个类型诊断错误（Line 146, 160）： - `get(supplier_id: str)` 接收 `str | None` 类型 - `_get_or_raise(supplier_id: str)` 接收 `str | None` 类型 这是类型标注问题，不影响运行时行为（`sid` 在 `allow_partial=False` 时已验证非空）。
- Recommended next action: pending
- Overall decision: pending
<!-- LIMCODE_REVIEW_SUMMARY_END -->

## Review Findings
<!-- LIMCODE_REVIEW_FINDINGS_START -->
- [low] maintainability: SupplierService Pylance 类型标注不一致
  - ID: F-001
  - Description: supplier_service.py Line 146/160 存在 Pylance 类型推断错误：`str | None` 传给期望 `str` 的参数。运行时安全（已有 not-None 校验），但影响 IDE 体验和静态分析可信度。
  - Evidence Files:
    - `core/services/process/supplier_service.py`
    - `core/services/process/route_parser.py`
    - `core/services/process/part_service.py`
  - Related Milestones: M1
  - Recommendation: 为 `get()` 和 `_get_or_raise()` 添加 `Optional[str]` 参数标注，或在调用前加 `assert sid is not None`。
<!-- LIMCODE_REVIEW_FINDINGS_END -->

## Review Milestones
<!-- LIMCODE_REVIEW_MILESTONES_START -->
### M1 · Route / Supplier / Persistence 链可观测性加固审查
- Status: completed
- Recorded At: 2026-04-01T16:58:03.183Z
- Reviewed Modules: core/services/process/route_parser.py, core/services/process/part_service.py, core/services/process/supplier_service.py
- Summary:
## 审查结果

### 1. `RouteParser.parse()` — 无供应商映射时补 warning ✅ 已修复

**源码确认**（L224-226）：
```python
else:
    op.default_days = 1.0
    warnings.append(f'工种"{op_type_name}"未找到供应商配置，已按默认 1.0 天初始化外协周期')
```

- 之前：完全静默（CFM-065 致命级问题）
- 现在：显式 warning，且因为 `warnings` 列表有内容，状态会自动降为 `ParseStatus.PARTIAL`（L238-242 逻辑）
- **验证通过**：warning 文案清晰，状态降级逻辑正确

### 2. `RouteParser._build_supplier_map()` — 拆开 `or 1.0` 逻辑 ✅ 已修复

**源码确认**（L315-333）：
- 使用 `missing = object()` sentinel 精确区分"属性不存在"、"值为 None/空串"、"值无法解析"、"值 <= 0" 四种情况
- 每种情况都生成明确的 `issue_messages`，而不是一律静默写 1.0
- `op_types_repo.get()` 异常现在有 logger.warning（L299-305）

**关键改进**：原来 `float(getattr(supplier, "default_days", 1.0) or 1.0)` 会把 `0.0` 也收敛为 `1.0`，现在改为 `parsed_default_days <= 0` 时给出明确诊断信息。

**残留问题**：`default_days = 0.0` 仍然被回退为 1.0 天并产生 issue，但 issue 消息文案中 `<= 0` 的处理是否合理取决于业务语义 — 如果业务允许 0 天周期，则此处仍是错误回退。当前实现视 0 为无效值是审慎的。

### 3. `PartService._coerce_external_default_days()` — 新增方法 ✅ 改进显著

**源码确认**（L81-118）：
- 提取为独立方法，返回 `(ext_days, used_fallback)` 元组
- 覆盖了 None/空串/解析失败/非有限/<=0 全部场景
- 每种场景都有 warning（同时写 warnings 列表和 logger）
- 返回值中 `used_fallback=True` 标志可让调用方感知

### 4. `_save_template_no_tx()` — 使用 `_coerce_external_default_days()` ✅ 已修复

**源码确认**（L340-342）：
```python
ext_days, used_fallback = self._coerce_external_default_days(op, warnings=parse_result.warnings)
if used_fallback and parse_result.status != ParseStatus.FAILED:
    parse_result.status = ParseStatus.PARTIAL
```

- 之前：`float(op.default_days or 1.0)` 完全静默洗白（审计报告新发现 NEW-001）
- 现在：有明确 warning + 状态降级
- **关键发现**：parse_result.warnings 是共享列表引用，写入会保留到上层

### 5. `SupplierService` 写侧 — 新增 `_normalize_default_days` + `_log_default_days_fallback` ✅ 已修复

**源码确认**：
- `_normalize_default_days()`（L28-39）：返回 `(value, fallback_reason)` 元组，区分 None/blank/invalid
- `_log_default_days_fallback()`（L41-50）：logger.warning 记录
- `_validate_fields()`（L81-83）：当 fallback 发生时调用日志记录
- `create()`（L155）：`float(sdays if sdays is not None else 1.0)` — 仍有冗余防御
- `update()`（L184）：同上

**残留问题**：`create()` 和 `update()` 中的 `float(sdays if sdays is not None else 1.0)` 存在微小风险 — 如果 `_validate_fields()` 因为 `allow_partial=True` 返回 `sdays=None`，`float(sdays if sdays is not None else 1.0)` 会再次写入 1.0。但在 `create()` 路径中 `allow_partial=False`，所以 `sdays` 一定不是 None（会在 validate 中被默认化）。在 `update()` 中 `sdays=None` 表示"用户未传入该字段"，条件 `if default_days is not None:` 会保护住不会写入。**此路径安全**。

### Pylance 诊断确认

`supplier_service.py` 有两个类型诊断错误（Line 146, 160）：
- `get(supplier_id: str)` 接收 `str | None` 类型
- `_get_or_raise(supplier_id: str)` 接收 `str | None` 类型

这是类型标注问题，不影响运行时行为（`sid` 在 `allow_partial=False` 时已验证非空）。
- Conclusion: ## 审查结果 ### 1. `RouteParser.parse()` — 无供应商映射时补 warning ✅ 已修复 **源码确认**（L224-226）： ```python else: op.default_days = 1.0 warnings.append(f'工种"{op_type_name}"未找到供应商配置，已按默认 1.0 天初始化外协周期') ``` - 之前：完全静默（CFM-065 致命级问题） - 现在：显式 warning，且因为 `warnings` 列表有内容，状态会自动降为 `ParseStatus.PARTIAL`（L238-242 逻辑） - **验证通过**：warning 文案清晰，状态降级逻辑正确 ### 2. `RouteParser._build_supplier_map()` — 拆开 `or 1.0` 逻辑 ✅ 已修复 **源码确认**（L315-333）： - 使用 `missing = object()` sentinel 精确区分"属性不存在"、"值为 None/空串"、"值无法解析"、"值 <= 0" 四种情况 - 每种情况都生成明确的 `issue_messages`，而不是一律静默写 1.0 - `op_types_repo.get()` 异常现在有 logger.warning（L299-305） **关键改进**：原来 `float(getattr(supplier, "default_days", 1.0) or 1.0)` 会把 `0.0` 也收敛为 `1.0`，现在改为 `parsed_default_days <= 0` 时给出明确诊断信息。 **残留问题**：`default_days = 0.0` 仍然被回退为 1.0 天并产生 issue，但 issue 消息文案中 `<= 0` 的处理是否合理取决于业务语义 — 如果业务允许 0 天周期，则此处仍是错误回退。当前实现视 0 为无效值是审慎的。 ### 3. `PartService._coerce_external_default_days()` — 新增方法 ✅ 改进显著 **源码确认**（L81-118）： - 提取为独立方法，返回 `(ext_days, used_fallback)` 元组 - 覆盖了 None/空串/解析失败/非有限/<=0 全部场景 - 每种场景都有 warning（同时写 warnings 列表和 logger） - 返回值中 `used_fallback=True` 标志可让调用方感知 ### 4. `_save_template_no_tx()` — 使用 `_coerce_external_default_days()` ✅ 已修复 **源码确认**（L340-342）： ```python ext_days, used_fallback = self._coerce_external_default_days(op, warnings=parse_result.warnings) if used_fallback and parse_result.status != ParseStatus.FAILED: parse_result.status = ParseStatus.PARTIAL ``` - 之前：`float(op.default_days or 1.0)` 完全静默洗白（审计报告新发现 NEW-001） - 现在：有明确 warning + 状态降级 - **关键发现**：parse_result.warnings 是共享列表引用，写入会保留到上层 ### 5. `SupplierService` 写侧 — 新增 `_normalize_default_days` + `_log_default_days_fallback` ✅ 已修复 **源码确认**： - `_normalize_default_days()`（L28-39）：返回 `(value, fallback_reason)` 元组，区分 None/blank/invalid - `_log_default_days_fallback()`（L41-50）：logger.warning 记录 - `_validate_fields()`（L81-83）：当 fallback 发生时调用日志记录 - `create()`（L155）：`float(sdays if sdays is not None else 1.0)` — 仍有冗余防御 - `update()`（L184）：同上 **残留问题**：`create()` 和 `update()` 中的 `float(sdays if sdays is not None else 1.0)` 存在微小风险 — 如果 `_validate_fields()` 因为 `allow_partial=True` 返回 `sdays=None`，`float(sdays if sdays is not None else 1.0)` 会再次写入 1.0。但在 `create()` 路径中 `allow_partial=False`，所以 `sdays` 一定不是 None（会在 validate 中被默认化）。在 `update()` 中 `sdays=None` 表示"用户未传入该字段"，条件 `if default_days is not None:` 会保护住不会写入。**此路径安全**。 ### Pylance 诊断确认 `supplier_service.py` 有两个类型诊断错误（Line 146, 160）： - `get(supplier_id: str)` 接收 `str | None` 类型 - `_get_or_raise(supplier_id: str)` 接收 `str | None` 类型 这是类型标注问题，不影响运行时行为（`sid` 在 `allow_partial=False` 时已验证非空）。
- Evidence Files:
  - `core/services/process/route_parser.py`
  - `core/services/process/part_service.py`
  - `core/services/process/supplier_service.py`
- Findings:
  - [low] maintainability: SupplierService Pylance 类型标注不一致
<!-- LIMCODE_REVIEW_MILESTONES_END -->

<!-- LIMCODE_REVIEW_METADATA_START -->
{
  "formatVersion": 3,
  "reviewRunId": "review-mngafx9k-aby8g4",
  "createdAt": "2026-04-01T00:00:00.000Z",
  "finalizedAt": null,
  "status": "in_progress",
  "overallDecision": null,
  "latestConclusion": "## 审查结果 ### 1. `RouteParser.parse()` — 无供应商映射时补 warning ✅ 已修复 **源码确认**（L224-226）： ```python else: op.default_days = 1.0 warnings.append(f'工种\"{op_type_name}\"未找到供应商配置，已按默认 1.0 天初始化外协周期') ``` - 之前：完全静默（CFM-065 致命级问题） - 现在：显式 warning，且因为 `warnings` 列表有内容，状态会自动降为 `ParseStatus.PARTIAL`（L238-242 逻辑） - **验证通过**：warning 文案清晰，状态降级逻辑正确 ### 2. `RouteParser._build_supplier_map()` — 拆开 `or 1.0` 逻辑 ✅ 已修复 **源码确认**（L315-333）： - 使用 `missing = object()` sentinel 精确区分\"属性不存在\"、\"值为 None/空串\"、\"值无法解析\"、\"值 <= 0\" 四种情况 - 每种情况都生成明确的 `issue_messages`，而不是一律静默写 1.0 - `op_types_repo.get()` 异常现在有 logger.warning（L299-305） **关键改进**：原来 `float(getattr(supplier, \"default_days\", 1.0) or 1.0)` 会把 `0.0` 也收敛为 `1.0`，现在改为 `parsed_default_days <= 0` 时给出明确诊断信息。 **残留问题**：`default_days = 0.0` 仍然被回退为 1.0 天并产生 issue，但 issue 消息文案中 `<= 0` 的处理是否合理取决于业务语义 — 如果业务允许 0 天周期，则此处仍是错误回退。当前实现视 0 为无效值是审慎的。 ### 3. `PartService._coerce_external_default_days()` — 新增方法 ✅ 改进显著 **源码确认**（L81-118）： - 提取为独立方法，返回 `(ext_days, used_fallback)` 元组 - 覆盖了 None/空串/解析失败/非有限/<=0 全部场景 - 每种场景都有 warning（同时写 warnings 列表和 logger） - 返回值中 `used_fallback=True` 标志可让调用方感知 ### 4. `_save_template_no_tx()` — 使用 `_coerce_external_default_days()` ✅ 已修复 **源码确认**（L340-342）： ```python ext_days, used_fallback = self._coerce_external_default_days(op, warnings=parse_result.warnings) if used_fallback and parse_result.status != ParseStatus.FAILED: parse_result.status = ParseStatus.PARTIAL ``` - 之前：`float(op.default_days or 1.0)` 完全静默洗白（审计报告新发现 NEW-001） - 现在：有明确 warning + 状态降级 - **关键发现**：parse_result.warnings 是共享列表引用，写入会保留到上层 ### 5. `SupplierService` 写侧 — 新增 `_normalize_default_days` + `_log_default_days_fallback` ✅ 已修复 **源码确认**： - `_normalize_default_days()`（L28-39）：返回 `(value, fallback_reason)` 元组，区分 None/blank/invalid - `_log_default_days_fallback()`（L41-50）：logger.warning 记录 - `_validate_fields()`（L81-83）：当 fallback 发生时调用日志记录 - `create()`（L155）：`float(sdays if sdays is not None else 1.0)` — 仍有冗余防御 - `update()`（L184）：同上 **残留问题**：`create()` 和 `update()` 中的 `float(sdays if sdays is not None else 1.0)` 存在微小风险 — 如果 `_validate_fields()` 因为 `allow_partial=True` 返回 `sdays=None`，`float(sdays if sdays is not None else 1.0)` 会再次写入 1.0。但在 `create()` 路径中 `allow_partial=False`，所以 `sdays` 一定不是 None（会在 validate 中被默认化）。在 `update()` 中 `sdays=None` 表示\"用户未传入该字段\"，条件 `if default_days is not None:` 会保护住不会写入。**此路径安全**。 ### Pylance 诊断确认 `supplier_service.py` 有两个类型诊断错误（Line 146, 160）： - `get(supplier_id: str)` 接收 `str | None` 类型 - `_get_or_raise(supplier_id: str)` 接收 `str | None` 类型 这是类型标注问题，不影响运行时行为（`sid` 在 `allow_partial=False` 时已验证非空）。",
  "recommendedNextAction": null,
  "reviewedModules": [
    "core/services/process/route_parser.py",
    "core/services/process/part_service.py",
    "core/services/process/supplier_service.py"
  ],
  "milestones": [
    {
      "id": "M1",
      "title": "Route / Supplier / Persistence 链可观测性加固审查",
      "summary": "## 审查结果\n\n### 1. `RouteParser.parse()` — 无供应商映射时补 warning ✅ 已修复\n\n**源码确认**（L224-226）：\n```python\nelse:\n    op.default_days = 1.0\n    warnings.append(f'工种\"{op_type_name}\"未找到供应商配置，已按默认 1.0 天初始化外协周期')\n```\n\n- 之前：完全静默（CFM-065 致命级问题）\n- 现在：显式 warning，且因为 `warnings` 列表有内容，状态会自动降为 `ParseStatus.PARTIAL`（L238-242 逻辑）\n- **验证通过**：warning 文案清晰，状态降级逻辑正确\n\n### 2. `RouteParser._build_supplier_map()` — 拆开 `or 1.0` 逻辑 ✅ 已修复\n\n**源码确认**（L315-333）：\n- 使用 `missing = object()` sentinel 精确区分\"属性不存在\"、\"值为 None/空串\"、\"值无法解析\"、\"值 <= 0\" 四种情况\n- 每种情况都生成明确的 `issue_messages`，而不是一律静默写 1.0\n- `op_types_repo.get()` 异常现在有 logger.warning（L299-305）\n\n**关键改进**：原来 `float(getattr(supplier, \"default_days\", 1.0) or 1.0)` 会把 `0.0` 也收敛为 `1.0`，现在改为 `parsed_default_days <= 0` 时给出明确诊断信息。\n\n**残留问题**：`default_days = 0.0` 仍然被回退为 1.0 天并产生 issue，但 issue 消息文案中 `<= 0` 的处理是否合理取决于业务语义 — 如果业务允许 0 天周期，则此处仍是错误回退。当前实现视 0 为无效值是审慎的。\n\n### 3. `PartService._coerce_external_default_days()` — 新增方法 ✅ 改进显著\n\n**源码确认**（L81-118）：\n- 提取为独立方法，返回 `(ext_days, used_fallback)` 元组\n- 覆盖了 None/空串/解析失败/非有限/<=0 全部场景\n- 每种场景都有 warning（同时写 warnings 列表和 logger）\n- 返回值中 `used_fallback=True` 标志可让调用方感知\n\n### 4. `_save_template_no_tx()` — 使用 `_coerce_external_default_days()` ✅ 已修复\n\n**源码确认**（L340-342）：\n```python\next_days, used_fallback = self._coerce_external_default_days(op, warnings=parse_result.warnings)\nif used_fallback and parse_result.status != ParseStatus.FAILED:\n    parse_result.status = ParseStatus.PARTIAL\n```\n\n- 之前：`float(op.default_days or 1.0)` 完全静默洗白（审计报告新发现 NEW-001）\n- 现在：有明确 warning + 状态降级\n- **关键发现**：parse_result.warnings 是共享列表引用，写入会保留到上层\n\n### 5. `SupplierService` 写侧 — 新增 `_normalize_default_days` + `_log_default_days_fallback` ✅ 已修复\n\n**源码确认**：\n- `_normalize_default_days()`（L28-39）：返回 `(value, fallback_reason)` 元组，区分 None/blank/invalid\n- `_log_default_days_fallback()`（L41-50）：logger.warning 记录\n- `_validate_fields()`（L81-83）：当 fallback 发生时调用日志记录\n- `create()`（L155）：`float(sdays if sdays is not None else 1.0)` — 仍有冗余防御\n- `update()`（L184）：同上\n\n**残留问题**：`create()` 和 `update()` 中的 `float(sdays if sdays is not None else 1.0)` 存在微小风险 — 如果 `_validate_fields()` 因为 `allow_partial=True` 返回 `sdays=None`，`float(sdays if sdays is not None else 1.0)` 会再次写入 1.0。但在 `create()` 路径中 `allow_partial=False`，所以 `sdays` 一定不是 None（会在 validate 中被默认化）。在 `update()` 中 `sdays=None` 表示\"用户未传入该字段\"，条件 `if default_days is not None:` 会保护住不会写入。**此路径安全**。\n\n### Pylance 诊断确认\n\n`supplier_service.py` 有两个类型诊断错误（Line 146, 160）：\n- `get(supplier_id: str)` 接收 `str | None` 类型\n- `_get_or_raise(supplier_id: str)` 接收 `str | None` 类型\n\n这是类型标注问题，不影响运行时行为（`sid` 在 `allow_partial=False` 时已验证非空）。",
      "status": "completed",
      "conclusion": "## 审查结果 ### 1. `RouteParser.parse()` — 无供应商映射时补 warning ✅ 已修复 **源码确认**（L224-226）： ```python else: op.default_days = 1.0 warnings.append(f'工种\"{op_type_name}\"未找到供应商配置，已按默认 1.0 天初始化外协周期') ``` - 之前：完全静默（CFM-065 致命级问题） - 现在：显式 warning，且因为 `warnings` 列表有内容，状态会自动降为 `ParseStatus.PARTIAL`（L238-242 逻辑） - **验证通过**：warning 文案清晰，状态降级逻辑正确 ### 2. `RouteParser._build_supplier_map()` — 拆开 `or 1.0` 逻辑 ✅ 已修复 **源码确认**（L315-333）： - 使用 `missing = object()` sentinel 精确区分\"属性不存在\"、\"值为 None/空串\"、\"值无法解析\"、\"值 <= 0\" 四种情况 - 每种情况都生成明确的 `issue_messages`，而不是一律静默写 1.0 - `op_types_repo.get()` 异常现在有 logger.warning（L299-305） **关键改进**：原来 `float(getattr(supplier, \"default_days\", 1.0) or 1.0)` 会把 `0.0` 也收敛为 `1.0`，现在改为 `parsed_default_days <= 0` 时给出明确诊断信息。 **残留问题**：`default_days = 0.0` 仍然被回退为 1.0 天并产生 issue，但 issue 消息文案中 `<= 0` 的处理是否合理取决于业务语义 — 如果业务允许 0 天周期，则此处仍是错误回退。当前实现视 0 为无效值是审慎的。 ### 3. `PartService._coerce_external_default_days()` — 新增方法 ✅ 改进显著 **源码确认**（L81-118）： - 提取为独立方法，返回 `(ext_days, used_fallback)` 元组 - 覆盖了 None/空串/解析失败/非有限/<=0 全部场景 - 每种场景都有 warning（同时写 warnings 列表和 logger） - 返回值中 `used_fallback=True` 标志可让调用方感知 ### 4. `_save_template_no_tx()` — 使用 `_coerce_external_default_days()` ✅ 已修复 **源码确认**（L340-342）： ```python ext_days, used_fallback = self._coerce_external_default_days(op, warnings=parse_result.warnings) if used_fallback and parse_result.status != ParseStatus.FAILED: parse_result.status = ParseStatus.PARTIAL ``` - 之前：`float(op.default_days or 1.0)` 完全静默洗白（审计报告新发现 NEW-001） - 现在：有明确 warning + 状态降级 - **关键发现**：parse_result.warnings 是共享列表引用，写入会保留到上层 ### 5. `SupplierService` 写侧 — 新增 `_normalize_default_days` + `_log_default_days_fallback` ✅ 已修复 **源码确认**： - `_normalize_default_days()`（L28-39）：返回 `(value, fallback_reason)` 元组，区分 None/blank/invalid - `_log_default_days_fallback()`（L41-50）：logger.warning 记录 - `_validate_fields()`（L81-83）：当 fallback 发生时调用日志记录 - `create()`（L155）：`float(sdays if sdays is not None else 1.0)` — 仍有冗余防御 - `update()`（L184）：同上 **残留问题**：`create()` 和 `update()` 中的 `float(sdays if sdays is not None else 1.0)` 存在微小风险 — 如果 `_validate_fields()` 因为 `allow_partial=True` 返回 `sdays=None`，`float(sdays if sdays is not None else 1.0)` 会再次写入 1.0。但在 `create()` 路径中 `allow_partial=False`，所以 `sdays` 一定不是 None（会在 validate 中被默认化）。在 `update()` 中 `sdays=None` 表示\"用户未传入该字段\"，条件 `if default_days is not None:` 会保护住不会写入。**此路径安全**。 ### Pylance 诊断确认 `supplier_service.py` 有两个类型诊断错误（Line 146, 160）： - `get(supplier_id: str)` 接收 `str | None` 类型 - `_get_or_raise(supplier_id: str)` 接收 `str | None` 类型 这是类型标注问题，不影响运行时行为（`sid` 在 `allow_partial=False` 时已验证非空）。",
      "evidenceFiles": [
        "core/services/process/route_parser.py",
        "core/services/process/part_service.py",
        "core/services/process/supplier_service.py"
      ],
      "reviewedModules": [
        "core/services/process/route_parser.py",
        "core/services/process/part_service.py",
        "core/services/process/supplier_service.py"
      ],
      "recommendedNextAction": null,
      "recordedAt": "2026-04-01T16:58:03.183Z",
      "findingIds": [
        "F-001"
      ]
    }
  ],
  "findings": [
    {
      "id": "F-001",
      "severity": "low",
      "category": "maintainability",
      "title": "SupplierService Pylance 类型标注不一致",
      "description": "supplier_service.py Line 146/160 存在 Pylance 类型推断错误：`str | None` 传给期望 `str` 的参数。运行时安全（已有 not-None 校验），但影响 IDE 体验和静态分析可信度。",
      "evidenceFiles": [
        "core/services/process/supplier_service.py",
        "core/services/process/route_parser.py",
        "core/services/process/part_service.py"
      ],
      "relatedMilestoneIds": [
        "M1"
      ],
      "recommendation": "为 `get()` 和 `_get_or_raise()` 添加 `Optional[str]` 参数标注，或在调用前加 `assert sid is not None`。"
    }
  ]
}
<!-- LIMCODE_REVIEW_METADATA_END -->
