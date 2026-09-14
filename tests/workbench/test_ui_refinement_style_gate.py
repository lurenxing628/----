"""Source-style rules run without browser tooling and reject deliberate regressions."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CHECKER = ROOT / "tests/workbench-app-styles.cjs"


def _node():
    configured = os.environ.get("WORKBENCH_NODE")
    installed = shutil.which("node")
    bundled = Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node"
    executable = configured or installed or (str(bundled) if bundled.is_file() else None)
    assert executable, "Node is required for the workbench CSS source contract (no browser is needed)"
    return executable


def _run(directory=None, check_variables=False):
    args = [_node(), str(CHECKER)]
    if directory is not None:
        args.extend(["--styles-dir", str(directory)])
    if check_variables:
        args.append("--check-variables")
    return subprocess.run(args, cwd=str(ROOT), capture_output=True, text=True, timeout=20)


def _fixture(tmp_path, files, check_variables=False):
    for name, source in files.items():
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source, encoding="utf-8")
    result = _run(tmp_path, check_variables=check_variables)
    assert result.returncode in (0, 1), result.stderr
    return result, json.loads(result.stdout)


def test_undefined_css_variable_is_rejected_when_variable_checks_are_on(tmp_path):
    files = {
        "00-tokens.css": ":root { --wb-detail-w: 320px; }",
        "30-workspaces.css": ".row { width: var(--wb-detail-w); color: var(--ui-text); background: var(--wb-not-defined, var(--ui-card-bg)); }",
    }
    result, report = _fixture(tmp_path, files, check_variables=True)
    assert result.returncode == 1
    assert [(row["rule"], row["file"], row["line"]) for row in report["violations"]] == [("undefined-variable", "30-workspaces.css", 1)]
    assert "--wb-not-defined" in report["violations"][0]["message"]
    passing, clean = _fixture(tmp_path, files)
    assert passing.returncode == 0 and clean["violations"] == []


def test_application_css_has_no_style_contract_violations():
    result = _run()
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["passed"] is True
    assert report["sources"] and report["violations"] == []


def test_valid_tokens_dynamic_variables_and_resource_values_are_supported(tmp_path):
    result, report = _fixture(tmp_path, {
        "00-tokens.css": ":root { --wb-z-sticky:10; --wb-sev-ok:var(--ui-success); --wb-detail-w:320px; }",
        "20-controls.css": """/* override: .plana select; preserve native control width under legacy specificity */
.plana select { width: auto !important; }
.control { --business-offset: calc(var(--task-end) - var(--task-start)); left: var(--business-offset); }
""",
        "31-batches.css": """/* Historical review example: color: #fff; font-size: 12.5px; z-index: 99 !important; */
#abc .row { color: var(--wb-sev-ok); background: var(--ui-card-bg); z-index: var(--wb-z-sticky); }
.row:before { content: "#fff rgb(0,0,0) font-size: 12.5px; z-index: 5 !important"; }
.row { background-image: url("data:image/svg+xml,<svg fill='#fff'>;rgb(0,0,0)</svg>"); }
.row { background-image: url(data:image/svg+xml,%3Csvg%20fill=#fff%3E); font-size: var(--font-size-2); }
@media (min-width: 1280px) { .row { font-size: 14px; border-width: .5px; } }
""",
    })
    assert result.returncode == 0, report
    assert report["passed"] is True and report["violations"] == []
    assert len(report["sources"]) == 3
    assert all(len(row["sha256"]) == 64 for row in report["sources"])


@pytest.mark.parametrize("value", ["#fff", "#AABBCC", "#aabbccdd", "#abcd", "RGB(0 0 0)", "rgba(0, 0, 0, .5)"])
def test_literal_color_is_rejected_in_declarations_and_token_definitions(tmp_path, value):
    result, report = _fixture(tmp_path, {
        "00-tokens.css": ":root { --wb-probe: " + value + "; }",
        "nested/31-batches.css": ".row { color: " + value + "; }",
    })
    assert result.returncode == 1
    assert len(report["violations"]) == 2
    assert {row["rule"] for row in report["violations"]} == {"no-literal-colors"}


@pytest.mark.parametrize("value", ["12.5px", ".5px", "calc(12.5px + 1px)", "13.25px"])
def test_fractional_font_size_is_rejected(tmp_path, value):
    result, report = _fixture(tmp_path, {"30-workspaces.css": ".row { font-size: " + value + "; }"})
    assert result.returncode == 1
    assert [row["rule"] for row in report["violations"]] == ["integer-font-size"]


@pytest.mark.parametrize("value", ["10", "0", "var(--ui-z-sticky)", "var(--business-z)", "var(--wb-z-sticky, 10)", "calc(var(--wb-z-sticky) + 1)"])
def test_uncontrolled_z_index_is_rejected(tmp_path, value):
    result, report = _fixture(tmp_path, {"30-workspaces.css": ".row { z-index: " + value + "; }"})
    assert result.returncode == 1
    assert [row["rule"] for row in report["violations"]] == ["z-index-token"]


def test_important_needs_adjacent_explanation_and_correct_owner_file(tmp_path):
    result, report = _fixture(tmp_path, {
        "20-controls.css": """/* override: .legacy; keep the repaired control width */
.valid { width: 100% !important; }

.missing { width: 100% !important; }
/* override: */
.empty { width: 100% !important; }
/* override: .legacy; explanation too far from declaration */

.distant { width: 100% !important; }
""",
        "30-workspaces.css": """/* override: .legacy; valid explanation in the wrong layer */
.wrong-layer { width: 100% !important; }
""",
    })
    assert result.returncode == 1
    assert [(row["file"], row["line"], row["rule"]) for row in report["violations"]] == [
        ("20-controls.css", 4, "important-override"),
        ("20-controls.css", 6, "important-override"),
        ("20-controls.css", 9, "important-override"),
        ("30-workspaces.css", 2, "important-file"),
    ]


def test_empty_or_missing_style_directory_cannot_pass(tmp_path):
    for directory in (tmp_path, tmp_path / "missing"):
        result = _run(directory)
        assert result.returncode == 2 and result.stderr


def test_malformed_comment_cannot_hide_declarations(tmp_path):
    result, report = _fixture(tmp_path, {"30-workspaces.css": "/* .row {color:#fff;}"})
    assert result.returncode == 1
    assert [row["rule"] for row in report["violations"]] == ["read-css"]
