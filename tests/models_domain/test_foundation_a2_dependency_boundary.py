"""Characterization tests for the foundation A2 one-way dependency boundary."""

from __future__ import annotations

import ast
import importlib
import json
import os
import sqlite3
import subprocess
import sys
from inspect import signature
from pathlib import Path
from typing import Dict, Iterable, Tuple

import pytest

from tests._support.paths import REPO_ROOT

_A2_MEMBERS = {
    "core/infrastructure",
    "core/infrastructure/migrations",
    "core/models",
    "core/shared",
}
_ERROR_EXPORTS = (
    "ErrorCode",
    "AppError",
    "ValidationError",
    "NotFoundError",
    "BusinessError",
    "app_error_http_status",
    "error_response",
)
_MIGRATION_EXPORTS = (
    "MigrationOutcome",
    "merge_outcomes",
    "table_exists",
    "column_exists",
    "add_column_if_missing",
    "fallback_log",
)
_ERROR_CODE_VALUES = (
    ("SUCCESS", "0000"),
    ("UNKNOWN_ERROR", "1000"),
    ("VALIDATION_ERROR", "1001"),
    ("NOT_FOUND", "1002"),
    ("DUPLICATE_ENTRY", "1003"),
    ("PERMISSION_DENIED", "1004"),
    ("DB_CONNECTION_ERROR", "2001"),
    ("DB_QUERY_ERROR", "2002"),
    ("DB_TRANSACTION_ERROR", "2003"),
    ("DB_INTEGRITY_ERROR", "2004"),
    ("OPERATOR_NOT_FOUND", "3001"),
    ("OPERATOR_ALREADY_EXISTS", "3002"),
    ("OPERATOR_IN_USE", "3003"),
    ("TEAM_NOT_FOUND", "3101"),
    ("TEAM_ALREADY_EXISTS", "3102"),
    ("TEAM_IN_USE", "3103"),
    ("MACHINE_NOT_FOUND", "4001"),
    ("MACHINE_ALREADY_EXISTS", "4002"),
    ("MACHINE_IN_USE", "4003"),
    ("MACHINE_NOT_AVAILABLE", "4004"),
    ("PART_NOT_FOUND", "5001"),
    ("PART_ALREADY_EXISTS", "5002"),
    ("ROUTE_PARSE_ERROR", "5003"),
    ("OPERATION_DELETE_DENIED", "5004"),
    ("EXTERNAL_GROUP_ERROR", "5005"),
    ("BATCH_NOT_FOUND", "6001"),
    ("BATCH_ALREADY_EXISTS", "6002"),
    ("SCHEDULE_CONFLICT", "6003"),
    ("SCHEDULE_LOCKED", "6004"),
    ("RESOURCE_NOT_AVAILABLE", "6005"),
    ("CALENDAR_ERROR", "6006"),
    ("EXCEL_READ_ERROR", "7001"),
    ("EXCEL_WRITE_ERROR", "7002"),
    ("EXCEL_FORMAT_ERROR", "7003"),
    ("IMPORT_VALIDATION_ERROR", "7004"),
    ("FILE_TOO_LARGE", "7005"),
)
_ERROR_SIGNATURES = {
    "AppError": "(code: 'ErrorCode', message: 'str', details: 'Optional[Dict[str, Any]]' = None, cause: 'Optional[Exception]' = None, internal_details: 'Optional[Dict[str, Any]]' = None) -> None",
    "ValidationError": "(message: 'str', field: 'Optional[str]' = None, details: 'Optional[Dict[str, Any]]' = None, **kwargs)",
    "NotFoundError": "(resource_type: 'str', resource_id: 'str')",
    "BusinessError": "(code: 'ErrorCode', message: 'str', details: 'Optional[Dict[str, Any]]' = None, cause: 'Optional[Exception]' = None, internal_details: 'Optional[Dict[str, Any]]' = None) -> None",
    "app_error_http_status": "(code: 'ErrorCode') -> 'int'",
    "error_response": "(code: 'ErrorCode', message: 'str', details=None) -> 'dict'",
}
_MIGRATION_SIGNATURES = {
    "merge_outcomes": "(*outcomes: 'MigrationOutcome') -> 'MigrationOutcome'",
    "table_exists": "(conn: 'sqlite3.Connection', table: 'str') -> 'bool'",
    "column_exists": "(conn: 'sqlite3.Connection', table: 'str', column: 'str') -> 'bool'",
    "add_column_if_missing": "(conn: 'sqlite3.Connection', table: 'str', column: 'str', ddl: 'str', *, migration_label: 'str', logger=None, log_added: 'bool' = False) -> 'MigrationOutcome'",
    "fallback_log": "(logger, level: 'str', message: 'str') -> 'None'",
}
_LOW_LEVEL_ERROR_CONSUMERS = (
    "core/models/schedule_config_runtime_coercion.py",
    "core/models/schedule_config_runtime_read.py",
    "core/models/schedule_config_runtime_weights.py",
    "core/models/schedule_resource_filter.py",
    "core/shared/compat_parse.py",
    "core/shared/field_parse.py",
    "core/shared/strict_parse.py",
)
_ERROR_FUNCTION_CONSUMERS = (
    "web/error_boundary.py",
    "web/error_handlers.py",
    "web/routes/domains/scheduler/scheduler_gantt.py",
    "web/routes/domains/scheduler/scheduler_gantt_adjustments.py",
    "web/routes/domains/scheduler/scheduler_resource_dispatch.py",
    "web/routes/domains/scheduler/scheduler_resource_dispatch_execution_context.py",
    "web/routes/domains/scheduler/scheduler_resource_dispatch_execution_routes.py",
)


def _module_imports(rel_path: str) -> Tuple[Tuple[int, str, Tuple[str, ...]], ...]:
    path = Path(REPO_ROOT) / rel_path
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel_path)
    rows = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            rows.append((int(node.level), str(node.module or ""), tuple(alias.name for alias in node.names)))
    return tuple(rows)


def _assert_same_exports(compat_module, canonical_module, names: Iterable[str]) -> None:
    for name in names:
        assert getattr(compat_module, name) is getattr(canonical_module, name), name


def test_existing_error_contract_is_characterized() -> None:
    errors = importlib.import_module("core.infrastructure.errors")

    assert tuple((item.name, item.value) for item in errors.ErrorCode) == _ERROR_CODE_VALUES
    assert {name: str(signature(getattr(errors, name))) for name in _ERROR_SIGNATURES} == _ERROR_SIGNATURES

    cause = RuntimeError("root cause")
    err = errors.AppError(
        errors.ErrorCode.UNKNOWN_ERROR,
        "用户能看到的错误",
        details={"field": "测试字段"},
        cause=cause,
        internal_details={"debug": "hidden"},
    )
    assert err.args == ("用户能看到的错误",)
    assert err.__cause__ is cause
    assert str(err) == "[1000] 用户能看到的错误"
    assert err.to_dict() == {
        "success": False,
        "error": {
            "code": "1000",
            "message": "用户能看到的错误",
            "details": {"field": "测试字段"},
        },
    }

    validation = errors.ValidationError("填写不正确", field="priority", details={"reason": "bad"})
    assert validation.field == "priority"
    assert validation.details == {"reason": "bad", "field": "priority"}
    assert errors.NotFoundError("批次", "B-1").message == "批次B-1不存在"

    expected_statuses = {
        errors.ErrorCode.VALIDATION_ERROR: 400,
        errors.ErrorCode.PERMISSION_DENIED: 403,
        errors.ErrorCode.NOT_FOUND: 404,
        errors.ErrorCode.DUPLICATE_ENTRY: 409,
        errors.ErrorCode.FILE_TOO_LARGE: 413,
    }
    assert {code: errors.app_error_http_status(code) for code in expected_statuses} == expected_statuses
    assert errors.error_response(errors.ErrorCode.VALIDATION_ERROR, "错误", {"field": "字段"}) == {
        "success": False,
        "error": {"code": "1001", "message": "错误", "details": {"field": "字段"}},
    }


def test_existing_migration_common_contract_is_characterized(capsys: pytest.CaptureFixture[str]) -> None:
    common = importlib.import_module("core.infrastructure.migrations.common")

    assert tuple((item.name, item.value) for item in common.MigrationOutcome) == (
        ("APPLIED", "applied"),
        ("SKIPPED", "skipped"),
        ("PARTIAL", "partial"),
    )
    assert {name: str(signature(getattr(common, name))) for name in _MIGRATION_SIGNATURES} == _MIGRATION_SIGNATURES
    assert common.merge_outcomes() is common.MigrationOutcome.SKIPPED
    assert common.merge_outcomes(common.MigrationOutcome.APPLIED) is common.MigrationOutcome.APPLIED
    assert common.merge_outcomes(common.MigrationOutcome.APPLIED, common.MigrationOutcome.SKIPPED) is common.MigrationOutcome.PARTIAL

    conn = sqlite3.connect(":memory:")
    try:
        conn.execute("CREATE TABLE Example (id INTEGER PRIMARY KEY, name TEXT)")
        assert common.table_exists(conn, "Example") is True
        assert common.column_exists(conn, "Example", "name") is True
        with pytest.raises(ValueError, match="非法 SQLite 表名"):
            common.table_exists(conn, "bad-table")
        with pytest.raises(ValueError, match="非法 SQLite 列名"):
            common.column_exists(conn, "Example", "bad-column")
    finally:
        conn.close()

    class _BrokenLogger:
        def warning(self, _message: str) -> None:
            raise RuntimeError("logger unavailable")

    common.fallback_log(_BrokenLogger(), "warning", "迁移日志回退")
    assert "迁移日志回退" in capsys.readouterr().err


def test_error_compatibility_path_reexports_canonical_object_identity() -> None:
    error_compat = importlib.import_module("core.infrastructure.errors")
    error_canonical = importlib.import_module("core.errors")
    _assert_same_exports(error_compat, error_canonical, _ERROR_EXPORTS)


def test_migration_compatibility_path_reexports_canonical_object_identity() -> None:
    migration_compat = importlib.import_module("core.infrastructure.migrations.common")
    migration_canonical = importlib.import_module("core.infrastructure.migration_common")
    _assert_same_exports(migration_compat, migration_canonical, _MIGRATION_EXPORTS)


def test_canonical_and_compatibility_modules_import_in_both_orders() -> None:
    env: Dict[str, str] = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    module_orders = (
        (
            "core.infrastructure.errors",
            "core.errors",
            "core.infrastructure.migrations.common",
            "core.infrastructure.migration_common",
        ),
        (
            "core.infrastructure.migration_common",
            "core.infrastructure.migrations.common",
            "core.errors",
            "core.infrastructure.errors",
        ),
    )
    for module_names in module_orders:
        code = "import importlib\n" + "\n".join(
            f"importlib.import_module({module_name!r})" for module_name in module_names
        )
        completed = subprocess.run(
            [sys.executable, "-c", code],
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 0, completed.stderr


def test_error_callers_use_the_approved_one_way_imports() -> None:
    for rel_path in _LOW_LEVEL_ERROR_CONSUMERS + _ERROR_FUNCTION_CONSUMERS:
        imports = _module_imports(rel_path)
        assert any(level == 0 and module == "core.errors" for level, module, _names in imports), rel_path
        assert not any(module == "core.infrastructure.errors" for _level, module, _names in imports), rel_path


def test_migration_callers_use_the_approved_one_way_imports() -> None:
    migrations_dir = Path(REPO_ROOT) / "core" / "infrastructure" / "migrations"
    for path in sorted(migrations_dir.glob("*.py")):
        if path.name == "common.py":
            continue
        rel_path = path.relative_to(REPO_ROOT).as_posix()
        imports = _module_imports(rel_path)
        assert not any(level == 1 and module == "common" for level, module, _names in imports), rel_path
        if path.name == "__init__.py" or any(module == "migration_common" for _level, module, _names in imports):
            assert any(level == 2 and module == "migration_common" for level, module, _names in imports), rel_path

    for rel_path in (
        "core/infrastructure/backup.py",
        "core/infrastructure/database.py",
        "core/infrastructure/database_bootstrap.py",
        "core/infrastructure/migration_backup.py",
        "core/infrastructure/migration_operation_execution_contract.py",
        "core/infrastructure/migration_runner.py",
        "core/infrastructure/migration_state.py",
        "web/bootstrap/factory.py",
    ):
        imports = _module_imports(rel_path)
        assert not any(module.endswith("migrations.common") for _level, module, _names in imports), rel_path
        assert any(module.endswith("migration_common") for _level, module, _names in imports), rel_path


def test_a2_hard_directory_scc_is_absent() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "tools.scan_import_cycles", "--json"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
    )
    report = json.loads(completed.stdout)
    cycles = [set(item["members"]) for item in report["hard_dir_cycles"]]
    remaining = [members for members in cycles if members & _A2_MEMBERS]
    assert not remaining, remaining
