"""Verify current workbench UI evidence; opt-in only and no browser skip-to-pass."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tools.test_registry_workbench_ui import WORKBENCH_UI_BROWSER_TARGETS

VIEWS = ("dashboard", "process", "basedata", "batches", "run", "analysis", "trial", "gantt",
         "delay", "field", "fieldgantt", "review", "reports", "calib", "system")
SIZES = ((1366, 768), (1280, 720))
THEMES = ("light", "dark")
BASE_CHECKS = {"G2", "G4", "G5", "G6", "L1", "L2", "L3"}
INTERACTION_CHECKS = {"batch-table-scroll": "G1", "batch-validation": "I2", "plan-selected": "G3", "run-picker": "I4",
                      "field-expanded": "I5", "dashboard-detail": "I6", "trial-new": "I7", "calibration-detail": "I8"}
UI_HOST_INPUTS = ("web/routes/workbench/pages.py", "web/routes/workbench/navigation_metadata.py",
                  "web/routes/workbench/navigation_boot.py", "web/routes/workbench/assets.py")
PROBE_INPUTS = ("ui_refinement_capture.cjs", "ui_refinement_geometry.cjs", "ui_refinement_interactions.cjs")
OWNERS = {
    "G1": ("batch_resources", "wbui-css-layer-table-frame"),
    "G2": ("style_foundation", "wbui-viewport-budget"),
    "G3": ("plan_gantt", "wbui-plan-center-first-screen"),
    "G4": ("workspace_owner", "wbui-viewport-budget"),
    "G5": ("workspace_owner", "wbui-run-stepper"),
    "G6": ("workspace_owner", "wbui-terms-and-ids"),
    "L1": ("workspace_owner", "wbui-viewport-budget"),
    "L2": ("workspace_owner", "wbui-viewport-budget"),
    "L3": ("workspace_owner", "wbui-css-layer-table-frame"),
}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def expected_ids():
    return {f"{view}-{width}-{height}-{theme}"
            for view in VIEWS for width, height in SIZES for theme in THEMES}


def validate_source_binding(source, repository):
    errors = []
    repository = Path(repository).resolve()
    if source.get("source_differences_at_freeze") != []:
        errors.append("source/build differences existed when the server was frozen")
    probes = source.get("probe_sources", {})
    if set(probes) != set(PROBE_INPUTS):
        errors.append("collector source binding is incomplete")
    for name, expected in probes.items():
        file = repository / "tests/workbench" / name
        if not file.is_file() or digest(file) != expected:
            errors.append("collector source changed: " + name)
    loaded = source.get("loaded_python_sources", {})
    for name in UI_HOST_INPUTS:
        file = repository / name
        if not file.is_file() or loaded.get(str(file)) != digest(file):
            errors.append("UI host source missing or changed: " + name)
    assets = source.get("assets_hashes", {})
    if "templates/workbench/index.html" not in assets:
        errors.append("frozen UI template binding is incomplete")
    for name, expected in assets.items():
        file = repository / name
        if not file.is_file() or digest(file) != expected:
            errors.append("frozen UI asset/template changed: " + name)
    return errors


def backend_source_drift(source, repository=REPO):
    """Background source changes are reported separately from the UI build binding."""
    root = Path(repository).resolve()
    changed = []
    for name, expected in source.get("loaded_python_sources", {}).items():
        file = Path(name)
        try:
            relative = file.relative_to(root).as_posix()
        except ValueError:
            continue
        if relative.startswith(".venv/") or relative in UI_HOST_INPUTS:
            continue
        if not file.is_file() or digest(file) != expected:
            changed.append(relative)
    return sorted(changed)


def validate_report(report, evidence_dir, *, repository=REPO, bind_current=True):
    """Return hard errors and failed measurements; missing measurements are hard errors."""
    evidence_dir, repository = Path(evidence_dir), Path(repository)
    errors, failures = [], []
    if report.get("schema_version") != 1 or report.get("kind") != "workbench-ui-refinement":
        errors.append("invalid evidence schema")
    if not str(report.get("browser", "")).startswith("109."):
        errors.append("real Chromium 109 evidence required")
    if not report.get("completed_at"):
        errors.append("capture did not finish")
    if report.get("errors"):
        errors.append("capture errors: " + json.dumps(report["errors"], ensure_ascii=False))
    if report.get("waivers"):
        errors.append("final evidence must contain zero waivers")
    source = report.get("source", {})
    if bind_current:
        errors.extend(validate_source_binding(source, repository))
    manifest_path = evidence_dir / "asset-manifest.json"
    if not manifest_path.is_file():
        errors.append("missing captured asset manifest")
    else:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if source.get("manifest_sha256") != digest(manifest_path) or source.get("build_id") != manifest.get("build_id"):
            errors.append("captured manifest identity mismatch")
        if bind_current:
            current = repository / "static/workbench/asset-manifest.json"
            if not current.is_file() or digest(current) != digest(manifest_path):
                errors.append("evidence does not match current built manifest")
            for item in manifest.get("inputs", []):
                path = repository / item["path"]
                if not path.is_file() or digest(path) != item["sha256"]:
                    errors.append("build input changed: " + item["path"])
    pages = report.get("pages", [])
    ids = [page.get("id") for page in pages]
    if len(ids) != len(set(ids)) or set(ids) != expected_ids():
        errors.append("view/viewport/theme matrix incomplete or duplicated")
    for page in pages:
        page_id = str(page.get("id", "missing"))
        view = page.get("view")
        viewport = page.get("viewport", {})
        identity = "{}-{}-{}-{}".format(view, viewport.get("width"), viewport.get("height"), page.get("theme"))
        if identity != page_id:
            errors.append(page_id + ": measured view/viewport/theme differs from requested case")
        url = urlparse(page.get("url", ""))
        valid_url = url.path == "/workbench/trial" if view == "trial" else (
            url.path == "/workbench" and parse_qs(url.query).get("view") == [view])
        if not valid_url:
            errors.append(page_id + ": landed on another view")
        checks = page.get("checks", [])
        required = BASE_CHECKS | ({"G1"} if view == "batches" else set()) | (
            {"G3"} if view in ("analysis", "gantt", "delay") else set())
        check_ids = [check.get("id") for check in checks]
        if set(check_ids) != required or len(check_ids) != len(set(check_ids)):
            errors.append(page_id + ": missing, unexpected or duplicate geometric checks")
        for check in checks:
            if check.get("ok") is not True:
                owner, item = OWNERS.get(check.get("id"), ("verification", "wbui-ui-baseline-gate"))
                failures.append({"case": page_id, "check": check.get("id"), "owner": owner,
                                 "roadmap_item": item, "remove_when": "same case passes with the final current build",
                                 "detail": check.get("detail")})
        if page.get("errors"):
            errors.append(page_id + ": browser/network errors")
        shot = evidence_dir / str(page.get("screenshot", ""))
        if not shot.is_file() or shot.read_bytes()[:8] != b"\x89PNG\r\n\x1a\n":
            errors.append(page_id + ": missing PNG screenshot")
        elif page.get("screenshot_sha256") != digest(shot):
            errors.append(page_id + ": screenshot hash mismatch")
        boot = evidence_dir / (page_id + ".boot.json")
        if not boot.is_file() or digest(boot) != page.get("boot_sha256"):
            errors.append(page_id + ": missing or changed boot evidence")
    return errors, failures


def validate_interactions(report, evidence_dir):
    errors, failures = [], []
    values = report.get("interactions", [])
    ids = [value.get("id") for value in values]
    if len(ids) != len(set(ids)) or set(ids) != set(INTERACTION_CHECKS):
        errors.append("eight interaction states are incomplete or duplicated")
    for value in values:
        key = value.get("id")
        if value.get("errors"):
            errors.append(str(key) + ": interaction capture failed")
        checks = value.get("checks", [])
        if {check.get("id") for check in checks} != {INTERACTION_CHECKS.get(key), "G6"} or len(checks) != 2:
            errors.append(str(key) + ": interaction assertions missing or duplicated")
        for check in checks:
            if check.get("ok") is not True:
                owner, item = OWNERS.get(check.get("id"), ("workspace_owner", "wbui-ui-baseline-gate"))
                failures.append({"case": key, "check": check.get("id"), "owner": owner, "roadmap_item": item,
                                 "remove_when": "same interaction passes with the final current build", "detail": check.get("detail")})
        shot = Path(evidence_dir) / str(value.get("screenshot", ""))
        if not shot.is_file() or shot.read_bytes()[:8] != b"\x89PNG\r\n\x1a\n":
            errors.append(str(key) + ": missing interaction PNG")
        elif value.get("screenshot_sha256") != digest(shot):
            errors.append(str(key) + ": interaction screenshot hash mismatch")
    return errors, failures


def validate_densities(report):
    expected = {f"batches-{width}-{height}-{theme}" for width, height in SIZES for theme in THEMES}
    rows = report.get("densities", [])
    ids = [row.get("id") for row in rows]
    if len(ids) != len(set(ids)) or set(ids) != expected:
        return ["dual-size dual-theme density samples are incomplete or duplicated"], []
    failures = []
    for row in rows:
        first, second = row.get("comfortable", []), row.get("compact", [])
        correct = bool(first) and len(first) == len(second) and row.get("table", {}).get("ok") is True
        if correct:
            correct = all(a.get("fontSize") == b.get("fontSize") and a.get("text") == b.get("text")
                          and b.get("height", 0) <= a.get("height", 0) for a, b in zip(first, second))
            correct = correct and any(b.get("height", 0) < a.get("height", 0) for a, b in zip(first, second))
        if not correct:
            failures.append({"case": row.get("id"), "check": "density", "owner": "root",
                             "roadmap_item": "wbui-table-density-noise", "detail": row,
                             "remove_when": "same text/font size, shorter rows and reachable actions in both densities"})
    return [], failures


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--baseline", action="store_true", help="Record owner debt; never represents final acceptance")
    args = parser.parse_args(argv)
    report = json.loads((args.evidence_dir / "report.json").read_text(encoding="utf-8"))
    errors, failures = validate_report(report, args.evidence_dir, bind_current=not args.baseline)
    interaction_errors, interaction_failures = validate_interactions(report, args.evidence_dir)
    errors.extend(interaction_errors)
    failures.extend(interaction_failures)
    if not args.baseline:
        density_errors, density_failures = validate_densities(report)
        errors.extend(density_errors)
        failures.extend(density_failures)
        node = os.environ.get("WORKBENCH_NODE") or shutil.which("node")
        if not node:
            errors.append("Node is required to verify current application styles")
        else:
            style_result = subprocess.run([node, str(REPO / "tests/workbench-app-styles.cjs")], cwd=str(REPO),
                                          capture_output=True, text=True, timeout=30)
            if style_result.returncode:
                errors.append("current application style contract failed: " + style_result.stdout + style_result.stderr)
        if not errors and not failures:
            browser_result = subprocess.run([sys.executable, "-B", "-m", "pytest", *WORKBENCH_UI_BROWSER_TARGETS,
                                             "-q", "-o", "addopts="], cwd=str(REPO),
                                            capture_output=True, text=True, timeout=180)
            if browser_result.returncode:
                errors.append("explicit UI browser contracts failed: " + browser_result.stdout + browser_result.stderr)
    outcome = {"mode": "baseline" if args.baseline else "final", "passed": not errors and not failures,
               "hard_errors": errors, "failures": failures, "waiver_count": len(failures) if args.baseline else 0,
               "backend_source_drift": backend_source_drift(report.get("source", {})),
               "verified_at": datetime.now(timezone.utc).isoformat(),
               "binding": "current UI sources, templates, assets and probes; backend is the recorded isolated server snapshot"}
    if args.baseline:
        (args.evidence_dir / "baseline-owner-debt.json").write_text(json.dumps(outcome, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        (args.evidence_dir / "verification.json").write_text(json.dumps(outcome, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"mode": outcome["mode"], "passed": outcome["passed"], "hard_errors": errors,
                      "failed_measurements": len(failures), "backend_source_drift": outcome["backend_source_drift"],
                      "evidence_dir": str(args.evidence_dir)}, ensure_ascii=False))
    return 1 if errors or (failures and not args.baseline) else 0


if __name__ == "__main__":
    sys.exit(main())
