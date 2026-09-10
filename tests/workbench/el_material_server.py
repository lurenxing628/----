"""EL real application fixture; reuse ED seed read-only, never its live database."""

import argparse
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests.workbench import run_live_server as live
from tests.workbench.ed_material_process_seed import seed
from tests.workbench.el_material_assets import freeze


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root, identity = live.prepare_root(args.root)
    original = live.seed_run_data

    def prepare(app, **kwargs):
        result = original(app, **kwargs)
        result["ed"] = seed(app)
        with closing(sqlite3.connect(app.config["DATABASE_PATH"])) as conn:
            conn.execute("PRAGMA foreign_keys=ON")
            for state, data in result["ed"]["states"].items():
                prefix = "EL-last-page-" + state + "-"
                data["delete_prefix"], data["delete_target"] = prefix, prefix + "041"
                data["create_code"] = "EL-created-" + state
                conn.executemany("""INSERT INTO Materials(material_id,name,spec,unit,stock_qty,status,remark)
                    VALUES (?,?,'retained-spec','kg',1,'active','retained-remark')""",
                    [(prefix + str(n).zfill(3), "EL deletion fixture " + str(n)) for n in range(1, 42)])
            conn.commit()
            assert not conn.execute("PRAGMA foreign_key_check").fetchall()
        return result

    live.seed_run_data = prepare
    live.freeze_built_assets = freeze
    live.FORBIDDEN_PORTS.update({52392, 58448, 64612})
    return live.serve(root, identity, profile="calibration")


if __name__ == "__main__":
    sys.exit(main())
