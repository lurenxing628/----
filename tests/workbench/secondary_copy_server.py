"""EO-only wrapper around the existing real factory fixture; temporary data only."""

import argparse
import hashlib
import json
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests.workbench import run_live_server as live
from tests.workbench.secondary_copy_assets import freeze


def record_transport(app, output):
    """Observe the real outer WSGI transport, including restore-host before Flask."""
    original = app.wsgi_app

    def transport(environ, start_response):
        digest = hashlib.sha256()
        status_code = []

        def start(status, headers, exc_info=None):
            status_code.append(int(status.split()[0]))
            write = start_response(status, headers, exc_info)

            def observed_write(data):
                digest.update(data)
                return write(data)

            return observed_write

        response = original(environ, start)
        try:
            for data in response:
                digest.update(data)
                yield data
        finally:
            if hasattr(response, "close"):
                response.close()
            if environ["PATH_INFO"].startswith("/api/workbench/"):
                with output.open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps({"method": environ["REQUEST_METHOD"], "path": environ["PATH_INFO"],
                                             "status": status_code, "body_sha256": digest.hexdigest()}) + "\n")

    app.wsgi_app = transport


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    root, identity = live.prepare_root(parser.parse_args().root)
    original = live.seed_run_data
    original_journal = live.attach_journal

    def journal(app, path):
        original_journal(app, path)
        record_transport(app, root / "secondary-copy-transport.jsonl")

    def seed(app, **kwargs):
        result = original(app, **kwargs)
        with closing(sqlite3.connect(app.config["DATABASE_PATH"])) as conn:
            conn.executemany("""INSERT INTO Materials(material_id,name,spec,unit,stock_qty,status,remark)
                VALUES (?,?,?,'千克',?,'active',?)""",
                [("EO-MAT-" + str(n).zfill(3), "精密轴承毛坯材料", None if n == 1 else "直径120毫米 / 长度850毫米", n + .125,
                  "独立临时库，只读文案验证") for n in range(1, 26)])
            conn.commit()
        result["secondary_copy"] = {"material_count": 25, "material_prefix": "EO-MAT-"}
        return result

    live.seed_run_data = seed
    live.attach_journal = journal
    live.freeze_built_assets = freeze
    live.FORBIDDEN_PORTS.update({52392, 58448, 64612})
    return live.serve(root, identity, profile="mixed")


if __name__ == "__main__":
    sys.exit(main())
