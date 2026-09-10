"""Real app_main host; only fixture paths/assets and evidence hooks are supplied."""

import atexit
import json
import os
import sys
import tempfile
from contextlib import closing
from pathlib import Path


def main():
    root = Path(sys.argv[1]).resolve()
    os.chdir(str(root))
    tempfile.tempdir = str(root / "tmp")
    from jinja2 import FileSystemLoader

    from core.infrastructure.database import get_connection
    from tests.workbench import system_restore_entrypoint_process_support as driver
    from tests.workbench.final_operations_source_binding import source_binding
    from tests.workbench.live_environment import install_path_guard
    from tests.workbench.run_jobs_support import JobCase
    from tests.workbench.run_live_server_support import attach_journal, loaded_python_sources
    from web.bootstrap import factory

    evidence = install_path_guard(root)
    original = driver.create_app
    make_server = factory.make_server

    def make(*args, **kwargs):
        server = make_server(*args, **kwargs)
        app = args[2].app
        worker_file = root / "worker-seed.json"
        if sys.argv[2] == "normal" and not worker_file.exists() and (root / "seed.json").exists():
            with app.app_context(), closing(get_connection(app.config["DATABASE_PATH"])) as conn:
                job = JobCase(conn)
                accepted = job.accept(key="final-operations-worker-000001", settings=job.settings("FQ1"))
            app.extensions["workbench_run_runtime"](accepted["run_ref"])
            worker_file.write_text(json.dumps(accepted), encoding="utf-8")
        return server

    def create_app(directory, mode):
        app = original(directory, mode)
        app.static_folder = str(root / "frozen" / "static")
        app.jinja_env.loader = FileSystemLoader(str(root / "frozen" / "templates"))
        app.config["WORKBENCH_INSTANCE_LABEL"] = "Final operations isolated fixture"
        attach_journal(app, root / "requests.jsonl")
        (root / "source-at-create.json").write_text(json.dumps(loaded_python_sources()), encoding="utf-8")
        binding = source_binding()
        assert binding is None or not binding["violations"], binding["violations"] if binding else None
        return app

    def record():
        binding = source_binding()
        violations = evidence["violations"] + (binding["violations"] if binding else [])
        payload = json.dumps({
            "sqlite_connections": evidence["sqlite_connections"], "violations": violations,
            "sources": loaded_python_sources(), "pid": os.getpid(), "source_binding": binding,
        }, ensure_ascii=False, indent=2)
        (root / "process-evidence.json").write_text(payload, encoding="utf-8")
        (root / f"process-evidence-{os.getpid()}.json").write_text(payload, encoding="utf-8")

    driver.create_app = create_app
    factory.make_server = make
    atexit.register(record)
    return driver.main()


if __name__ == "__main__":
    sys.exit(main())
