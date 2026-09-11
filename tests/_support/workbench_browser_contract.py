"""Small Chromium 109 contracts against existing assets and isolated Flask apps."""

import json
import os
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

from werkzeug.serving import make_server

from tests._support.paths import REPO_ROOT
from web.bootstrap.workbench_request_lifecycle import WorkbenchRequestHandler

REQUIRED_INPUTS = (
    "tests/_support/workbench_browser_probe.cjs",
    "static/workbench/vendor/react-18.3.1.production.min.js",
    "static/workbench/vendor/react-dom-18.3.1.production.min.js",
)


def browser_contract(body, *, scripts=(), data=None, app=None, path="/workbench"):
    """Execute declared test assertions in real React, without builds or installs."""
    bundled = Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node"
    node = os.environ.get("WORKBENCH_NODE") or (str(bundled / "bin/node") if (bundled / "bin/node").is_file() else shutil.which("node"))
    browser = os.environ.get("WORKBENCH_BROWSER") or "/tmp/aps-chromium109-assessment/runtime/chrome-mac/Chromium.app/Contents/MacOS/Chromium"
    assert node and Path(browser).is_file(), "Existing Node and Chromium 109 are required; never install/skip."
    inputs = REQUIRED_INPUTS + tuple(scripts)
    if app is not None:
        manifest = json.loads((REPO_ROOT / "static/workbench/asset-manifest.json").read_text(encoding="utf-8"))
        inputs += ("static/workbench/asset-manifest.json",) + tuple(
            "static/" + name for name in manifest["styles"] + manifest["scripts"] + [manifest["theme_script"]])
    inputs = tuple(dict.fromkeys(inputs))
    assert all((REPO_ROOT / name).is_file() for name in inputs), inputs
    output = Path(tempfile.mkdtemp(prefix="aps-A-web-contract-"))
    request = {"body": body, "data": data, "scripts": list(scripts), "inputs": list(inputs),
               "root": str(REPO_ROOT), "output": str(output), "url": None}
    server = thread = None
    try:
        if app is not None:
            server = make_server("127.0.0.1", 0, app, threaded=True, request_handler=WorkbenchRequestHandler)
            thread = threading.Thread(target=server.serve_forever)
            thread.start()
            request["url"] = "http://127.0.0.1:" + str(server.server_port) + path
        env = dict(os.environ, WORKBENCH_BROWSER=browser,
                   NODE_PATH=os.pathsep.join(value for value in (os.environ.get("NODE_PATH"), str(bundled / "node_modules")) if value))
        result = subprocess.run([node, str(REPO_ROOT / REQUIRED_INPUTS[0])], input=json.dumps(request),
                                cwd=str(REPO_ROOT), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, timeout=120)
        (output / "probe.log").write_text(result.stdout, encoding="utf-8")
    finally:
        if server is not None:
            server.shutdown()
            thread.join(timeout=15)
            server.server_close()
    print("A_WEB_CONTRACT_ARTIFACTS " + str(output), flush=True)
    assert result.returncode == 0, result.stdout + "\n" + str(output)
    return json.loads((output / "result.json").read_text(encoding="utf-8"))["value"]
