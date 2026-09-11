"""Run selected regressions from bound source with no original-checkout fallback."""

import argparse
import json
import os
import sys
import traceback
from pathlib import Path

from factory_runtime import configure, enforce_private_writes
from source_guard import FrozenSourceGuard


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("runtime", type=Path)
    parser.add_argument("tests", nargs="+")
    args = parser.parse_args()
    source, runtime = configure(args.source, args.runtime)
    guard = FrozenSourceGuard(source, Path(__file__).resolve().parent, Path(os.environ["FACTORY_SOURCE_MANIFEST"]))
    guard.restrict_sys_path()
    enforce_private_writes(runtime, guard)
    os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    import pytest

    try:
        code = int(pytest.main(["-q", "-p", "no:cacheprovider", "-o", "log_file=" + str(runtime / "pytest.log"),
                               "--basetemp", str(runtime / "pytest"), *args.tests]))
        loaded = guard.inspect_modules()
        guard.verify_files()
        result = {"passed": code == 0, "exit_code": code, "tests": args.tests,
                  "source_sha256": guard.manifest["aggregate_sha256"],
                  "source_content_and_modes_verified": True, "loaded_modules": loaded, "sys_path": list(sys.path)}
    except Exception as exc:
        code = 1
        result = {"passed": False, "error": str(exc), "traceback": traceback.format_exc()}
    (runtime / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": result["passed"], "error": result.get("error")}, ensure_ascii=False), flush=True)
    return code


if __name__ == "__main__":
    sys.exit(main())
