"""File/process-only checks of capacity binding; no host, database or workload runs."""

import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys

import pytest

from tests.workbench.final_capacity_binding import (
    ENV,
    EXPECTED_ROOT,
    FORBIDDEN_ORIGIN,
    G_FILES,
    G_PATH,
    MANIFEST_SHA256,
)
from tests.workbench.live_environment import REPO


@pytest.fixture
def source_case(tmp_path):
    source, harness, origin = (tmp_path / name for name in ("source", "harness", "origin"))
    for path in (source, harness, origin):
        path.mkdir()
    own = ("final_capacity_binding.py", "final_foundation_live_source_guard.py", "live_environment.py")
    names = ["tests/workbench/" + name for name in own]
    names += [G_PATH + "/" + name for name in G_FILES]
    for name in names:
        target = source / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(REPO / name), str(target))
    for name in G_FILES:
        shutil.copy2(str(source / G_PATH / name), str(harness / name))
    for root in (source, origin):
        leaf = root / "capacity_fixture_ns/leaf.py"
        leaf.parent.mkdir()
        leaf.write_text("VALUE = 17\n", encoding="utf-8")
    (source / "schema.sql").write_text("SELECT 1;\n", encoding="utf-8")
    manifest = tmp_path / "source-manifest.json"
    env = {key: value for key, value in os.environ.items() if not key.startswith(("WORKBENCH_", "FACTORY_"))}
    env.pop("PYTHONPATH", None)
    env.update({"PYTHONDONTWRITEBYTECODE": "1", "PYTHONPYCACHEPREFIX": str(tmp_path / "pycache")})
    command = [sys.executable, "-B", str(harness / "source_binding.py"), "capture", str(source), str(manifest),
               "--origin", str(origin)]
    for name in G_FILES:
        command.extend(["--extra", G_PATH + "/" + name])
    subprocess.run(command, cwd=str(tmp_path), env=env, capture_output=True, text=True, timeout=30, check=True)
    env.update({ENV: str(manifest), EXPECTED_ROOT: str(source), FORBIDDEN_ORIGIN: str(origin),
                MANIFEST_SHA256: hashlib.sha256(manifest.read_bytes()).hexdigest()})
    return source, harness, origin, manifest, env


def probe(case, body, arguments=()):
    source, _harness, origin, _manifest, env = case
    code = """
import importlib, importlib.util, json, pathlib, sqlite3, sys, types
source, origin = map(pathlib.Path, sys.argv[1:3])
sys.path.insert(0, str(source))
from tests.workbench.final_capacity_binding import install_capacity_binding
""" + body
    result = subprocess.run([sys.executable, "-B", "-c", code, str(source), str(origin)] + list(arguments), cwd=str(source.parent),
                            env=env, text=True, capture_output=True, timeout=30, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


def test_private_source_alias_namespace_and_original_venv_are_bound(source_case):
    _source, _harness, _origin, manifest, env = source_case
    value = json.loads(manifest.read_text(encoding="utf-8"))
    value["origin_root"] = str(REPO)
    manifest.write_text(json.dumps(value), encoding="utf-8")
    env[FORBIDDEN_ORIGIN] = str(REPO)
    env[MANIFEST_SHA256] = hashlib.sha256(manifest.read_bytes()).hexdigest()
    result = probe(source_case, """
guard = install_capacity_binding(required=True)
before = guard.evidence()
spec = importlib.util.spec_from_file_location('opaque_capacity_alias', source / 'capacity_fixture_ns/leaf.py')
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
namespace = importlib.import_module('capacity_fixture_ns')
import flask
assert module.VALUE == 17 and list(namespace.__path__) == [str(source / 'capacity_fixture_ns')]
dependency = pathlib.Path(flask.__file__).resolve()
assert guard.guard.dependency(dependency)
assert dependency.read_bytes()
after = guard.evidence()
assert after['manifest_sha256'] == before['manifest_sha256'] and after['verified']
assert after['loaded_modules']['opaque_capacity_alias']['file'] == str(source / 'capacity_fixture_ns/leaf.py')
assert after['loaded_modules']['capacity_fixture_ns']['namespace_paths'] == [str(source / 'capacity_fixture_ns')]
assert after['read_guard']['violations'] == []
assert 'web.bootstrap.factory' not in sys.modules
print(json.dumps({'bound': True, 'files': after['manifest_file_count'], 'formal_run': False}))
""")
    assert result == {"bound": True, "files": len(value["files"]), "formal_run": False}


@pytest.mark.parametrize("action", [
    "(origin / 'capacity_fixture_ns/leaf.py').read_bytes()",
    "sqlite3.connect((origin / 'capacity_fixture_ns/leaf.py').as_uri() + '?mode=ro', uri=True)",
    "(source / 'schema.sql').write_text('SELECT 1;\\n')",
    "sys.modules.update(opaque_alias=types.SimpleNamespace(__file__=str(origin / 'capacity_fixture_ns/leaf.py'))); guard.evidence()",
    "sys.modules.update(opaque_namespace=types.SimpleNamespace(__path__=[str(origin / 'capacity_fixture_ns')])); guard.evidence()",
    "sys.modules.update(opaque_spec=types.SimpleNamespace(__spec__=types.SimpleNamespace(origin=str(origin / 'capacity_fixture_ns/leaf.py')))); guard.evidence()",
    "sys.path.append(str(origin)); guard.evidence()",
    "spec = importlib.util.spec_from_file_location('dynamic_alias', origin / 'capacity_fixture_ns/leaf.py'); spec.loader.exec_module(importlib.util.module_from_spec(spec))",
])
def test_private_binding_blocks_original_reads_alias_namespace_and_source_writes(source_case, action):
    result = probe(source_case, """
guard = install_capacity_binding(required=True)
try:
    exec(sys.argv[3])
except (PermissionError, RuntimeError) as exc:
    assert 'source' in str(exc).lower() or 'checkout' in str(exc).lower() or 'sys.path' in str(exc)
else:
    raise AssertionError('Forbidden origin or source write was accepted')
assert 'web.bootstrap.factory' not in sys.modules
print(json.dumps({'blocked': True, 'formal_run': False}))
""", [action])
    assert result == {"blocked": True, "formal_run": False}


@pytest.mark.parametrize("damage", ["missing_manifest", "missing_expected", "missing_origin", "wrong_root", "wrong_origin",
                                     "wrong_sha", "source_bytes", "source_mode", "harness_bytes", "harness_mode"])
def test_binding_refuses_missing_or_changed_frozen_inputs_before_host_import(source_case, damage):
    source, harness, origin, _manifest, env = source_case
    if damage == "missing_manifest":
        env.pop(ENV)
    elif damage == "missing_expected":
        env.pop(EXPECTED_ROOT)
    elif damage == "missing_origin":
        env.pop(FORBIDDEN_ORIGIN)
    elif damage == "wrong_root":
        env[EXPECTED_ROOT] = str(origin)
    elif damage == "wrong_origin":
        env[FORBIDDEN_ORIGIN] = str(source)
    elif damage == "wrong_sha":
        env[MANIFEST_SHA256] = "0" * 64
    else:
        path = harness / "source_guard.py" if damage.startswith("harness") else source / "schema.sql"
        if damage.endswith("mode"):
            path.chmod(stat.S_IMODE(path.stat().st_mode) ^ stat.S_IXUSR)
        else:
            path.write_bytes(path.read_bytes() + b"\n")
    assert probe(source_case, """
try:
    install_capacity_binding(required=True)
except (ValueError, RuntimeError):
    pass
else:
    raise AssertionError('Invalid source binding accepted')
assert 'web.bootstrap.factory' not in sys.modules
print(json.dumps({'blocked': True}))
""") == {"blocked": True}


def test_symlink_read_and_unlisted_local_alias_are_not_frozen_inputs(source_case):
    source, _harness, origin, _manifest, _env = source_case
    (source / "escape.py").symlink_to(origin / "capacity_fixture_ns/leaf.py")
    (source / "unlisted.py").write_text("VALUE = 19\n", encoding="utf-8")
    assert probe(source_case, """
guard = install_capacity_binding(required=True)
try:
    (source / 'escape.py').read_bytes()
except PermissionError:
    pass
else:
    raise AssertionError('Original symlink read was permitted')
spec = importlib.util.spec_from_file_location('opaque_unlisted_alias', source / 'unlisted.py')
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
try:
    guard.evidence()
except RuntimeError as exc:
    assert 'absent from source manifest' in str(exc)
else:
    raise AssertionError('Unlisted local module was treated as bound')
print(json.dumps({'blocked': 2}))
""") == {"blocked": 2}


@pytest.mark.parametrize("target,mode", [("source/schema.sql", "bytes"), ("source/schema.sql", "mode"),
                                       ("harness/source_guard.py", "bytes"), ("harness/source_guard.py", "mode")])
def test_exit_verification_rejects_external_source_or_harness_drift(source_case, target, mode):
    mutator = """
import pathlib, stat, sys
path = pathlib.Path(sys.argv[1])
if sys.argv[2] == 'mode':
    path.chmod(stat.S_IMODE(path.stat().st_mode) ^ stat.S_IXUSR)
else:
    path.write_bytes(path.read_bytes() + b'\\n')
"""
    assert probe(source_case, """
import subprocess
guard = install_capacity_binding(required=True)
assert guard.evidence()['verified']
target, mode, mutator = json.loads(sys.argv[3])
path = source.parent / target
subprocess.run([sys.executable, '-B', '-c', mutator, str(path), mode], check=True, timeout=10)
try:
    guard.evidence()
except (RuntimeError, ValueError):
    pass
else:
    raise AssertionError('Changed source or harness produced a verified exit')
print(json.dumps({'exit_rejected': True}))
""", [json.dumps([target, mode, mutator])]) == {"exit_rejected": True}


def test_preloaded_alias_and_changed_process_binding_are_rejected(source_case):
    assert probe(source_case, """
sys.modules['unrelated_alias'] = types.SimpleNamespace(__file__=str(origin / 'capacity_fixture_ns/leaf.py'))
try:
    install_capacity_binding(required=True)
except PermissionError:
    pass
else:
    raise AssertionError('Preloaded original alias was accepted')
print(json.dumps({'blocked': True}))
""") == {"blocked": True}
    assert probe(source_case, """
import os
guard = install_capacity_binding(required=True)
os.environ['WORKBENCH_CAPACITY_EXPECTED_SOURCE_ROOT'] = str(origin)
try:
    install_capacity_binding(required=True)
except ValueError:
    pass
else:
    raise AssertionError('Process changed its declared binding')
print(json.dumps({'blocked': True}))
""") == {"blocked": True}


@pytest.mark.parametrize("damage", ["missing_after", "disabled", "wrong_pid", "wrong_manifest", "wrong_source", "wrong_origin"])
def test_coordinator_rejects_missing_or_misbound_child_receipt(source_case, damage):
    assert probe(source_case, """
import os
guard = install_capacity_binding(required=True)
record = {'before': guard.evidence(), 'after': guard.evidence()}
directory = source.parent / 'receipt-only'
directory.mkdir()
file = directory / 'capacity-source-binding.json'
file.write_text(json.dumps(record))
assert guard.host_evidence(directory, expected_pid=os.getpid()) == record
damage = sys.argv[3]
if damage == 'missing_after':
    del record['after']
elif damage == 'disabled':
    record['after']['enabled'] = False
elif damage == 'wrong_pid':
    record['after']['read_guard']['pid'] += 1
elif damage == 'wrong_manifest':
    record['after']['manifest_sha256'] = '0' * 64
elif damage == 'wrong_source':
    record['after']['expected_source_root'] = str(origin)
else:
    record['after']['origin_root'] = str(source)
file.write_text(json.dumps(record))
try:
    guard.host_evidence(directory, expected_pid=os.getpid())
except (AssertionError, KeyError):
    pass
else:
    raise AssertionError('Wrong or disabled child guard was accepted')
print(json.dumps({'blocked': True, 'formal_run': False}))
""", [damage]) == {"blocked": True, "formal_run": False}


def test_unbound_formal_coordinator_and_child_refuse_before_creating_runtime(source_case):
    source, _harness, _origin, _manifest, env = source_case
    for name in ("final_capacity_probe.py", "final_capacity_sources.py", "final_capacity_support.py", "final_capacity_server.py"):
        shutil.copy2(str(REPO / "tests/workbench" / name), str(source / "tests/workbench" / name))
    for key in (ENV, EXPECTED_ROOT, FORBIDDEN_ORIGIN, MANIFEST_SHA256):
        env.pop(key)
    assert probe(source_case, """
assert install_capacity_binding() is None
from tests.workbench.final_capacity_probe import run_managed
output = source.parent / 'not-created'
try:
    run_managed(output, batches=100, operations=50, exclusive_window='parameter-contract-only', asset_root=source.parent / 'unused-assets')
except ValueError as exc:
    assert 'FACTORY_SOURCE_MANIFEST' in str(exc)
else:
    raise AssertionError('Unbound formal run was accepted')
assert not output.exists() and 'web.bootstrap.factory' not in sys.modules
print(json.dumps({'blocked': True}))
""") == {"blocked": True}
    root = source.parent / "unstarted-child"
    root.mkdir()
    (root / "final-capacity.json").write_text(json.dumps({"root": str(root), "kind": "final-capacity-B-v1",
        "exclusive_window": "parameter-contract-only"}), encoding="utf-8")
    result = subprocess.run([sys.executable, "-B", str(source / "tests/workbench/final_capacity_server.py"),
                             "--root", str(root)], cwd=str(source), env=env, text=True, capture_output=True, timeout=30, check=False)
    assert result.returncode != 0 and "FACTORY_SOURCE_MANIFEST" in result.stderr
    assert sorted(path.name for path in root.iterdir()) == ["final-capacity.json"]
