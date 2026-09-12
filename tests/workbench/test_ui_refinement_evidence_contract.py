"""UI evidence gates fail closed for omissions, stale artifacts and remaining debt."""

import hashlib
import json

from tests.workbench.ui_refinement_gate import (
    BASE_CHECKS,
    INTERACTION_CHECKS,
    PROBE_INPUTS,
    SIZES,
    THEMES,
    UI_HOST_INPUTS,
    VIEWS,
    backend_source_drift,
    validate_densities,
    validate_interactions,
    validate_report,
)


def valid_evidence(tmp_path):
    manifest = {"build_id": "fixture-build", "inputs": []}
    raw = json.dumps(manifest).encode()
    (tmp_path / "asset-manifest.json").write_bytes(raw)
    static = tmp_path / "static/workbench"
    static.mkdir(parents=True)
    (static / "asset-manifest.json").write_bytes(raw)
    report = {"schema_version": 1, "kind": "workbench-ui-refinement", "browser": "109.0.1",
              "completed_at": "2026-09-12T00:00:00Z", "errors": [],
              "source": {"build_id": "fixture-build", "manifest_sha256": hashlib.sha256(raw).hexdigest()}, "pages": []}
    source = report["source"]
    source.update(source_differences_at_freeze=[], probe_sources={}, loaded_python_sources={}, assets_hashes={})
    for name in PROBE_INPUTS:
        file = tmp_path / "tests/workbench" / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(b"probe")
        source["probe_sources"][name] = hashlib.sha256(b"probe").hexdigest()
    for name in UI_HOST_INPUTS:
        file = tmp_path / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(b"host")
        source["loaded_python_sources"][str(file)] = hashlib.sha256(b"host").hexdigest()
    template = tmp_path / "templates/workbench/index.html"
    template.parent.mkdir(parents=True)
    template.write_bytes(b"template")
    source["assets_hashes"]["templates/workbench/index.html"] = hashlib.sha256(b"template").hexdigest()
    for view in VIEWS:
        for width, height in SIZES:
            for theme in THEMES:
                key = f"{view}-{width}-{height}-{theme}"
                (tmp_path / (key + ".png")).write_bytes(b"\x89PNG\r\n\x1a\nfixture")
                (tmp_path / (key + ".boot.json")).write_bytes(b"{}")
                required = BASE_CHECKS | ({"G1"} if view == "batches" else set()) | (
                    {"G3"} if view in ("analysis", "gantt", "delay") else set())
                report["pages"].append({"id": key, "view": view, "theme": theme,
                                        "viewport": {"width": width, "height": height},
                                        "url": "http://127.0.0.1:1/" + ("workbench/trial" if view == "trial" else "workbench?view=" + view),
                                        "screenshot": key + ".png", "boot_sha256": hashlib.sha256(b"{}").hexdigest(),
                                        "screenshot_sha256": hashlib.sha256(b"\x89PNG\r\n\x1a\nfixture").hexdigest(),
                                        "checks": [{"id": check, "ok": True} for check in sorted(required)]})
    return report


def test_complete_matrix_is_accepted(tmp_path):
    report = valid_evidence(tmp_path)
    assert validate_report(report, tmp_path, repository=tmp_path) == ([], [])


def test_missing_case_and_missing_check_cannot_pass(tmp_path):
    report = valid_evidence(tmp_path)
    report["pages"].pop()
    report["pages"][0]["checks"].pop()
    errors, _ = validate_report(report, tmp_path, repository=tmp_path)
    assert any("matrix incomplete" in error for error in errors)
    assert any("geometric checks" in error for error in errors)


def test_failed_checks_keep_owner_and_final_waivers_are_rejected(tmp_path):
    report = valid_evidence(tmp_path)
    report["pages"][0]["checks"][0]["ok"] = False
    report["waivers"] = [{"owner": "someone", "check": "G2"}]
    errors, failures = validate_report(report, tmp_path, repository=tmp_path)
    assert "final evidence must contain zero waivers" in errors
    assert len(failures) == 1 and failures[0]["owner"] and failures[0]["roadmap_item"]


def test_old_build_and_newer_browser_are_rejected(tmp_path):
    report = valid_evidence(tmp_path)
    report["browser"] = "152.0.1"
    (tmp_path / "static/workbench/asset-manifest.json").write_text("{}", encoding="utf-8")
    errors, _ = validate_report(report, tmp_path, repository=tmp_path)
    assert "real Chromium 109 evidence required" in errors
    assert "evidence does not match current built manifest" in errors


def test_wrong_actual_theme_and_changed_boot_are_rejected(tmp_path):
    report = valid_evidence(tmp_path)
    report["pages"][0]["theme"] = "dark"
    (tmp_path / (report["pages"][1]["id"] + ".boot.json")).write_text("changed", encoding="utf-8")
    errors, _ = validate_report(report, tmp_path, repository=tmp_path)
    assert any("measured view/viewport/theme" in error for error in errors)
    assert any("boot evidence" in error for error in errors)


def test_interactions_cannot_be_silently_omitted(tmp_path):
    errors, failures = validate_interactions({"interactions": []}, tmp_path)
    assert errors == ["eight interaction states are incomplete or duplicated"]
    assert failures == []


def test_interaction_missing_assertion_is_hard_error(tmp_path):
    values = []
    for key, check in INTERACTION_CHECKS.items():
        (tmp_path / (key + ".png")).write_bytes(b"\x89PNG\r\n\x1a\nfixture")
        values.append({"id": key, "screenshot": key + ".png", "screenshot_sha256": hashlib.sha256(b"\x89PNG\r\n\x1a\nfixture").hexdigest(),
                       "checks": [{"id": check, "ok": True}, {"id": "G6", "ok": True}]})
    assert validate_interactions({"interactions": values}, tmp_path) == ([], [])
    values[0]["checks"].pop()
    errors, _ = validate_interactions({"interactions": values}, tmp_path)
    assert any("assertions missing" in error for error in errors)


def test_changed_probe_host_and_template_cannot_reuse_old_evidence(tmp_path):
    report = valid_evidence(tmp_path)
    for name in ("tests/workbench/" + PROBE_INPUTS[0], UI_HOST_INPUTS[0], "templates/workbench/index.html"):
        (tmp_path / name).write_bytes(b"changed")
    report["source"]["source_differences_at_freeze"] = ["frontend/workbench/app/main.jsx"]
    errors, _ = validate_report(report, tmp_path, repository=tmp_path)
    for expected in ("source/build differences", "collector source changed", "UI host source missing or changed", "frozen UI asset/template changed"):
        assert any(expected in error for error in errors)


def test_backend_drift_is_explicit_and_separate_from_ui_binding(tmp_path):
    report = valid_evidence(tmp_path)
    backend = tmp_path / "core/example.py"
    backend.parent.mkdir()
    backend.write_bytes(b"after")
    report["source"]["loaded_python_sources"][str(backend)] = hashlib.sha256(b"before").hexdigest()
    assert backend_source_drift(report["source"], tmp_path) == ["core/example.py"]
    assert validate_report(report, tmp_path, repository=tmp_path) == ([], [])


def test_density_requires_four_cases_and_real_row_reduction_without_font_change():
    assert validate_densities({})[0]
    values = [{"id": f"batches-{width}-{height}-{theme}", "table": {"ok": True},
               "comfortable": [{"fontSize": "13px", "text": "批次", "height": 40}],
               "compact": [{"fontSize": "13px", "text": "批次", "height": 32}]}
              for width, height in SIZES for theme in THEMES]
    assert validate_densities({"densities": values}) == ([], [])
    values[0]["compact"][0]["fontSize"] = "11px"
    assert len(validate_densities({"densities": values})[1]) == 1
