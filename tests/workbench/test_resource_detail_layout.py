"""Built ResourceForms + Chromium 109 + memory-only data; no production DB proof."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from test_live_browser import runtime_tools

CASE_NAMES = {
    "material-typical-shuffled", "material-zero", "material-unknown",
    "material-long-identity-spec-unit-remark", "material-reordered-same-content",
    "machine-legacy-fields-and-relations", "operator-legacy-fields-and-authorizations",
    "internal-op-type-capacity-and-relations", "external-op-type-policy-and-suppliers",
    "supplier-legacy-fields-and-relations", "create-material-review-keeps-input",
    "create-op_type-review-keeps-input",
}


def test_resource_detail_layout_and_create_review(output=None):
    node, browser, modules = runtime_tools()
    artifacts = Path(output or tempfile.mkdtemp(prefix="aps-resource-detail-layout-")).resolve()
    repo = HERE.parent.parent
    if artifacts == repo or repo in artifacts.parents:
        raise ValueError("Artifacts must stay outside the checkout")
    artifacts.mkdir(parents=True, exist_ok=True)
    print("RESOURCE_DETAIL_LAYOUT_ARTIFACTS " + str(artifacts), flush=True)
    result = subprocess.run(
        [node, str(HERE / "resource_detail_layout_probe.cjs"), str(artifacts)],
        cwd=str(HERE.parent.parent),
        env=dict(os.environ, NODE_PATH=modules, WORKBENCH_BROWSER=browser),
        capture_output=True, text=True, timeout=300,
    )
    diagnostic = result.stdout + result.stderr + "\nArtifacts: " + str(artifacts)
    report_path = artifacts / "resource-detail-layout-result.json"
    if result.returncode and report_path.is_file():
        failed_report = json.loads(report_path.read_text(encoding="utf-8"))
        diagnostic += "\n" + failed_report.get("runner_error", "")
        diagnostic += "\n".join(row.get("error", "") for row in failed_report["cases"] if not row["passed"])
    assert result.returncode == 0, diagnostic
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert "runner_error" not in report, diagnostic
    assert report["scope"] == "read-only-component-mock"
    assert report["data_source"] == "in-memory-fixture"
    assert report["production_persistence_tested"] is False
    assert report["win7_hardware_tested"] is False
    assert report["browser"].startswith("109.")
    assert report["writes"] == 0
    for key in ("errors", "external", "unexpected_requests"):
        assert report[key] == [], (key, report[key])
    expected = {
        (f"{width}x{height}-{theme}", name)
        for width, height in ((1920, 1080), (1392, 924))
        for theme in ("light", "dark")
        for name in CASE_NAMES
    }
    cases = report["cases"]
    assert len(cases) == len(expected) == 48
    assert {(row["state"], row["name"]) for row in cases} == expected
    assert all(row["passed"] for row in cases), diagnostic
    assert all(len(row["assertions"]) >= 12 for row in cases)
    assert all(check["passed"] for row in cases for check in row["assertions"])
    assert report["assertions"] == sum(len(row["assertions"]) for row in cases)
    assert report["summary"]["failed"] == 0
    screenshots = [name for row in cases for name in row["screenshots"]]
    assert screenshots == report["screenshots"]
    assert len(screenshots) == len(set(screenshots)) == 96
    for name in screenshots:
        screenshot = Path(name)
        screenshot.relative_to(artifacts)
        assert screenshot.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"), name
    print("RESOURCE_DETAIL_LAYOUT_VERIFIED " + json.dumps({
        "build_id": report["build_id"], "browser": report["browser"], **report["summary"],
        "scope": report["scope"], "artifacts": str(artifacts),
    }), flush=True)


if __name__ == "__main__":
    test_resource_detail_layout_and_create_review(sys.argv[1] if len(sys.argv) > 1 else None)
