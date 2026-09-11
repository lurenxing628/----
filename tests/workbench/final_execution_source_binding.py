"""Capture a full source copy and run Task E with G's strict source guard."""

import argparse
import hashlib
import importlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HELPERS = Path(".codestable/roadmap/workbench-prototype-migration/legacy-retirement/factory-tests")


def seal(parent):
    parent = parent.resolve()
    parent.mkdir(parents=True, exist_ok=False)
    source, manifest = parent / "source", parent / "source-manifest.json"
    capture = [sys.executable, "-B", str(REPO / HELPERS / "source_binding.py")]
    facts = sorted(path.relative_to(REPO).as_posix() for path in (REPO / ".codestable").rglob("*")
                   if path.is_file() and path.suffix not in (".py", ".pyc", ".pyo") and "__pycache__" not in path.parts)
    helpers = [(HELPERS / name).as_posix() for name in ("source_guard.py", "source_binding.py", "source_inventory.py")]
    documents = sorted(path.name for path in REPO.glob("*.md"))
    documents += [name for name in ("docs", "开发文档", "策划方案", "前端设计", ".github", ".limcode") if (REPO / name).exists()]
    extras = [item for name in facts + helpers + documents for item in ("--extra", name)]
    subprocess.run(capture + ["capture", str(REPO), str(manifest)] + extras, check=True)
    value = json.loads(manifest.read_text(encoding="utf-8"))
    for row in value["files"]:
        target = source / row["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(REPO / row["path"]), str(target))
    subprocess.run(capture + ["check", str(REPO), str(manifest)], check=True)
    subprocess.run(capture + ["check", str(source), str(manifest)], check=True)
    value["root"] = str(source)
    value["copy_preimage_content_and_modes_verified"] = True
    manifest.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    shutil.copytree(str(source / HELPERS), str(parent / "factory-tests"))
    print(json.dumps({"manifest": str(manifest), "source": str(source), "aggregate_sha256": value["aggregate_sha256"]}), flush=True)


def derive(base_manifest, parent, overrides):
    base = json.loads(base_manifest.read_text(encoding="utf-8"))
    base_source, parent = Path(base["root"]).resolve(), parent.resolve()
    allowed = {"tests/workbench/final_execution_analytics.cjs", "tests/workbench/final_execution_read_reentry.cjs",
               "tests/workbench/test_actual_gantt_browser.cjs", "tests/workbench/calibration_lineage_ui_probe.cjs",
               "tests/workbench/calibration_adoption_widgets_probe.cjs", "tests/workbench/point_downstream_browser.cjs",
               "tests/workbench/test_point_downstream_api.py", "tests/workbench/test_point_downstream_browser.py",
               "frontend/workbench/app/ActualGanttWorkspace.jsx"}
    if not overrides or set(overrides) - allowed or len(overrides) != len(set(overrides)):
        raise ValueError("Only the explicitly authorized Task E source delta may differ from this sealed base")
    parent.mkdir(parents=True, exist_ok=False)
    source, manifest = parent / "source", parent / "source-manifest.json"
    command = [sys.executable, "-B", str(base_source / HELPERS / "source_binding.py")]
    subprocess.run(command + ["check", str(base_source), str(base_manifest)], check=True)
    for row in base["files"]:
        target = source / row["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(base_source / row["path"]), str(target))
    subprocess.run(command + ["check", str(source), str(base_manifest)], check=True)
    for name in overrides:
        shutil.copy2(str(REPO / name), str(source / name))
    dependency_root = Path(sys.prefix).resolve()
    (source / ".venv").symlink_to(dependency_root, target_is_directory=True)
    extras = [item for row in base["files"] for item in ("--extra", row["path"])]
    subprocess.run(command + ["capture", str(source), str(manifest), "--origin", base["origin_root"]] + extras, check=True)
    current = json.loads(manifest.read_text(encoding="utf-8"))
    if base.get("additional_forbidden_source_roots"):
        current["additional_forbidden_source_roots"] = base["additional_forbidden_source_roots"]
    current["dependency_links"] = {".venv": str(dependency_root)}
    manifest.write_text(json.dumps(current, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    before, after = ({row["path"]: row for row in value["files"]} for value in (base, current))
    changed = {name for name in set(before) | set(after) if before.get(name) != after.get(name)}
    if changed != set(overrides):
        raise RuntimeError("Derived source differs beyond the declared probe corrections: " + repr(changed))
    subprocess.run(command + ["check", str(base_source), str(base_manifest)], check=True)
    subprocess.run(command + ["check", str(source), str(manifest)], check=True)
    shutil.copytree(str(source / HELPERS), str(parent / "factory-tests"))
    product_changes = sorted(name for name in changed if not name.startswith("tests/"))
    delta = {"base_manifest": str(base_manifest), "base_aggregate_sha256": base["aggregate_sha256"],
             "aggregate_sha256": current["aggregate_sha256"], "all_product_files_unchanged": not product_changes,
             "authorized_product_changes": product_changes,
             "dependency_links": current["dependency_links"],
             "changes": [{"before": before[name], "after": after[name]} for name in sorted(changed)]}
    (parent / "source-delta.json").write_text(json.dumps(delta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"source": str(source), "manifest": str(manifest), **delta}), flush=True)


def copy_failure(manifest, expected_sha256, parent):
    raw = manifest.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("The public failed-source manifest differs from the supplied SHA-256")
    baseline = json.loads(raw)
    original, parent = Path(baseline["root"]).resolve(), parent.resolve()
    source = parent / "source"
    parent.mkdir(parents=True, exist_ok=False)
    for row in baseline["entries"]:
        relative = Path(row["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Source manifest path must remain inside its declared root")
        item, copied = original / relative, source / relative
        data = item.read_bytes()
        if (hashlib.sha256(data).hexdigest(), len(data), stat.S_IMODE(item.stat().st_mode)) != (row["sha256"], row["bytes"], row["mode"]):
            raise RuntimeError("The immutable failed source changed: " + str(relative))
        copied.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(item), str(copied))
        if copied.read_bytes() != data or stat.S_IMODE(copied.stat().st_mode) != row["mode"]:
            raise RuntimeError("Failed-source copy content or modes differ: " + str(relative))
    guard_source = Path("/private/tmp/aps-final-e-sealed-read-after-20260911-06/source")
    guard_manifest = json.loads((guard_source.parent / "source-manifest.json").read_text(encoding="utf-8"))
    declared = {row["path"]: row for row in guard_manifest["files"]}
    additions = []
    for name in ("source_guard.py", "source_binding.py", "source_inventory.py"):
        relative = (HELPERS / name).as_posix()
        item, target = guard_source / relative, source / relative
        if hashlib.sha256(item.read_bytes()).hexdigest() != declared[relative]["sha256"]:
            raise RuntimeError("The sealed G source helper changed")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(item), str(target))
        additions.append(relative)
    runner = "tests/workbench/final_execution_source_binding.py"
    shutil.copy2(str(Path(__file__).resolve()), str(source / runner))
    command = [sys.executable, "-B", str(source / HELPERS / "source_binding.py")]
    extras = [part for relative in [row["path"] for row in baseline["entries"]] + additions for part in ("--extra", relative)]
    result = parent / "source-manifest.json"
    subprocess.run(command + ["capture", str(source), str(result), "--origin", str(REPO)] + extras, check=True)
    current = json.loads(result.read_text(encoding="utf-8"))
    current["additional_forbidden_source_roots"] = [str(original), baseline["source"]]
    result.write_text(json.dumps(current, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    subprocess.run(command + ["check", str(source), str(result)], check=True)
    for row in baseline["entries"]:
        item = original / row["path"]
        if (hashlib.sha256(item.read_bytes()).hexdigest(), item.stat().st_size, stat.S_IMODE(item.stat().st_mode)) != (row["sha256"], row["bytes"], row["mode"]):
            raise RuntimeError("The public failed source changed while being copied")
    if manifest.read_bytes() != raw:
        raise RuntimeError("The public source manifest changed while being copied")
    shutil.copytree(str(source / HELPERS), str(parent / "factory-tests"))
    proof = {"public_manifest": str(manifest.resolve()), "public_manifest_sha256": expected_sha256,
             "source": str(source), "files": baseline["file_count"], "bytes": baseline["bytes"],
             "public_files_sha256_and_modes_verified_before_after": True,
             "product_delta": [], "test_harness_additions": additions, "test_harness_replaced": [runner],
             "aggregate_sha256": current["aggregate_sha256"]}
    (parent / "copy-proof.json").write_text(json.dumps(proof, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(proof), flush=True)


def install_guard():
    name = os.environ.get("FINAL_E_SOURCE_MANIFEST")
    if not name:
        return None
    manifest = Path(name).resolve()
    value = json.loads(manifest.read_text(encoding="utf-8"))
    if Path(value["root"]).resolve() != REPO or Path(value["origin_root"]).resolve() == REPO:
        raise RuntimeError("Task E must execute from its declared sealed source copy")
    harness = REPO.parent / "factory-tests"
    rows = {row["path"]: row for row in value["files"]}
    for filename in ("source_guard.py", "source_binding.py", "source_inventory.py"):
        path = harness / filename
        data = path.read_bytes()
        expected = rows[(HELPERS / filename).as_posix()]
        if (hashlib.sha256(data).hexdigest(), len(data), format(stat.S_IMODE(path.stat().st_mode), "04o")) != (
                expected["sha256"], expected["bytes"], expected["mode"]):
            raise RuntimeError("Copied G guard differs from the sealed manifest: " + filename)
    sys.path.insert(0, str(harness))
    guard = importlib.import_module("source_guard").FrozenSourceGuard(REPO, harness, manifest)
    guard.restrict_sys_path()
    violations = []
    forbidden = [Path(path).resolve() for path in value.get("additional_forbidden_source_roots", [])]

    def audit(event, args):
        if event in ("open", "os.listdir", "os.scandir"):
            try:
                guard.check_read(args[0])
                if args[0] is not None and not isinstance(args[0], int):
                    path = Path(os.fsdecode(args[0])).resolve()
                    if any(path == root or root in path.parents for root in forbidden) and not guard.dependency(path):
                        raise PermissionError("External fixed-source fallback blocked: " + str(path))
            except PermissionError as error:
                violations.append({"event": event, "error": str(error)})
                raise

    sys.addaudithook(audit)
    return guard, violations


def finish_guard(binding, output):
    if binding is None:
        return
    guard, violations = binding
    value = {"source": str(REPO), "origin": str(guard.origin), "manifest": str(guard.manifest_path),
             "aggregate_sha256": guard.manifest["aggregate_sha256"], "read_violations": violations}
    try:
        value["loaded_modules"] = guard.inspect_modules()
        guard.verify_files()
        if violations:
            raise RuntimeError("The sealed source attempted original-checkout fallback")
        value["content_and_modes_verified"] = True
    except Exception as error:
        value["error"] = str(error)
        raise
    finally:
        output.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run(manifest, output, tests):
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    (output / "tmp").mkdir()
    os.environ.update(FINAL_E_SOURCE_MANIFEST=str(manifest.resolve()), FINAL_E_PARENT=str(output),
                      PYTHONDONTWRITEBYTECODE="1", PYTEST_DISABLE_PLUGIN_AUTOLOAD="1", TMPDIR=str(output / "tmp"))
    sys.dont_write_bytecode = True
    tempfile.tempdir = str(output / "tmp")
    os.chdir(str(REPO))
    binding = install_guard()
    if binding is None:
        raise RuntimeError("A full source manifest is required")
    import pytest

    try:
        return int(pytest.main(["-q", "-s", "-p", "no:cacheprovider", "-o", "log_file=" + str(output / "pytest.log"),
                               "--basetemp", str(output / "pytest"), "--junitxml", str(output / "pytest.xml"), *tests]))
    finally:
        finish_guard(binding, output / "sealed-pytest-source.json")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    capture = sub.add_parser("seal")
    capture.add_argument("parent", type=Path)
    delta = sub.add_parser("derive")
    delta.add_argument("base_manifest", type=Path)
    delta.add_argument("parent", type=Path)
    delta.add_argument("overrides", nargs="+")
    failure = sub.add_parser("copy-failure")
    failure.add_argument("manifest", type=Path)
    failure.add_argument("expected_sha256")
    failure.add_argument("parent", type=Path)
    execute = sub.add_parser("run")
    execute.add_argument("manifest", type=Path)
    execute.add_argument("output", type=Path)
    execute.add_argument("tests", nargs="+")
    args = parser.parse_args()
    if args.mode == "seal":
        seal(args.parent)
        return 0
    if args.mode == "derive":
        derive(args.base_manifest, args.parent, args.overrides)
        return 0
    if args.mode == "copy-failure":
        copy_failure(args.manifest, args.expected_sha256, args.parent)
        return 0
    return run(args.manifest, args.output, args.tests)


if __name__ == "__main__":
    sys.exit(main())
