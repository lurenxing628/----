"""Owned process, immutable current-input build, browser and SQL evidence."""

import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
from contextlib import closing
from pathlib import Path

from core.infrastructure.database import get_connection
from tests.workbench.test_live_browser import runtime_tools
from tests.workbench.test_system_restore_entrypoint_support import ProcessHost, wait_for

REPO = Path(__file__).resolve().parents[2]
DEFAULT_BUILD = REPO / "static/workbench"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def freeze(root):
    build = Path(os.environ.get("FINAL_OPERATIONS_BUILD", str(DEFAULT_BUILD))).resolve()
    source = build / "asset-manifest.json"
    manifest = json.loads(source.read_text(encoding="utf-8"))
    assert manifest["target"] == "chrome109"
    stale = [row["path"] for row in manifest["inputs"] if digest(REPO / row["path"]) != row["sha256"]]
    assert not stale, "Build input drift; request a current full build: " + repr(stale)
    target = root / "frozen" / "static" / "workbench"
    for row in manifest["files"]:
        name = Path(row["path"]).relative_to("workbench")
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        data = (build / name).read_bytes()
        assert len(data) == row["bytes"] and hashlib.sha256(data).hexdigest() == row["sha256"]
        path.write_bytes(data)
    shutil.copyfile(str(source), str(target / "asset-manifest.json"))
    shutil.copytree(str(REPO / "templates/workbench"), str(root / "frozen/templates/workbench"))
    return {"build_id": manifest["build_id"], "manifest_sha256": digest(source),
            "build_source": str(source), "source_inputs": manifest["inputs"], "files": manifest["files"]}


class OperationsHost(ProcessHost):
    def __init__(self, root, mode="normal"):
        super().__init__(root, mode)
        for name in ("logs", "tmp", "home", "templates", "downloads", "screenshots"):
            (self.root / name).mkdir(exist_ok=True)
        self.assets = freeze(self.root)

    def start(self, *, reuse_port=False):
        if not reuse_port:
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                self.port = sock.getsockname()[1]
        assert self.port != 53144
        env = {key: value for key, value in os.environ.items() if not key.startswith("APS_")}
        env.update(APS_ENV="production", APS_HOST="127.0.0.1", APS_PORT=str(self.port),
                   APS_DB_PATH=str(self.path), APS_LOG_DIR=str(self.root / "logs"),
                   APS_BACKUP_DIR=str(self.backups), APS_SYSTEM_JOURNAL_DIR=str(self.journal_dir),
                   APS_EXCEL_TEMPLATE_DIR=str(self.root / "templates"), SECRET_KEY="final-operations-private-key",
                   TMPDIR=str(self.root / "tmp"), HOME=str(self.root / "home"),
                   PYTHONPYCACHEPREFIX=str(self.root / "pycache"), PYTHONDONTWRITEBYTECODE="1")
        env.pop("WERKZEUG_RUN_MAIN", None)
        (self.root / "ready.json").unlink(missing_ok=True)
        if hasattr(self, "log"):
            self.log.close()
        self.log = open(self.root / "process.log", "a", encoding="utf-8")
        self._process = subprocess.Popen([sys.executable, "-B", "-m", "tests.workbench.final_operations_host", str(self.root), self.mode],
                                        cwd=str(REPO), env=env, stdout=self.log, stderr=subprocess.STDOUT)
        wait_for(lambda: (self.root / "ready.json").exists() or self.process.poll() is not None, timeout=45)
        assert self.process.poll() is None, (self.root / "process.log").read_text()
        self.ready = json.loads((self.root / "ready.json").read_text())
        self.contract = json.loads((self.root / "logs/aps_runtime.json").read_text())
        self.lock_paths = [self.root / "logs/aps_runtime.lock", Path(str(self.path) + ".lock")]
        self.lock_bytes = [path.read_bytes() for path in self.lock_paths]
        assert self.ready["pid"] == self.process.pid and self.ready["port"] == self.port
        return self

    def stored(self, sql, args=()):
        with closing(get_connection(str(self.path))) as conn:
            return [dict(row) for row in conn.execute(sql, args)]

    def marker(self):
        return self.stored("SELECT config_value FROM SystemConfig WHERE config_key='FINAL_OPERATIONS'")[0]["config_value"]

    def probe(self, mode, width=1392, theme="light", **extra):
        node, browser, modules = runtime_tools()
        output = self.root / f"probe-{mode}-{width}-{theme}"
        output.mkdir()
        config = {"origin": "http://127.0.0.1:" + str(self.port), "output": str(output), "mode": mode,
                  "viewport": {"width": width, "height": 1080 if width == 1920 else 924}, "theme": theme,
                  "assets": self.assets, "backup_dir": str(self.backups), "database": str(self.path),
                  "journal_dir": str(self.journal_dir), **extra}
        result = subprocess.run([node, str(REPO / "tests/workbench/final_operations.cjs")],
                                input=json.dumps(config), text=True, capture_output=True, timeout=240,
                                cwd=str(REPO), env=dict(os.environ, NODE_PATH=modules, WORKBENCH_BROWSER=browser))
        (output / "runner.log").write_text(result.stdout + result.stderr, encoding="utf-8")
        assert result.returncode == 0, str(output) + "\n" + result.stdout + result.stderr
        return json.loads((output / "report.json").read_text(encoding="utf-8"))
