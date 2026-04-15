# 引用链追踪报告（深度 Review 辅助）

> 说明：本报告基于 AST 提取“定义”，并用文本搜索定位“调用点/被调用者”。
> 由于 Python 动态特性与启发式匹配限制，可能存在漏报/误报，仅作为审查线索。
> 建议：对每条调用关系回到源码上下文手工核对。

## web/routes/scheduler_excel_batches.py（Route 层）

### `_sorted_existing_list()` [私有]
- 位置：第 52-55 行
- 参数：existing_preview_data
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_parse_auto_generate_ops()` [私有]
- 位置：第 58-59 行
- 参数：value
- 返回类型：Name(id='bool', ctx=Load())

### `_build_existing_preview_data()` [私有]
- 位置：第 62-77 行
- 参数：batch_svc
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_build_parts_cache()` [私有]
- 位置：第 80-81 行
- 参数：part_svc
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_render_excel_batches_page()` [私有]
- 位置：第 84-113 行
- 参数：无
- 返回类型：无注解

### `excel_batches_page()` [公开]
- 位置：第 117-129 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（4 个）：`bp.get`, `_build_existing_preview_data`, `_render_excel_batches_page`, `_sorted_existing_list`

### `excel_batches_preview()` [公开]
- 位置：第 133-211 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（27 个）：`bp.post`, `time.time`, `_parse_mode`, `_parse_auto_generate_ops`, `_strict_mode_enabled`, `get`, `_read_uploaded_xlsx`, `_ensure_unique_ids`, `_build_existing_preview_data`, `_build_parts_cache`, `get_batch_row_validate_and_normalize`, `excel_svc.preview_import`, `build_preview_baseline_token`, `int`, `log_excel_import`

### `excel_batches_confirm()` [公开]
- 位置：第 215-315 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（34 个）：`bp.post`, `time.time`, `_parse_mode`, `_strict_mode_enabled`, `_parse_auto_generate_ops`, `load_confirm_payload`, `_ensure_unique_ids`, `_build_existing_preview_data`, `_build_parts_cache`, `preview_baseline_is_stale`, `get_batch_row_validate_and_normalize`, `excel_svc.preview_import`, `collect_error_rows`, `batch_svc.import_from_preview_rows`, `extract_import_stats`

### `excel_batches_template()` [公开]
- 位置：第 319-360 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（13 个）：`bp.get`, `time.time`, `join`, `exists`, `get_template_definition`, `build_xlsx_bytes`, `int`, `log_excel_export`, `send_file`, `send_excel_template_file`, `template_def.get`, `getattr`, `len`

### `excel_batches_export()` [公开]
- 位置：第 364-396 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（11 个）：`bp.get`, `time.time`, `svc.list`, `get_template_definition`, `build_xlsx_bytes`, `int`, `log_excel_export`, `send_file`, `template_def.get`, `getattr`, `len`

---
- 分析函数/方法数：10
- 找到调用关系：0 处
- 跨层边界风险：0 项
