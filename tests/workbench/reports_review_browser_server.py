"""EI factory server with a frozen main-page build, owned candidates and SQL evidence."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import threading
import uuid
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests.workbench import run_live_server as live
from tests.workbench.live_environment import REPO, sha256, write_json
from tests.workbench.reports_review_browser_seed import seed
from tests.workbench.run_live_server_support import freeze_built_assets, tree_hashes


def freeze(root, session):
    result = freeze_built_assets(root, session)
    order = json.loads((REPO / "scripts/workbench/build-order.json").read_text())
    sources = []
    directory = root / "owned-sources"
    directory.mkdir()
    for source in (REPO / "frontend/workbench/app").iterdir():
        if source.name.startswith(("Report", "Review")) and source.suffix in (".js", ".jsx"):
            code = source.read_text(encoding="utf-8")
            (directory / source.name).write_text(code, encoding="utf-8")
            sources.append({"path": "app/" + source.name, "code": code})
    request = {"babel_path": str(REPO / "frontend/workbench/prototype" / order["babel"]["path"]), "sources": sources}
    compiled = subprocess.run([os.environ["WORKBENCH_NODE"], str(REPO / "scripts/workbench/compile.cjs")],
                              input=json.dumps(request), text=True, capture_output=True, check=True)
    candidates = []
    for source, output in zip(sources, json.loads(compiled.stdout)["outputs"]):
        target = Path(result["static"]) / "workbench" / Path(output["path"]).with_suffix(".js")
        previous = sha256(target.read_bytes())
        target.write_text(output["code"], encoding="utf-8")
        candidates.append({"source": "frontend/workbench/" + source["path"],
                           "source_sha256": sha256(source["code"].encode("utf-8")),
                           "static": str(target), "baseline_sha256": previous, "candidate_sha256": sha256(target.read_bytes())})
    result.update(ei_candidates=candidates, global_build=False,
                  binding="Frozen published main-page baseline plus owned Report/Review candidates, not a unified build",
                  hashes=tree_hashes(Path(result["root"])))
    write_json(root / "ei-candidate-assets.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root, identity = live.prepare_root(args.root)
    lock = threading.Lock()

    def prepare(app, **_kwargs):
        from flask import g, request

        from tests.workbench.report_execution_ledger_support import report_ledger_api

        api = report_ledger_api.__wrapped__(app.test_client())
        recording = [False]

        @app.before_request
        def trace_reports():
            if recording[0] and request.method == "GET" and request.path.startswith(("/api/workbench/v1/analytics", "/api/workbench/v1/reports/")):
                g.db.execute("PRAGMA query_only=ON")
                url = request.full_path

                def trace(sql):
                    with lock, (root / "ei-sql.jsonl").open("a", encoding="utf-8") as stream:
                        stream.write(json.dumps({"url": url, "sql": sql}, ensure_ascii=False) + "\n")

                g.db.set_trace_callback(trace)

        @app.after_request
        def capture_payload(response):
            if recording[0] and not request.path.startswith("/static/"):
                row = {"url": request.full_path, "method": request.method, "status": response.status_code,
                       "sha256": None if response.direct_passthrough else sha256(response.get_data()),
                       "streamed": response.direct_passthrough, "headers": dict(response.headers)}
                if response.is_json:
                    row["payload"] = response.get_json()
                with lock, (root / "ei-http.jsonl").open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(row, ensure_ascii=False) + "\n")
                if response.direct_passthrough:
                    original = response.response
                    target = root / "downloads" / ("wire-" + uuid.uuid4().hex + ".bin")

                    def capture_stream():
                        digest, length = hashlib.sha256(), 0
                        try:
                            with target.open("wb") as output:
                                for chunk in original:
                                    output.write(chunk)
                                    digest.update(chunk)
                                    length += len(chunk)
                                    yield chunk
                            saved = {"url": row["url"], "path": str(target), "bytes": length, "sha256": digest.hexdigest()}
                            with lock, (root / "ei-streams.jsonl").open("a", encoding="utf-8") as stream:
                                stream.write(json.dumps(saved) + "\n")
                        finally:
                            if hasattr(original, "close"):
                                original.close()

                    response.response = capture_stream()
            return response

        expected = seed(api)
        recording[0] = True
        write_json(root / "ei-seed.json", expected)
        return {"ei": expected}

    live.seed_run_data = prepare
    live.freeze_built_assets = freeze
    live.FORBIDDEN_PORTS.update({52392, 58448, 64612})
    return live.serve(root, identity, profile="first-plan")


if __name__ == "__main__":
    sys.exit(main())
