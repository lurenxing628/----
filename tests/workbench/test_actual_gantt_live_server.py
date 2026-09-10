"""Test-only Flask server against the caller's temporary fixture database."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from werkzeug.serving import make_server

from tests.workbench.test_actual_gantt_support import prepare


def serve(root):
    root = Path(root)
    api = prepare(root / "actual-gantt.db")
    before = api.state()
    server = make_server("127.0.0.1", 0, api.app)
    (root / "ready.json").write_text(json.dumps({"url": "http://127.0.0.1:" + str(server.server_port), "plan_ref": api.ref()}), encoding="utf-8")
    try:
        server.serve_forever()
    finally:
        (root / "db-evidence.json").write_text(json.dumps({"unchanged": before == api.state(), "statements": api.statements}), encoding="utf-8")
        server.server_close()


if __name__ == "__main__":
    import signal
    signal.signal(signal.SIGTERM, lambda *args: sys.exit(0))
    serve(sys.argv[1])
