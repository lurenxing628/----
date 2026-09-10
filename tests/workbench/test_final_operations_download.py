"""Current real factory backup downloads: exact bytes, read scope and stale refs."""

from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import quote, unquote

import pytest

from core.infrastructure.backup import BackupManager
from core.infrastructure.database import get_connection
from tests.workbench.final_operations_support import digest
from web.bootstrap import factory
from web.routes.workbench import system_backup_export as exports
from web.routes.workbench.system_context import issue_context

BASE = "/api/workbench/v1/system"


@pytest.fixture
def download_case(db_env, tmp_path):
    app = factory.create_app_core(ui_mode="default", enable_secret_key=False,
                                 enable_security_headers=False, enable_session_cookie_hardening=False)
    with closing(get_connection(db_env)) as conn:
        conn.execute("INSERT INTO SystemConfig(config_key,config_value) VALUES ('FINAL_DOWNLOAD','original preserved row')")
        conn.commit()
    path = Path(BackupManager(db_env, app.config["BACKUP_DIR"]).backup(suffix="final_download"))
    return SimpleNamespace(app=app, client=app.test_client(), path=path, database=Path(db_env), root=tmp_path)


def selected(case, **filters):
    response = case.client.get(BASE + "/backups", query_string=filters)
    assert response.status_code == 200, response.get_json()
    payload = response.get_json()
    return payload["data"]["rows"][0], payload["meta"]["snapshot_ref"]


def download(case, row, snapshot, **query):
    return case.client.get(BASE + "/backups/" + quote(row["backup_ref"], safe="") + "/download",
                           query_string={"snapshot_ref": snapshot, **query})


@pytest.mark.parametrize("unicode_name", [False, True])
def test_download_exact_sqlite_bytes_name_size_and_original_row(download_case, unicode_name):
    case = download_case
    if unicode_name:
        renamed = case.path.with_name("aps_backup_验收原件.db")
        case.path.rename(renamed)
        case.path = renamed
    row, snapshot = selected(case)
    source_hash, backup_hash = digest(case.database), digest(case.path)
    result = download(case, row, snapshot)
    assert result.status_code == 200
    assert result.content_type == "application/vnd.sqlite3"
    assert result.data == case.path.read_bytes() and result.data[:16] == b"SQLite format 3\x00"
    assert int(result.headers["Content-Length"]) == row["size_bytes"] == len(result.data)
    assert unquote(result.headers["Content-Disposition"].split("filename*=UTF-8''")[1]) == row["filename"]
    assert result.headers["X-APS-Backup-Ref"] == row["backup_ref"]
    assert result.headers["Cache-Control"] == "no-store"
    target = case.root / "actual-download.db"
    target.write_bytes(result.data)
    with closing(get_connection(str(target))) as conn:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert conn.execute("SELECT config_value FROM SystemConfig WHERE config_key='FINAL_DOWNLOAD'").fetchone()[0] == "original preserved row"
    assert digest(case.database) == source_hash and digest(case.path) == backup_hash


@pytest.mark.parametrize("change", ["missing-snapshot", "raw-filename", "expired-ref", "wrong-kind", "wrong-scope", "filename-query", "duplicate-snapshot"])
def test_download_rejects_unbound_or_client_named_files(download_case, monkeypatch, change):
    case = download_case
    row, snapshot = selected(case)
    original = {str(path): digest(path) for path in (case.database, case.path)}
    query = {}
    if change == "missing-snapshot":
        snapshot = ""
    elif change == "raw-filename":
        row = {**row, "backup_ref": row["filename"]}
    elif change == "expired-ref":
        from web import public_token_registry
        now = public_token_registry.time.time()
        monkeypatch.setattr(public_token_registry, "time", SimpleNamespace(time=lambda: now + 901))
    elif change == "wrong-kind":
        with case.app.app_context():
            row = {**row, "backup_ref": issue_context("file", row["backup_ref"])}
    elif change == "wrong-scope":
        query["query"] = "different range"
    elif change == "filename-query":
        query["filename"] = str(case.path)
    elif change == "duplicate-snapshot":
        query["snapshot_ref"] = [snapshot, snapshot]
    response = download(case, row, snapshot, **query)
    assert response.status_code in (400, 404, 409), response.get_json()
    assert response.is_json and response.get_json()["ok"] is False
    assert "Content-Disposition" not in response.headers
    assert {str(path): digest(path) for path in (case.database, case.path)} == original


@pytest.mark.parametrize("change", ["removed", "changed", "during-read", "unreadable", "bad-header"])
def test_download_changed_deleted_unreadable_or_invalid_backup_fails_closed(download_case, monkeypatch, change):
    case = download_case
    if change == "bad-header":
        case.path.write_bytes(b"not a SQLite backup file")
    row, snapshot = selected(case)
    source_hash = digest(case.database)
    if change == "removed":
        case.path.unlink()
    elif change == "changed":
        with case.path.open("ab") as stream:
            stream.write(b"changed since the original read")
    elif change == "during-read":
        original_read = exports.read_fixed_bytes
        def changed_read(path):
            result = original_read(path)
            with Path(path).open("ab") as stream:
                stream.write(b"changed during the read")
            return result
        monkeypatch.setattr(exports, "read_fixed_bytes", changed_read)
    elif change == "unreadable":
        def unreadable(_path):
            raise PermissionError("final operations injected file read denial")
        monkeypatch.setattr(exports, "read_fixed_bytes", unreadable)
    result = download(case, row, snapshot)
    assert result.status_code in (404, 409, 422), result.get_json()
    assert result.is_json and result.get_json()["ok"] is False
    assert "Content-Disposition" not in result.headers
    assert digest(case.database) == source_hash


def test_download_cannot_switch_database_with_a_previous_reference(download_case):
    case = download_case
    row, snapshot = selected(case)
    original = case.app.config["DATABASE_PATH"]
    # Only change the identity guard during the endpoint call; do not open another database.
    with case.app.test_request_context(BASE + "/backups/" + row["backup_ref"] + "/download", query_string={"snapshot_ref": snapshot}):
        case.app.config["DATABASE_PATH"] = str(case.root / "another-never-created.db")
        try:
            result = exports.system_backup_export(row["backup_ref"])
            assert result.status_code == 409 and result.get_json()["error"]["code"] == "stale_write"
        finally:
            case.app.config["DATABASE_PATH"] = original
    assert not (case.root / "another-never-created.db").exists()
