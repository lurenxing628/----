# 引用链追踪报告（深度 Review 辅助）

> 说明：本报告基于 AST 提取“定义”，并用文本搜索定位“调用点/被调用者”。
> 由于 Python 动态特性与启发式匹配限制，可能存在漏报/误报，仅作为审查线索。
> 建议：对每条调用关系回到源码上下文手工核对。

## scripts/sync_debt_ledger.py（Script 层）

### `current_git_head_sha()` [公开]
- 位置：第 37-46 行
- 参数：无
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`subprocess.run`, `strip`

### `collect_current_test_debt_payload()` [公开]
- 位置：第 49-79 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Tuple(elt
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（7 个）：`dict`, `subprocess.run`, `json.loads`, `isinstance`, `QualityGateError`, `join`, `str`

### `_build_parser()` [私有]
- 位置：第 82-127 行
- 参数：无
- 返回类型：Attribute(value=Name(id='argparse', ctx=Load()), attr='Argum

### `_print_summary()` [私有]
- 位置：第 130-132 行
- 参数：title, payload
- 返回类型：Constant(value=None)

### `_handle_check()` [私有]
- 位置：第 135-149 行
- 参数：_args
- 返回类型：Name(id='int', ctx=Load())

### `_handle_refresh()` [私有]
- 位置：第 152-175 行
- 参数：args
- 返回类型：Name(id='int', ctx=Load())

### `_handle_set_entry_fields()` [私有]
- 位置：第 178-199 行
- 参数：args
- 返回类型：Name(id='int', ctx=Load())

### `_handle_upsert_risk()` [私有]
- 位置：第 202-223 行
- 参数：args
- 返回类型：Name(id='int', ctx=Load())

### `_handle_delete_risk()` [私有]
- 位置：第 226-234 行
- 参数：args
- 返回类型：Name(id='int', ctx=Load())

### `_handle_import_test_debt_baseline()` [私有]
- 位置：第 237-253 行
- 参数：args
- 返回类型：Name(id='int', ctx=Load())

### `main()` [公开]
- 位置：第 256-263 行
- 参数：argv
- 返回类型：Name(id='int', ctx=Load())
- **调用者**（4 处）：
  - `scripts/convert_rotary_shell_unit_excel.py:124` [Script] `raise SystemExit(main())`
  - `scripts/run_quality_gate.py:700` [Script] `raise SystemExit(main())`
  - `tools/collect_full_test_debt.py:314` [Tool] `exitstatus = int(pytest.main(list(args.pytest_args), plugins=[collector]))`
  - `tools/collect_full_test_debt.py:350` [Tool] `raise SystemExit(main())`
- **被调用者**（5 个）：`_build_parser`, `parser.parse_args`, `int`, `args.handler`, `print`

## tools/collect_full_test_debt.py（Tool 层）

### `_now_iso()` [私有]
- 位置：第 26-27 行
- 参数：无
- 返回类型：Name(id='str', ctx=Load())

### `_git_head_sha()` [私有]
- 位置：第 30-42 行
- 参数：无
- 返回类型：Name(id='str', ctx=Load())

### `_longrepr_text()` [私有]
- 位置：第 45-52 行
- 参数：report
- 返回类型：Name(id='str', ctx=Load())

### `_report_nodeid()` [私有]
- 位置：第 55-60 行
- 参数：report
- 返回类型：Name(id='str', ctx=Load())

### `FullTestDebtCollector.__init__()` [私有]
- 位置：第 64-68 行
- 参数：无
- 返回类型：Constant(value=None)

### `FullTestDebtCollector.pytest_collection_modifyitems()` [公开]
- 位置：第 70-71 行
- 参数：session, config, items
- 返回类型：Constant(value=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（1 个）：`str`

### `FullTestDebtCollector.pytest_collectreport()` [公开]
- 位置：第 73-82 行
- 参数：report
- 返回类型：Constant(value=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（5 个）：`append`, `str`, `_report_nodeid`, `_longrepr_text`, `getattr`

### `FullTestDebtCollector.pytest_runtest_logreport()` [公开]
- 位置：第 84-93 行
- 参数：report
- 返回类型：Constant(value=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（5 个）：`append`, `str`, `float`, `_longrepr_text`, `getattr`

### `FullTestDebtCollector.pytest_sessionfinish()` [公开]
- 位置：第 95-96 行
- 参数：session, exitstatus
- 返回类型：Constant(value=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（1 个）：`int`

### `_nodeid_path()` [私有]
- 位置：第 99-100 行
- 参数：nodeid
- 返回类型：Name(id='str', ctx=Load())

### `_is_main_style_nodeid()` [私有]
- 位置：第 103-106 行
- 参数：nodeid
- 返回类型：Name(id='bool', ctx=Load())

### `_belongs_to_required_tests()` [私有]
- 位置：第 109-115 行
- 参数：nodeid, required_paths
- 返回类型：Name(id='bool', ctx=Load())

### `_has_main_style_pollution_signature()` [私有]
- 位置：第 118-124 行
- 参数：text
- 返回类型：Name(id='bool', ctx=Load())

### `_failed_report_texts()` [私有]
- 位置：第 127-137 行
- 参数：reports, collection_errors
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Tuple(elt

### `_classify_failures()` [私有]
- 位置：第 140-162 行
- 参数：reports, collection_errors, required_paths, baseline_kind
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Tuple(elt

### `_summarize()` [私有]
- 位置：第 165-187 行
- 参数：collected_nodeids, reports, collection_errors, classifications
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Tuple(elt

### `_build_payload()` [私有]
- 位置：第 190-220 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Tuple(elt

### `_render_baseline_markdown()` [私有]
- 位置：第 223-253 行
- 参数：payload
- 返回类型：Name(id='str', ctx=Load())

### `_parse_args()` [私有]
- 位置：第 256-282 行
- 参数：argv
- 返回类型：Attribute(value=Name(id='argparse', ctx=Load()), attr='Names

### `_importable_baseline_blockers()` [私有]
- 位置：第 285-297 行
- 参数：payload
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Name(id='

### `main()` [公开]
- 位置：第 300-346 行
- 参数：argv
- 返回类型：Name(id='int', ctx=Load())
- **调用者**（3 处）：
  - `scripts/sync_debt_ledger.py:267` [Script] `raise SystemExit(main())`
  - `scripts/convert_rotary_shell_unit_excel.py:124` [Script] `raise SystemExit(main())`
  - `scripts/run_quality_gate.py:700` [Script] `raise SystemExit(main())`
- **被调用者**（23 个）：`_parse_args`, `FullTestDebtCollector`, `io.StringIO`, `_now_iso`, `_git_head_sha`, `iter_quality_gate_required_tests`, `_build_payload`, `write`, `int`, `contextlib.redirect_stderr`, `_importable_baseline_blockers`, `Path`, `mkdir`, `baseline_path.write_text`, `json.dumps`

## tools/quality_gate_ledger.py（Tool 层）

### `default_ledger()` [公开]
- 位置：第 34-44 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Tuple(elt
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`now_shanghai_iso`, `list`

### `load_ledger()` [公开]
- 位置：第 47-55 行
- 参数：required
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Tuple(elt
- **调用者**（10 处）：
  - `scripts/sync_debt_ledger.py:136` [Script] `ledger = load_ledger(required=True)`
  - `scripts/sync_debt_ledger.py:154` [Script] `current = load_ledger(required=False) if mode in {"migrate-inline-facts", "scan-`
  - `scripts/sync_debt_ledger.py:160` [Script] `current = load_ledger(required=True)`
  - `scripts/sync_debt_ledger.py:179` [Script] `ledger = load_ledger(required=True)`
  - `scripts/sync_debt_ledger.py:203` [Script] `ledger = load_ledger(required=True)`
  - `scripts/sync_debt_ledger.py:227` [Script] `ledger = load_ledger(required=True)`
  - `tools/test_debt_registry.py:269` [Tool] `source_ledger = load_ledger(required=True) if ledger is None else ledger`
  - `tools/quality_gate_operations.py:50` [Tool] `ledger = load_ledger(required=False)`
  - `tools/quality_gate_operations.py:128` [Tool] `ledger = load_ledger(required=False)`
  - `tools/quality_gate_operations.py:213` [Tool] `ledger = load_ledger(required=True)`
- **被调用者**（8 个）：`read_text_file`, `extract_json_code_block`, `validate_ledger`, `sort_ledger`, `exists`, `default_ledger`, `copy.deepcopy`, `QualityGateError`

### `_validate_legacy_ledger_for_test_debt_import()` [私有]
- 位置：第 58-78 行
- 参数：ledger
- 返回类型：Constant(value=None)

### `load_ledger_for_test_debt_import()` [公开]
- 位置：第 81-95 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Tuple(elt
- **调用者**（1 处）：
  - `scripts/sync_debt_ledger.py:238` [Script] `ledger = load_ledger_for_test_debt_import()`
- **被调用者**（11 个）：`read_text_file`, `extract_json_code_block`, `ledger.get`, `QualityGateError`, `exists`, `validate_ledger`, `get`, `sort_ledger`, `_validate_legacy_ledger_for_test_debt_import`, `copy.deepcopy`, `cast`

### `render_ledger_markdown()` [公开]
- 位置：第 98-162 行
- 参数：ledger
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（9 个）：`len`, `render_marked_json_block`, `strip`, `body.replace`, `get`, `str`, `ledger.get`, `textwrap.dedent`, `cast`

### `save_ledger()` [公开]
- 位置：第 165-168 行
- 参数：ledger
- 返回类型：Constant(value=None)
- **调用者**（5 处）：
  - `scripts/sync_debt_ledger.py:164` [Script] `save_ledger(next_ledger)`
  - `scripts/sync_debt_ledger.py:190` [Script] `save_ledger(next_ledger)`
  - `scripts/sync_debt_ledger.py:214` [Script] `save_ledger(next_ledger)`
  - `scripts/sync_debt_ledger.py:229` [Script] `save_ledger(next_ledger)`
  - `scripts/sync_debt_ledger.py:251` [Script] `save_ledger(next_ledger)`
- **被调用者**（5 个）：`sort_ledger`, `validate_ledger`, `write_text_file`, `copy.deepcopy`, `render_ledger_markdown`

### `load_sp02_facts_snapshot()` [公开]
- 位置：第 171-178 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Tuple(elt
- **调用者**（1 处）：
  - `tools/quality_gate_operations.py:51` [Tool] `snapshot = load_sp02_facts_snapshot()`
- **被调用者**（6 个）：`read_text_file`, `extract_json_code_block`, `exists`, `QualityGateError`, `isinstance`, `payload.get`

### `_require_string()` [私有]
- 位置：第 181-184 行
- 参数：value, field_name
- 返回类型：Name(id='str', ctx=Load())

### `_require_entry_status()` [私有]
- 位置：第 187-191 行
- 参数：value, field_name
- 返回类型：Name(id='str', ctx=Load())

### `_require_int()` [私有]
- 位置：第 194-197 行
- 参数：value, field_name
- 返回类型：Name(id='int', ctx=Load())

### `_validate_common_entry()` [私有]
- 位置：第 200-214 行
- 参数：entry, field_prefix
- 返回类型：Constant(value=None)

### `_require_no_untriaged()` [私有]
- 位置：第 217-219 行
- 参数：value, field_name
- 返回类型：Constant(value=None)

### `_validate_test_debt_entry()` [私有]
- 位置：第 222-255 行
- 参数：entry, field_prefix
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Tuple(el

### `_validate_ledger_sections()` [私有]
- 位置：第 258-307 行
- 参数：ledger
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Tuple(el

### `_register_main_entry_id()` [私有]
- 位置：第 310-313 行
- 参数：all_main_ids, entry_id
- 返回类型：Constant(value=None)

### `_validate_oversize_entries()` [私有]
- 位置：第 316-323 行
- 参数：oversize_entries, all_main_ids
- 返回类型：Constant(value=None)

### `_validate_complexity_entries()` [私有]
- 位置：第 326-333 行
- 参数：complexity_entries, all_main_ids
- 返回类型：Constant(value=None)

### `_validate_ui_mode_scope()` [私有]
- 位置：第 336-345 行
- 参数：entry
- 返回类型：Constant(value=None)

### `_validate_silent_fallback_entries()` [私有]
- 位置：第 348-374 行
- 参数：silent_entries, all_main_ids
- 返回类型：Constant(value=None)

### `_validate_test_debt_entries()` [私有]
- 位置：第 377-394 行
- 参数：test_debt_entries, max_registered_xfail
- 返回类型：Constant(value=None)

### `_validate_accepted_risks()` [私有]
- 位置：第 397-422 行
- 参数：accepted_risks, all_main_ids
- 返回类型：Constant(value=None)

### `validate_ledger()` [公开]
- 位置：第 425-439 行
- 参数：ledger
- 返回类型：Constant(value=None)
- **调用者**（3 处）：
  - `tools/test_debt_registry.py:248` [Tool] `validate_ledger(sorted_ledger)`
  - `tools/test_debt_registry.py:261` [Tool] `validate_ledger(ledger)`
  - `tools/quality_gate_operations.py:339` [Tool] `validate_ledger(ledger)`
- **被调用者**（7 个）：`_validate_ledger_sections`, `set`, `_validate_oversize_entries`, `_validate_complexity_entries`, `_validate_silent_fallback_entries`, `_validate_test_debt_entries`, `_validate_accepted_risks`

### `entry_sort_key()` [公开]
- 位置：第 442-449 行
- 参数：entry
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Tuple(el
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（3 个）：`str`, `int`, `entry.get`

### `_ordered_common_fields()` [私有]
- 位置：第 452-465 行
- 参数：entry
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Tuple(elt

### `_ordered_test_debt_entry()` [私有]
- 位置：第 468-487 行
- 参数：entry
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Tuple(elt

### `_ordered_oversize_entries()` [私有]
- 位置：第 490-500 行
- 参数：ledger
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Subscript

### `_ordered_complexity_entries()` [私有]
- 位置：第 503-513 行
- 参数：ledger
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Subscript

### `_ordered_silent_entries()` [私有]
- 位置：第 516-533 行
- 参数：ledger
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Subscript

### `_ordered_test_debt_section()` [私有]
- 位置：第 536-548 行
- 参数：test_debt
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Tuple(elt

### `_ordered_accepted_risks()` [私有]
- 位置：第 551-565 行
- 参数：ledger
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Subscript

### `sort_ledger()` [公开]
- 位置：第 568-583 行
- 参数：ledger
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Tuple(elt
- **调用者**（1 处）：
  - `tools/test_debt_registry.py:247` [Tool] `sorted_ledger = sort_ledger(next_ledger)`
- **被调用者**（12 个）：`cast`, `isinstance`, `QualityGateError`, `_ordered_oversize_entries`, `_ordered_complexity_entries`, `_ordered_test_debt_section`, `_ordered_accepted_risks`, `ledger.get`, `test_debt.get`, `now_shanghai_iso`, `list`, `_ordered_silent_entries`

### `collect_main_entry_ids()` [公开]
- 位置：第 586-593 行
- 参数：ledger
- 返回类型：Subscript(value=Name(id='Set', ctx=Load()), slice=Name(id='s
- **调用者**（1 处）：
  - `tools/quality_gate_operations.py:301` [Tool] `main_ids = collect_main_entry_ids(ledger)`
- **被调用者**（7 个）：`set`, `cast`, `get`, `ids.add`, `str`, `ledger.get`, `entry.get`

### `_ledger_semantics_equal()` [私有]
- 位置：第 596-601 行
- 参数：left, right
- 返回类型：Name(id='bool', ctx=Load())

### `finalize_ledger_update()` [公开]
- 位置：第 604-613 行
- 参数：ledger
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Tuple(elt
- **调用者**（6 处）：
  - `tools/quality_gate_operations.py:123` [Tool] `return finalize_ledger_update(ledger)`
  - `tools/quality_gate_operations.py:170` [Tool] `return finalize_ledger_update(ledger)`
  - `tools/quality_gate_operations.py:263` [Tool] `return finalize_ledger_update(ledger)`
  - `tools/quality_gate_operations.py:288` [Tool] `return finalize_ledger_update(ledger)`
  - `tools/quality_gate_operations.py:326` [Tool] `return finalize_ledger_update(ledger)`
  - `tools/quality_gate_operations.py:335` [Tool] `return finalize_ledger_update(ledger)`
- **被调用者**（8 个）：`load_ledger`, `sort_ledger`, `_ledger_semantics_equal`, `validate_ledger`, `copy.deepcopy`, `now_shanghai_iso`, `current_sorted.get`, `next_ledger.get`

## tools/quality_gate_shared.py（Tool 层）

### `now_shanghai_iso()` [公开]
- 位置：第 317-318 行
- 参数：无
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（9 处）：
  - `scripts/sync_debt_ledger.py:139` [Script] `"checked_at": now_shanghai_iso(),`
  - `scripts/sync_debt_ledger.py:249` [Script] `last_verified_at=now_shanghai_iso(),`
  - `tools/quality_gate_entries.py:35` [Tool] `"last_verified_at": now_shanghai_iso(),`
  - `tools/quality_gate_entries.py:54` [Tool] `merged["last_verified_at"] = now_shanghai_iso()`
  - `tools/quality_gate_entries.py:64` [Tool] `merged["last_verified_at"] = now_shanghai_iso()`
  - `tools/test_debt_registry.py:235` [Tool] `verified_at = last_verified_at or now_shanghai_iso()`
  - `tools/quality_gate_ledger.py:38` [Tool] `"updated_at": now_shanghai_iso(),`
  - `tools/quality_gate_ledger.py:577` [Tool] `"updated_at": ledger.get("updated_at") or now_shanghai_iso(),`
  - `tools/quality_gate_ledger.py:611` [Tool] `next_ledger["updated_at"] = now_shanghai_iso()`
- **被调用者**（3 个）：`isoformat`, `replace`, `datetime.now`

### `repo_rel()` [公开]
- 位置：第 321-322 行
- 参数：path
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`replace`, `relpath`

### `repo_abs()` [公开]
- 位置：第 325-326 行
- 参数：rel_path
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（3 个）：`join`, `replace`, `str`

### `read_text_file()` [公开]
- 位置：第 329-331 行
- 参数：rel_path
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（11 处）：
  - `tools/quality_gate_operations.py:63` [Tool] `current_value = len(read_text_file(path).splitlines())`
  - `tools/quality_gate_operations.py:226` [Tool] `current_value = len(read_text_file(path).splitlines())`
  - `tools/quality_gate_operations.py:348` [Tool] `current_value = len(read_text_file(str(entry.get("path"))).splitlines())`
  - `tools/quality_gate_ledger.py:52` [Tool] `text = read_text_file("开发文档/技术债务治理台账.md")`
  - `tools/quality_gate_ledger.py:84` [Tool] `text = read_text_file("开发文档/技术债务治理台账.md")`
  - `tools/quality_gate_ledger.py:174` [Tool] `text = read_text_file("开发文档/阶段留痕与验收记录.md")`
  - `tools/quality_gate_scan.py:34` [Tool] `source = read_text_file(rel_path)`
  - `tools/quality_gate_scan.py:573` [Tool] `source_lines = read_text_file(rel_path).splitlines()`
  - `tools/quality_gate_scan.py:698` [Tool] `source_lines = read_text_file(rel_path).splitlines()`
  - `tools/quality_gate_scan.py:745` [Tool] `source = read_text_file(rel_path)`
  - `tools/quality_gate_scan.py:776` [Tool] `line_count = len(read_text_file(rel_path).splitlines())`
- **被调用者**（3 个）：`open`, `f.read`, `repo_abs`

### `write_text_file()` [公开]
- 位置：第 334-340 行
- 参数：rel_path, content
- 返回类型：Constant(value=None)
- **调用者**（1 处）：
  - `tools/quality_gate_ledger.py:168` [Tool] `write_text_file("开发文档/技术债务治理台账.md", render_ledger_markdown(sorted_ledger))`
- **被调用者**（5 个）：`repo_abs`, `dirname`, `os.makedirs`, `open`, `f.write`

### `slugify()` [公开]
- 位置：第 343-352 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（11 处）：
  - `tools/quality_gate_entries.py:71` [Tool] `"id": f"oversize:{slugify(path)}",`
  - `tools/quality_gate_entries.py:86` [Tool] `"id": f"complexity:{slugify(path)}-{slugify(symbol)}",`
  - `tools/quality_gate_operations.py:64` [Tool] `existing = find_existing_by_id(oversize_existing, f"oversize:{slugify(path)}")`
  - `tools/quality_gate_operations.py:77` [Tool] `"complexity:{}-{}".format(slugify(item["path"]), slugify(item["symbol"])),`
  - `tools/quality_gate_operations.py:138` [Tool] `existing = find_existing_by_id(oversize_existing, "oversize:{}".format(slugify(i`
  - `tools/quality_gate_operations.py:147` [Tool] `"complexity:{}-{}".format(slugify(item["path"]), slugify(item["symbol"])),`
  - `tools/quality_gate_scan.py:138` [Tool] `return slugify(slice_node.value)`
  - `tools/quality_gate_scan.py:142` [Tool] `return slugify(inner.value)`
  - `tools/quality_gate_scan.py:150` [Tool] `return f"attr:{slugify(target.attr)}"`
  - `tools/quality_gate_scan.py:371` [Tool] `slugify(entry.get("path")),`
  - `tools/quality_gate_scan.py:372` [Tool] `slugify(entry.get("symbol") or "module"),`
- **被调用者**（6 个）：`strip`, `text.replace`, `text.endswith`, `re.sub`, `lower`, `str`

### `collect_py_files()` [公开]
- 位置：第 355-368 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Name(id='
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（10 个）：`sorted`, `repo_abs`, `os.walk`, `set`, `isdir`, `files.append`, `name.endswith`, `name.startswith`, `repo_rel`, `join`

### `collect_globbed_files()` [公开]
- 位置：第 371-378 行
- 参数：patterns
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Name(id='
- **调用者**（4 处）：
  - `tools/quality_gate_operations.py:425` [Tool] `entries = scan_request_service_direct_assembly_entries(collect_globbed_files(REQ`
  - `tools/quality_gate_operations.py:441` [Tool] `return scan_repository_bundle_drift_entries(collect_globbed_files(REPOSITORY_BUN`
  - `tools/quality_gate_scan.py:569` [Tool] `paths = collect_globbed_files(REQUEST_SERVICE_SCAN_SCOPE_PATTERNS)`
  - `tools/quality_gate_scan.py:694` [Tool] `paths = collect_globbed_files(REPOSITORY_BUNDLE_DRIFT_SCOPE_PATTERNS)`
- **被调用者**（8 个）：`sorted`, `join`, `glob.glob`, `set`, `pattern.replace`, `isfile`, `files.append`, `repo_rel`

### `collect_startup_scope_files()` [公开]
- 位置：第 381-382 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Name(id='
- **调用者**（2 处）：
  - `tools/quality_gate_operations.py:130` [Tool] `startup_files = collect_startup_scope_files()`
  - `tools/quality_gate_scan.py:384` [Tool] `entries = scan_silent_fallback_entries(collect_startup_scope_files())`
- **被调用者**（1 个）：`collect_globbed_files`

### `_stable_json_hash()` [私有]
- 位置：第 385-387 行
- 参数：payload
- 返回类型：Name(id='str', ctx=Load())

### `_sha256_text()` [私有]
- 位置：第 390-391 行
- 参数：text
- 返回类型：Name(id='str', ctx=Load())

### `_normalize_command_rows()` [私有]
- 位置：第 394-409 行
- 参数：commands
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Subscript

### `_normalize_source_rows()` [私有]
- 位置：第 412-423 行
- 参数：gate_sources
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Subscript

### `_normalize_required_tests()` [私有]
- 位置：第 426-435 行
- 参数：required_tests
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Name(id='

### `_normalize_collection_proof()` [私有]
- 位置：第 438-460 行
- 参数：collection_proof
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Tuple(elt

### `_normalize_command_receipt_payload()` [私有]
- 位置：第 463-476 行
- 参数：payload
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Tuple(elt

### `_normalize_command_receipt_index()` [私有]
- 位置：第 479-488 行
- 参数：rows
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Subscript

### `parse_pytest_collect_nodeids()` [公开]
- 位置：第 491-505 行
- 参数：output
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Name(id='
- **调用者**（1 处）：
  - `scripts/run_quality_gate.py:464` [Script] `return parse_pytest_collect_nodeids(output)`
- **被调用者**（9 个）：`set`, `splitlines`, `raw_line.strip`, `seen.add`, `nodeids.append`, `str`, `line.startswith`, `line.split`, `token.startswith`

### `collect_current_pytest_nodeids()` [公开]
- 位置：第 508-522 行
- 参数：repo_root
- 返回类型：Subscript(value=Name(id='tuple', ctx=Load()), slice=Tuple(el
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（5 个）：`subprocess.run`, `str`, `int`, `parse_pytest_collect_nodeids`, `os.fspath`

### `_resolve_quality_gate_command_args()` [私有]
- 位置：第 525-530 行
- 参数：command
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Name(id='

### `_command_output_policy()` [私有]
- 位置：第 533-535 行
- 参数：command
- 返回类型：Name(id='str', ctx=Load())

### `_normalize_command_output_for_policy()` [私有]
- 位置：第 538-554 行
- 参数：text
- 返回类型：Name(id='str', ctx=Load())

### `_hash_command_output()` [私有]
- 位置：第 557-558 行
- 参数：text
- 返回类型：Name(id='str', ctx=Load())

### `replay_quality_gate_command_plan()` [公开]
- 位置：第 561-596 行
- 参数：repo_root, commands
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Name(
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（20 个）：`enumerate`, `_normalize_command_rows`, `strip`, `subprocess.run`, `_resolve_quality_gate_command_args`, `int`, `build_quality_gate_receipt_rel_path`, `join`, `_normalize_command_receipt_payload`, `_command_output_policy`, `str`, `os.fspath`, `receipt_rel.replace`, `isfile`, `json.loads`

### `iter_quality_gate_required_tests()` [公开]
- 位置：第 599-600 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Name(id='
- **调用者**（2 处）：
  - `scripts/run_quality_gate.py:38` [Script] `REQUIRED_TEST_ARGS = list(iter_quality_gate_required_tests())`
  - `tools/collect_full_test_debt.py:310` [Tool] `required_paths = iter_quality_gate_required_tests()`
- **被调用者**（2 个）：`list`, `_normalize_required_tests`

### `iter_non_regression_guard_tests()` [公开]
- 位置：第 603-610 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Name(id='
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（4 个）：`basename`, `name.startswith`, `out.append`, `str`

### `build_quality_gate_command_plan()` [公开]
- 位置：第 613-688 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Subscript
- **调用者**（1 处）：
  - `scripts/run_quality_gate.py:562` [Script] `command_plan = build_quality_gate_command_plan()`
- **被调用者**（3 个）：`iter_quality_gate_required_tests`, `join`, `list`

### `build_quality_gate_receipt_rel_path()` [公开]
- 位置：第 691-695 行
- 参数：index, display
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（1 处）：
  - `scripts/run_quality_gate.py:127` [Script] `receipt_rel = build_quality_gate_receipt_rel_path(index, str(command.get("displa`
- **被调用者**（9 个）：`replace`, `slugify`, `rstrip`, `hexdigest`, `join`, `int`, `hashlib.sha256`, `encode`, `str`

### `build_quality_gate_command_receipt()` [公开]
- 位置：第 698-723 行
- 参数：command
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Tuple(elt
- **调用者**（1 处）：
  - `scripts/run_quality_gate.py:130` [Script] `receipt_payload = build_quality_gate_command_receipt(`
- **被调用者**（10 个）：`_command_output_policy`, `_normalize_command_receipt_payload`, `_normalize_command_rows`, `strip`, `int`, `_stable_json_hash`, `list`, `bool`, `_hash_command_output`, `str`

### `build_quality_gate_collection_proof()` [公开]
- 位置：第 726-746 行
- 参数：default_collect_nodeids
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Tuple(elt
- **调用者**（1 处）：
  - `scripts/run_quality_gate.py:468` [Script] `return build_quality_gate_collection_proof(default_collect_nodeids, required_tes`
- **被调用者**（9 个）：`_normalize_required_tests`, `_normalize_collection_proof`, `strip`, `any`, `key_test_rows.append`, `list`, `iter_quality_gate_required_tests`, `str`, `nodeid.startswith`

### `_sha256_file()` [私有]
- 位置：第 749-757 行
- 参数：abs_path
- 返回类型：Name(id='str', ctx=Load())

### `build_quality_gate_source_proof()` [公开]
- 位置：第 760-773 行
- 参数：repo_root
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Subscript
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（11 个）：`abspath`, `_normalize_source_rows`, `join`, `isfile`, `rows.append`, `os.fspath`, `rel_path.replace`, `replace`, `bool`, `_sha256_file`, `str`

### `hash_required_tests_registry()` [公开]
- 位置：第 776-777 行
- 参数：required_tests
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`_stable_json_hash`, `_normalize_required_tests`

### `hash_quality_gate_commands()` [公开]
- 位置：第 780-781 行
- 参数：commands
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`_stable_json_hash`, `_normalize_command_rows`

### `hash_quality_gate_collection_proof()` [公开]
- 位置：第 784-785 行
- 参数：collection_proof
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`_stable_json_hash`, `_normalize_collection_proof`

### `hash_quality_gate_source_proof()` [公开]
- 位置：第 788-789 行
- 参数：gate_sources
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`_stable_json_hash`, `_normalize_source_rows`

### `hash_quality_gate_command_receipts()` [公开]
- 位置：第 792-793 行
- 参数：command_receipts
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`_stable_json_hash`, `_normalize_command_receipt_index`

### `apply_quality_gate_manifest_proof_fields()` [公开]
- 位置：第 796-822 行
- 参数：manifest
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Tuple(elt
- **调用者**（3 处）：
  - `scripts/run_quality_gate.py:540` [Script] `apply_quality_gate_manifest_proof_fields(manifest, repo_root=REPO_ROOT)`
  - `scripts/run_quality_gate.py:664` [Script] `apply_quality_gate_manifest_proof_fields(manifest, repo_root=REPO_ROOT)`
  - `scripts/run_quality_gate.py:693` [Script] `apply_quality_gate_manifest_proof_fields(manifest, repo_root=REPO_ROOT)`
- **被调用者**（14 个）：`dict`, `_normalize_required_tests`, `hash_required_tests_registry`, `_normalize_command_rows`, `hash_quality_gate_commands`, `_normalize_collection_proof`, `hash_quality_gate_collection_proof`, `_normalize_command_receipt_index`, `hash_quality_gate_command_receipts`, `_normalize_source_rows`, `hash_quality_gate_source_proof`, `manifest.get`, `iter_quality_gate_required_tests`, `build_quality_gate_source_proof`

### `_git_rev_parse_path()` [私有]
- 位置：第 825-840 行
- 参数：repo_root
- 返回类型：Name(id='str', ctx=Load())

### `repo_identity()` [公开]
- 位置：第 843-848 行
- 参数：repo_root
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Tuple(elt
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（4 个）：`abspath`, `_git_rev_parse_path`, `os.fspath`, `join`

### `_verify_quality_gate_collection_proof()` [私有]
- 位置：第 851-866 行
- 参数：manifest
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Name(

### `_load_verified_quality_gate_receipt()` [私有]
- 位置：第 869-890 行
- 参数：repo_root, receipt_entry, command
- 返回类型：Subscript(value=Name(id='tuple', ctx=Load()), slice=Tuple(el

### `_verify_receipt_header()` [私有]
- 位置：第 893-908 行
- 参数：receipt, normalized_command
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Name(

### `_verify_receipt_command_fields()` [私有]
- 位置：第 911-921 行
- 参数：receipt, command, normalized_command
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Name(

### `_verify_receipt_output_hashes()` [私有]
- 位置：第 924-942 行
- 参数：receipt, normalized_command
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Name(

### `_verify_quality_gate_receipt_payload()` [私有]
- 位置：第 945-969 行
- 参数：receipt_payload, command
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Name(

### `_verify_quality_gate_command_receipts()` [私有]
- 位置：第 972-1006 行
- 参数：repo_root, manifest
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Name(

### `_verify_manifest_header()` [私有]
- 位置：第 1009-1030 行
- 参数：repo_root, manifest, head_sha
- 返回类型：Subscript(value=Name(id='tuple', ctx=Load()), slice=Tuple(el

### `_verify_manifest_git_status()` [私有]
- 位置：第 1033-1043 行
- 参数：manifest, git_status_lines
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Name(

### `_verify_manifest_clean_finish()` [私有]
- 位置：第 1046-1057 行
- 参数：manifest, manifest_git_status_after, current_git_status
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Name(

### `_verify_manifest_static_proof()` [私有]
- 位置：第 1060-1077 行
- 参数：manifest
- 返回类型：Subscript(value=Name(id='tuple', ctx=Load()), slice=Tuple(el

### `_verify_manifest_collection_and_receipts()` [私有]
- 位置：第 1080-1112 行
- 参数：repo_root, manifest
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Name(

### `_verify_manifest_gate_sources()` [私有]
- 位置：第 1115-1124 行
- 参数：repo_root, manifest
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Name(

### `_verify_manifest_replay()` [私有]
- 位置：第 1127-1144 行
- 参数：repo_root, expected_commands
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Name(

### `verify_quality_gate_manifest()` [公开]
- 位置：第 1147-1182 行
- 参数：无
- 返回类型：Subscript(value=Name(id='tuple', ctx=Load()), slice=Tuple(el
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（7 个）：`_verify_manifest_header`, `_verify_manifest_git_status`, `_verify_manifest_static_proof`, `_verify_manifest_collection_and_receipts`, `_verify_manifest_gate_sources`, `_verify_manifest_replay`, `isinstance`

### `git_status_short_lines()` [公开]
- 位置：第 1185-1196 行
- 参数：repo_root
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Name(id='
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（5 个）：`subprocess.run`, `rstrip`, `str`, `splitlines`, `strip`

### `collect_quality_rule_files()` [公开]
- 位置：第 1199-1200 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Name(id='
- **调用者**（3 处）：
  - `tools/quality_gate_operations.py:399` [Tool] `for entry in scan_silent_fallback_entries(collect_quality_rule_files()):`
  - `tools/quality_gate_operations.py:412` [Tool] `return {str(entry.get("path")): entry for entry in scan_oversize_entries(collect`
  - `tools/quality_gate_operations.py:416` [Tool] `return complexity_scan_map(collect_quality_rule_files())`
- **被调用者**（4 个）：`sorted`, `set`, `collect_py_files`, `collect_startup_scope_files`

### `is_startup_scope_path()` [公开]
- 位置：第 1203-1205 行
- 参数：path
- 返回类型：Name(id='bool', ctx=Load())
- **调用者**（2 处）：
  - `tools/quality_gate_operations.py:168` [Tool] `"entries": remove_entries_by_predicate(silent_existing, lambda entry: is_startup`
  - `tools/quality_gate_operations.py:400` [Tool] `if is_startup_scope_path(str(entry.get("path"))):`
- **被调用者**（3 个）：`replace`, `rel_path.startswith`, `str`

### `ensure_single_marker()` [公开]
- 位置：第 1208-1211 行
- 参数：text, marker, label
- 返回类型：Constant(value=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`text.count`, `QualityGateError`

### `extract_marked_block()` [公开]
- 位置：第 1214-1221 行
- 参数：text, begin_marker, end_marker, label
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（5 个）：`ensure_single_marker`, `text.index`, `strip`, `len`, `QualityGateError`

### `extract_json_code_block()` [公开]
- 位置：第 1224-1236 行
- 参数：text, begin_marker, end_marker, label
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Tuple(elt
- **调用者**（4 处）：
  - `tools/test_debt_registry.py:137` [Tool] `payload = extract_json_code_block(`
  - `tools/quality_gate_ledger.py:53` [Tool] `ledger = extract_json_code_block(text, LEDGER_BEGIN, LEDGER_END, "治理台账")`
  - `tools/quality_gate_ledger.py:85` [Tool] `ledger = extract_json_code_block(text, LEDGER_BEGIN, LEDGER_END, "治理台账")`
  - `tools/quality_gate_ledger.py:175` [Tool] `payload = extract_json_code_block(text, SP02_FACT_BEGIN, SP02_FACT_END, "SP02 事实`
- **被调用者**（7 个）：`extract_marked_block`, `re.search`, `strip`, `QualityGateError`, `json.loads`, `isinstance`, `match.group`

### `render_marked_json_block()` [公开]
- 位置：第 1239-1241 行
- 参数：begin_marker, end_marker, payload
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（1 处）：
  - `tools/quality_gate_ledger.py:104` [Tool] `payload_block = render_marked_json_block(LEDGER_BEGIN, LEDGER_END, ledger)`
- **被调用者**（1 个）：`json.dumps`

## tools/test_debt_registry.py（Tool 层）

### `_require_text()` [私有]
- 位置：第 83-89 行
- 参数：value, field_name
- 返回类型：Name(id='str', ctx=Load())

### `_classification_list()` [私有]
- 位置：第 92-94 行
- 参数：payload, key
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Name(id='

### `baseline_candidate_nodeids()` [公开]
- 位置：第 97-98 行
- 参数：payload
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Name(id='
- **调用者**（1 处）：
  - `scripts/sync_debt_ledger.py:243` [Script] `expected_nodeids=baseline_candidate_nodeids(payload),`
- **被调用者**（2 个）：`sorted`, `_classification_list`

### `_count_or_actual_blocker()` [私有]
- 位置：第 101-104 行
- 参数：payload, counts, key
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Name(

### `_collection_error_blocker()` [私有]
- 位置：第 107-110 行
- 参数：payload, summary
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Name(

### `_baseline_blockers()` [私有]
- 位置：第 113-130 行
- 参数：payload
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Name(id='

### `load_full_test_debt_baseline()` [公开]
- 位置：第 133-144 行
- 参数：path
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Tuple(elt
- **调用者**（1 处）：
  - `scripts/sync_debt_ledger.py:239` [Script] `payload = load_full_test_debt_baseline(str(args.baseline))`
- **被调用者**（6 个）：`Path`, `extract_json_code_block`, `validate_importable_baseline`, `baseline_path.exists`, `QualityGateError`, `baseline_path.read_text`

### `validate_importable_baseline()` [公开]
- 位置：第 147-153 行
- 参数：payload
- 返回类型：Constant(value=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（6 个）：`_baseline_blockers`, `_validate_candidate_nodeids`, `isinstance`, `QualityGateError`, `sorted`, `join`

### `validate_current_candidate_payload()` [公开]
- 位置：第 156-162 行
- 参数：payload
- 返回类型：Constant(value=None)
- **调用者**（1 处）：
  - `scripts/sync_debt_ledger.py:241` [Script] `validate_current_candidate_payload(`
- **被调用者**（7 个）：`_baseline_blockers`, `_validate_candidate_nodeids`, `isinstance`, `QualityGateError`, `sorted`, `join`, `str`

### `_validate_candidate_nodeids()` [私有]
- 位置：第 165-175 行
- 参数：payload
- 返回类型：Constant(value=None)

### `build_test_debt_entries()` [公开]
- 位置：第 178-202 行
- 参数：payload
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Subscript
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（9 个）：`validate_importable_baseline`, `sorted`, `copy.deepcopy`, `validate_test_debt_entry`, `entries.append`, `str`, `get`, `cast`, `payload.get`

### `validate_test_debt_entry()` [公开]
- 位置：第 205-225 行
- 参数：entry
- 返回类型：Constant(value=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（6 个）：`entry.get`, `_require_text`, `str`, `QualityGateError`, `isinstance`, `root.get`

### `build_test_debt_ledger_from_baseline()` [公开]
- 位置：第 228-257 行
- 参数：ledger, payload
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Tuple(el
- **调用者**（1 处）：
  - `scripts/sync_debt_ledger.py:245` [Script] `next_ledger, summary = build_test_debt_ledger_from_baseline(`
- **被调用者**（13 个）：`build_test_debt_entries`, `copy.deepcopy`, `next_ledger.get`, `sort_ledger`, `validate_ledger`, `now_shanghai_iso`, `isinstance`, `existing_test_debt.get`, `QualityGateError`, `str`, `len`, `sorted_ledger.get`, `payload.get`

### `registered_test_debt_entries()` [公开]
- 位置：第 260-265 行
- 参数：ledger
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Subscript
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（5 个）：`validate_ledger`, `dict`, `cast`, `get`, `ledger.get`

### `active_xfail_entries_by_nodeid()` [公开]
- 位置：第 268-274 行
- 参数：ledger
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Tuple(elt
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（5 个）：`load_ledger`, `str`, `dict`, `registered_test_debt_entries`, `entry.get`

### `active_xfail_nodeids()` [公开]
- 位置：第 277-278 行
- 参数：ledger
- 返回类型：Subscript(value=Name(id='Set', ctx=Load()), slice=Name(id='s
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`set`, `active_xfail_entries_by_nodeid`

---
- 分析函数/方法数：144
- 找到调用关系：97 处
- 跨层边界风险：0 项
