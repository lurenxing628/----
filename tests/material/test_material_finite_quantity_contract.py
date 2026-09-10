"""Material stock quantities reject non-finite writes without repairing stored data."""

from __future__ import annotations

import math
import sqlite3
from decimal import Decimal
from unittest.mock import Mock

import pytest

from core.infrastructure.errors import AppError, ErrorCode, ValidationError
from core.models import Material
from core.services.material.material_service import MaterialService

NON_FINITE = [
    float("nan"), float("inf"), float("-inf"), "nan", "NaN", " inf ",
    "+Infinity", "-Infinity", "1e309", "-1e309", Decimal("NaN"), Decimal("Infinity"),
]
WRITE_PATHS = ("service_create", "service_update", "repo_create_model", "repo_create_dict", "repo_update")
READ_PATHS = ("repo_get", "repo_list", "service_get", "service_list", "service_list_page")


@pytest.fixture
def material_service(tmp_path):
    conn = sqlite3.connect(str(tmp_path / "materials.db"))
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE Materials (material_id TEXT PRIMARY KEY, name TEXT NOT NULL,"
        " spec TEXT, unit TEXT, stock_qty REAL DEFAULT 0, status TEXT DEFAULT 'active',"
        " remark TEXT, created_at DATETIME DEFAULT CURRENT_TIMESTAMP)"
    )
    conn.execute("INSERT INTO Materials (material_id, name, stock_qty) VALUES ('M001', 'original', 5)")
    conn.commit()
    try:
        yield MaterialService(conn, op_logger=Mock())
    finally:
        conn.close()


def _write(service, path, value):
    if path == "service_create":
        return service.create("M002", "new", stock_qty=value)
    if path == "service_update":
        return service.update("M001", name="changed", stock_qty=value, remark="changed")
    if path == "repo_create_model":
        return service.repo.create(Material("M002", "new", stock_qty=value))
    if path == "repo_create_dict":
        return service.repo.create({"material_id": "M002", "name": "new", "stock_qty": value})
    if path == "repo_update":
        return service.repo.update("M001", {"name": "changed", "stock_qty": value, "remark": "changed"})
    raise AssertionError(path)


def _read(service, path, material_id="M002"):
    if path == "repo_get":
        return service.repo.get(material_id)
    if path == "repo_list":
        return service.repo.list()
    if path == "service_get":
        return service.get(material_id)
    if path == "service_list":
        return service.list()
    if path == "service_list_page":
        return service.list_page(per_page=2)
    raise AssertionError(path)


def _snapshot(conn):
    return [tuple(row) for row in conn.execute("SELECT *, typeof(stock_qty) FROM Materials ORDER BY material_id")]


@pytest.mark.parametrize("path", WRITE_PATHS)
@pytest.mark.parametrize("value", NON_FINITE)
def test_non_finite_write_is_rejected_before_any_mutation(material_service, path, value):
    service = material_service
    before = _snapshot(service.conn)
    changes = service.conn.total_changes
    expected_error = ValidationError if path.startswith("service") else ValueError
    with pytest.raises(expected_error) as caught:
        _write(service, path, value)
    if path.startswith("service"):
        assert caught.value.field == "\u5e93\u5b58\u6570\u91cf"
        assert "\u6709\u9650" in caught.value.message
    else:
        assert "stock_qty" in str(caught.value)
    assert _snapshot(service.conn) == before
    assert service.conn.total_changes == changes
    assert not service.conn.in_transaction
    service.op_logger.info.assert_not_called()


@pytest.mark.parametrize("path", WRITE_PATHS)
@pytest.mark.parametrize("value", [0, -0.0, 12, 12.5, " 12.5 ", "1e3", "1e308", "1.7976931348623157e308", "5e-324", Decimal("2.5")])
def test_finite_numeric_write_contract_is_preserved(material_service, path, value):
    service = material_service
    result = _write(service, path, value)
    mid = "M001" if path.endswith("update") else "M002"
    stored = service.get(mid).stock_qty
    assert stored == float(value)
    assert math.isfinite(stored)
    if result is not None:
        assert float(result.stock_qty) == stored
    assert len(service.list()) == (1 if mid == "M001" else 2)


@pytest.mark.parametrize("path", WRITE_PATHS)
@pytest.mark.parametrize("value", [None, ""])
def test_empty_create_defaults_to_zero_and_empty_update_preserves_quantity(material_service, path, value):
    _write(material_service, path, value)
    mid = "M001" if path.endswith("update") else "M002"
    material = material_service.get(mid)
    assert material.stock_qty == (5.0 if mid == "M001" else 0.0)
    if mid == "M001":
        assert material.name == "changed"


@pytest.mark.parametrize("path", [path for path in WRITE_PATHS if path != "repo_create_model"])
def test_whitespace_keeps_existing_empty_contract(material_service, path):
    _write(material_service, path, " \t ")
    mid = "M001" if path.endswith("update") else "M002"
    assert material_service.get(mid).stock_qty == (5.0 if mid == "M001" else 0.0)


def test_model_whitespace_create_remains_invalid(material_service):
    with pytest.raises(ValueError):
        _write(material_service, "repo_create_model", "   ")
    assert material_service.repo.count() == 1


@pytest.mark.parametrize("path", WRITE_PATHS)
def test_missing_quantity_contract_is_preserved(material_service, path):
    service = material_service
    if path == "service_create":
        service.create("M002", "new")
    elif path == "repo_create_model":
        service.repo.create(Material("M002", "new"))
    elif path == "repo_create_dict":
        service.repo.create({"material_id": "M002", "name": "new"})
    elif path == "service_update":
        service.update("M001", name="changed")
    else:
        service.repo.update("M001", {"name": "changed"})
    mid = "M001" if path.endswith("update") else "M002"
    assert service.get(mid).stock_qty == (5.0 if mid == "M001" else 0.0)


@pytest.mark.parametrize("path", WRITE_PATHS)
@pytest.mark.parametrize("value", ["not-a-number", 10 ** 400])
def test_invalid_numeric_inputs_do_not_partially_write(material_service, path, value):
    before = _snapshot(material_service.conn)
    expected_error = ValidationError if path.startswith("service") else (ValueError, OverflowError)
    with pytest.raises(expected_error):
        _write(material_service, path, value)
    assert _snapshot(material_service.conn) == before


@pytest.mark.parametrize("path", WRITE_PATHS)
def test_negative_number_validation_stays_at_existing_service_boundary(material_service, path):
    if path.startswith("service"):
        with pytest.raises(ValidationError):
            _write(material_service, path, -2)
    else:
        _write(material_service, path, -2)
        mid = "M001" if path.endswith("update") else "M002"
        assert material_service.get(mid).stock_qty == -2


@pytest.mark.parametrize("path", READ_PATHS)
@pytest.mark.parametrize("value", [float("inf"), float("-inf"), "NaN", "Infinity", "-Infinity", "1e309", "-1e309", "bad"])
def test_dirty_read_reports_material_and_field_without_cleaning(material_service, tmp_path, path, value):
    service = material_service
    service.conn.execute(
        "INSERT INTO Materials (material_id, name, stock_qty) VALUES ('M002', 'dirty', ?)", (value,)
    )
    service.conn.commit()
    before = _snapshot(service.conn)
    stored_value = service.conn.execute("SELECT stock_qty FROM Materials WHERE material_id='M002'").fetchone()[0]
    db_bytes = (tmp_path / "materials.db").read_bytes()
    changes = service.conn.total_changes
    with pytest.raises(AppError) as caught:
        _read(service, path)
    error = caught.value
    assert error.code == ErrorCode.DB_INTEGRITY_ERROR
    assert "M002" in error.message
    assert "\u5e93\u5b58\u6570\u91cf" in error.message
    assert error.details == {
        "table": "Materials", "material_id": "M002", "field": "stock_qty", "value": repr(stored_value),
    }
    assert error.internal_details == error.details
    assert isinstance(error.__cause__, ValueError)
    assert _snapshot(service.conn) == before
    assert service.conn.total_changes == changes
    assert (tmp_path / "materials.db").read_bytes() == db_bytes
    assert not service.conn.in_transaction
    service.op_logger.info.assert_not_called()


@pytest.mark.parametrize("value", [None, "", "   ", float("nan")])
def test_stored_empty_and_nan_already_erased_to_null_keep_legacy_contract(material_service, value):
    service = material_service
    service.conn.execute("INSERT INTO Materials (material_id, name, stock_qty) VALUES ('M002', 'empty', ?)", (value,))
    service.conn.commit()
    before = _snapshot(service.conn)
    if isinstance(value, float):
        assert service.conn.execute("SELECT stock_qty FROM Materials WHERE material_id='M002'").fetchone()[0] is None
    assert service.get("M002").stock_qty == 0.0
    assert service.list()[1].stock_qty == 0.0
    assert service.list_page(per_page=2)[0][1].stock_qty == 0.0
    assert _snapshot(service.conn) == before


@pytest.mark.parametrize("path", ["repo_get", "repo_list"])
def test_row_containing_actual_nan_is_rejected_with_location(material_service, monkeypatch, path):
    row = {"material_id": "M002", "name": "dirty", "stock_qty": float("nan")}
    method = "fetchone" if path == "repo_get" else "fetchall"
    monkeypatch.setattr(material_service.repo, method, Mock(return_value=row if path == "repo_get" else [row]))
    with pytest.raises(AppError, match="M002") as caught:
        _read(material_service, path)
    assert caught.value.details["value"] == "nan"


def test_dirty_row_outside_requested_filter_or_page_is_not_read(material_service):
    service = material_service
    service.conn.execute(
        "INSERT INTO Materials (material_id, name, stock_qty, status) VALUES ('M002', 'dirty', 'NaN', 'inactive')"
    )
    service.conn.commit()
    assert service.repo.count() == 2
    assert service.repo.exists("M002")
    assert service.get("M001").stock_qty == 5
    assert len(service.list(status="active")) == 1
    assert len(service.list_page(page=1, per_page=1)[0]) == 1
    with pytest.raises(AppError, match="M002"):
        service.list_page(page=2, per_page=1)


@pytest.mark.parametrize("path", WRITE_PATHS)
def test_invalid_quantity_rolls_back_prior_writes_in_outer_transaction(material_service, path):
    service = material_service
    before = _snapshot(service.conn)
    expected_error = ValidationError if path.startswith("service") else ValueError
    with pytest.raises(expected_error):
        with service.tx.transaction():
            service.create("M003", "earlier", stock_qty=3)
            _write(service, path, "Infinity")
    assert _snapshot(service.conn) == before
    assert not service.conn.in_transaction


@pytest.mark.parametrize("path", ["repo_create_model", "repo_create_dict", "repo_update"])
def test_repository_does_not_commit_callers_transaction(material_service, path):
    before = _snapshot(material_service.conn)
    _write(material_service, path, 7)
    assert material_service.conn.in_transaction
    material_service.conn.rollback()
    assert _snapshot(material_service.conn) == before


@pytest.mark.parametrize("path", WRITE_PATHS)
def test_caught_validation_error_preserves_callers_uncommitted_work(material_service, path):
    service = material_service
    service.conn.execute("INSERT INTO Materials (material_id, name, stock_qty) VALUES ('M003', 'pending', 3)")
    before = _snapshot(service.conn)
    changes = service.conn.total_changes
    expected_error = ValidationError if path.startswith("service") else ValueError
    with pytest.raises(expected_error):
        _write(service, path, "NaN")
    assert service.conn.in_transaction
    assert service.conn.total_changes == changes
    assert _snapshot(service.conn) == before
    service.conn.commit()
    assert _snapshot(service.conn) == before


@pytest.mark.parametrize("path", ["service_create", "service_update"])
def test_operation_log_failure_rolls_back_material_and_log_writes(material_service, path):
    service = material_service
    service.conn.execute("CREATE TABLE Audit (detail TEXT)")
    service.conn.commit()
    before = _snapshot(service.conn)

    def fail_log(**kwargs):
        service.conn.execute("INSERT INTO Audit VALUES ('partial')")
        raise RuntimeError("audit failed")

    service.op_logger.info.side_effect = fail_log
    with pytest.raises(RuntimeError, match="audit failed"):
        _write(service, path, 7)
    assert _snapshot(service.conn) == before
    assert service.conn.execute("SELECT COUNT(*) FROM Audit").fetchone()[0] == 0
    assert not service.conn.in_transaction


@pytest.mark.parametrize("accept", ["text/html", "application/json"])
def test_existing_material_page_surfaces_dirty_quantity_location(app_client, db_path, accept, caplog):
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("INSERT INTO Materials (material_id, name, stock_qty) VALUES ('M002', 'dirty', 'NaN')")
        conn.commit()
        before = _snapshot(conn)
        response = app_client.get("/material/materials", headers={"Accept": accept})
        assert response.status_code == 409
        if accept == "application/json":
            payload = response.get_json()
            assert payload["error"]["code"] == ErrorCode.DB_INTEGRITY_ERROR.value
            message = payload["error"]["message"]
        else:
            message = response.get_data(as_text=True)
        assert "M002" in message
        assert "\u5e93\u5b58\u6570\u91cf" in message
        assert "\u6709\u9650\u6570\u5b57" in message
        assert "Materials" in caplog.text
        assert "stock_qty" in caplog.text
        assert "NaN" in caplog.text
        assert _snapshot(conn) == before
    finally:
        conn.close()
