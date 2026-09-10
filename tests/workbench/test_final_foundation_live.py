"""Full Main shell with real HTTP, four desktop themes and a live-page restart."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from flask import Flask
from werkzeug.datastructures import MultiDict

from core.infrastructure.database import ensure_schema
from tests.workbench import final_foundation_live_support as support
from tests.workbench.final_foundation_live import run
from tests.workbench.final_foundation_live_nav_cases import build_navigation_cases, execution_plan
from tests.workbench.final_foundation_live_source_guard import OWNED
from tests.workbench.final_foundation_live_source_guard import test_snapshot as source_test_snapshot
from tests.workbench.final_foundation_navigation_seed import prepare_navigation_draft
from tests.workbench.live_environment import create_root, read_identity, write_json
from tests.workbench.run_live_server_support import database_state, seed_run_data
from web.routes.workbench.navigation_boot import WorkbenchNavigationInvalid, read_navigation


def _prebuilt_fixture(tmp_path):
    assets = tmp_path / "source/static/workbench"
    assets.mkdir(parents=True)
    payload = b"window.fixture = true;\n"
    (assets / "one.js").write_bytes(payload)
    (assets / "unlisted.js").write_text("unmounted leaf", encoding="utf-8")
    manifest = {"schema_version": 1, "target": "chrome109", "build_id": "fixture",
                "files": [{"path": "workbench/one.js", "bytes": len(payload),
                           "sha256": hashlib.sha256(payload).hexdigest()}],
                "inputs": [{"path": "source.js", "sha256": hashlib.sha256(payload).hexdigest()}]}
    raw = json.dumps(manifest).encode("utf-8")
    (assets / "asset-manifest.json").write_bytes(raw)
    return assets, payload, raw, hashlib.sha256(raw).hexdigest()


def test_prebuilt_copy_is_manifest_scoped_and_byte_exact(tmp_path):
    assets, payload, raw, digest = _prebuilt_fixture(tmp_path)
    root = tmp_path / "private"
    support.copy_prebuilt(root, assets, digest)
    frozen = root / "full-build/static/workbench"
    assert (frozen / "one.js").read_bytes() == payload
    assert (frozen / "asset-manifest.json").read_bytes() == raw
    assert not (frozen / "unlisted.js").exists()


@pytest.mark.parametrize("changed", ["manifest", "payload"])
def test_prebuilt_copy_rejects_changed_bytes(tmp_path, changed):
    assets, _, _, digest = _prebuilt_fixture(tmp_path)
    target = assets / ("asset-manifest.json" if changed == "manifest" else "one.js")
    target.write_bytes(target.read_bytes() + b" ")
    with pytest.raises(AssertionError):
        support.copy_prebuilt(tmp_path / "private", assets, digest)


def test_prebuilt_copy_does_not_relax_input_validation(tmp_path, monkeypatch):
    assets, _, _, digest = _prebuilt_fixture(tmp_path)
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "source.js").write_text("changed registered source", encoding="utf-8")
    monkeypatch.setattr(support, "REPO", repo)
    with pytest.raises(AssertionError, match="source.js"):
        support.build_private(tmp_path / "private", {}, "unused", assets, "fixture", digest)


@pytest.fixture
def navigation_fixture(tmp_path):
    root = create_root(tmp_path)
    db = root / "db/aps-live.db"
    ensure_schema(str(db), schema_path=str(support.REPO / "schema.sql"), backup_dir=str(root / "backups"))
    app = Flask("foundation-navigation-preparation-unit")
    app.config["DATABASE_PATH"] = str(db)
    seed_run_data(app)
    return app, root


def _prepare_navigation(fixture):
    app, root = fixture
    return prepare_navigation_draft(app, root, owner_pid=os.getpid(), nonce=read_identity(root)["nonce"])


def test_navigation_preparation_real_draft_and_existing_rows(navigation_fixture):
    app, root = navigation_fixture
    before = database_state(app.config["DATABASE_PATH"])
    metadata = _prepare_navigation(navigation_fixture)
    evidence = support.read_json(metadata["evidence"])
    after = database_state(app.config["DATABASE_PATH"])
    assert evidence["created_before_business_baseline"] and evidence["original_rows_preserved"]
    assert not (root / "business-before.json").exists()
    assert evidence["receipt"]["ok"] and evidence["receipt"]["result"] == "committed"
    assert evidence["draft"]["draft_ref"] == metadata["draft_ref"]
    assert evidence["draft"]["base"] == {"plan_ref": metadata["plan_ref"]}
    assert evidence["draft"]["scope"] == metadata["full_scope"]
    assert evidence["draft"]["task_count"] == evidence["workspace"]["task_count"]
    assert len(after["WorkbenchTrialDrafts"]) == 1
    assert after["WorkbenchTrialDrafts"][0]["draft_ref"] == metadata["draft_ref"]
    assert after["WorkbenchCommandReceipts"][-1]["request_key"] == metadata["request_key"]
    for name, rows in before.items():
        assert after[name][:len(rows)] == rows
    with pytest.raises(ValueError, match="once before"):
        _prepare_navigation(navigation_fixture)
    assert database_state(app.config["DATABASE_PATH"]) == after


@pytest.mark.parametrize("marker", ["business-before.json", "run-seed.json", "server-ready.json"])
def test_navigation_preparation_refuses_late_creation(navigation_fixture, marker):
    app, root = navigation_fixture
    before = database_state(app.config["DATABASE_PATH"])
    write_json(root / marker, {"already_started": True})
    with pytest.raises(ValueError, match="once before"):
        _prepare_navigation(navigation_fixture)
    assert database_state(app.config["DATABASE_PATH"]) == before


def test_navigation_preparation_refuses_foreign_path_and_owner(navigation_fixture):
    app, root = navigation_fixture
    with pytest.raises(ValueError, match="private fixture"):
        prepare_navigation_draft(app, root, owner_pid=0, nonce=read_identity(root)["nonce"])
    foreign = root / "not-owned.sqlite"
    app.config["DATABASE_PATH"] = str(foreign)
    with pytest.raises(ValueError, match="owned private fixture"):
        _prepare_navigation(navigation_fixture)
    assert not foreign.exists()


def test_navigation_case_plan_uses_real_receipt_and_current_schema(navigation_fixture):
    metadata = _prepare_navigation(navigation_fixture)
    evidence = support.read_json(metadata["evidence"])
    plan = build_navigation_cases(evidence)
    assert plan["status"] == "prepared_not_live_verified"
    assert len(plan["cases"]) == 35
    assert len({row["id"] for row in plan["cases"]}) == 35
    assert {group: len([row for row in plan["cases"] if row["group"] == group]) for group in plan["groups"]} == {
        "canonical-positive": 6, "canonical-http400": 24, "canonical-domain-failure": 5}
    assert metadata["draft_ref"] in next(row["url_suffix"] for row in plan["cases"] if row["id"] == "trial-existing-real-draft")
    for row in plan["cases"]:
        args = MultiDict(row["query_pairs"])
        view = "trial" if row["path"] == "/workbench/trial" else args.get("view", "dashboard")
        if row["group"] == "canonical-http400":
            with pytest.raises(WorkbenchNavigationInvalid):
                read_navigation(view, args)
        else:
            assert read_navigation(view, args) == row["payload"]
    write_json(navigation_fixture[1] / "foundation-navigation-case-plan.json", plan)
    print("FOUNDATION_NAVIGATION_PLAN_UNIT_ROOT " + str(navigation_fixture[1]))


def test_focused_boot_mutation_builder_without_browser():
    node = os.environ.get("WORKBENCH_NODE") or str(Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node")
    script = support.HERE / "final_foundation_live_boot_cases.cjs"
    result = subprocess.run([node, str(script)], check=True, capture_output=True, text=True, timeout=20)
    assert json.loads(result.stdout) == {"definitions": 10, "mutation_checks": 10,
                                       "missing_or_duplicate_rejected": 2, "browser_executed": False}


@pytest.mark.parametrize("groups,total,pages", [("legacy", 92, 4), ("canonical", 212, 24), ("boot", 40, 0),
                                               ("canonical,boot", 252, 24), ("all", 344, 28)])
def test_executable_group_denominators(groups, total, pages):
    plan = execution_plan(groups.split(","))
    assert plan["total_cases"] == total and plan["restart_pages"] == pages
    assert sum(plan["case_kinds"].values()) == total
    assert plan["navigation_seed"] == ("canonical" in plan["groups"])


@pytest.mark.parametrize("groups", [[], ["canonical", "canonical"], ["unknown"], ["all", "boot"]])
def test_executable_group_rejects_unknown_or_duplicate(groups):
    with pytest.raises(ValueError, match="Groups must"):
        execution_plan(groups)


def test_new_groups_do_not_start_on_an_unguarded_original_tree(tmp_path):
    with pytest.raises(ValueError, match="explicit frozen source root"):
        run(tmp_path, groups=("canonical", "boot"))
    assert list(tmp_path.iterdir()) == []


def _copied_tests(tmp_path):
    copied = tmp_path / "snapshot"
    target = copied / "tests/workbench"
    target.mkdir(parents=True)
    for name in OWNED:
        shutil.copyfile(str(support.HERE / name), str(target / name))
    for name in ("tests/__init__.py", "tests/workbench/__init__.py"):
        (copied / name).touch()
    return copied


def test_frozen_source_cli_describes_real_groups_without_a_host(tmp_path):
    copied = _copied_tests(tmp_path)
    result = subprocess.run([sys.executable, "-B", str(copied / "tests/workbench/final_foundation_live.py"),
                             "--groups", "canonical,boot", "--describe-groups"], cwd=str(tmp_path),
                            check=True, capture_output=True, text=True, timeout=20)
    value = json.loads(result.stdout)
    assert value["execution"] == execution_plan(("canonical", "boot"))
    assert value["test_snapshot"] == source_test_snapshot()
    assert value["browser_executed"] is False
    assert not list(tmp_path.glob("aps-workbench-live-*"))


def test_frozen_source_guard_blocks_original_reads_db_and_frozen_writes(tmp_path):
    copied = _copied_tests(tmp_path)
    code = r'''
import json, pathlib, sqlite3, sys
sys.path.insert(0, sys.argv[1])
from tests.workbench.final_foundation_live_source_guard import configuration, install
copy, original = map(pathlib.Path, sys.argv[1:3])
alias = copy / "alias.py"
alias.symlink_to(original / "tests/workbench/final_foundation_live.py")
guard = install(configuration(copy, [original], sys.argv[3]))
assert (copy / "tests/workbench/final_foundation_live.py").read_text()
operations = [lambda: (original / "tests/workbench/final_foundation_live.py").read_text(),
              lambda: alias.read_text(),
              lambda: (copy / "forbidden.txt").write_text("must not write"),
              lambda: sqlite3.connect(str(original / "must-not-create.db"))]
for action in operations:
    try: action()
    except PermissionError: pass
    else: raise AssertionError("Guard permitted a forbidden operation")
assert not (copy / "forbidden.txt").exists()
assert len(guard.violations) == 4
assert all(str(copy) in value for value in guard.evidence()["loaded_project_modules"].values())
print(json.dumps({"blocked": len(guard.violations), "browser_executed": False}))
'''
    result = subprocess.run([sys.executable, "-B", "-c", code, str(copied), str(support.REPO), source_test_snapshot()["sha256"]],
                            cwd=str(tmp_path), check=True, capture_output=True, text=True, timeout=20)
    assert json.loads(result.stdout) == {"blocked": 4, "browser_executed": False}


def test_browser_group_helpers_syntax_and_pure_contracts(navigation_fixture):
    metadata = _prepare_navigation(navigation_fixture)
    plan = build_navigation_cases(support.read_json(metadata["evidence"]))
    plan_path = navigation_fixture[1] / "node-plan-unit.json"
    write_json(plan_path, plan)
    node, _, modules = support.runtime_tools()
    code = r'''
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const dir = process.argv[1], plan = JSON.parse(fs.readFileSync(process.argv[2]));
const names = fs.readdirSync(dir).filter(name => /^final_foundation_live.*\.cjs$/.test(name));
for (const name of names) new vm.Script(fs.readFileSync(path.join(dir, name), 'utf8'), {filename: name});
const {subset, missingDTO, savedContext} = require(path.join(dir, 'final_foundation_live_navigation.cjs'));
const record = {equal: assert.deepEqual, ok: assert.ok};
for (const row of plan.cases.filter(row => row.group === 'canonical-domain-failure')) {
  const dto = missingDTO(row);
  assert.ok(JSON.stringify(dto).includes(row.missing_ref));
}
subset({scope:{a:1,other:true}}, {scope:{a:1}}, record, 'scope');
assert.throws(() => subset({scope:{a:2}}, {scope:{a:1}}, record, 'scope'));
const trial = plan.cases.find(row => row.id === 'trial-existing-real-draft');
const before = {route:null};
assert.equal(savedContext(before, trial, record).persisted, false);
assert.deepEqual(before, {route:null});
assert.throws(() => savedContext({route:null}, plan.cases[0], record));
assert.equal(savedContext({route:{view:'trial',context:trial.payload.context}}, trial, record).persisted, true);
assert.throws(() => savedContext({route:{view:'trial',context:{draft_ref:'another-ref'}}}, trial, record));
console.log(JSON.stringify({syntax_files: names.length, unknown_requests:5, saved_context_checks:4, browser_executed:false}));
'''
    result = subprocess.run([node, "-e", code, str(support.HERE), str(plan_path)], env={**os.environ, "NODE_PATH": modules},
                            check=True, capture_output=True, text=True, timeout=20)
    assert json.loads(result.stdout) == {"syntax_files": 6, "unknown_requests": 5, "saved_context_checks": 4, "browser_executed": False}


def test_main_shell_real_first_views_faults_and_restart(tmp_path):
    root, result = run(tmp_path)
    assert result["complete"], str(root / "foundation-result.json")
    assert result["final_head_bound"] is False
    assert result["browser_returncode"] == 0
    browser = result["browser"]
    assert browser["browser_version"].startswith("109.")
    assert browser["external_requests"] == []
    assert browser["normal_errors"] == []
    first = [row for row in browser["cases"] if row["kind"] == "first_view"]
    assert len(first) == 56 and all(row["status"] == "passed" for row in first)
    assert len([row for row in browser["cases"] if row["kind"] == "fault"]) == 16
    assert len([row for row in browser["cases"] if row["kind"] == "host_restart"]) == 4
    assert result["initial_shutdown"]["returncode"] == result["restart_shutdown"]["returncode"] == 0
    assert result["retention"]["original_rows_preserved"]
