from __future__ import annotations

from textwrap import dedent

import tools.quality_gate_operations as ops_mod
import tools.quality_gate_scan as scan_mod
import tools.quality_gate_shared as shared_mod


def _patch_sources(monkeypatch, source_map):
    monkeypatch.setattr(scan_mod, "read_text_file", lambda rel_path: source_map[str(rel_path)])


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
    monkeypatch.setattr(
        ops_mod,
        "scan_request_service_direct_assembly_entries",
        lambda _paths: [
            {"path": rel_path, "symbol": "preview", "line": 10, "rule": "g_db_first_arg_helper", "target": "helper_builder", "excerpt": "a"},
            {"path": rel_path, "symbol": "confirm", "line": 20, "rule": "g_db_first_arg_helper", "target": "helper_builder", "excerpt": "b"},
            {"path": rel_path, "symbol": "confirm", "line": 21, "rule": "g_db_first_arg_helper", "target": "helper_builder", "excerpt": "c"},
            {"path": rel_path, "symbol": "confirm", "line": 30, "rule": "service_or_repository_g_db", "target": "BatchService", "excerpt": "d"},
        ],
    )

    entries = ops_mod.architecture_request_service_direct_assembly_entries()

    assert [(entry["symbol"], entry["line"], entry["rule"], entry["target"]) for entry in entries] == [
        ("preview", 10, "g_db_first_arg_helper", "helper_builder"),
        ("confirm", 20, "g_db_first_arg_helper", "helper_builder"),
        ("confirm", 21, "g_db_first_arg_helper", "helper_builder"),
        ("confirm", 30, "service_or_repository_g_db", "BatchService"),
    ]


def test_request_service_target_files_cover_history_and_system_routes() -> None:
    expected_targets = {
        "web/routes/domains/scheduler/scheduler_analysis.py",
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


def test_ui_mode_split_scope_tags_stay_separated() -> None:
    assert scan_mod.ui_mode_scope_tag("_read_ui_mode_from_db", "web/ui_mode.py") == "startup_guard"
    assert scan_mod.ui_mode_scope_tag("render_ui_template", "web/ui_mode.py") == "render_bridge"
    assert scan_mod.ui_mode_scope_tag("read_ui_mode_request", "web/ui_mode_request.py") == "startup_guard"
    assert scan_mod.ui_mode_scope_tag("read_ui_mode_store", "web/ui_mode_store.py") == "startup_guard"
    assert scan_mod.ui_mode_scope_tag("render_ui_template", "web/render_bridge.py") == "render_bridge"
    assert scan_mod.ui_mode_scope_tag("normalize_manual_src", "web/manual_src_security.py") == "render_bridge"


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
    monkeypatch.setattr(
        ops_mod,
        "scan_request_service_direct_assembly_entries",
        lambda _paths: [
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
        ],
    )

    entries = ops_mod.architecture_request_service_direct_assembly_entries()

    assert [(entry["symbol"], entry["line"], entry["target"]) for entry in entries] == [
        ("_open_db", 230, "BatchService"),
    ]
