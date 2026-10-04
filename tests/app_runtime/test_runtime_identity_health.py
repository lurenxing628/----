"""The real health route must identify the instance in its runtime contract."""

import hashlib
import os

from flask import Flask
from werkzeug.test import Client
from werkzeug.wrappers import Response

from web.bootstrap.launcher_contracts import _runtime_contract_payload
from web.bootstrap.launcher_shutdown import RuntimeHostStopTransport
from web.routes.workbench.system_runtime import bp


def test_health_identity_matches_the_published_runtime_contract(tmp_path):
    app = Flask("runtime-identity-health")
    db_path = str(tmp_path / "database with spaces !" / "aps.db")
    token = "isolated-health-identity-token"
    owner = "LOCALBOX\\operator"
    app.config.update(DATABASE_PATH=db_path, APS_RUNTIME_OWNER=owner, APS_RUNTIME_SHUTDOWN_TOKEN=token)
    app.register_blueprint(bp)
    contract = _runtime_contract_payload(str(tmp_path), "127.0.0.1", 5705, db_path=db_path,
                                         shutdown_token=token, ui_mode="default", log_dir=None,
                                         backup_dir=None, excel_template_dir=None, owner=owner)
    response = app.test_client().get("/system/health")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["pid"] == contract["pid"] == os.getpid()
    assert payload["owner"] == contract["owner"]
    assert payload["db_path_hash"] == hashlib.sha256(contract["db_path"].encode("utf-8")).hexdigest()
    assert payload["instance_id"] == hashlib.sha256(contract["shutdown_token"].encode("utf-8")).hexdigest()
    assert db_path not in response.get_data(as_text=True)
    assert token not in response.get_data(as_text=True)


def test_unconfigured_health_cannot_supply_instance_identity():
    app = Flask("unconfigured-health")
    app.register_blueprint(bp)
    payload = app.test_client().get("/system/health").get_json()
    assert payload["instance_id"] == ""
    assert payload["db_path_hash"] == ""


def test_recovery_health_identifies_the_host_without_claiming_normal_operation(tmp_path):
    app = Flask("recovery-health")
    app.config.update(DATABASE_PATH=str(tmp_path / "unavailable.db"), APS_RUNTIME_OWNER="LOCAL\\operator",
                      APS_RUNTIME_SHUTDOWN_TOKEN="isolated-recovery-token")
    app.extensions["workbench_system_restore_recovery"] = True

    def no_database_application(*args):
        raise AssertionError("Recovery health must not enter normal initialization or the database")

    app.wsgi_app = no_database_application
    response = Client(RuntimeHostStopTransport(app), Response).get("/system/health")
    assert response.status_code == 503
    assert response.get_json()["status"] == "recovery_required"
    assert response.get_json()["operations_available"] is False
    assert response.get_json()["pid"] == os.getpid()
    assert response.get_json()["instance_id"]
