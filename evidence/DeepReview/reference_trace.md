# 引用链追踪报告（深度 Review 辅助）

## ⚠ 跨层边界风险

- ⚠ normalize_operator_machine_text() 返回 Optional，但 core/services/personnel/operator_machine_service.py:34 的调用者未做 None 检查
- ⚠ normalize_skill_level_optional() 返回 Optional，但 core/services/personnel/operator_machine_service.py:38 的调用者未做 None 检查
- ⚠ normalize_yes_no_optional() 返回 Optional，但 core/services/personnel/operator_machine_service.py:42 的调用者未做 None 检查
- ⚠ SystemConfigService.get_value() 返回 Optional，但 core/services/scheduler/config_snapshot.py:85 的调用者未做 None 检查
- ⚠ SystemConfigService.get_value() 返回 Optional，但 core/services/scheduler/config_snapshot.py:98 的调用者未做 None 检查
- ⚠ SystemConfigService.get_value() 返回 Optional，但 core/services/scheduler/config_snapshot.py:101 的调用者未做 None 检查
- ⚠ SystemConfigService.get_value() 返回 Optional，但 core/services/scheduler/config_snapshot.py:125 的调用者未做 None 检查
- ⚠ get_full_manual_section_url() 返回 Optional，但 web/routes/scheduler_config.py:192 的调用者未做 None 检查

> 说明：本报告基于 AST 提取“定义”，并用文本搜索定位“调用点/被调用者”。
> 由于 Python 动态特性与启发式匹配限制，可能存在漏报/误报，仅作为审查线索。
> 建议：对每条调用关系回到源码上下文手工核对。

## .windsurf/skills/aps-arch-audit/scripts/arch_audit.py（Other 层）

### `find_repo_root()` [公开]
- 位置：第 16-22 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（6 个）：`dirname`, `range`, `RuntimeError`, `abspath`, `exists`, `join`

### `_read()` [私有]
- 位置：第 25-27 行
- 参数：path
- 返回类型：无注解

### `scan_layer_violations()` [公开]
- 位置：第 30-70 行
- 参数：repo_root
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（16 个）：`join`, `re.compile`, `isdir`, `os.walk`, `_read`, `replace`, `enumerate`, `fname.endswith`, `txt.splitlines`, `line.strip`, `s.startswith`, `route_db_re.search`, `re.search`, `relpath`, `violations.append`

### `scan_file_sizes()` [公开]
- 位置：第 73-89 行
- 参数：repo_root
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（10 个）：`join`, `os.walk`, `isdir`, `len`, `fname.endswith`, `splitlines`, `replace`, `issues.append`, `_read`, `relpath`

### `scan_forbidden_patterns()` [公开]
- 位置：第 92-116 行
- 参数：repo_root
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（13 个）：`join`, `os.walk`, `isdir`, `_read`, `replace`, `enumerate`, `fname.endswith`, `txt.splitlines`, `line.strip`, `s.startswith`, `re.match`, `relpath`, `issues.append`

### `scan_naming()` [公开]
- 位置：第 119-135 行
- 参数：repo_root
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（10 个）：`re.compile`, `join`, `os.walk`, `isdir`, `fname.startswith`, `snake_re.match`, `replace`, `issues.append`, `fname.endswith`, `relpath`

### `scan_bare_enum_strings()` [公开]
- 位置：第 158-194 行
- 参数：repo_root
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（23 个）：`join`, `os.walk`, `isdir`, `any`, `_read`, `replace`, `enumerate`, `fname.endswith`, `txt.splitlines`, `line.strip`, `s.startswith`, `_ENUM_RE.search`, `_ENUM_IN_RE.search`, `split`, `relpath`

### `scan_future_annotations()` [公开]
- 位置：第 197-215 行
- 参数：repo_root
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（9 个）：`join`, `os.walk`, `isdir`, `_read`, `replace`, `fname.endswith`, `txt.strip`, `issues.append`, `relpath`

### `scan_public_func_annotations()` [公开]
- 位置：第 218-258 行
- 参数：repo_root
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（14 个）：`join`, `os.walk`, `isdir`, `replace`, `fname.endswith`, `_read`, `ast.parse`, `relpath`, `skipped.append`, `isinstance`, `func_name.startswith`, `issues.append`, `getattr`, `type`

### `_extract_imports()` [私有]
- 位置：第 264-272 行
- 参数：filepath
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `scan_circular_dependencies()` [公开]
- 位置：第 275-331 行
- 参数：repo_root
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（20 个）：`join`, `os.walk`, `set`, `module_imports.items`, `isdir`, `replace`, `_extract_imports`, `mod_a.split`, `tuple`, `fname.endswith`, `dep.split`, `sorted`, `re.search`, `mod_b.split`, `targets.add`

### `scan_route_imports_repository()` [公开]
- 位置：第 334-364 行
- 参数：repo_root
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（10 个）：`join`, `re.compile`, `os.walk`, `isdir`, `replace`, `_extract_imports`, `fname.endswith`, `repo_class_re.findall`, `relpath`, `issues.append`

### `scan_dead_public_methods()` [公开]
- 位置：第 367-444 行
- 参数：repo_root
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（20 个）：`join`, `re.compile`, `os.walk`, `isdir`, `_read`, `txt.splitlines`, `replace`, `func_re.finditer`, `fname.endswith`, `m.group`, `search_pat.findall`, `relpath`, `func_name.startswith`, `len`, `count`

### `scan_cyclomatic_complexity()` [公开]
- 位置：第 447-489 行
- 参数：repo_root
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（14 个）：`join`, `os.walk`, `isdir`, `replace`, `fname.endswith`, `_read`, `cc_visit`, `relpath`, `cc_rank`, `skipped.append`, `issues.append`, `getattr`, `str`, `type`

### `scan_vulture_dead_code()` [公开]
- 位置：第 495-511 行
- 参数：repo_root
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（8 个）：`sp.run`, `splitlines`, `line.strip`, `skipped.append`, `str`, `strip`, `issues.append`, `int`

### `generate_report()` [公开]
- 位置：第 514-607 行
- 参数：repo_root
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（19 个）：`scan_layer_violations`, `scan_file_sizes`, `scan_forbidden_patterns`, `scan_naming`, `scan_bare_enum_strings`, `scan_future_annotations`, `scan_public_func_annotations`, `scan_circular_dependencies`, `scan_route_imports_repository`, `scan_dead_public_methods`, `scan_cyclomatic_complexity`, `scan_vulture_dead_code`, `len`, `lines.append`, `complexity_stats.get`

### `main()` [公开]
- 位置：第 610-627 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（10 个）：`find_repo_root`, `generate_report`, `join`, `os.makedirs`, `print`, `open`, `f.write`, `getattr`, `decode`, `content.encode`

## check_manual_layout.py（Other 层）

### `_has_manual_related_min_width()` [私有]
- 位置：第 33-38 行
- 参数：css_content
- 返回类型：Name(id='bool', ctx=Load())

### `_server_is_reachable()` [私有]
- 位置：第 41-48 行
- 参数：url
- 返回类型：Name(id='bool', ctx=Load())

### `check_layout_via_styles()` [公开]
- 位置：第 51-78 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（5 个）：`print`, `css_file.read_text`, `checks.items`, `css_file.exists`, `_has_manual_related_min_width`

### `check_layout_via_browser()` [公开]
- 位置：第 81-240 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（21 个）：`print`, `Options`, `options.add_argument`, `_server_is_reachable`, `webdriver.Chrome`, `driver.quit`, `driver.get`, `time.sleep`, `driver.add_cookie`, `driver.refresh`, `until`, `driver.find_element`, `driver.execute_script`, `results.append`, `EC.presence_of_element_located`

### `main()` [公开]
- 位置：第 243-290 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（10 个）：`print`, `check_layout_via_styles`, `check_layout_via_browser`, `sys.exit`, `sum`, `len`, `mkdir`, `report_file.write_text`, `all`, `json.dumps`

## core/services/personnel/operator_machine_normalizers.py（Service 层）

### `normalize_operator_machine_text()` [公开]
- 位置：第 12-13 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（1 处）：
  - `core/services/personnel/operator_machine_service.py:34` [Service] `return om_normalizers.normalize_operator_machine_text(value)`
- **被调用者**（1 个）：`normalize_text`

### `normalize_skill_level_optional()` [公开]
- 位置：第 16-24 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（1 处）：
  - `core/services/personnel/operator_machine_service.py:38` [Service] `return om_normalizers.normalize_skill_level_optional(value)`
- **被调用者**（2 个）：`normalize_skill_level`, `ValidationError`

### `normalize_yes_no_optional()` [公开]
- 位置：第 27-39 行
- 参数：value, field
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（1 处）：
  - `core/services/personnel/operator_machine_service.py:42` [Service] `return om_normalizers.normalize_yes_no_optional(value, field)`
- **被调用者**（4 个）：`strip`, `s.lower`, `ValidationError`, `str`

### `normalize_skill_level_stored()` [公开]
- 位置：第 42-46 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（1 处）：
  - `core/services/personnel/operator_machine_service.py:46` [Service] `return om_normalizers.normalize_skill_level_stored(value)`
- **被调用者**（1 个）：`normalize_skill_level`

### `normalize_yes_no_stored()` [公开]
- 位置：第 49-60 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（1 处）：
  - `core/services/personnel/operator_machine_service.py:50` [Service] `return om_normalizers.normalize_yes_no_stored(value)`
- **被调用者**（3 个）：`strip`, `s.lower`, `str`

### `normalize_link_record()` [公开]
- 位置：第 63-66 行
- 参数：link
- 返回类型：Name(id='OperatorMachine', ctx=Load())
- **调用者**（1 处）：
  - `core/services/personnel/operator_machine_service.py:54` [Service] `return om_normalizers.normalize_link_record(link)`
- **被调用者**（3 个）：`normalize_skill_level_stored`, `normalize_yes_no_stored`, `getattr`

## core/services/personnel/operator_machine_service.py（Service 层）

### `OperatorMachineService.__init__()` [私有]
- 位置：第 21-29 行
- 参数：conn, logger, op_logger
- 返回类型：无注解

### `OperatorMachineService._normalize_text()` [私有]
- 位置：第 33-34 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `OperatorMachineService._normalize_skill_level_optional()` [私有]
- 位置：第 37-38 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `OperatorMachineService._normalize_yes_no_optional()` [私有]
- 位置：第 41-42 行
- 参数：value, field
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `OperatorMachineService._normalize_skill_level_stored()` [私有]
- 位置：第 45-46 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `OperatorMachineService._normalize_yes_no_stored()` [私有]
- 位置：第 49-50 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `OperatorMachineService._normalize_link()` [私有]
- 位置：第 53-54 行
- 参数：link
- 返回类型：Name(id='OperatorMachine', ctx=Load())

### `OperatorMachineService._ensure_operator_exists()` [私有]
- 位置：第 56-58 行
- 参数：operator_id
- 返回类型：Constant(value=None, kind=None)

### `OperatorMachineService._ensure_machine_exists()` [私有]
- 位置：第 60-62 行
- 参数：machine_id
- 返回类型：Constant(value=None, kind=None)

### `OperatorMachineService._detect_optional_columns()` [私有]
- 位置：第 65-68 行
- 参数：rows
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `OperatorMachineService._detect_optional_columns_from_preview()` [私有]
- 位置：第 71-74 行
- 参数：preview_rows
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `OperatorMachineService._build_existing_link_map()` [私有]
- 位置：第 76-88 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `OperatorMachineService._validate_required_ids_for_preview_row()` [私有]
- 位置：第 90-101 行
- 参数：row, row_num
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `OperatorMachineService._check_duplicate_key_in_file()` [私有]
- 位置：第 104-113 行
- 参数：key
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `OperatorMachineService._check_fk_exists()` [私有]
- 位置：第 115-130 行
- 参数：op_id, mc_id
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `OperatorMachineService._parse_skill_optional_for_preview()` [私有]
- 位置：第 132-142 行
- 参数：row, row_num
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `OperatorMachineService._parse_primary_optional_for_preview()` [私有]
- 位置：第 144-154 行
- 参数：row, row_num
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `OperatorMachineService._build_overwrite_preview_for_existing()` [私有]
- 位置：第 156-168 行
- 参数：无
- 返回类型：Name(id='ImportPreviewRow', ctx=Load())

### `OperatorMachineService._decide_preview_row()` [私有]
- 位置：第 170-180 行
- 参数：无
- 返回类型：Name(id='ImportPreviewRow', ctx=Load())

### `OperatorMachineService._preview_one_row()` [私有]
- 位置：第 182-210 行
- 参数：无
- 返回类型：Name(id='ImportPreviewRow', ctx=Load())

### `OperatorMachineService._is_primary_yes()` [私有]
- 位置：第 213-215 行
- 参数：data
- 返回类型：Name(id='bool', ctx=Load())

### `OperatorMachineService._collect_dup_primary_yes_operators()` [私有]
- 位置：第 217-227 行
- 参数：preview
- 返回类型：Subscript(value=Name(id='Set', ctx=Load()), slice=Index(valu

### `OperatorMachineService._mark_dup_primary_yes()` [私有]
- 位置：第 230-240 行
- 参数：preview, dup_ops
- 返回类型：Constant(value=None, kind=None)

### `OperatorMachineService._enforce_primary_unique_in_file()` [私有]
- 位置：第 242-245 行
- 参数：preview
- 返回类型：Constant(value=None, kind=None)

### `OperatorMachineService._resolve_write_values()` [私有]
- 位置：第 247-269 行
- 参数：pr
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `OperatorMachineService.list_by_operator()` [公开]
- 位置：第 274-278 行
- 参数：operator_id
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（2 处）：
  - `web/routes/personnel_pages.py:106` [Route] `links = link_svc.list_by_operator(operator_id)`
  - `core/services/scheduler/calendar_admin.py:350` [Service] `return self.operator_calendar_repo.list_by_operator(op_id)`
- **被调用者**（3 个）：`self._normalize_text`, `ValidationError`, `self._normalize_link`

### `OperatorMachineService.list_by_machine()` [公开]
- 位置：第 280-284 行
- 参数：machine_id
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（3 处）：
  - `web/routes/equipment_pages.py:199` [Route] `links = link_svc.list_by_machine(machine_id)`
  - `web/routes/equipment_pages.py:200` [Route] `downtimes = dt_svc.list_by_machine(machine_id, include_cancelled=False)`
  - `core/services/equipment/machine_downtime_service.py:76` [Service] `return self.repo.list_by_machine(mc_id, include_cancelled=include_cancelled)`
- **被调用者**（3 个）：`self._normalize_text`, `ValidationError`, `self._normalize_link`

### `OperatorMachineService.add_link()` [公开]
- 位置：第 286-314 行
- 参数：operator_id, machine_id, skill_level, is_primary
- 返回类型：Name(id='OperatorMachine', ctx=Load())
- **调用者**（2 处）：
  - `web/routes/equipment_pages.py:343` [Route] `svc.add_link(operator_id=operator_id, machine_id=machine_id)`
  - `web/routes/personnel_pages.py:253` [Route] `svc.add_link(operator_id=operator_id, machine_id=machine_id)`
- **被调用者**（11 个）：`self._normalize_text`, `self._ensure_operator_exists`, `self._ensure_machine_exists`, `exists`, `ValidationError`, `BusinessError`, `self._normalize_skill_level_optional`, `self._normalize_yes_no_optional`, `transaction`, `add`, `clear_primary_for_operator`

### `OperatorMachineService.remove_link()` [公开]
- 位置：第 316-324 行
- 参数：operator_id, machine_id
- 返回类型：Constant(value=None, kind=None)
- **调用者**（2 处）：
  - `web/routes/equipment_pages.py:368` [Route] `svc.remove_link(operator_id=operator_id, machine_id=machine_id)`
  - `web/routes/personnel_pages.py:279` [Route] `svc.remove_link(operator_id=operator_id, machine_id=machine_id)`
- **被调用者**（4 个）：`self._normalize_text`, `ValidationError`, `transaction`, `remove`

### `OperatorMachineService.update_link_fields()` [公开]
- 位置：第 326-357 行
- 参数：operator_id, machine_id
- 返回类型：Constant(value=None, kind=None)
- **调用者**（2 处）：
  - `web/routes/equipment_pages.py:354` [Route] `svc.update_link_fields(`
  - `web/routes/personnel_pages.py:265` [Route] `svc.update_link_fields(`
- **被调用者**（9 个）：`self._normalize_text`, `ValidationError`, `exists`, `BusinessError`, `self._normalize_skill_level_optional`, `self._normalize_yes_no_optional`, `transaction`, `update_fields`, `clear_primary_for_operator`

### `OperatorMachineService.preview_import_links()` [公开]
- 位置：第 362-394 行
- 参数：rows, mode
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（4 处）：
  - `web/routes/equipment_excel_links.py:81` [Route] `preview_rows = link_svc.preview_import_links(rows=normalized_rows, mode=mode)`
  - `web/routes/equipment_excel_links.py:141` [Route] `preview_rows = link_svc.preview_import_links(rows=rows, mode=mode)`
  - `web/routes/personnel_excel_links.py:68` [Route] `preview_rows = link_svc.preview_import_links(rows=rows, mode=mode)`
  - `web/routes/personnel_excel_links.py:129` [Route] `preview_rows = link_svc.preview_import_links(rows=rows, mode=mode)`
- **被调用者**（7 个）：`self._detect_optional_columns`, `self._build_existing_link_map`, `set`, `enumerate`, `self._preview_one_row`, `preview.append`, `self._enforce_primary_unique_in_file`

### `OperatorMachineService.apply_import_links()` [公开]
- 位置：第 396-471 行
- 参数：preview_rows, mode
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（2 处）：
  - `web/routes/equipment_excel_links.py:181` [Route] `stats = link_svc.apply_import_links(preview_rows=preview_rows, mode=mode)`
  - `web/routes/personnel_excel_links.py:169` [Route] `stats = link_svc.apply_import_links(preview_rows=preview_rows, mode=mode)`
- **被调用者**（15 个）：`self._detect_optional_columns_from_preview`, `self._build_existing_link_map`, `transaction`, `len`, `delete_all`, `strip`, `existing_map.get`, `self._resolve_write_values`, `exists`, `update_fields`, `add`, `errors_sample.append`, `str`, `clear_primary_for_operator`, `get`

## core/services/scheduler/resource_dispatch_excel.py（Service 层）

### `_auto_width()` [私有]
- 位置：第 10-21 行
- 参数：ws
- 返回类型：Constant(value=None, kind=None)

### `_write_table()` [私有]
- 位置：第 24-34 行
- 参数：ws, headers, rows
- 返回类型：Constant(value=None, kind=None)

### `_detail_headers()` [私有]
- 位置：第 37-58 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_first_present()` [私有]
- 位置：第 61-66 行
- 参数：row
- 返回类型：Name(id='Any', ctx=Load())

### `_yes_no_label()` [私有]
- 位置：第 69-70 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `_build_detail_row()` [私有]
- 位置：第 73-95 行
- 参数：row
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_detail_table_rows()` [私有]
- 位置：第 98-99 行
- 参数：detail_rows
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_calendar_table_rows()` [私有]
- 位置：第 102-110 行
- 参数：calendar_rows
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_summary_pairs()` [私有]
- 位置：第 113-128 行
- 参数：filters, summary
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_write_summary_sheet()` [私有]
- 位置：第 131-139 行
- 参数：wb, filters, summary
- 返回类型：Constant(value=None, kind=None)

### `_write_calendar_sheet()` [私有]
- 位置：第 142-144 行
- 参数：wb, title, headers, rows
- 返回类型：Constant(value=None, kind=None)

### `_write_detail_sheet()` [私有]
- 位置：第 147-149 行
- 参数：wb, title, rows
- 返回类型：Constant(value=None, kind=None)

### `_write_team_scope_sheets()` [私有]
- 位置：第 152-169 行
- 参数：wb, payload
- 返回类型：Constant(value=None, kind=None)

### `_write_resource_scope_sheets()` [私有]
- 位置：第 172-179 行
- 参数：wb, payload
- 返回类型：Constant(value=None, kind=None)

### `build_resource_dispatch_workbook()` [公开]
- 位置：第 182-199 行
- 参数：payload
- 返回类型：Name(id='BytesIO', ctx=Load())
- **调用者**（1 处）：
  - `core/services/scheduler/resource_dispatch_service.py:305` [Service] `buf = build_resource_dispatch_workbook(payload)`
- **被调用者**（11 个）：`Workbook`, `wb.remove`, `_write_summary_sheet`, `BytesIO`, `wb.save`, `buf.seek`, `payload.get`, `str`, `_write_team_scope_sheets`, `_write_resource_scope_sheets`, `filters.get`

## core/services/system/system_config_service.py（Service 层）

### `_normalize_yes_no()` [私有]
- 位置：第 12-18 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())

### `_parse_int()` [私有]
- 位置：第 21-31 行
- 参数：value, field, min_v, max_v
- 返回类型：Name(id='int', ctx=Load())

### `SystemConfigSnapshot.to_dict()` [公开]
- 位置：第 45-55 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（62 处）：
  - `web/routes/equipment_pages.py:216` [Route] `machine=m.to_dict(),`
  - `web/routes/equipment_pages.py:229` [Route] `downtime_rows=[d.to_dict() for d in downtimes],`
  - `web/routes/material.py:27` [Route] `items = [m.to_dict() for m in svc.list()]`
  - `web/routes/material.py:131` [Route] `batch=(selected_batch.to_dict() if selected_batch else None),`
  - `web/routes/personnel_calendar_pages.py:23` [Route] `rows = [c.to_dict() for c in cal_svc.list_operator_calendar(operator_id)]`
  - `web/routes/personnel_calendar_pages.py:48` [Route] `operator=op.to_dict(),`
  - `web/routes/personnel_pages.py:144` [Route] `operator=op.to_dict(),`
  - `web/routes/process_op_types.py:21` [Route] `rows = [x.to_dict() for x in svc.list()]`
  - `web/routes/process_op_types.py:42` [Route] `return render_template("process/op_type_detail.html", title=f"工种详情 - {ot.op_type`
  - `web/routes/process_parts.py:81` [Route] `part = detail["part"].to_dict()`
  - `web/routes/process_parts.py:82` [Route] `ops = [o.to_dict() for o in detail["operations"]]`
  - `web/routes/process_parts.py:83` [Route] `groups = [gr.to_dict() for gr in detail["groups"]]`
  - `web/routes/process_parts.py:112` [Route] `suppliers_map={k: v.to_dict() for k, v in suppliers.items()},`
  - `web/routes/process_suppliers.py:27` [Route] `rows = [x.to_dict() for x in svc.list()]`
  - `web/routes/process_suppliers.py:85` [Route] `supplier=s.to_dict(),`
  - `web/routes/scheduler_batches.py:41` [Route] `**b.to_dict(),`
  - `web/routes/scheduler_batches.py:64` [Route] `latest_history = items[0].to_dict() if items else None`
  - `web/routes/scheduler_batches.py:113` [Route] `**b.to_dict(),`
  - `web/routes/scheduler_batch_detail.py:186` [Route] `d = op.to_dict()`
  - `web/routes/scheduler_batch_detail.py:230` [Route] `batch=b.to_dict(),`
  - `web/routes/scheduler_calendar_pages.py:25` [Route] `rows = [c.to_dict() for c in cal_svc.list_all()]`
  - `web/routes/scheduler_resource_dispatch.py:51` [Route] `for key, value in request.args.to_dict(flat=True).items():`
  - `web/routes/scheduler_resource_dispatch.py:188` [Route] `return redirect(url_for("scheduler.resource_dispatch_page", **request.args.to_di`
  - `web/routes/system_backup.py:38` [Route] `settings=cfg.to_dict(),`
  - `web/routes/system_history.py:35` [Route] `selected = item.to_dict()`
  - `web/routes/system_history.py:42` [Route] `items = [x.to_dict() for x in q.list_recent(limit=limit)]`
  - `web/routes/system_logs.py:52` [Route] `settings=_get_system_cfg_snapshot().to_dict(),`
  - `web/routes/system_utils.py:145` [Route] `d = it.to_dict()`
  - `core/services/common/pandas_backend.py:64` [Service] `raw_rows = df.to_dict(orient="records")`
  - `core/services/equipment/machine_excel_import_service.py:96` [Service] `out = stats.to_dict()`
  - `core/services/material/material_service.py:82` [Service] `self.op_logger.info(module="material", action="create", target_type="material", `
  - `core/services/personnel/operator_excel_import_service.py:90` [Service] `out = stats.to_dict()`
  - `core/services/personnel/resource_team_service.py:74` [Service] `return [team.to_dict() for team in self.list(status=status)]`
  - `core/services/process/op_type_excel_import_service.py:79` [Service] `out = stats.to_dict()`
  - `core/services/process/part_operation_hours_excel_import_service.py:58` [Service] `return stats.to_dict(total_rows=len(preview_rows))`
  - `core/services/process/route_parser.py:57` [Service] `"operations": [x.to_dict() for x in self.operations],`
  - `core/services/process/route_parser.py:77` [Service] `"operations": [x.to_dict() for x in self.operations],`
  - `core/services/process/route_parser.py:78` [Service] `"external_groups": [g.to_dict() for g in self.external_groups],`
  - `core/services/process/supplier_excel_import_service.py:106` [Service] `out = stats.to_dict()`
  - `core/services/scheduler/batch_excel_import.py:101` [Service] `result = stats.to_dict()`
  - `core/services/scheduler/batch_service.py:262` [Service] `self.batch_repo.create(b.to_dict())`
  - `core/services/scheduler/calendar_admin.py:314` [Service] `self.repo.upsert(cal.to_dict())`
  - `core/services/scheduler/calendar_admin.py:325` [Service] `self.repo.upsert(c.to_dict())`
  - `core/services/scheduler/calendar_admin.py:381` [Service] `self.operator_calendar_repo.upsert(cal.to_dict())`
  - `core/services/scheduler/calendar_admin.py:386` [Service] `self.operator_calendar_repo.upsert(c.to_dict())`
  - `core/services/scheduler/calendar_service.py:209` [Service] `result = stats.to_dict()`
  - `core/services/scheduler/config_presets.py:20` [Service] `**base.to_dict(),`
  - `core/services/scheduler/config_presets.py:29` [Service] `**base.to_dict(),`
  - `core/services/scheduler/config_presets.py:37` [Service] `**base.to_dict(),`
  - `core/services/scheduler/config_presets.py:128` [Service] `json.dumps(snap.to_dict(), ensure_ascii=False, sort_keys=True),`
  - `core/services/scheduler/config_presets.py:180` [Service] `payload = json.dumps(snap.to_dict(), ensure_ascii=False, sort_keys=True)`
  - `core/services/scheduler/gantt_contract.py:70` [Service] `return dto.to_dict(include_history=bool(include_history))`
  - `core/services/scheduler/gantt_service.py:164` [Service] `hist_dict = hist.to_dict() if hist else None`
  - `core/services/scheduler/gantt_service.py:206` [Service] `"history": hist.to_dict() if hist else None,`
  - `core/services/scheduler/schedule_optimizer.py:148` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/schedule_optimizer.py:161` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/schedule_optimizer.py:208` [Service] `cfg_snapshot = cfg.to_dict() if hasattr(cfg, "to_dict") else (cfg if isinstance(`
  - `core/services/scheduler/schedule_optimizer_steps.py:96` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/schedule_optimizer_steps.py:121` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/schedule_optimizer_steps.py:198` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/schedule_optimizer_steps.py:223` [Service] `"metrics": metrics.to_dict(),`
  - `core/services/scheduler/schedule_summary.py:233` [Service] `"metrics": best_metrics.to_dict() if best_metrics is not None else None,`
- **被调用者**（1 个）：`int`

### `SystemConfigService.__init__()` [私有]
- 位置：第 73-77 行
- 参数：conn, logger
- 返回类型：无注解

### `SystemConfigService._read_snapshot()` [私有]
- 位置：第 79-110 行
- 参数：backup_keep_days_default
- 返回类型：Name(id='SystemConfigSnapshot', ctx=Load())

### `SystemConfigService.ensure_defaults()` [公开]
- 位置：第 112-135 行
- 参数：backup_keep_days_default
- 返回类型：Constant(value=None, kind=None)
- **调用者**（5 处）：
  - `core/services/scheduler/config_presets.py:156` [Service] `svc.ensure_defaults()`
  - `core/services/scheduler/config_presets.py:225` [Service] `svc.ensure_defaults()`
  - `core/services/scheduler/config_service.py:268` [Service] `self.ensure_defaults()`
  - `core/services/scheduler/config_service.py:313` [Service] `self.ensure_defaults()`
  - `core/services/scheduler/config_service.py:323` [Service] `self.ensure_defaults()`
- **被调用者**（6 个）：`transaction`, `list_all`, `str`, `defaults.items`, `set`, `int`

### `SystemConfigService.get_snapshot()` [公开]
- 位置：第 137-139 行
- 参数：backup_keep_days_default
- 返回类型：Name(id='SystemConfigSnapshot', ctx=Load())
- **调用者**（8 处）：
  - `web/routes/scheduler_batches.py:49` [Route] `cfg = cfg_svc.get_snapshot()`
  - `web/routes/scheduler_batch_detail.py:214` [Route] `prefer_primary_skill = ConfigService(g.db, logger=getattr(g, "app_logger", None)`
  - `web/routes/scheduler_config.py:280` [Route] `cfg = cfg_svc.get_snapshot()`
  - `web/routes/scheduler_config.py:393` [Route] `cur = cfg_svc.get_snapshot()`
  - `web/routes/system_utils.py:135` [Route] `return svc.get_snapshot(backup_keep_days_default=int(current_app.config.get("BAC`
  - `core/services/scheduler/config_presets.py:179` [Service] `snap = svc.get_snapshot()`
  - `core/services/scheduler/schedule_service.py:268` [Service] `cfg = cfg_svc.get_snapshot()`
  - `core/services/system/system_maintenance_service.py:85` [Service] `cfg = cfg_svc.get_snapshot(backup_keep_days_default=int(backup_keep_days_default`
- **被调用者**（2 个）：`self.ensure_defaults`, `self._read_snapshot`

### `SystemConfigService.get_snapshot_readonly()` [公开]
- 位置：第 141-142 行
- 参数：backup_keep_days_default
- 返回类型：Name(id='SystemConfigSnapshot', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（1 个）：`self._read_snapshot`

### `SystemConfigService.get_value()` [公开]
- 位置：第 144-145 行
- 参数：config_key, default
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（15 处）：
  - `core/services/scheduler/config_presets.py:226` [Service] `raw = svc.repo.get_value(svc._preset_key(n), default=None)`
  - `core/services/scheduler/config_service.py:269` [Service] `raw = self.repo.get_value(self.ACTIVE_PRESET_KEY, default=None)`
  - `core/services/scheduler/config_service.py:314` [Service] `return self.repo.get_value(str(config_key), default=str(default) if default is n`
  - `core/services/scheduler/config_snapshot.py:62` [Service] `strategy = repo.get_value("sort_strategy", default=defaults["sort_strategy"]) or`
  - `core/services/scheduler/config_snapshot.py:67` [Service] `raw = repo.get_value(key, default=str(default))`
  - `core/services/scheduler/config_snapshot.py:85` [Service] `raw_enforce = repo.get_value("enforce_ready_default", default=str(defaults["enfo`
  - `core/services/scheduler/config_snapshot.py:88` [Service] `raw_pref = repo.get_value("prefer_primary_skill", default="no")`
  - `core/services/scheduler/config_snapshot.py:91` [Service] `dm = (repo.get_value("dispatch_mode", default=defaults["dispatch_mode"]) or defa`
  - `core/services/scheduler/config_snapshot.py:94` [Service] `dr = (repo.get_value("dispatch_rule", default=defaults["dispatch_rule"]) or defa`
  - `core/services/scheduler/config_snapshot.py:98` [Service] `aa_raw = repo.get_value("auto_assign_enabled", default=defaults["auto_assign_ena`
  - `core/services/scheduler/config_snapshot.py:101` [Service] `ort_raw = repo.get_value("ortools_enabled", default=defaults["ortools_enabled"])`
  - `core/services/scheduler/config_snapshot.py:105` [Service] `raw = repo.get_value(key, default=str(default))`
  - `core/services/scheduler/config_snapshot.py:114` [Service] `algo_mode = (repo.get_value("algo_mode", default=defaults["algo_mode"]) or defau`
  - `core/services/scheduler/config_snapshot.py:118` [Service] `obj = (repo.get_value("objective", default=defaults["objective"]) or defaults["o`
  - `core/services/scheduler/config_snapshot.py:125` [Service] `fw_enabled_raw = repo.get_value("freeze_window_enabled", default=defaults["freez`

### `SystemConfigService.set_value()` [公开]
- 位置：第 147-153 行
- 参数：config_key, value, description
- 返回类型：Constant(value=None, kind=None)
- **调用者**（2 处）：
  - `web/routes/system_plugins.py:30` [Route] `SystemConfigService(g.db, logger=current_app.logger).set_value(key, enabled, des`
  - `web/routes/system_ui_mode.py:27` [Route] `SystemConfigService(g.db, logger=current_app.logger).set_value(`
- **被调用者**（5 个）：`strip`, `ValidationError`, `str`, `transaction`, `set`

### `SystemConfigService.update_backup_settings()` [公开]
- 位置：第 155-178 行
- 参数：auto_backup_enabled, auto_backup_interval_minutes, auto_backup_cleanup_enabled, auto_backup_keep_days, auto_backup_cleanup_interval_minutes
- 返回类型：Constant(value=None, kind=None)
- **调用者**（1 处）：
  - `web/routes/system_backup.py:87` [Route] `svc.update_backup_settings(`
- **被调用者**（5 个）：`_normalize_yes_no`, `_parse_int`, `transaction`, `set`, `str`

### `SystemConfigService.update_logs_settings()` [公开]
- 位置：第 180-192 行
- 参数：auto_log_cleanup_enabled, auto_log_cleanup_keep_days, auto_log_cleanup_interval_minutes
- 返回类型：Constant(value=None, kind=None)
- **调用者**（1 处）：
  - `web/routes/system_logs.py:73` [Route] `svc.update_logs_settings(`
- **被调用者**（5 个）：`_normalize_yes_no`, `_parse_int`, `transaction`, `set`, `str`

## verify_manual_styles.py（Other 层）

### `_prepare_env()` [私有]
- 位置：第 19-25 行
- 参数：tmpdir
- 返回类型：Constant(value=None, kind=None)

### `_load_app()` [私有]
- 位置：第 28-34 行
- 参数：repo_root
- 返回类型：无注解

### `_mode_headers()` [私有]
- 位置：第 37-38 行
- 参数：ui_mode
- 返回类型：Name(id='dict', ctx=Load())

### `_build_url()` [私有]
- 位置：第 41-43 行
- 参数：app, endpoint
- 返回类型：Name(id='str', ctx=Load())

### `_check()` [私有]
- 位置：第 46-51 行
- 参数：condition, message, failures
- 返回类型：Constant(value=None, kind=None)

### `_has_css_rule()` [私有]
- 位置：第 54-55 行
- 参数：css_content, pattern
- 返回类型：Name(id='bool', ctx=Load())

### `main()` [公开]
- 位置：第 58-126 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（15 个）：`print`, `_check`, `css_file.read_text`, `Path`, `_prepare_env`, `_load_app`, `app.test_client`, `css_file.exists`, `sys.exit`, `tempfile.mkdtemp`, `_has_css_rule`, `_build_url`, `client.get`, `resp.get_data`, `_mode_headers`

## web/routes/equipment_pages.py（Route 层）

### `_build_linked_operator_rows()` [私有]
- 位置：第 22-36 行
- 参数：links, operators
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_build_available_operator_rows()` [私有]
- 位置：第 39-53 行
- 参数：operators, linked_operator_ids
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_selected_op_type_name()` [私有]
- 位置：第 56-58 行
- 参数：op_types, machine
- 返回类型：Name(id='Any', ctx=Load())

### `_load_active_downtime_machine_ids()` [私有]
- 位置：第 61-67 行
- 参数：无
- 返回类型：Name(id='set', ctx=Load())

### `_group_machine_operator_links()` [私有]
- 位置：第 70-81 行
- 参数：link_rows
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_build_machine_list_rows()` [私有]
- 位置：第 84-114 行
- 参数：machines
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `list_page()` [公开]
- 位置：第 118-162 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（23 个）：`bp.get`, `MachineService`, `OpTypeService`, `parse_page_args`, `load_team_options`, `build_team_name_map`, `_load_active_downtime_machine_ids`, `OperatorMachineQueryService`, `_group_machine_operator_links`, `_build_machine_list_rows`, `paginate_rows`, `render_template`, `strip`, `svc.list`, `om_q.list_links_with_operator_info`

### `create_machine()` [公开]
- 位置：第 166-186 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（8 个）：`bp.post`, `get`, `MachineService`, `svc.create`, `flash`, `redirect`, `url_for`, `getattr`

### `detail_page()` [公开]
- 位置：第 190-232 行
- 参数：machine_id
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（25 个）：`bp.get`, `MachineService`, `OperatorMachineService`, `MachineDowntimeService`, `OpTypeService`, `OperatorService`, `m_svc.get`, `link_svc.list_by_machine`, `dt_svc.list_by_machine`, `load_team_options`, `build_team_name_map`, `_build_linked_operator_rows`, `_build_available_operator_rows`, `render_template`, `getattr`

### `update_machine()` [公开]
- 位置：第 236-255 行
- 参数：machine_id
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（8 个）：`bp.post`, `get`, `MachineService`, `svc.update`, `flash`, `redirect`, `url_for`, `getattr`

### `set_status()` [公开]
- 位置：第 259-266 行
- 参数：machine_id
- 返回类型：无注解
- **调用者**（2 处）：
  - `web/routes/personnel_pages.py:174` [Route] `op = svc.set_status(operator_id=operator_id, status=status)`
  - `web/routes/personnel_pages.py:208` [Route] `svc.set_status(oid, status=status)`
- **被调用者**（10 个）：`bp.post`, `get`, `MachineService`, `svc.set_status`, `flash`, `redirect`, `ValidationError`, `url_for`, `getattr`, `_machine_status_zh`

### `delete_machine()` [公开]
- 位置：第 270-277 行
- 参数：machine_id
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（7 个）：`bp.post`, `MachineService`, `redirect`, `svc.delete`, `flash`, `url_for`, `getattr`

### `bulk_set_status()` [公开]
- 位置：第 281-308 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（15 个）：`bp.post`, `strip`, `getlist`, `MachineService`, `flash`, `redirect`, `ValidationError`, `join`, `url_for`, `getattr`, `svc.set_status`, `get`, `failed.append`, `len`, `str`

### `bulk_delete()` [公开]
- 位置：第 312-336 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（12 个）：`bp.post`, `getlist`, `MachineService`, `flash`, `redirect`, `join`, `url_for`, `getattr`, `svc.delete`, `failed.append`, `len`, `str`

### `add_link()` [公开]
- 位置：第 340-345 行
- 参数：machine_id
- 返回类型：无注解
- **调用者**（1 处）：
  - `web/routes/personnel_pages.py:253` [Route] `svc.add_link(operator_id=operator_id, machine_id=machine_id)`
- **被调用者**（8 个）：`bp.post`, `get`, `OperatorMachineService`, `svc.add_link`, `flash`, `redirect`, `url_for`, `getattr`

### `update_link()` [公开]
- 位置：第 349-361 行
- 参数：machine_id
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（8 个）：`bp.post`, `get`, `OperatorMachineService`, `svc.update_link_fields`, `flash`, `redirect`, `url_for`, `getattr`

### `remove_link()` [公开]
- 位置：第 365-370 行
- 参数：machine_id
- 返回类型：无注解
- **调用者**（1 处）：
  - `web/routes/personnel_pages.py:279` [Route] `svc.remove_link(operator_id=operator_id, machine_id=machine_id)`
- **被调用者**（8 个）：`bp.post`, `get`, `OperatorMachineService`, `svc.remove_link`, `flash`, `redirect`, `url_for`, `getattr`

## web/routes/scheduler_config.py（Route 层）

### `_resolve_scheduler_manual_md_path()` [私有]
- 位置：第 28-73 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_resolve_manual_back_url()` [私有]
- 位置：第 76-84 行
- 参数：raw_src
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_build_manual_page_url()` [私有]
- 位置：第 87-93 行
- 参数：raw_src, raw_page
- 返回类型：Name(id='str', ctx=Load())

### `_resolve_manual_entry_endpoint()` [私有]
- 位置：第 96-100 行
- 参数：manual_id
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_format_manual_mtime()` [私有]
- 位置：第 103-107 行
- 参数：manual_path
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_load_manual_text_and_mtime()` [私有]
- 位置：第 110-124 行
- 参数：manual_path, candidates
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_build_manual_download_url()` [私有]
- 位置：第 127-136 行
- 参数：manual_path, safe_src, safe_page
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_build_related_manual_links()` [私有]
- 位置：第 139-150 行
- 参数：related_manuals, link_src
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_resolve_page_back_action()` [私有]
- 位置：第 153-158 行
- 参数：raw_page, back_url
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_build_manual_page_view_state()` [私有]
- 位置：第 161-198 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `config_manual_page()` [公开]
- 位置：第 202-243 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（12 个）：`bp.get`, `strip`, `normalize_manual_src`, `_resolve_manual_back_url`, `_resolve_scheduler_manual_md_path`, `_load_manual_text_and_mtime`, `_build_manual_download_url`, `_build_manual_page_view_state`, `render_template`, `build_page_manual_bundle`, `back_url.startswith`, `get`

### `config_manual_download()` [公开]
- 位置：第 247-269 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（11 个）：`bp.get`, `strip`, `normalize_manual_src`, `_resolve_scheduler_manual_md_path`, `flash`, `redirect`, `send_file`, `_build_manual_page_url`, `exception`, `get`, `resolve_manual_id`

### `config_page()` [公开]
- 位置：第 273-300 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（8 个）：`bp.get`, `ConfigService`, `cfg_svc.get_snapshot`, `cfg_svc.get_available_strategies`, `cfg_svc.list_presets`, `cfg_svc.get_active_preset`, `render_template`, `getattr`

### `preset_apply()` [公开]
- 位置：第 304-327 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（15 个）：`bp.post`, `ConfigService`, `_safe_next_url`, `redirect`, `get`, `strip`, `cfg_svc.apply_preset`, `flash`, `getattr`, `url_for`, `cfg_svc.mark_active_preset_custom`, `exception`, `name_text.lower`, `lower`, `str`

### `preset_save()` [公开]
- 位置：第 331-345 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（9 个）：`bp.post`, `ConfigService`, `redirect`, `get`, `cfg_svc.save_preset`, `flash`, `url_for`, `getattr`, `exception`

### `preset_delete()` [公开]
- 位置：第 349-360 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（9 个）：`bp.post`, `ConfigService`, `redirect`, `get`, `cfg_svc.delete_preset`, `flash`, `url_for`, `getattr`, `exception`

### `_apply_basic_scheduler_config()` [私有]
- 位置：第 363-384 行
- 参数：cfg_svc, form
- 返回类型：Constant(value=None, kind=None)

### `_apply_weight_settings_if_present()` [私有]
- 位置：第 387-401 行
- 参数：cfg_svc, form
- 返回类型：Constant(value=None, kind=None)

### `_mark_active_preset_custom_safely()` [私有]
- 位置：第 404-408 行
- 参数：cfg_svc
- 返回类型：Constant(value=None, kind=None)

### `update_config()` [公开]
- 位置：第 412-425 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（10 个）：`bp.post`, `ConfigService`, `redirect`, `_apply_basic_scheduler_config`, `_apply_weight_settings_if_present`, `_mark_active_preset_custom_safely`, `flash`, `url_for`, `getattr`, `exception`

### `restore_config_default()` [公开]
- 位置：第 429-433 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（7 个）：`bp.post`, `ConfigService`, `cfg_svc.restore_default`, `flash`, `redirect`, `url_for`, `getattr`

## web/routes/system_utils.py（Route 层）

### `_safe_next_url()` [私有]
- 位置：第 18-40 行
- 参数：raw
- 返回类型：Name(id='str', ctx=Load())

### `_parse_dt()` [私有]
- 位置：第 43-69 行
- 参数：value, field
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_normalize_time_range()` [私有]
- 位置：第 72-106 行
- 参数：start_raw, end_raw
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_safe_int()` [私有]
- 位置：第 109-121 行
- 参数：value, field, default, min_v, max_v
- 返回类型：Name(id='int', ctx=Load())

### `_get_backup_manager()` [私有]
- 位置：第 124-130 行
- 参数：keep_days
- 返回类型：Name(id='BackupManager', ctx=Load())

### `_get_system_cfg_snapshot()` [私有]
- 位置：第 133-135 行
- 参数：无
- 返回类型：无注解

### `_get_job_state_map()` [私有]
- 位置：第 138-157 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_validate_backup_filename()` [私有]
- 位置：第 160-172 行
- 参数：filename
- 返回类型：Name(id='str', ctx=Load())

## web/ui_mode.py（Other 层）

### `normalize_ui_mode()` [公开]
- 位置：第 29-31 行
- 参数：value
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（1 处）：
  - `web/routes/system_ui_mode.py:19` [Route] `mode = normalize_ui_mode(request.form.get("mode"))`
- **被调用者**（3 个）：`lower`, `strip`, `str`

### `_resolve_manual_endpoint()` [私有]
- 位置：第 34-42 行
- 参数：endpoint
- 返回类型：Name(id='str', ctx=Load())

### `normalize_manual_src()` [公开]
- 位置：第 45-57 行
- 参数：raw
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（3 处）：
  - `web/routes/scheduler_config.py:78` [Route] `输入应为已经过 normalize_manual_src() 过滤的站内相对地址。`
  - `web/routes/scheduler_config.py:210` [Route] `safe_src = normalize_manual_src(raw_src)`
  - `web/routes/scheduler_config.py:253` [Route] `safe_src = normalize_manual_src(raw_src)`
- **被调用者**（6 个）：`strip`, `any`, `text.startswith`, `urlsplit`, `startswith`, `str`

### `_resolve_manual_src()` [私有]
- 位置：第 60-74 行
- 参数：src
- 返回类型：Name(id='str', ctx=Load())

### `get_manual_url()` [公开]
- 位置：第 77-82 行
- 参数：endpoint, src
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（1 处）：
  - `web/routes/scheduler_config.py:145` [Route] `enriched["url"] = get_manual_url(endpoint=entry_endpoint, src=link_src) if entry`
- **被调用者**（5 个）：`_resolve_manual_endpoint`, `normalize_manual_src`, `safe_url_for`, `_resolve_manual_src`, `resolve_manual_id`

### `get_full_manual_section_url()` [公开]
- 位置：第 85-97 行
- 参数：endpoint, src
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（2 处）：
  - `web/routes/scheduler_config.py:147` [Route] `get_full_manual_section_url(endpoint=entry_endpoint, src=link_src) if entry_endp`
  - `web/routes/scheduler_config.py:192` [Route] `"full_manual_section_url": get_full_manual_section_url(endpoint=raw_page, src=li`
- **被调用者**（8 个）：`_resolve_manual_endpoint`, `build_manual_for_endpoint`, `normalize_manual_src`, `safe_url_for`, `strip`, `_resolve_manual_src`, `str`, `manual.get`

### `get_help_card()` [公开]
- 位置：第 100-114 行
- 参数：endpoint, src
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（8 个）：`_resolve_manual_endpoint`, `build_manual_for_endpoint`, `manual.get`, `strip`, `list`, `get_manual_url`, `str`, `help_card.get`

### `init_ui_mode()` [公开]
- 位置：第 117-177 行
- 参数：app, base_dir
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（11 个）：`join`, `str`, `Blueprint`, `app.register_blueprint`, `FileSystemLoader`, `ChoiceLoader`, `overlay`, `setdefault`, `get`, `isdir`, `warning`

### `_read_ui_mode_from_db()` [私有]
- 位置：第 180-193 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `get_ui_mode()` [公开]
- 位置：第 196-220 行
- 参数：default
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（4 个）：`_read_ui_mode_from_db`, `normalize_ui_mode`, `has_request_context`, `get`

### `_get_v2_env()` [私有]
- 位置：第 223-225 行
- 参数：app
- 返回类型：Name(id='Any', ctx=Load())

### `safe_url_for()` [公开]
- 位置：第 228-264 行
- 参数：endpoint
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（6 个）：`has_request_context`, `url_for`, `getattr`, `set`, `logged.add`, `warning`

### `_resolve_template_url_for()` [私有]
- 位置：第 267-275 行
- 参数：无
- 返回类型：无注解

### `render_ui_template()` [公开]
- 位置：第 278-321 行
- 参数：template_name_or_list
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（9 个）：`current_app._get_current_object`, `get_ui_mode`, `context.setdefault`, `app.update_template_context`, `_resolve_template_url_for`, `env.get_or_select_template`, `template.render`, `setdefault`, `_get_v2_env`

## web/viewmodels/page_manuals.py（Other 层）

### `resolve_manual_id()` [公开]
- 位置：第 36-40 行
- 参数：endpoint
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（1 处）：
  - `web/routes/scheduler_config.py:254` [Route] `safe_page = raw_page if raw_page and resolve_manual_id(raw_page) is not None els`
- **被调用者**（3 个）：`strip`, `ENDPOINT_TO_MANUAL_ID.get`, `str`

### `build_manual_payload()` [公开]
- 位置：第 43-57 行
- 参数：manual_id, overrides, include_sections
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（4 个）：`strip`, `MANUAL_TOPICS.get`, `build_manual_payload_from_topic`, `str`

### `build_manual_for_endpoint()` [公开]
- 位置：第 60-69 行
- 参数：endpoint, include_sections
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（5 个）：`strip`, `resolve_manual_id`, `build_manual_payload`, `str`, `ENDPOINT_OVERRIDES.get`

### `get_related_manual_ids()` [公开]
- 位置：第 72-76 行
- 参数：manual_id
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（6 个）：`MANUAL_TOPICS.get`, `_clean_related_ids`, `strip`, `list`, `str`, `topic.get`

### `build_related_manuals()` [公开]
- 位置：第 79-87 行
- 参数：manual_id
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（6 个）：`get_related_manual_ids`, `build_manual_payload`, `related.pop`, `out.append`, `list`, `related.get`

### `build_page_manual_bundle()` [公开]
- 位置：第 90-97 行
- 参数：endpoint
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（1 处）：
  - `web/routes/scheduler_config.py:211` [Route] `bundle = build_page_manual_bundle(raw_page) if raw_page else None`
- **被调用者**（3 个）：`build_manual_for_endpoint`, `build_related_manuals`, `current_manual.get`

### `build_page_fallback_text()` [公开]
- 位置：第 100-103 行
- 参数：endpoint, bundle
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（1 处）：
  - `web/routes/scheduler_config.py:191` [Route] `"fallback_text": build_page_fallback_text(raw_page, bundle=bundle) or manual_tex`
- **被调用者**（2 个）：`build_page_fallback_text_from_bundle`, `build_page_manual_bundle`

## web/viewmodels/page_manuals_common.py（Other 层）

### `_card()` [私有]
- 位置：第 7-11 行
- 参数：title
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_section()` [私有]
- 位置：第 14-18 行
- 参数：title, body_md
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_topic()` [私有]
- 位置：第 21-38 行
- 参数：title, summary, full_manual_anchor, sections, related_manual_ids, help_card
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_expand_fragments()` [私有]
- 位置：第 102-106 行
- 参数：text
- 返回类型：Name(id='str', ctx=Load())

### `_build_full_manual_label()` [私有]
- 位置：第 109-121 行
- 参数：anchor
- 返回类型：Name(id='str', ctx=Load())

### `_clone_help_card()` [私有]
- 位置：第 124-131 行
- 参数：card
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_clone_sections()` [私有]
- 位置：第 134-141 行
- 参数：sections
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_clean_related_ids()` [私有]
- 位置：第 144-153 行
- 参数：items
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_apply_payload_overrides()` [私有]
- 位置：第 156-164 行
- 参数：payload, overrides
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `build_manual_payload_from_topic()` [公开]
- 位置：第 167-184 行
- 参数：manual_id, topic, overrides, include_sections
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（9 个）：`_apply_payload_overrides`, `strip`, `_build_full_manual_label`, `_clone_help_card`, `_clean_related_ids`, `_clone_sections`, `topic.get`, `list`, `str`

### `build_page_fallback_text_from_bundle()` [公开]
- 位置：第 187-202 行
- 参数：bundle
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（5 个）：`strip`, `current.get`, `lines.extend`, `join`, `item.get`

---
- 分析函数/方法数：172
- 找到调用关系：132 处
- 跨层边界风险：8 项
