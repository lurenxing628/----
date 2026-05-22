from __future__ import annotations

import json
from textwrap import dedent

import tools.quality_gate_operations as ops_mod
import tools.quality_gate_scan as scan_mod
import tools.quality_gate_shared as shared_mod


def _architecture_fact(
    path,
    *,
    line_count=0,
    silent_entries=None,
    complexity_entries=None,
    request_entries=None,
    repository_entries=None,
):
    return {
        "schema_version": 1,
        "path": path,
        "fact_kinds": ["silent", "complexity", "request", "repository"],
        "line_count": line_count,
        "silent_fallback_handlers_without_global_id": [
            {key: value for key, value in dict(entry).items() if key != "id"}
            for entry in list(silent_entries or [])
            if str(entry.get("path")) == path
        ],
        "complexity_blocks_all": [
            dict(entry)
            for entry in list(complexity_entries or [])
            if str(entry.get("path")) == path
        ],
        "request_service_direct_assembly_entries": [
            dict(entry)
            for entry in list(request_entries or [])
            if str(entry.get("path")) == path
        ],
        "repository_bundle_drift_entries": [
            dict(entry)
            for entry in list(repository_entries or [])
            if str(entry.get("path")) == path
        ],
    }


def _patch_sources(monkeypatch, source_map):
    monkeypatch.setattr(scan_mod, "read_text_file", lambda rel_path: source_map[str(rel_path)])


def test_scan_context_reuses_source_lines_and_ast(monkeypatch) -> None:
    rel_path = "tmp/context_sample.py"
    reads = []
    monkeypatch.setattr(
        scan_mod,
        "read_text_file",
        lambda path: reads.append(str(path)) or "def f():\n    return 1\n",
    )

    context = scan_mod.ScanContext()

    assert context.read_text(rel_path) == "def f():\n    return 1\n"
    assert context.source_lines(rel_path) == ["def f():", "    return 1"]
    assert context.read_text(rel_path) == "def f():\n    return 1\n"
    assert context.ast_tree(rel_path) is context.ast_tree(rel_path)
    assert reads == [rel_path]


def test_scan_context_is_single_snapshot_for_one_scan_pass() -> None:
    rel_path = "tmp/context_snapshot_sample.py"
    sources = iter(
        (
            "def f():\n    return 1\n",
            "def f():\n    return 2\n",
        )
    )
    context = scan_mod.ScanContext(read_text=lambda _path: next(sources))

    assert context.read_text(rel_path) == "def f():\n    return 1\n"
    assert context.read_text(rel_path) == "def f():\n    return 1\n"
    assert scan_mod.ScanContext(read_text=lambda _path: "def f():\n    return 2\n").read_text(rel_path) == (
        "def f():\n    return 2\n"
    )


def test_request_service_scan_reads_each_source_once(monkeypatch) -> None:
    rel_path = "tmp/request_gate_single_read_sample.py"
    source = dedent(
        """
        from somewhere import BatchService

        def build():
            BatchService(g.db, logger=None)
        """
    ).strip()
    reads = []
    monkeypatch.setattr(scan_mod, "read_text_file", lambda path: reads.append(str(path)) or source)

    entries = scan_mod.scan_request_service_direct_assembly_entries([rel_path])

    assert [(entry["rule"], entry["target"], entry["line"]) for entry in entries] == [
        ("service_or_repository_g_db", "BatchService", 4)
    ]
    assert reads == [rel_path]


def test_scan_context_can_be_shared_across_scanners_without_rereading(monkeypatch) -> None:
    rel_path = "tmp/shared_context_scan_sample.py"
    source = dedent(
        """
        from somewhere import BatchService

        class Demo:
            def bad(self):
                return self.repos.batch_repo

        def build():
            BatchService(g.db, logger=None)
        """
    ).strip()
    reads = []
    monkeypatch.setattr(scan_mod, "read_text_file", lambda path: reads.append(str(path)) or source)
    context = scan_mod.ScanContext()

    request_entries = scan_mod.scan_request_service_direct_assembly_entries([rel_path], context=context)
    repository_entries = scan_mod.scan_repository_bundle_drift_entries([rel_path], context=context)

    assert [(entry["rule"], entry["target"]) for entry in request_entries] == [
        ("service_or_repository_g_db", "BatchService")
    ]
    assert any(entry["chain"] == "self.repos.batch_repo" for entry in repository_entries)
    assert reads == [rel_path]


def test_repository_bundle_scan_skips_ast_when_source_has_no_repos_token(monkeypatch) -> None:
    rel_path = "tmp/repository_bundle_unrelated.py"
    _patch_sources(
        monkeypatch,
        {
            rel_path: dedent(
                """
                def build():
                    return "普通文件"
                """
            ).strip(),
        },
    )

    def _fail_ast_parse(_rel_path, _source):
        raise AssertionError("unrelated repository bundle files should not parse AST")

    monkeypatch.setattr(scan_mod, "_ast_tree_for_source", _fail_ast_parse)

    assert scan_mod.scan_repository_bundle_drift_entries([rel_path]) == []


def test_repository_bundle_scan_keeps_public_repos_chain_and_alias(monkeypatch) -> None:
    rel_path = "tmp/repository_public_repos_sample.py"
    _patch_sources(
        monkeypatch,
        {
            rel_path: dedent(
                """
                class Demo:
                    def bad(self):
                        bundle = self.repos
                        return bundle.batch_repo

                    def also_bad(self):
                        return self.repos.machine_repo
                """
            ).strip(),
        },
    )

    entries = scan_mod.scan_repository_bundle_drift_entries([rel_path])

    assert {entry["line"] for entry in entries} == {3, 4, 7}
    assert any(entry["chain"] == "self.repos" and entry["line"] == 3 for entry in entries)
    assert any(entry["resolved_chain"] == "self.repos.batch_repo" for entry in entries)
    assert any(entry["chain"] == "self.repos.machine_repo" for entry in entries)


def test_request_service_scan_flags_keyword_conn_and_alias_calls(monkeypatch) -> None:
    rel_path = "tmp/request_gate_sample.py"
    _patch_sources(
        monkeypatch,
        {
            rel_path: dedent(
                """
                from somewhere import BatchService

                ServiceAlias = BatchService

                def build():
                    local_alias = ServiceAlias
                    local_alias(conn=g.db, logger=None)
                    local_alias(conn=conn, logger=None)
                """
            ).strip(),
        },
    )

    entries = scan_mod.scan_request_service_direct_assembly_entries([rel_path])

    assert [entry["rule"] for entry in entries] == [
        "service_or_repository_g_db",
        "service_or_repository_conn",
    ]
    assert [entry["target"] for entry in entries] == ["BatchService", "BatchService"]
    assert [entry["line"] for entry in entries] == [7, 8]


def test_request_service_scan_flags_import_from_as_alias(monkeypatch) -> None:
    rel_path = "tmp/request_gate_import_from_as_sample.py"
    _patch_sources(
        monkeypatch,
        {
            rel_path: dedent(
                """
                from somewhere import BatchService as BS
                from somewhere import get_excel_backend as build_backend

                def build():
                    BS(g.db, logger=None)
                    build_backend()
                """
            ).strip(),
        },
    )

    entries = scan_mod.scan_request_service_direct_assembly_entries([rel_path])

    assert [(entry["rule"], entry["target"], entry["line"]) for entry in entries] == [
        ("service_or_repository_g_db", "BatchService", 5),
        ("get_excel_backend", "get_excel_backend", 6),
    ]


def test_request_service_scan_keeps_module_import_alias_detection(monkeypatch) -> None:
    rel_path = "tmp/request_gate_import_module_alias_sample.py"
    _patch_sources(
        monkeypatch,
        {
            rel_path: dedent(
                """
                import somewhere as svc_mod

                def build():
                    svc_mod.BatchService(g.db, logger=None)
                """
            ).strip(),
        },
    )

    entries = scan_mod.scan_request_service_direct_assembly_entries([rel_path])

    assert [(entry["rule"], entry["target"], entry["line"]) for entry in entries] == [("service_or_repository_g_db", "BatchService", 4)]


def test_request_service_scan_flags_g_db_local_alias_for_service_and_helper(monkeypatch) -> None:
    rel_path = "tmp/request_gate_local_db_alias_sample.py"
    _patch_sources(
        monkeypatch,
        {
            rel_path: dedent(
                """
                from somewhere import BatchService

                def helper_builder(conn):
                    return conn

                def build():
                    db = g.db
                    helper_builder(db)
                    BatchService(db, logger=None)
                """
            ).strip(),
        },
    )

    entries = scan_mod.scan_request_service_direct_assembly_entries([rel_path])

    assert [(entry["rule"], entry["target"], entry["line"]) for entry in entries] == [
        ("g_db_first_arg_helper", "helper_builder", 8),
        ("service_or_repository_g_db", "BatchService", 9),
    ]


def test_request_service_scan_flags_private_helper_with_g_db_alias(monkeypatch) -> None:
    rel_path = "tmp/request_gate_private_helper_alias_sample.py"
    _patch_sources(
        monkeypatch,
        {
            rel_path: dedent(
                """
                def _helper(conn):
                    return conn

                def build():
                    db = g.db
                    _helper(db)
                """
            ).strip(),
        },
    )

    entries = scan_mod.scan_request_service_direct_assembly_entries([rel_path])

    assert [(entry["rule"], entry["target"], entry["line"]) for entry in entries] == [
        ("g_db_first_arg_helper", "_helper", 6),
    ]


def test_repository_bundle_scan_flags_root_return_and_alias_consumption(monkeypatch) -> None:
    rel_path = "tmp/repository_bundle_sample.py"
    _patch_sources(
        monkeypatch,
        {
            rel_path: dedent(
                """
                class Demo:
                    def bad(self):
                        bundle = self._repos
                        return bundle.batch_repo

                    def also_bad(self):
                        return self._repos
                """
            ).strip(),
        },
    )

    entries = scan_mod.scan_repository_bundle_drift_entries([rel_path])

    assert sorted(entry["line"] for entry in entries) == [3, 4, 7]
    assert any(entry["chain"] == "self._repos" and entry["line"] == 3 for entry in entries)
    assert any(entry["chain"] == "bundle.batch_repo" and entry["line"] == 4 for entry in entries)
    assert any(entry["resolved_chain"] == "self._repos.batch_repo" for entry in entries)
    assert any(entry["chain"] == "self._repos" and entry["line"] == 7 for entry in entries)


def test_repository_bundle_scan_allows_schedule_service_proxy_assignment(monkeypatch) -> None:
    rel_path = "core/services/scheduler/schedule_service.py"
    _patch_sources(
        monkeypatch,
        {
            rel_path: dedent(
                """
                class ScheduleService:
                    def __init__(self):
                        self.batch_repo = self._repos.batch_repo
                """
            ).strip(),
        },
    )

    entries = scan_mod.scan_repository_bundle_drift_entries([rel_path])

    assert entries == []


def test_request_service_architecture_filter_does_not_hide_registered_helper_debt(monkeypatch) -> None:
    rel_path = "tmp/request_gate_architecture_sample.py"
    monkeypatch.setattr(ops_mod, "REQUEST_SERVICE_TARGET_FILES", [rel_path])
    monkeypatch.setattr(ops_mod, "REQUEST_SERVICE_TARGET_SYMBOLS", {})
    monkeypatch.setattr(
        ops_mod,
        "REQUEST_SERVICE_TARGET_ALLOWED_HELPERS",
        [
            {
                "path": rel_path,
                "symbol": "preview",
                "line": 10,
                "rule": "g_db_first_arg_helper",
                "target": "helper_builder",
            },
            {
                "path": rel_path,
                "symbol": "confirm",
                "line": 20,
                "rule": "g_db_first_arg_helper",
                "target": "helper_builder",
            },
        ],
        raising=False,
    )
    monkeypatch.setattr(ops_mod, "collect_globbed_files", lambda _patterns: [rel_path])
    received_paths = []

    request_entries = [
        {"path": rel_path, "symbol": "preview", "line": 10, "rule": "g_db_first_arg_helper", "target": "helper_builder", "excerpt": "a"},
        {"path": rel_path, "symbol": "confirm", "line": 20, "rule": "g_db_first_arg_helper", "target": "helper_builder", "excerpt": "b"},
        {"path": rel_path, "symbol": "confirm", "line": 21, "rule": "g_db_first_arg_helper", "target": "helper_builder", "excerpt": "c"},
        {"path": rel_path, "symbol": "confirm", "line": 30, "rule": "service_or_repository_g_db", "target": "BatchService", "excerpt": "d"},
    ]

    def _fake_scan_files(_paths, cache_path=None, force=False, context=None, fact_kinds=None):
        del cache_path, force, context, fact_kinds
        received_paths.append(list(_paths))
        return [_architecture_fact(str(path), request_entries=request_entries) for path in _paths]

    monkeypatch.setattr(ops_mod, "scan_files_with_cache", _fake_scan_files)

    entries = ops_mod.architecture_request_service_direct_assembly_entries()

    assert [(entry["symbol"], entry["line"], entry["rule"], entry["target"]) for entry in entries] == [
        ("confirm", 20, "g_db_first_arg_helper", "helper_builder"),
        ("confirm", 21, "g_db_first_arg_helper", "helper_builder"),
        ("confirm", 30, "service_or_repository_g_db", "BatchService"),
        ("preview", 10, "g_db_first_arg_helper", "helper_builder"),
    ]
    assert received_paths == [[rel_path]]


def test_request_service_target_files_cover_history_and_system_routes() -> None:
    expected_targets = {
        "web/routes/domains/scheduler/scheduler_analysis.py",
        "web/routes/domains/scheduler/scheduler_analysis_read.py",
        "web/routes/system_history.py",
        "web/routes/system_backup.py",
        "web/routes/system_logs.py",
        "web/routes/system_plugins.py",
        "web/routes/system_ui_mode.py",
        "web/routes/system_utils.py",
        "web/error_handlers.py",
        "web/error_boundary.py",
    }

    assert expected_targets.issubset(set(shared_mod.REQUEST_SERVICE_TARGET_FILES))


def test_request_service_target_files_cover_scheduler_calendar_and_resource_residuals() -> None:
    expected_targets = {
        "web/routes/domains/scheduler/scheduler_resource_dispatch.py",
        "web/routes/domains/scheduler/scheduler_calendar_pages.py",
        "web/routes/domains/scheduler/scheduler_excel_calendar.py",
    }

    assert expected_targets.issubset(set(shared_mod.REQUEST_SERVICE_TARGET_FILES))
    assert ops_mod.architecture_request_service_direct_assembly_entries() == []
    assert shared_mod.REQUEST_SERVICE_TARGET_ALLOWED_HELPERS == []


def test_request_service_scan_scope_covers_error_path_files() -> None:
    scanned = set(shared_mod.collect_globbed_files(shared_mod.REQUEST_SERVICE_SCAN_SCOPE_PATTERNS))

    assert "web/error_handlers.py" in scanned
    assert "web/error_boundary.py" in scanned
    assert set(shared_mod.UI_MODE_STARTUP_SCOPE_PATHS).issubset(scanned)


def test_startup_scope_patterns_cover_ui_mode_split_files() -> None:
    expected_patterns = {
        "web/bootstrap/**/*.py",
        "web/ui_mode.py",
        "web/ui_mode_request.py",
        "web/ui_mode_store.py",
        "web/render_bridge.py",
        "web/manual_src_security.py",
    }

    assert expected_patterns.issubset(set(shared_mod.STARTUP_SCOPE_PATTERNS))
    assert all(shared_mod.is_startup_scope_path(path) for path in expected_patterns if not path.endswith("*.py"))
    assert expected_patterns - {"web/bootstrap/**/*.py"} <= set(shared_mod.collect_startup_scope_files())


def test_ui_mode_split_scope_tags_stay_separated() -> None:
    assert scan_mod.ui_mode_scope_tag("_read_ui_mode_from_db", "web/ui_mode.py") == "startup_guard"
    assert scan_mod.ui_mode_scope_tag("render_ui_template", "web/ui_mode.py") == "render_bridge"
    assert scan_mod.ui_mode_scope_tag("read_ui_mode_request", "web/ui_mode_request.py") == "startup_guard"
    assert scan_mod.ui_mode_scope_tag("read_ui_mode_store", "web/ui_mode_store.py") == "startup_guard"
    assert scan_mod.ui_mode_scope_tag("render_ui_template", "web/render_bridge.py") == "render_bridge"
    assert scan_mod.ui_mode_scope_tag("normalize_manual_src", "web/manual_src_security.py") == "render_bridge"

    entries = scan_mod.scan_silent_fallback_entries(shared_mod.collect_startup_scope_files())
    ui_entries = [entry for entry in entries if entry.get("path") in set(shared_mod.UI_MODE_STARTUP_SCOPE_PATHS)]
    assert ui_entries
    for entry in ui_entries:
        path = str(entry.get("path"))
        if path in shared_mod.UI_MODE_STARTUP_GUARD_PATHS:
            assert entry.get("scope_tag") == "startup_guard"
        if path in shared_mod.UI_MODE_RENDER_BRIDGE_PATHS:
            assert entry.get("scope_tag") == "render_bridge"


def test_silent_fallback_entries_include_stable_handler_context_hash() -> None:
    entries = scan_mod.scan_silent_fallback_entries(shared_mod.collect_startup_scope_files())
    assert entries
    for entry in entries:
        assert str(entry.get("handler_context_hash") or "").startswith("sha1:")

    import ast

    first = ast.parse(
        "def f():\n"
        "    try:\n"
        "        work()\n"
        "    except Exception:\n"
        "        logger.warning('x')\n"
    )
    second = ast.parse(
        "\n\n"
        "def f():\n"
        "    try:\n"
        "        work()\n"
        "    except Exception:\n"
        "        logger.warning('x')\n"
    )

    def _handler(tree):
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                return node
        raise AssertionError("missing handler")

    assert scan_mod._handler_context_hash(_handler(first)) == scan_mod._handler_context_hash(_handler(second))


def test_strict_silent_fallback_cli_is_quiet_on_success(monkeypatch, capsys) -> None:
    scan_entry = {
        "id": "silent-fallback:demo",
        "path": "web/bootstrap/demo.py",
        "symbol": "demo",
        "fallback_kind": "silent_swallow",
    }
    ledger = {
        "silent_fallback": {
            "entries": [
                {
                    "id": "silent-fallback:demo",
                    "fallback_kind": "silent_swallow",
                    "status": "open",
                }
            ]
        }
    }

    monkeypatch.setattr(scan_mod, "load_ledger", lambda required=True: ledger)
    monkeypatch.setattr(scan_mod, "validate_ledger", lambda _ledger: None)
    monkeypatch.setattr(scan_mod, "validate_startup_samples", lambda: {"sample_count": 0})
    monkeypatch.setattr(ops_mod, "architecture_silent_scan_entries", lambda: [scan_entry])

    assert scan_mod.main(["--strict"]) == 0

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_strict_silent_fallback_cli_json_summary(monkeypatch, capsys) -> None:
    scan_entry = {
        "id": "silent-fallback:demo-json",
        "path": "web/bootstrap/demo.py",
        "symbol": "demo",
        "fallback_kind": "observable_degrade",
    }
    ledger = {
        "silent_fallback": {
            "entries": [
                {
                    "id": "silent-fallback:demo-json",
                    "fallback_kind": "observable_degrade",
                    "status": "open",
                }
            ]
        }
    }

    monkeypatch.setattr(scan_mod, "load_ledger", lambda required=True: ledger)
    monkeypatch.setattr(scan_mod, "validate_ledger", lambda _ledger: None)
    monkeypatch.setattr(scan_mod, "validate_startup_samples", lambda: {"sample_count": 0})
    monkeypatch.setattr(ops_mod, "architecture_silent_scan_entries", lambda: [scan_entry])

    assert scan_mod.main(["--strict", "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["scan_entry_count"] == 1
    assert payload["ledger_entry_count"] == 1
    assert payload["by_fallback_kind"] == {"observable_degrade": 1}
    assert payload["ledger_by_status"] == {"open": 1}


def test_strict_silent_fallback_cli_reports_drift_to_stderr(monkeypatch, capsys) -> None:
    scan_entry = {"id": "silent-fallback:missing", "fallback_kind": "silent_swallow"}
    monkeypatch.setattr(scan_mod, "load_ledger", lambda required=True: {"silent_fallback": {"entries": []}})
    monkeypatch.setattr(scan_mod, "validate_ledger", lambda _ledger: None)
    monkeypatch.setattr(scan_mod, "validate_startup_samples", lambda: {"sample_count": 0})
    monkeypatch.setattr(ops_mod, "architecture_silent_scan_entries", lambda: [scan_entry])

    assert scan_mod.main(["--strict"]) == 2

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "strict silent-fallback gate drift" in captured.err


def test_request_service_target_files_keep_system_route_gate_coverage() -> None:
    system_targets = {
        "web/routes/system_backup.py",
        "web/routes/system_logs.py",
        "web/routes/system_plugins.py",
        "web/routes/system_ui_mode.py",
        "web/routes/system_utils.py",
    }

    assert set(shared_mod.REQUEST_SERVICE_TARGET_FILES) & system_targets == system_targets


def test_request_service_target_symbols_include_nested_custom_test_factory_open_db() -> None:
    assert "_open_db" in shared_mod.REQUEST_SERVICE_TARGET_SYMBOLS["tests/run_real_db_replay_e2e.py"]
    assert "_open_db" in shared_mod.REQUEST_SERVICE_TARGET_SYMBOLS["tests/run_complex_excel_cases_e2e.py"]


def test_request_service_architecture_filter_tracks_nested_open_db_in_custom_test_factory(monkeypatch) -> None:
    rel_path = "tests/run_real_db_replay_e2e.py"
    monkeypatch.setattr(ops_mod, "REQUEST_SERVICE_TARGET_FILES", [])
    monkeypatch.setattr(ops_mod, "REQUEST_SERVICE_TARGET_SYMBOLS", {rel_path: ["_create_test_app", "_open_db"]})
    monkeypatch.setattr(ops_mod, "REQUEST_SERVICE_TARGET_ALLOWED_HELPERS", [], raising=False)
    monkeypatch.setattr(ops_mod, "collect_globbed_files", lambda _patterns: [rel_path])
    received_paths = []

    request_entries = [
        {
            "path": rel_path,
            "symbol": "_open_db",
            "line": 230,
            "rule": "service_or_repository_g_db",
            "target": "BatchService",
            "excerpt": "open",
        },
        {
            "path": rel_path,
            "symbol": "_close_db",
            "line": 245,
            "rule": "service_or_repository_g_db",
            "target": "BatchService",
            "excerpt": "close",
        },
    ]

    def _fake_scan_files(_paths, cache_path=None, force=False, context=None, fact_kinds=None):
        del cache_path, force, context, fact_kinds
        received_paths.append(list(_paths))
        return [_architecture_fact(str(path), request_entries=request_entries) for path in _paths]

    monkeypatch.setattr(ops_mod, "scan_files_with_cache", _fake_scan_files)

    entries = ops_mod.architecture_request_service_direct_assembly_entries()

    assert [(entry["symbol"], entry["line"], entry["target"]) for entry in entries] == [
        ("_open_db", 230, "BatchService"),
    ]
    assert received_paths == [[rel_path]]


def test_architecture_scan_wrappers_pass_context_and_original_paths(monkeypatch) -> None:
    quality_paths = ["web/routes/demo.py", "core/services/demo.py"]
    drift_paths = ["web/routes/demo.py"]
    calls = []

    monkeypatch.setattr(ops_mod, "collect_quality_rule_files", lambda: list(quality_paths))

    def _fake_collect_globbed_files(patterns):
        calls.append(("collect_globbed_files", list(patterns)))
        return list(drift_paths)

    monkeypatch.setattr(ops_mod, "collect_globbed_files", _fake_collect_globbed_files)
    monkeypatch.setattr(ops_mod, "is_startup_scope_path", lambda _path: True)

    silent_entries = [
        {
            "path": "web/routes/demo.py",
            "symbol": "route",
            "handler_fingerprint": "abc",
            "except_ordinal": 1,
        }
    ]
    complexity_entries = [
        {
            "path": "web/routes/demo.py",
            "symbol": "route",
            "current_value": shared_mod.COMPLEXITY_THRESHOLD + 1,
        }
    ]
    repository_entries = [{"path": "web/routes/demo.py", "symbol": "route", "chain": "self.repos.batch_repo"}]

    def _fake_scan_files(paths, cache_path=None, force=False, context=None, fact_kinds=None):
        del cache_path, force, context
        calls.append(("scan_files_with_cache", list(paths), tuple(fact_kinds or ())))
        return [
            _architecture_fact(
                str(path),
                line_count=shared_mod.FILE_SIZE_LIMIT + 1 if str(path) == "web/routes/demo.py" else 0,
                silent_entries=silent_entries,
                complexity_entries=complexity_entries,
                repository_entries=repository_entries,
            )
            for path in paths
        ]

    monkeypatch.setattr(ops_mod, "scan_files_with_cache", _fake_scan_files)

    assert [entry["path"] for entry in ops_mod.architecture_silent_scan_entries()] == ["web/routes/demo.py"]
    assert set(ops_mod.architecture_oversize_scan_map()) == {"web/routes/demo.py"}
    assert set(ops_mod.architecture_complexity_scan_map()) == {"web/routes/demo.py:route"}
    assert [entry["path"] for entry in ops_mod.architecture_repository_bundle_drift_entries()] == [
        "web/routes/demo.py"
    ]

    normalized_quality_paths = sorted(quality_paths)
    assert ("scan_files_with_cache", normalized_quality_paths, ("silent",)) in calls
    assert ("scan_files_with_cache", normalized_quality_paths, ()) in calls
    assert ("scan_files_with_cache", normalized_quality_paths, ("complexity",)) in calls
    assert ("collect_globbed_files", list(shared_mod.REPOSITORY_BUNDLE_DRIFT_SCOPE_PATTERNS)) in calls
    assert ("scan_files_with_cache", drift_paths, ("repository",)) in calls


def test_architecture_scan_wrapper_uses_fresh_context_per_call(monkeypatch) -> None:
    calls = []

    monkeypatch.setattr(ops_mod, "collect_quality_rule_files", lambda: ["web/routes/demo.py"])

    def _fake_scan_files(paths, cache_path=None, force=False, context=None, fact_kinds=None):
        del cache_path, force, context
        calls.append((list(paths), tuple(fact_kinds or ())))
        return [
            _architecture_fact(
                str(path),
                line_count=shared_mod.FILE_SIZE_LIMIT + 1,
            )
            for path in paths
        ]

    monkeypatch.setattr(ops_mod, "scan_files_with_cache", _fake_scan_files)

    assert set(ops_mod.architecture_oversize_scan_map()) == {"web/routes/demo.py"}
    assert set(ops_mod.architecture_oversize_scan_map()) == {"web/routes/demo.py"}
    assert calls == [
        (["web/routes/demo.py"], ()),
        (["web/routes/demo.py"], ()),
    ]
