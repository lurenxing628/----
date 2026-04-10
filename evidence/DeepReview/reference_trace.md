# 引用链追踪报告（深度 Review 辅助）

## ⚠ 跨层边界风险

- ⚠ find_existing_by_id() 返回 Optional，但 tools/quality_gate_operations.py:56 的调用者未做 None 检查
- ⚠ find_existing_by_id() 返回 Optional，但 tools/quality_gate_operations.py:67 的调用者未做 None 检查
- ⚠ find_existing_by_id() 返回 Optional，但 tools/quality_gate_operations.py:92 的调用者未做 None 检查
- ⚠ find_existing_by_id() 返回 Optional，但 tools/quality_gate_operations.py:130 的调用者未做 None 检查
- ⚠ find_existing_by_id() 返回 Optional，但 tools/quality_gate_operations.py:137 的调用者未做 None 检查

> 说明：本报告基于 AST 提取“定义”，并用文本搜索定位“调用点/被调用者”。
> 由于 Python 动态特性与启发式匹配限制，可能存在漏报/误报，仅作为审查线索。
> 建议：对每条调用关系回到源码上下文手工核对。

## tools/quality_gate_shared.py（Tool 层）

### `now_shanghai_iso()` [公开]
- 位置：第 153-154 行
- 参数：无
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（7 处）：
  - `scripts/sync_debt_ledger.py:85` [Script] `"checked_at": now_shanghai_iso(),`
  - `tools/quality_gate_entries.py:35` [Tool] `"last_verified_at": now_shanghai_iso(),`
  - `tools/quality_gate_entries.py:54` [Tool] `merged["last_verified_at"] = now_shanghai_iso()`
  - `tools/quality_gate_entries.py:64` [Tool] `merged["last_verified_at"] = now_shanghai_iso()`
  - `tools/quality_gate_ledger.py:37` [Tool] `"updated_at": now_shanghai_iso(),`
  - `tools/quality_gate_ledger.py:309` [Tool] `"updated_at": ledger.get("updated_at") or now_shanghai_iso(),`
  - `tools/quality_gate_ledger.py:386` [Tool] `next_ledger["updated_at"] = now_shanghai_iso()`
- **被调用者**（3 个）：`isoformat`, `replace`, `datetime.now`

### `repo_rel()` [公开]
- 位置：第 157-158 行
- 参数：path
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`replace`, `relpath`

### `repo_abs()` [公开]
- 位置：第 161-162 行
- 参数：rel_path
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（3 个）：`join`, `replace`, `str`

### `read_text_file()` [公开]
- 位置：第 165-167 行
- 参数：rel_path
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（8 处）：
  - `tools/quality_gate_ledger.py:50` [Tool] `text = read_text_file("开发文档/技术债务治理台账.md")`
  - `tools/quality_gate_ledger.py:117` [Tool] `text = read_text_file("开发文档/阶段留痕与验收记录.md")`
  - `tools/quality_gate_operations.py:55` [Tool] `current_value = len(read_text_file(path).splitlines())`
  - `tools/quality_gate_operations.py:188` [Tool] `current_value = len(read_text_file(path).splitlines())`
  - `tools/quality_gate_operations.py:307` [Tool] `current_value = len(read_text_file(str(entry.get("path"))).splitlines())`
  - `tools/quality_gate_scan.py:30` [Tool] `source = read_text_file(rel_path)`
  - `tools/quality_gate_scan.py:449` [Tool] `source = read_text_file(rel_path)`
  - `tools/quality_gate_scan.py:480` [Tool] `line_count = len(read_text_file(rel_path).splitlines())`
- **被调用者**（3 个）：`open`, `f.read`, `repo_abs`

### `write_text_file()` [公开]
- 位置：第 170-176 行
- 参数：rel_path, content
- 返回类型：Constant(value=None, kind=None)
- **调用者**（1 处）：
  - `tools/quality_gate_ledger.py:111` [Tool] `write_text_file("开发文档/技术债务治理台账.md", render_ledger_markdown(sorted_ledger))`
- **被调用者**（5 个）：`repo_abs`, `dirname`, `os.makedirs`, `open`, `f.write`

### `slugify()` [公开]
- 位置：第 179-188 行
- 参数：value
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（11 处）：
  - `tools/quality_gate_entries.py:71` [Tool] `"id": f"oversize:{slugify(path)}",`
  - `tools/quality_gate_entries.py:86` [Tool] `"id": f"complexity:{slugify(path)}-{slugify(symbol)}",`
  - `tools/quality_gate_operations.py:56` [Tool] `existing = find_existing_by_id(oversize_existing, f"oversize:{slugify(path)}")`
  - `tools/quality_gate_operations.py:69` [Tool] `"complexity:{}-{}".format(slugify(item["path"]), slugify(item["symbol"])),`
  - `tools/quality_gate_operations.py:130` [Tool] `existing = find_existing_by_id(oversize_existing, "oversize:{}".format(slugify(i`
  - `tools/quality_gate_operations.py:139` [Tool] `"complexity:{}-{}".format(slugify(item["path"]), slugify(item["symbol"])),`
  - `tools/quality_gate_scan.py:130` [Tool] `return slugify(slice_node.value)`
  - `tools/quality_gate_scan.py:134` [Tool] `return slugify(inner.value)`
  - `tools/quality_gate_scan.py:142` [Tool] `return f"attr:{slugify(target.attr)}"`
  - `tools/quality_gate_scan.py:363` [Tool] `slugify(entry.get("path")),`
  - `tools/quality_gate_scan.py:364` [Tool] `slugify(entry.get("symbol") or "module"),`
- **被调用者**（6 个）：`strip`, `text.replace`, `text.endswith`, `re.sub`, `lower`, `str`

### `collect_py_files()` [公开]
- 位置：第 191-204 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（10 个）：`sorted`, `repo_abs`, `os.walk`, `set`, `isdir`, `files.append`, `name.endswith`, `name.startswith`, `repo_rel`, `join`

### `collect_globbed_files()` [公开]
- 位置：第 207-214 行
- 参数：patterns
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（8 个）：`sorted`, `join`, `glob.glob`, `set`, `pattern.replace`, `isfile`, `files.append`, `repo_rel`

### `collect_startup_scope_files()` [公开]
- 位置：第 217-218 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（2 处）：
  - `tools/quality_gate_operations.py:122` [Tool] `startup_files = collect_startup_scope_files()`
  - `tools/quality_gate_scan.py:376` [Tool] `entries = scan_silent_fallback_entries(collect_startup_scope_files())`
- **被调用者**（1 个）：`collect_globbed_files`

### `collect_quality_rule_files()` [公开]
- 位置：第 221-222 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（3 处）：
  - `tools/quality_gate_operations.py:358` [Tool] `for entry in scan_silent_fallback_entries(collect_quality_rule_files()):`
  - `tools/quality_gate_operations.py:371` [Tool] `return {str(entry.get("path")): entry for entry in scan_oversize_entries(collect`
  - `tools/quality_gate_operations.py:375` [Tool] `return complexity_scan_map(collect_quality_rule_files())`
- **被调用者**（4 个）：`sorted`, `set`, `collect_py_files`, `collect_startup_scope_files`

### `is_startup_scope_path()` [公开]
- 位置：第 225-227 行
- 参数：path
- 返回类型：Name(id='bool', ctx=Load())
- **调用者**（2 处）：
  - `tools/quality_gate_operations.py:160` [Tool] `"entries": remove_entries_by_predicate(silent_existing, lambda entry: is_startup`
  - `tools/quality_gate_operations.py:359` [Tool] `if is_startup_scope_path(str(entry.get("path"))):`
- **被调用者**（3 个）：`replace`, `rel_path.startswith`, `str`

### `ensure_single_marker()` [公开]
- 位置：第 230-233 行
- 参数：text, marker, label
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`text.count`, `QualityGateError`

### `extract_marked_block()` [公开]
- 位置：第 236-243 行
- 参数：text, begin_marker, end_marker, label
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（5 个）：`ensure_single_marker`, `text.index`, `strip`, `len`, `QualityGateError`

### `extract_json_code_block()` [公开]
- 位置：第 246-258 行
- 参数：text, begin_marker, end_marker, label
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（2 处）：
  - `tools/quality_gate_ledger.py:51` [Tool] `ledger = extract_json_code_block(text, LEDGER_BEGIN, LEDGER_END, "治理台账")`
  - `tools/quality_gate_ledger.py:118` [Tool] `payload = extract_json_code_block(text, SP02_FACT_BEGIN, SP02_FACT_END, "SP02 事实`
- **被调用者**（7 个）：`extract_marked_block`, `re.search`, `strip`, `QualityGateError`, `json.loads`, `isinstance`, `match.group`

### `render_marked_json_block()` [公开]
- 位置：第 261-263 行
- 参数：begin_marker, end_marker, payload
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（1 处）：
  - `tools/quality_gate_ledger.py:61` [Tool] `payload_block = render_marked_json_block(LEDGER_BEGIN, LEDGER_END, ledger)`
- **被调用者**（1 个）：`json.dumps`

## tools/quality_gate_ledger.py（Tool 层）

### `default_ledger()` [公开]
- 位置：第 33-42 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`now_shanghai_iso`, `list`

### `load_ledger()` [公开]
- 位置：第 45-53 行
- 参数：required
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（9 处）：
  - `scripts/sync_debt_ledger.py:71` [Script] `ledger = load_ledger(required=True)`
  - `scripts/sync_debt_ledger.py:82` [Script] `ledger = load_ledger(required=True)`
  - `scripts/sync_debt_ledger.py:99` [Script] `current = load_ledger(required=False) if mode in {"migrate-inline-facts", "scan-`
  - `scripts/sync_debt_ledger.py:123` [Script] `ledger = load_ledger(required=True)`
  - `scripts/sync_debt_ledger.py:147` [Script] `ledger = load_ledger(required=True)`
  - `scripts/sync_debt_ledger.py:171` [Script] `ledger = load_ledger(required=True)`
  - `tools/quality_gate_operations.py:42` [Tool] `ledger = load_ledger(required=False)`
  - `tools/quality_gate_operations.py:120` [Tool] `ledger = load_ledger(required=False)`
  - `tools/quality_gate_operations.py:180` [Tool] `ledger = load_ledger(required=True)`
- **被调用者**（8 个）：`read_text_file`, `extract_json_code_block`, `validate_ledger`, `sort_ledger`, `exists`, `default_ledger`, `copy.deepcopy`, `QualityGateError`

### `render_ledger_markdown()` [公开]
- 位置：第 56-105 行
- 参数：ledger
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（9 个）：`len`, `render_marked_json_block`, `strip`, `body.replace`, `get`, `str`, `ledger.get`, `textwrap.dedent`, `cast`

### `save_ledger()` [公开]
- 位置：第 108-111 行
- 参数：ledger
- 返回类型：Constant(value=None, kind=None)
- **调用者**（4 处）：
  - `scripts/sync_debt_ledger.py:109` [Script] `save_ledger(next_ledger)`
  - `scripts/sync_debt_ledger.py:134` [Script] `save_ledger(next_ledger)`
  - `scripts/sync_debt_ledger.py:158` [Script] `save_ledger(next_ledger)`
  - `scripts/sync_debt_ledger.py:173` [Script] `save_ledger(next_ledger)`
- **被调用者**（5 个）：`sort_ledger`, `validate_ledger`, `write_text_file`, `copy.deepcopy`, `render_ledger_markdown`

### `load_sp02_facts_snapshot()` [公开]
- 位置：第 114-121 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `tools/quality_gate_operations.py:43` [Tool] `snapshot = load_sp02_facts_snapshot()`
- **被调用者**（6 个）：`read_text_file`, `extract_json_code_block`, `exists`, `QualityGateError`, `isinstance`, `payload.get`

### `_require_string()` [私有]
- 位置：第 124-127 行
- 参数：value, field_name
- 返回类型：Name(id='str', ctx=Load())

### `_require_entry_status()` [私有]
- 位置：第 130-134 行
- 参数：value, field_name
- 返回类型：Name(id='str', ctx=Load())

### `_require_int()` [私有]
- 位置：第 137-140 行
- 参数：value, field_name
- 返回类型：Name(id='int', ctx=Load())

### `_validate_common_entry()` [私有]
- 位置：第 143-157 行
- 参数：entry, field_prefix
- 返回类型：Constant(value=None, kind=None)

### `validate_ledger()` [公开]
- 位置：第 160-276 行
- 参数：ledger
- 返回类型：Constant(value=None, kind=None)
- **调用者**（1 处）：
  - `tools/quality_gate_operations.py:298` [Tool] `validate_ledger(ledger)`
- **被调用者**（17 个）：`ledger.get`, `_require_string`, `silent_fallback.get`, `set`, `enumerate`, `isinstance`, `QualityGateError`, `list`, `_validate_common_entry`, `_require_int`, `str`, `all_main_ids.add`, `entry.get`, `fallback_unique_keys.add`, `risk_ids.add`

### `entry_sort_key()` [公开]
- 位置：第 279-286 行
- 参数：entry
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（3 个）：`str`, `int`, `entry.get`

### `_ordered_common_fields()` [私有]
- 位置：第 289-302 行
- 参数：entry
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `sort_ledger()` [公开]
- 位置：第 305-358 行
- 参数：ledger
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（14 个）：`sorted`, `cast`, `_ordered_common_fields`, `int`, `append`, `entry.get`, `data.setdefault`, `ledger.get`, `now_shanghai_iso`, `list`, `risk.get`, `get`, `str`, `item.get`

### `collect_main_entry_ids()` [公开]
- 位置：第 361-368 行
- 参数：ledger
- 返回类型：Subscript(value=Name(id='Set', ctx=Load()), slice=Index(valu
- **调用者**（1 处）：
  - `tools/quality_gate_operations.py:260` [Tool] `main_ids = collect_main_entry_ids(ledger)`
- **被调用者**（7 个）：`set`, `cast`, `get`, `ids.add`, `str`, `ledger.get`, `entry.get`

### `_ledger_semantics_equal()` [私有]
- 位置：第 371-376 行
- 参数：left, right
- 返回类型：Name(id='bool', ctx=Load())

### `finalize_ledger_update()` [公开]
- 位置：第 379-388 行
- 参数：ledger
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（6 处）：
  - `tools/quality_gate_operations.py:115` [Tool] `return finalize_ledger_update(ledger)`
  - `tools/quality_gate_operations.py:162` [Tool] `return finalize_ledger_update(ledger)`
  - `tools/quality_gate_operations.py:222` [Tool] `return finalize_ledger_update(ledger)`
  - `tools/quality_gate_operations.py:247` [Tool] `return finalize_ledger_update(ledger)`
  - `tools/quality_gate_operations.py:285` [Tool] `return finalize_ledger_update(ledger)`
  - `tools/quality_gate_operations.py:294` [Tool] `return finalize_ledger_update(ledger)`
- **被调用者**（8 个）：`load_ledger`, `sort_ledger`, `_ledger_semantics_equal`, `validate_ledger`, `copy.deepcopy`, `now_shanghai_iso`, `current_sorted.get`, `next_ledger.get`

## tools/quality_gate_scan.py（Tool 层）

### `_ast_tree_for_file()` [私有]
- 位置：第 29-38 行
- 参数：rel_path
- 返回类型：Attribute(value=Name(id='ast', ctx=Load()), attr='AST', ctx=

### `_find_enclosing_symbol()` [私有]
- 位置：第 41-49 行
- 参数：node
- 返回类型：Name(id='str', ctx=Load())

### `_iter_body_nodes()` [私有]
- 位置：第 52-54 行
- 参数：body
- 返回类型：Subscript(value=Name(id='Iterable', ctx=Load()), slice=Index

### `_contains_keyword()` [私有]
- 位置：第 57-62 行
- 参数：text, keywords
- 返回类型：Name(id='bool', ctx=Load())

### `_call_target_name()` [私有]
- 位置：第 65-77 行
- 参数：func
- 返回类型：Name(id='str', ctx=Load())

### `_literal_kind()` [私有]
- 位置：第 80-108 行
- 参数：node
- 返回类型：Name(id='str', ctx=Load())

### `_categorize_call()` [私有]
- 位置：第 111-124 行
- 参数：node
- 返回类型：Name(id='str', ctx=Load())

### `_subscript_key()` [私有]
- 位置：第 127-135 行
- 参数：target
- 返回类型：Name(id='str', ctx=Load())

### `_target_descriptor()` [私有]
- 位置：第 138-145 行
- 参数：target
- 返回类型：Name(id='str', ctx=Load())

### `_is_default_literal()` [私有]
- 位置：第 148-161 行
- 参数：node
- 返回类型：Name(id='bool', ctx=Load())

### `_collect_fallback_actions()` [私有]
- 位置：第 164-183 行
- 参数：body
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_collect_observable_channels()` [私有]
- 位置：第 186-205 行
- 参数：body
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_collect_cleanup_actions()` [私有]
- 位置：第 208-216 行
- 参数：try_node, body
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_collect_control_flow()` [私有]
- 位置：第 219-247 行
- 参数：body
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_is_exception_handler()` [私有]
- 位置：第 250-261 行
- 参数：handler
- 返回类型：Name(id='bool', ctx=Load())

### `_is_legacy_silent_swallow()` [私有]
- 位置：第 264-273 行
- 参数：body
- 返回类型：Name(id='bool', ctx=Load())

### `classify_silent_fallback()` [公开]
- 位置：第 276-303 行
- 参数：try_node, handler
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（10 个）：`_collect_observable_channels`, `_collect_cleanup_actions`, `_collect_fallback_actions`, `_collect_control_flow`, `_iter_body_nodes`, `sorted`, `isinstance`, `set`, `call_categories.append`, `_categorize_call`

### `_fingerprint_for_signature()` [私有]
- 位置：第 306-308 行
- 参数：signature
- 返回类型：Name(id='str', ctx=Load())

### `ui_mode_scope_tag()` [公开]
- 位置：第 311-314 行
- 参数：symbol
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）

### `scan_silent_fallback_entries()` [公开]
- 位置：第 317-354 行
- 参数：paths
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（5 处）：
  - `tools/quality_gate_operations.py:76` [Tool] `silent_scan_entries = scan_silent_fallback_entries(silent_scan_paths)`
  - `tools/quality_gate_operations.py:146` [Tool] `for item in scan_silent_fallback_entries(startup_files):`
  - `tools/quality_gate_operations.py:204` [Tool] `silent_scan = _silent_scan_index(scan_silent_fallback_entries(silent_paths))`
  - `tools/quality_gate_operations.py:319` [Tool] `silent_scan = _silent_scan_index(scan_silent_fallback_entries(silent_paths))`
  - `tools/quality_gate_operations.py:358` [Tool] `for entry in scan_silent_fallback_entries(collect_quality_rule_files()):`
- **被调用者**（21 个）：`sorted`, `_assign_silent_entry_ids`, `set`, `_ast_tree_for_file`, `ast.walk`, `handlers.sort`, `defaultdict`, `classify_silent_fallback`, `_is_legacy_silent_swallow`, `_fingerprint_for_signature`, `entries.append`, `replace`, `isinstance`, `_find_enclosing_symbol`, `handlers.append`

### `_assign_silent_entry_ids()` [私有]
- 位置：第 357-371 行
- 参数：entries
- 返回类型：Constant(value=None, kind=None)

### `validate_startup_samples()` [公开]
- 位置：第 374-434 行
- 参数：entries
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（2 处）：
  - `tools/quality_gate_operations.py:121` [Tool] `validate_startup_samples()`
  - `tools/quality_gate_operations.py:299` [Tool] `sample_summary = validate_startup_samples()`
- **被调用者**（20 个）：`list`, `set`, `sorted`, `scan_silent_fallback_entries`, `int`, `matches.sort`, `matched_kinds.add`, `match.get`, `errors.append`, `QualityGateError`, `len`, `collect_startup_scope_files`, `max`, `min`, `str`

### `complexity_scan_map()` [公开]
- 位置：第 437-470 行
- 参数：paths, include_all
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（4 处）：
  - `tools/quality_gate_operations.py:59` [Tool] `complexity_scan = complexity_scan_map(sorted({str(item).split(":", 1)[0] for ite`
  - `tools/quality_gate_operations.py:192` [Tool] `complexity_scan = complexity_scan_map(complexity_paths)`
  - `tools/quality_gate_operations.py:311` [Tool] `complexity_scan = complexity_scan_map(complexity_paths)`
  - `tools/quality_gate_operations.py:375` [Tool] `return complexity_scan_map(collect_quality_rule_files())`
- **被调用者**（13 个）：`getattr`, `sorted`, `find_spec`, `QualityGateError`, `importlib.import_module`, `callable`, `set`, `read_text_file`, `cast`, `int`, `str`, `replace`, `cc_visit`

### `scan_complexity_entries()` [公开]
- 位置：第 473-474 行
- 参数：paths
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `tools/quality_gate_operations.py:136` [Tool] `for item in scan_complexity_entries(startup_files):`
- **被调用者**（3 个）：`sorted`, `items`, `complexity_scan_map`

### `scan_oversize_entries()` [公开]
- 位置：第 477-483 行
- 参数：paths
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（2 处）：
  - `tools/quality_gate_operations.py:129` [Tool] `for item in scan_oversize_entries(startup_files):`
  - `tools/quality_gate_operations.py:371` [Tool] `return {str(entry.get("path")): entry for entry in scan_oversize_entries(collect`
- **被调用者**（8 个）：`sorted`, `set`, `len`, `splitlines`, `entries.append`, `replace`, `read_text_file`, `str`

## tools/quality_gate_entries.py（Tool 层）

### `build_default_note()` [公开]
- 位置：第 14-21 行
- 参数：source, fallback_kind, scope_tag
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（1 处）：
  - `tools/quality_gate_operations.py:153` [Tool] `entry["notes"] = build_default_note("baseline_scan", fallback_kind=str(item.get(`

### `_default_entry_manual_fields()` [私有]
- 位置：第 24-36 行
- 参数：source, fallback_kind, scope_tag
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_merge_manual_fields()` [私有]
- 位置：第 39-49 行
- 参数：existing, fresh
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_maybe_refresh_last_verified()` [私有]
- 位置：第 52-66 行
- 参数：existing, merged, auto_fields
- 返回类型：Constant(value=None, kind=None)

### `build_oversize_entry()` [公开]
- 位置：第 69-81 行
- 参数：path, current_value, existing
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（3 处）：
  - `tools/quality_gate_operations.py:57` [Tool] `new_oversize_entries.append(build_oversize_entry(path, current_value, existing=e`
  - `tools/quality_gate_operations.py:131` [Tool] `entry = build_oversize_entry(str(item["path"]), int(item["current_value"]), exis`
  - `tools/quality_gate_operations.py:189` [Tool] `refreshed_oversize.append(build_oversize_entry(path, current_value, existing=ent`
- **被调用者**（6 个）：`base.update`, `_merge_manual_fields`, `_maybe_refresh_last_verified`, `int`, `_default_entry_manual_fields`, `slugify`

### `build_complexity_entry()` [公开]
- 位置：第 84-96 行
- 参数：path, symbol, current_value, existing
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（3 处）：
  - `tools/quality_gate_operations.py:72` [Tool] `build_complexity_entry(item["path"], item["symbol"], int(item["current_value"]),`
  - `tools/quality_gate_operations.py:141` [Tool] `entry = build_complexity_entry(str(item["path"]), str(item["symbol"]), int(item[`
  - `tools/quality_gate_operations.py:200` [Tool] `build_complexity_entry(str(item["path"]), str(item["symbol"]), int(item["current`
- **被调用者**（6 个）：`base.update`, `_merge_manual_fields`, `_maybe_refresh_last_verified`, `int`, `_default_entry_manual_fields`, `slugify`

### `build_silent_entry()` [公开]
- 位置：第 99-122 行
- 参数：entry, source, existing
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（3 处）：
  - `tools/quality_gate_operations.py:94` [Tool] `build_silent_entry(matched_entry, source="migrated_from_architecture_fitness_cou`
  - `tools/quality_gate_operations.py:148` [Tool] `entry = build_silent_entry(item, source="baseline_scan", existing=existing)`
  - `tools/quality_gate_operations.py:216` [Tool] `build_silent_entry(silent_scan[key], source=str(entry.get("source") or "baseline`
- **被调用者**（8 个）：`entry.get`, `base.update`, `_merge_manual_fields`, `_maybe_refresh_last_verified`, `int`, `_default_entry_manual_fields`, `str`, `cast`

### `find_existing_by_id()` [公开]
- 位置：第 125-129 行
- 参数：entries, entry_id
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（6 处）：
  - `tools/quality_gate_operations.py:56` [Tool] `existing = find_existing_by_id(oversize_existing, f"oversize:{slugify(path)}")`
  - `tools/quality_gate_operations.py:67` [Tool] `existing = find_existing_by_id(`
  - `tools/quality_gate_operations.py:92` [Tool] `existing = find_existing_by_id(silent_existing, str(matched_entry.get("id")))`
  - `tools/quality_gate_operations.py:130` [Tool] `existing = find_existing_by_id(oversize_existing, "oversize:{}".format(slugify(i`
  - `tools/quality_gate_operations.py:137` [Tool] `existing = find_existing_by_id(`
  - `tools/quality_gate_operations.py:147` [Tool] `existing = find_existing_by_id(silent_existing, str(item.get("id")))`
- **被调用者**（3 个）：`str`, `dict`, `entry.get`

### `remove_entries_by_predicate()` [公开]
- 位置：第 132-133 行
- 参数：entries, predicate
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（3 处）：
  - `tools/quality_gate_operations.py:156` [Tool] `ledger["oversize_allowlist"] = remove_entries_by_predicate(oversize_existing, la`
  - `tools/quality_gate_operations.py:157` [Tool] `ledger["complexity_allowlist"] = remove_entries_by_predicate(complexity_existing`
  - `tools/quality_gate_operations.py:160` [Tool] `"entries": remove_entries_by_predicate(silent_existing, lambda entry: is_startup`
- **被调用者**（2 个）：`dict`, `predicate`

## tools/quality_gate_operations.py（Tool 层）

### `refresh_migrate_inline_facts()` [公开]
- 位置：第 40-115 行
- 参数：ledger
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `scripts/sync_debt_ledger.py:101` [Script] `next_ledger = refresh_migrate_inline_facts(current)`
- **被调用者**（35 个）：`load_sp02_facts_snapshot`, `cast`, `sorted`, `complexity_scan_map`, `scan_silent_fallback_entries`, `finalize_ledger_update`, `load_ledger`, `get`, `set`, `len`, `find_existing_by_id`, `new_oversize_entries.append`, `new_complexity_entries.append`, `silent_counter.items`, `key.split`

### `refresh_scan_startup_baseline()` [公开]
- 位置：第 118-162 行
- 参数：ledger
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `scripts/sync_debt_ledger.py:103` [Script] `next_ledger = refresh_scan_startup_baseline(current)`
- **被调用者**（30 个）：`validate_startup_samples`, `collect_startup_scope_files`, `cast`, `set`, `scan_oversize_entries`, `scan_complexity_entries`, `scan_silent_fallback_entries`, `finalize_ledger_update`, `load_ledger`, `get`, `find_existing_by_id`, `build_oversize_entry`, `entry.setdefault`, `startup_oversize.append`, `build_complexity_entry`

### `_silent_scan_index()` [私有]
- 位置：第 165-175 行
- 参数：entries
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `refresh_auto_fields()` [公开]
- 位置：第 178-222 行
- 参数：ledger
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `scripts/sync_debt_ledger.py:106` [Script] `next_ledger = refresh_auto_fields(current)`
- **被调用者**（24 个）：`cast`, `sorted`, `complexity_scan_map`, `_silent_scan_index`, `finalize_ledger_update`, `load_ledger`, `get`, `str`, `len`, `refreshed_oversize.append`, `format`, `refreshed_complexity.append`, `scan_silent_fallback_entries`, `refreshed_silent.append`, `list`

### `set_entry_fields()` [公开]
- 位置：第 225-247 行
- 参数：ledger, entry_id, updates
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `scripts/sync_debt_ledger.py:133` [Script] `next_ledger = set_entry_fields(ledger, args.id, updates)`
- **被调用者**（8 个）：`finalize_ledger_update`, `cast`, `get`, `updates.items`, `QualityGateError`, `str`, `ledger.get`, `entry.get`

### `upsert_risk()` [公开]
- 位置：第 250-285 行
- 参数：ledger, risk_id, entry_ids, owner, reason, review_after, exit_condition, notes
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `scripts/sync_debt_ledger.py:148` [Script] `next_ledger = upsert_risk(`
- **被调用者**（10 个）：`collect_main_entry_ids`, `cast`, `finalize_ledger_update`, `list`, `accepted_risks.append`, `QualityGateError`, `ledger.get`, `str`, `current.get`, `dict`

### `delete_risk()` [公开]
- 位置：第 288-294 行
- 参数：ledger, risk_id
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `scripts/sync_debt_ledger.py:172` [Script] `next_ledger = delete_risk(ledger, args.id)`
- **被调用者**（8 个）：`cast`, `finalize_ledger_update`, `dict`, `len`, `QualityGateError`, `ledger.get`, `str`, `risk.get`

### `validate_ledger_against_current_scan()` [公开]
- 位置：第 297-329 行
- 参数：ledger
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（2 处）：
  - `scripts/sync_debt_ledger.py:72` [Script] `validate_ledger_against_current_scan(ledger)`
  - `scripts/sync_debt_ledger.py:83` [Script] `summary = validate_ledger_against_current_scan(ledger)`
- **被调用者**（16 个）：`validate_ledger`, `validate_startup_samples`, `str`, `cast`, `complexity_scan_map`, `_silent_scan_index`, `entry.get`, `len`, `format`, `scan_silent_fallback_entries`, `get`, `ledger.get`, `splitlines`, `int`, `QualityGateError`

### `architecture_oversize_allowlist_map()` [公开]
- 位置：第 332-333 行
- 参数：ledger
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（5 个）：`str`, `dict`, `entry.get`, `cast`, `ledger.get`

### `architecture_complexity_allowlist_map()` [公开]
- 位置：第 336-340 行
- 参数：ledger
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（5 个）：`format`, `dict`, `entry.get`, `cast`, `ledger.get`

### `architecture_silent_allowlist_map()` [公开]
- 位置：第 343-347 行
- 参数：ledger
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（6 个）：`str`, `dict`, `entry.get`, `get`, `cast`, `ledger.get`

### `architecture_silent_scan_entries()` [公开]
- 位置：第 350-367 行
- 参数：无
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（10 个）：`scan_silent_fallback_entries`, `sorted`, `collect_quality_rule_files`, `is_startup_scope_path`, `bool`, `str`, `entries.append`, `entry.get`, `dict`, `normalized.pop`

### `architecture_oversize_scan_map()` [公开]
- 位置：第 370-371 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（4 个）：`str`, `entry.get`, `scan_oversize_entries`, `collect_quality_rule_files`

### `architecture_complexity_scan_map()` [公开]
- 位置：第 374-375 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（2 个）：`complexity_scan_map`, `collect_quality_rule_files`

## scripts/run_quality_gate.py（Script 层）

### `_run_command()` [私有]
- 位置：第 34-51 行
- 参数：display, args, capture_output
- 返回类型：Name(id='str', ctx=Load())

### `_parse_ruff_version()` [私有]
- 位置：第 54-61 行
- 参数：text
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_assert_ruff_version()` [私有]
- 位置：第 64-68 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)

### `_state_paths()` [私有]
- 位置：第 71-72 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_load_runtime_state()` [私有]
- 位置：第 75-85 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_coerce_int()` [私有]
- 位置：第 88-91 行
- 参数：value
- 返回类型：Name(id='int', ctx=Load())

### `_describe_runtime_endpoint()` [私有]
- 位置：第 94-97 行
- 参数：host, port
- 返回类型：Name(id='str', ctx=Load())

### `_describe_cleanup_hint()` [私有]
- 位置：第 100-104 行
- 参数：paths
- 返回类型：Name(id='str', ctx=Load())

### `_describe_uncertain_reason()` [私有]
- 位置：第 107-117 行
- 参数：pid_state, health_state, exe_path, port
- 返回类型：Name(id='str', ctx=Load())

### `_pid_signal()` [私有]
- 位置：第 120-140 行
- 参数：payload
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_health_signal()` [私有]
- 位置：第 143-154 行
- 参数：contract
- 返回类型：Subscript(value=Name(id='Tuple', ctx=Load()), slice=Index(va

### `_assert_no_active_runtime()` [私有]
- 位置：第 157-189 行
- 参数：无
- 返回类型：Constant(value=None, kind=None)

### `main()` [公开]
- 位置：第 192-214 行
- 参数：无
- 返回类型：Name(id='int', ctx=Load())
- **调用者**（2 处）：
  - `scripts/convert_rotary_shell_unit_excel.py:124` [Script] `raise SystemExit(main())`
  - `scripts/sync_debt_ledger.py:192` [Script] `raise SystemExit(main())`
- **被调用者**（5 个）：`_assert_no_active_runtime`, `_assert_ruff_version`, `_run_command`, `print`, `join`

## scripts/sync_debt_ledger.py（Script 层）

### `_build_parser()` [私有]
- 位置：第 29-67 行
- 参数：无
- 返回类型：Attribute(value=Name(id='argparse', ctx=Load()), attr='Argum

### `_load_current_ledger_for_write()` [私有]
- 位置：第 70-73 行
- 参数：无
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_print_summary()` [私有]
- 位置：第 76-78 行
- 参数：title, payload
- 返回类型：Constant(value=None, kind=None)

### `_handle_check()` [私有]
- 位置：第 81-94 行
- 参数：_args
- 返回类型：Name(id='int', ctx=Load())

### `_handle_refresh()` [私有]
- 位置：第 97-119 行
- 参数：args
- 返回类型：Name(id='int', ctx=Load())

### `_handle_set_entry_fields()` [私有]
- 位置：第 122-143 行
- 参数：args
- 返回类型：Name(id='int', ctx=Load())

### `_handle_upsert_risk()` [私有]
- 位置：第 146-167 行
- 参数：args
- 返回类型：Name(id='int', ctx=Load())

### `_handle_delete_risk()` [私有]
- 位置：第 170-178 行
- 参数：args
- 返回类型：Name(id='int', ctx=Load())

### `main()` [公开]
- 位置：第 181-188 行
- 参数：argv
- 返回类型：Name(id='int', ctx=Load())
- **调用者**（2 处）：
  - `scripts/convert_rotary_shell_unit_excel.py:124` [Script] `raise SystemExit(main())`
  - `scripts/run_quality_gate.py:219` [Script] `raise SystemExit(main())`
- **被调用者**（5 个）：`_build_parser`, `parser.parse_args`, `int`, `args.handler`, `print`

## web/bootstrap/launcher.py（Bootstrap 层）

### `pick_bind_host()` [公开]
- 位置：第 22-35 行
- 参数：raw_host
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（1 处）：
  - `web/bootstrap/entrypoint.py:180` [Bootstrap] `host = deps.pick_bind_host(raw_host, logger=app.logger)`
- **被调用者**（5 个）：`strip`, `ipaddress.ip_address`, `getattr`, `ValueError`, `logger.warning`

### `_can_bind()` [私有]
- 位置：第 38-53 行
- 参数：host0, port0
- 返回类型：Name(id='bool', ctx=Load())

### `pick_port()` [公开]
- 位置：第 56-94 行
- 参数：host, preferred
- 返回类型：Subscript(value=Name(id='tuple', ctx=Load()), slice=Index(va
- **调用者**（1 处）：
  - `web/bootstrap/entrypoint.py:191` [Bootstrap] `host, port = deps.pick_port(host, preferred_port, logger=app.logger)`
- **被调用者**（7 个）：`socket.socket`, `_can_bind`, `int`, `candidates.append`, `s.bind`, `s.getsockname`, `s.close`

### `_normalize_db_path_for_runtime()` [私有]
- 位置：第 97-101 行
- 参数：db_path
- 返回类型：Name(id='str', ctx=Load())

### `_normalize_abs_dir()` [私有]
- 位置：第 104-108 行
- 参数：path
- 返回类型：Name(id='str', ctx=Load())

### `_compose_runtime_owner()` [私有]
- 位置：第 111-116 行
- 参数：user, domain
- 返回类型：Name(id='str', ctx=Load())

### `current_runtime_owner()` [公开]
- 位置：第 119-127 行
- 参数：无
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（1 处）：
  - `web/bootstrap/entrypoint.py:161` [Bootstrap] `runtime_owner = deps.current_runtime_owner()`
- **被调用者**（5 个）：`strip`, `_compose_runtime_owner`, `str`, `get`, `getpass.getuser`

### `read_shared_data_root_from_registry()` [公开]
- 位置：第 130-154 行
- 参数：无
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（6 个）：`int`, `getattr`, `_normalize_abs_dir`, `winreg.OpenKey`, `winreg.QueryValueEx`, `winreg.CloseKey`

### `resolve_shared_data_root()` [公开]
- 位置：第 157-173 行
- 参数：base_dir
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（1 处）：
  - `web/bootstrap/factory.py:51` [Bootstrap] `data_root = resolve_shared_data_root(base_dir)`
- **被调用者**（9 个）：`_normalize_abs_dir`, `read_shared_data_root_from_registry`, `get`, `abspath`, `bool`, `join`, `isdir`, `str`, `getattr`

### `resolve_prelaunch_log_dir()` [公开]
- 位置：第 176-180 行
- 参数：runtime_dir
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（1 处）：
  - `web/bootstrap/entrypoint.py:160` [Bootstrap] `prelaunch_log_dir = deps.resolve_prelaunch_log_dir(runtime_dir)`
- **被调用者**（4 个）：`_normalize_abs_dir`, `join`, `get`, `resolve_shared_data_root`

### `_runtime_log_dir()` [私有]
- 位置：第 183-184 行
- 参数：runtime_dir
- 返回类型：Name(id='str', ctx=Load())

### `resolve_runtime_state_dir()` [公开]
- 位置：第 187-195 行
- 参数：runtime_dir, cfg_log_dir
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（4 个）：`abspath`, `_runtime_log_dir`, `strip`, `str`

### `_resolve_runtime_state_dir_for_read()` [私有]
- 位置：第 198-212 行
- 参数：runtime_dir_or_state_dir
- 返回类型：Name(id='str', ctx=Load())

### `_runtime_dir_from_state_dir()` [私有]
- 位置：第 215-221 行
- 参数：state_dir
- 返回类型：Name(id='str', ctx=Load())

### `_resolve_runtime_stop_context()` [私有]
- 位置：第 224-231 行
- 参数：runtime_dir_or_state_dir
- 返回类型：Subscript(value=Name(id='tuple', ctx=Load()), slice=Index(va

### `_runtime_log_mirror_dir()` [私有]
- 位置：第 234-239 行
- 参数：runtime_dir, cfg_log_dir
- 返回类型：Name(id='str', ctx=Load())

### `_state_contract_paths()` [私有]
- 位置：第 242-248 行
- 参数：state_dir
- 返回类型：Subscript(value=Name(id='tuple', ctx=Load()), slice=Index(va

### `_runtime_lock_path()` [私有]
- 位置：第 251-252 行
- 参数：state_dir
- 返回类型：Name(id='str', ctx=Load())

### `_launch_error_path()` [私有]
- 位置：第 255-256 行
- 参数：state_dir
- 返回类型：Name(id='str', ctx=Load())

### `resolve_runtime_state_paths()` [公开]
- 位置：第 259-276 行
- 参数：runtime_dir_or_state_dir
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `scripts/run_quality_gate.py:72` [Script] `return launcher.resolve_runtime_state_paths(REPO_ROOT)`
- **被调用者**（4 个）：`_resolve_runtime_state_dir_for_read`, `_state_contract_paths`, `_runtime_lock_path`, `_launch_error_path`

### `_write_runtime_state_triplet()` [私有]
- 位置：第 279-289 行
- 参数：state_dir, host, port, db_for_runtime
- 返回类型：Constant(value=None, kind=None)

### `_write_key_value_file()` [私有]
- 位置：第 292-301 行
- 参数：path, data
- 返回类型：Constant(value=None, kind=None)

### `_read_key_value_file()` [私有]
- 位置：第 304-322 行
- 参数：path
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `_pid_exists()` [私有]
- 位置：第 325-352 行
- 参数：pid
- 返回类型：Name(id='bool', ctx=Load())

### `runtime_pid_exists()` [公开]
- 位置：第 355-358 行
- 参数：pid
- 返回类型：Name(id='bool', ctx=Load())
- **调用者**（1 处）：
  - `scripts/run_quality_gate.py:130` [Script] `pid_exists = bool(launcher.runtime_pid_exists(pid))`
- **被调用者**（1 个）：`_pid_exists`

### `runtime_pid_matches_executable()` [公开]
- 位置：第 361-367 行
- 参数：pid, expected_exe_path
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（1 处）：
  - `scripts/run_quality_gate.py:135` [Script] `pid_match = launcher.runtime_pid_matches_executable(pid, exe_path)`
- **被调用者**（1 个）：`_pid_matches_contract`

### `probe_runtime_health()` [公开]
- 位置：第 370-373 行
- 参数：host, port, timeout_s
- 返回类型：Name(id='bool', ctx=Load())
- **调用者**（1 处）：
  - `scripts/run_quality_gate.py:153` [Script] `healthy = bool(launcher.probe_runtime_health(host, port, timeout_s=1.0))`
- **被调用者**（1 个）：`_probe_runtime_health`

### `RuntimeLockError.__init__()` [私有]
- 位置：第 377-383 行
- 参数：message
- 返回类型：无注解

### `read_runtime_lock()` [公开]
- 位置：第 386-401 行
- 参数：runtime_dir_or_state_dir
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（1 处）：
  - `scripts/run_quality_gate.py:80` [Script] `lock = launcher.read_runtime_lock(REPO_ROOT)`
- **被调用者**（7 个）：`_resolve_runtime_state_dir_for_read`, `_runtime_lock_path`, `_read_key_value_file`, `dict`, `exists`, `int`, `payload.get`

### `_is_runtime_lock_active()` [私有]
- 位置：第 404-418 行
- 参数：lock_payload, expected_exe_path
- 返回类型：Name(id='bool', ctx=Load())

### `acquire_runtime_lock()` [公开]
- 位置：第 421-481 行
- 参数：runtime_dir, cfg_log_dir
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val
- **调用者**（1 处）：
  - `web/bootstrap/entrypoint.py:206` [Bootstrap] `deps.acquire_runtime_lock(`
- **被调用者**（22 个）：`resolve_runtime_state_dir`, `os.makedirs`, `_runtime_lock_path`, `strip`, `range`, `RuntimeLockError`, `int`, `time.strftime`, `abspath`, `os.getpid`, `time.gmtime`, `os.open`, `str`, `_is_runtime_lock_active`, `os.fdopen`

### `release_runtime_lock()` [公开]
- 位置：第 484-501 行
- 参数：runtime_dir_or_state_dir, expected_pid
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（6 个）：`read_runtime_lock`, `int`, `os.remove`, `existing.get`, `str`, `os.getpid`

### `write_launch_error()` [公开]
- 位置：第 504-510 行
- 参数：runtime_dir, message, cfg_log_dir
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（3 处）：
  - `web/bootstrap/entrypoint.py:171` [Bootstrap] `deps.write_launch_error(runtime_dir, f"应用启动失败：{e}", prelaunch_log_dir)`
  - `web/bootstrap/entrypoint.py:214` [Bootstrap] `deps.write_launch_error(runtime_dir, str(e), prelaunch_log_dir)`
  - `web/bootstrap/entrypoint.py:236` [Bootstrap] `deps.write_launch_error(runtime_dir, f"写入运行时契约失败：{e}", app.config.get("LOG_DIR")`
- **被调用者**（7 个）：`resolve_runtime_state_dir`, `os.makedirs`, `_launch_error_path`, `open`, `f.write`, `strip`, `str`

### `clear_launch_error()` [公开]
- 位置：第 513-521 行
- 参数：runtime_dir_or_state_dir
- 返回类型：Constant(value=None, kind=None)
- **调用者**（1 处）：
  - `web/bootstrap/entrypoint.py:163` [Bootstrap] `deps.clear_launch_error(prelaunch_log_dir)`
- **被调用者**（3 个）：`_resolve_runtime_state_dir_for_read`, `_launch_error_path`, `os.remove`

### `write_runtime_host_port_files()` [公开]
- 位置：第 524-552 行
- 参数：runtime_dir, cfg_log_dir, host, port, db_path
- 返回类型：Constant(value=None, kind=None)
- **调用者**（1 处）：
  - `web/bootstrap/entrypoint.py:115` [Bootstrap] `deps.write_runtime_host_port_files(`
- **被调用者**（8 个）：`_normalize_db_path_for_runtime`, `resolve_runtime_state_dir`, `os.makedirs`, `_write_runtime_state_triplet`, `_runtime_log_mirror_dir`, `_state_contract_paths`, `logger.info`, `int`

### `default_chrome_profile_dir()` [公开]
- 位置：第 555-559 行
- 参数：runtime_dir
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（1 处）：
  - `web/bootstrap/entrypoint.py:134` [Bootstrap] `chrome_profile_dir=deps.default_chrome_profile_dir(runtime_dir),`
- **被调用者**（4 个）：`strip`, `join`, `str`, `get`

### `_runtime_contract_path()` [私有]
- 位置：第 562-563 行
- 参数：state_dir
- 返回类型：Name(id='str', ctx=Load())

### `_runtime_contract_payload()` [私有]
- 位置：第 566-608 行
- 参数：runtime_dir, host, port
- 返回类型：Subscript(value=Name(id='Dict', ctx=Load()), slice=Index(val

### `write_runtime_contract_file()` [公开]
- 位置：第 611-662 行
- 参数：runtime_dir, host, port
- 返回类型：Name(id='str', ctx=Load())
- **调用者**（1 处）：
  - `web/bootstrap/entrypoint.py:123` [Bootstrap] `deps.write_runtime_contract_file(`
- **被调用者**（10 个）：`_runtime_contract_payload`, `resolve_runtime_state_dir`, `os.makedirs`, `_runtime_contract_path`, `_runtime_log_mirror_dir`, `open`, `json.dump`, `f.write`, `logger.info`, `f2.write`

### `read_runtime_contract()` [公开]
- 位置：第 665-691 行
- 参数：runtime_dir
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index
- **调用者**（1 处）：
  - `scripts/run_quality_gate.py:79` [Script] `contract = launcher.read_runtime_contract(REPO_ROOT)`
- **被调用者**（8 个）：`_resolve_runtime_state_dir_for_read`, `_runtime_contract_path`, `exists`, `isinstance`, `int`, `open`, `json.load`, `payload.get`

### `delete_runtime_contract_files()` [公开]
- 位置：第 694-735 行
- 参数：runtime_dir
- 返回类型：Constant(value=None, kind=None)
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（16 个）：`_resolve_runtime_state_dir_for_read`, `_runtime_contract_path`, `isinstance`, `paths.extend`, `open`, `json.load`, `strip`, `os.remove`, `abspath`, `payload.get`, `join`, `str`, `_runtime_log_dir`, `normcase`, `log_dirs.append`

### `_build_shutdown_url()` [私有]
- 位置：第 738-749 行
- 参数：contract
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_request_runtime_shutdown()` [私有]
- 位置：第 752-766 行
- 参数：contract, timeout_s
- 返回类型：Name(id='bool', ctx=Load())

### `_probe_runtime_health()` [私有]
- 位置：第 769-781 行
- 参数：host, port, timeout_s
- 返回类型：Name(id='bool', ctx=Load())

### `_run_powershell_text()` [私有]
- 位置：第 784-803 行
- 参数：script, timeout_s
- 返回类型：Subscript(value=Name(id='tuple', ctx=Load()), slice=Index(va

### `_query_process_executable_path()` [私有]
- 位置：第 806-836 行
- 参数：pid
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_pid_matches_contract()` [私有]
- 位置：第 839-848 行
- 参数：pid, expected_exe_path
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `_kill_runtime_pid()` [私有]
- 位置：第 851-870 行
- 参数：pid
- 返回类型：Name(id='bool', ctx=Load())

### `_list_aps_chrome_pids()` [私有]
- 位置：第 873-923 行
- 参数：profile_dir
- 返回类型：Subscript(value=Name(id='Optional', ctx=Load()), slice=Index

### `stop_aps_chrome_processes()` [公开]
- 位置：第 926-947 行
- 参数：profile_dir, logger
- 返回类型：Name(id='bool', ctx=Load())
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（5 个）：`strip`, `_list_aps_chrome_pids`, `str`, `_kill_runtime_pid`, `logger.warning`

### `_stop_aps_chrome_if_requested()` [私有]
- 位置：第 950-958 行
- 参数：stop_aps_chrome, profile_dir
- 返回类型：Name(id='bool', ctx=Load())

### `stop_runtime_from_dir()` [公开]
- 位置：第 961-1034 行
- 参数：runtime_dir
- 返回类型：Name(id='int', ctx=Load())
- **调用者**（1 处）：
  - `web/bootstrap/entrypoint.py:153` [Bootstrap] `deps.stop_runtime_from_dir(`
- **被调用者**（25 个）：`_resolve_runtime_stop_context`, `read_runtime_contract`, `int`, `strip`, `_request_runtime_shutdown`, `_pid_matches_contract`, `normcase`, `join`, `delete_runtime_contract_files`, `time.time`, `max`, `time.sleep`, `abspath`, `_kill_runtime_pid`, `exists`

---
- 分析函数/方法数：153
- 找到调用关系：124 处
- 跨层边界风险：5 项
