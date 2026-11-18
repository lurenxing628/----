"""The single browser transport: envelopes, unified errors, verdicts and downloads with mocked fetch only."""

import json
import os
import shlex
import subprocess
from pathlib import Path

import pytest

from scripts.workbench import node_runtime as node_runtime_mod
from scripts.workbench.node_runtime import (
    NodeNotFoundError,
    NodeProbeError,
    node_cli_args,
    parse_node_version,
    select_node_runtime,
)
from tests._support.node_runtime_support import run_node
from tools.long_gate_fingerprint import resolve_cached_node_runtime

ROOT = Path(__file__).resolve().parents[2]


def _write_posix_shim(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)
    return path


def _host_node_and_clean_env():
    host_env = {k: v for k, v in os.environ.items() if k != "NODE_OPTIONS"}
    return resolve_cached_node_runtime(host_env), host_env


def test_transport_contract_and_bounded_request_lifetime():
    result = run_node([Path(__file__).with_name("transport_probe.cjs")])
    report = json.loads(result.stdout)
    assert report["network"] == "mock-only" and report["production"] is False
    assert report["checks"] == len(report["cases"]) == 96
    cases = set(report["cases"])
    # Q2-A: one definite-rejection verdict for every command module.
    for status in (400, 403, 404, 409, 413, 422, 500, 503):
        assert f"rejected for committed:false HTTP {status}" in cases
    assert "request_key_conflict is never a rejection" in cases
    assert "envelopeFailure maps the backend failure envelope to the unified error" in cases
    assert "envelope rejects sixth meta key" in cases and "envelope accepts a null snapshot_ref" in cases
    assert "lookup returns a 200 not_observed payload for the domain to validate" in cases
    assert "types maps the four download formats to frozen MIME types" in cases
    assert "rejected for a local failure that never reached the server" in cases
    assert "read network failure is a definite non-commit, lookup failure never is" in cases
    assert "download rejects a missing filename" in cases
    assert "download with a body posts it as JSON and keeps the file checks" in cases
    assert "download rejects a suffix that does not match the type: CSV saved as .xlsx" in cases


def test_node_sparkplug_version_matrix_and_cli_injection(tmp_path):
    for affected in ("v24.0.0", "v24.15.0", "v24.15", "v24.21.9"):
        assert node_cli_args("/opt/node", parse_node_version(affected)) == ["/opt/node", "--no-sparkplug"]
    for unaffected in ("v20.11.1", "v22.23.3", "v24.22.0", "v24.22.3", "v25.0.0"):
        assert node_cli_args("/opt/node", parse_node_version(unaffected)) == ["/opt/node"]

    real_rt, clean_env = _host_node_and_clean_env()
    probe_expr = "process.stdout.write(JSON.stringify(process.execArgv))"
    if os.name == "nt":
        res = run_node(["-e", probe_expr], env={**clean_env, "WORKBENCH_NODE": real_rt.realpath})
        assert ("--no-sparkplug" in json.loads(res.stdout)) is (
            "--no-sparkplug" in node_cli_args(real_rt.realpath, real_rt.major_minor)
        )
        return

    quoted = shlex.quote(real_rt.realpath)
    shim_15 = _write_posix_shim(tmp_path / "n15", f'#!/bin/sh\n[ "$1" = "--version" ] && {{ echo v24.15.0; exit 0; }}\nexec {quoted} "$@"\n')
    shim_22 = _write_posix_shim(tmp_path / "n22", f'#!/bin/sh\n[ "$1" = "--version" ] && {{ echo v24.22.3; exit 0; }}\nexec {quoted} "$@"\n')
    unmitigated_argv = json.loads(run_node(["-e", probe_expr], env={**clean_env, "WORKBENCH_NODE": str(shim_22)}).stdout)
    mitigated_argv = json.loads(run_node(["-e", probe_expr], env={**clean_env, "WORKBENCH_NODE": str(shim_15)}).stdout)
    assert "--no-sparkplug" not in unmitigated_argv
    assert mitigated_argv == ["--no-sparkplug", *unmitigated_argv]


def test_node_auto_discovery_preserves_first_probe_error_and_rejects_broken_links(tmp_path, monkeypatch):
    empty_home, dir_1, dir_2 = tmp_path / "home", tmp_path / "b1", tmp_path / "b2"
    for d in (empty_home, dir_1, dir_2):
        d.mkdir()
    if os.name == "nt":
        first_exe = dir_1 / "node.exe"
        first_exe.write_bytes(b"corrupt-pe-1")
        (dir_2 / "node.exe").write_bytes(b"corrupt-pe-2")
        with pytest.raises(NodeProbeError) as exc_info:
            run_node(["-e", "0"], env={"PATH": f"{dir_1}{os.pathsep}{dir_2}", "HOME": str(empty_home), "USERPROFILE": str(empty_home)})
        assert os.path.normcase(os.path.realpath(str(first_exe))) in os.path.normcase(str(exc_info.value))
        return

    real_rt, clean_env = _host_node_and_clean_env()
    second_log = tmp_path / "second.log"
    first_node = _write_posix_shim(dir_1 / "node", "#!/bin/sh\nprintf 'probe-out-1\\n'\nprintf 'probe-err-1\\n' >&2\nexit 17\n")
    _write_posix_shim(dir_2 / "node", f"#!/bin/sh\nprintf '1\\n' >> {shlex.quote(str(second_log))}\nexit 29\n")
    with pytest.raises(NodeProbeError) as auto_exc:
        run_node(
            ["-e", "0"],
            env={
                "PATH": f"{dir_1}{os.pathsep}{dir_2}",
                "HOME": str(empty_home),
                "NODE_OPTIONS": "--definitely-invalid-node-option",
            },
        )
    msg = str(auto_exc.value)
    assert second_log.is_file() and os.path.realpath(str(first_node)) in msg
    assert "failed with returncode 17:\nstdout:\nprobe-out-1\nstderr:\nprobe-err-1" in msg and "returncode 29" not in msg

    bad_ver = _write_posix_shim(tmp_path / "bad_ver", "#!/bin/sh\nprintf 'v24\\n'\nprintf 'bad-ver-err\\n' >&2\n")
    with pytest.raises(NodeProbeError, match=r"Unrecognized Node version: 'v24'.*\nstderr:\nbad-ver-err"):
        run_node(["-e", "0"], env={**clean_env, "WORKBENCH_NODE": str(bad_ver)})

    hang_node = _write_posix_shim(
        tmp_path / "hang",
        f"#!/bin/sh\nprintf 'hang-out\\n'\nprintf 'hang-err\\n' >&2\nexec {shlex.quote(real_rt.realpath)} -e "
        '"Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 5000);"\n',
    )
    real_run = subprocess.run
    with monkeypatch.context() as patch_ctx:
        patch_ctx.setattr(
            node_runtime_mod.subprocess, "run",
            lambda *a, **kw: real_run(*a, **{**kw, "timeout": 0.5 if kw.get("timeout") == 5 else kw.get("timeout")}),
        )
        with pytest.raises(NodeProbeError, match=r"timed out after 0\.5s:\nstdout:\nhang-out\nstderr:\nhang-err"):
            run_node(["-e", "0"], env={**clean_env, "WORKBENCH_NODE": str(hang_node)})

    _write_posix_shim(tmp_path / "good" / "node", '#!/bin/sh\necho "v24.15.0"\n')
    caller_dir = tmp_path / "caller"
    caller_dir.mkdir()
    broken = caller_dir / "broken"
    broken.symlink_to(os.path.join("..", "missing_mid", "..", "good"), target_is_directory=True)
    monkeypatch.chdir(caller_dir)
    for spec in (str(broken / "node"), os.path.join("broken", "node")):
        with pytest.raises(NodeNotFoundError, match=r"Node executable is not runnable:"):
            select_node_runtime(clean_env, explicit_node=spec)


def test_node_crash_diagnostics_and_nested_spawn_propagation(tmp_path):
    real_rt, clean_env = _host_node_and_clean_env()
    real_node_env = {**clean_env, "WORKBENCH_NODE": real_rt.realpath}

    with pytest.raises(AssertionError) as ws_exc:
        run_node(["-e", "process.stdout.write('   \\n'); process.exit(6);"], env=real_node_env, label="Blank probe")
    assert str(ws_exc.value) == "Blank probe failed with returncode 6:\nstdout:\n   "

    bad_utf8_js = (
        "const fs = require('node:fs');"
        "fs.writeSync(1, Buffer.concat([Buffer.from('OUT:'), Buffer.from([0xff, 0xfe])]));"
        "fs.writeSync(2, Buffer.concat([Buffer.from('ERR:'), Buffer.from([0x80])]));"
        "process.exit(7);"
    )
    with pytest.raises(AssertionError) as utf8_exc:
        run_node(["-e", bad_utf8_js], env=real_node_env, label="UTF-8 probe")
    assert str(utf8_exc.value) == "UTF-8 probe failed with returncode 7:\nstdout:\nOUT:\ufffd\ufffd\nstderr:\nERR:\ufffd"

    probe_lines = [
        "'use strict';",
        "const assert = require('node:assert/strict');",
        f"const tmpDir = {json.dumps(str(tmp_path))};",
        f"const {{ spawnNodeSync }} = require({json.dumps(str(ROOT / 'tests/_support/spawn_node.cjs'))});",
        "const ok = spawnNodeSync(['-e', 'process.stdout.write(JSON.stringify(process.execArgv))'], {}, 'Probe child');",
        "assert.deepEqual(JSON.parse(ok.stdout).slice(0, process.execArgv.length), process.execArgv);",
        "assert.throws(",
        "  () => spawnNodeSync(['-e', \"process.stdout.write('out'); process.stderr.write('err'); process.exit(5);\"], {}, 'Exit child'),",
        "  err => err.message === 'Exit child failed (status=5, signal=null):\\nstdout:\\nout\\nstderr:\\nerr'",
        ");",
    ]
    run_env = real_node_env
    if os.name != "nt":
        with pytest.raises(AssertionError, match=r"Crash probe failed with returncode -11 \(SIGSEGV\) \(empty stdout and stderr\)"):
            run_node(["-e", "process.kill(process.pid, 'SIGSEGV')"], cwd=tmp_path, env=real_node_env, label="Crash probe")
        shim_15 = _write_posix_shim(
            tmp_path / "s15",
            f'#!/bin/sh\n[ "$1" = "--version" ] && {{ echo v24.15.0; exit 0; }}\nexec {shlex.quote(real_rt.realpath)} "$@"\n',
        )
        run_env = {**clean_env, "WORKBENCH_NODE": str(shim_15)}
        probe_lines.extend([
            "assert(process.execArgv.includes('--no-sparkplug'));",
            "assert.throws(",
            "  () => spawnNodeSync(['-e', \"process.kill(process.pid, 'SIGSEGV')\"], { cwd: tmpDir }, 'Segv child'),",
            "  err => err.message.includes('signal=SIGSEGV') && err.message.includes('(empty stdout and stderr)')",
            ");",
        ])
    probe_lines.append("process.stdout.write('spawn_ok');")
    probe_file = tmp_path / "spawn_probe.cjs"
    probe_file.write_text("\n".join(probe_lines) + "\n", encoding="utf-8")
    assert run_node([probe_file], cwd=ROOT, env=run_env).stdout == "spawn_ok"
