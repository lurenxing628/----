"""Real factory runtime isolated from the Main checkout and production storage."""

import hashlib
import importlib
import json
import os
import sys
import tempfile
from contextlib import closing
from datetime import date, datetime
from pathlib import Path
from urllib.parse import unquote, urlsplit

from source_guard import FrozenSourceGuard


def json_value(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    raise TypeError("Unsupported evidence value: " + type(value).__name__)


def configure(source, root):
    source, root = source.resolve(), root.resolve()
    if source.parent != root.parent.parent or not str(source).startswith("/private/tmp/aps-g-retirement-candidate-"):
        raise ValueError("Factory acceptance requires the explicitly owned private snapshot.")
    root.mkdir(parents=True, exist_ok=True)
    for name in ("db", "logs", "backups", "templates_excel", "journal", "tmp", "home"):
        (root / name).mkdir(exist_ok=True)
    for key in list(os.environ):
        if key.startswith("APS_") or key == "WERKZEUG_RUN_MAIN":
            del os.environ[key]
    os.environ.update(APS_ENV="production", APS_SHARED_DATA_ROOT=str(root),
                      APS_DB_PATH=str(root / "db/aps.db"), APS_LOG_DIR=str(root / "logs"),
                      APS_BACKUP_DIR=str(root / "backups"), APS_EXCEL_TEMPLATE_DIR=str(root / "templates_excel"),
                      APS_SYSTEM_JOURNAL_DIR=str(root / "journal"), SECRET_KEY="private-factory-retirement-session",
                      TMPDIR=str(root / "tmp"), HOME=str(root / "home"), PYTHONDONTWRITEBYTECODE="1")
    sys.dont_write_bytecode = True
    tempfile.tempdir = str(root / "tmp")
    os.chdir(str(source))
    return source, root


def enforce_private_writes(root, source_guard):
    def allowed(value, event="filesystem"):
        if isinstance(value, int) or value is None:
            return
        path = Path(os.fsdecode(value)).resolve()
        if root != path and root not in path.parents:
            raise PermissionError("Private acceptance blocked external write (" + event + "): " + str(path))

    def audit(event, args):
        if event == "open":
            source_guard.check_read(args[0])
            mode, flags = args[1], args[2]
            if (isinstance(mode, str) and any(mark in mode for mark in "wax+")) or (isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)):
                allowed(args[0], "open " + repr(args))
        elif event in ("os.mkdir", "os.remove", "os.rmdir"):
            allowed(args[0], event + " " + repr(args))
        elif event in ("os.rename", "os.replace"):
            allowed(args[0])
            allowed(args[1])
        elif event == "sqlite3.connect" and args[0] != ":memory:":
            value = os.fsdecode(args[0])
            if value == ":memory:":
                return
            if value.startswith("file:"):
                uri = urlsplit(value)
                if uri.netloc:
                    raise PermissionError("SQLite URI must identify a private local file.")
                value = unquote(uri.path)
            allowed(value, event + " " + repr(args))
        elif event in ("socket.connect", "subprocess.Popen"):
            raise PermissionError("Private factory worker does not start processes or make external connections.")
    sys.addaudithook(audit)


class FactoryCase:
    def __init__(self, source, root, *, candidate):
        self.source, self.root = configure(source, root)
        manifest = Path(os.environ["FACTORY_SOURCE_MANIFEST"])
        self.source_guard = FrozenSourceGuard(self.source, Path(__file__).resolve().parent, manifest)
        self.source_guard.restrict_sys_path()
        enforce_private_writes(self.root, self.source_guard)
        # app.py invokes the real create_app at import, with all paths set first.
        module = importlib.import_module("app")
        self.app = module.app
        self.path = self.app.config["DATABASE_PATH"]
        self.original = dict(self.app.view_functions)
        self.candidate = candidate
        if candidate:
            from web.routes.workbench.legacy_dispatch import install_legacy_retirement
            install_legacy_retirement(self.app)
        self.client = self.app.test_client()
        self.responses = []
        self.state_counter = 0
        self.assert_loaded_source()
        self.seed()

    def assert_loaded_source(self):
        self.loaded_modules = self.source_guard.inspect_modules()

    def db(self):
        from core.infrastructure.database import get_connection
        return closing(get_connection(self.path))

    def seed(self):
        from core.services.equipment.machine_service import MachineService
        from core.services.personnel.operator_service import OperatorService
        from core.services.process.op_type_service import OpTypeService
        from core.services.process.part_service import PartService
        from core.services.process.supplier_service import SupplierService
        from core.services.scheduler.config.config_service import ConfigService
        with self.db() as conn:
            OpTypeService(conn).create("OT-IN", "数车", "internal")
            OpTypeService(conn).create("OT-EXT", "标印", "external")
            OperatorService(conn).create("O-BASE", "基线人员", "active")
            MachineService(conn).create("M-BASE", "基线设备", op_type_id="OT-IN", status="active")
            SupplierService(conn).create("S-BASE", "基线供方", op_type_value="OT-EXT", default_days=2)
            PartService(conn).upsert_and_parse_no_tx("P-HOURS", "基线工艺", "5数车")
            ConfigService(conn).ensure_defaults()
            conn.commit()
            settings = dict(conn.execute("SELECT config_key,config_value FROM SystemConfig"))
            assert all(settings.get(key, "no") == "no" for key in
                       ("auto_backup_enabled", "auto_backup_cleanup_enabled", "auto_log_cleanup_enabled"))
        self.client.get("/scheduler/config/manual").close()

    def business_state(self):
        with self.db() as conn:
            tables = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
                      if row[0] not in ("OperationLogs", "sqlite_sequence", "SystemJobState")]
            values = {name: [list(row) for row in conn.execute('SELECT * FROM "' + name.replace('"', '""') + '"')]
                      for name in tables}
        raw = json.dumps(values, ensure_ascii=False, sort_keys=True, default=json_value)
        self.state_counter += 1
        (self.root / ("business-state-" + str(self.state_counter) + ".json")).write_text(raw, encoding="utf-8")
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def save_response(self, label, response):
        body = response.get_data()
        content_type = response.headers.get("Content-Type", "")
        suffix = ".html" if "html" in content_type else ".json" if "json" in content_type else ".bin"
        target = self.root / (label + suffix)
        target.write_bytes(body)
        row = {"label": label, "status": response.status_code, "content_type": content_type,
               "location": response.headers.get("Location"), "disposition": response.headers.get("Content-Disposition"),
               "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest(), "path": str(target)}
        self.responses.append(row)
        return row

    def write_result(self, value):
        self.assert_loaded_source()
        self.source_guard.verify_files()
        result = {"source": str(self.source), "runtime_root": str(self.root), "candidate": self.candidate,
                  "factory": "app.py:create_app -> create_app_with_mode(default) -> create_app_core",
                  "configured_paths": {key: self.app.config[key] for key in ("BASE_DIR", "DATABASE_PATH", "LOG_DIR", "BACKUP_DIR", "EXCEL_TEMPLATE_DIR")},
                  "fixture_preparation": "Original ConfigService.ensure_defaults initializes pristine ScheduleConfig before the measured import flow; cold behavior recorded separately in R1.",
                  "source_binding": {"manifest": str(self.source_guard.manifest_path),
                                     "aggregate_sha256": self.source_guard.manifest["aggregate_sha256"],
                                     "origin_root": str(self.source_guard.origin),
                                     "sys_path": list(sys.path), "dependency_roots": [str(path) for path in self.source_guard.dependencies],
                                     "static_inventory": self.source_guard.manifest["static_import_inventory"],
                                     "owned_import_roots": sorted(self.source_guard.owners), "source_content_and_modes_verified": True},
                  "loaded_modules": self.loaded_modules, "responses": self.responses, **value}
        (self.root / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, default=json_value) + "\n", encoding="utf-8")
        return result
