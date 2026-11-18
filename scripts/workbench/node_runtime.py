"""Pure-stdlib Python 3.8 Node.js runtime discovery, version probing, and execution."""

import itertools
import os
import re
import signal
import subprocess
from typing import Dict, Iterator, List, Mapping, NamedTuple, Optional, Sequence, Set, Tuple, Union

NODE_VERSION_RE = re.compile(r"\Av(\d{1,6})\.(\d{1,6})(?:\.|\Z)")


class NodeRuntimeError(ValueError):
    def __init__(self, message: str, *, configured_node: Optional[str] = None) -> None:
        super().__init__(message)
        self.configured_node = configured_node


class NodeNotFoundError(NodeRuntimeError):
    pass


class NodeProbeError(NodeRuntimeError):
    pass


class SelectedNodeRuntime(NamedTuple):
    realpath: str
    version: str
    major_minor: Tuple[int, int]


def parse_node_version(version: str) -> Tuple[int, int]:
    match = NODE_VERSION_RE.match(version)
    if not match:
        raise NodeProbeError(f"Unrecognized Node version: {version!r}")
    return int(match.group(1)), int(match.group(2))


def _home_dir(env: Mapping[str, str]) -> str:
    return env.get("HOME") or (env.get("USERPROFILE") if os.name == "nt" else None) or os.path.expanduser("~")


def _expand_user(raw: str, env: Mapping[str, str]) -> str:
    if raw == "~":
        return ""
    if raw.startswith("~/") or (os.name == "nt" and raw.startswith("~\\")):
        rest = raw[1:].lstrip(os.path.sep + (os.path.altsep or ""))
        return "" if (not rest or os.path.splitdrive(rest)[0]) else os.path.join(_home_dir(env), rest)
    return os.path.expanduser(raw)


def effective_path(env: Mapping[str, str]) -> str:
    return env["PATH"] if "PATH" in env else os.environ.get("PATH", os.defpath)


def _has_root_anchor(path: str) -> bool:
    return os.path.isabs(path) and (os.name != "nt" or bool(os.path.splitdrive(path)[0]))


def _anchor_path_entry(entry: str, cwd: str) -> str:
    if os.name == "nt":
        return entry if (not entry or _has_root_anchor(entry)) else os.path.join(cwd, entry)
    return entry if _has_root_anchor(entry) else (os.path.join(cwd, entry) if entry else cwd)


def _anchor_win_candidate(anchored: str) -> Optional[str]:
    candidates = (anchored,) if os.path.splitext(os.path.basename(anchored))[1] else (anchored + ".exe", anchored)
    return next((os.path.realpath(c) for c in candidates if os.path.isfile(c)), None)


def _anchor_candidate(raw: str, env: Mapping[str, str]) -> Optional[str]:
    expanded = _expand_user(raw, env)
    seps = (os.path.sep, os.path.altsep) if os.path.altsep else (os.path.sep,)
    if not expanded or expanded.endswith(seps):
        return None
    anchored = expanded if _has_root_anchor(expanded) else os.path.join(os.getcwd(), expanded)
    if os.name == "nt":
        return _anchor_win_candidate(anchored)
    return os.path.realpath(anchored) if (os.path.isfile(anchored) and os.access(anchored, os.X_OK)) else None


def _iter_path_candidates(name: str, path_value: str) -> Iterator[str]:
    if not path_value:
        return
    target = (name if os.path.splitext(name)[1] else (name + ".exe")) if os.name == "nt" else name
    cwd = os.getcwd()
    for entry in path_value.split(os.pathsep):
        anchored_dir = _anchor_path_entry(entry, cwd)
        if not anchored_dir:
            continue
        cand = os.path.join(anchored_dir, target)
        if os.path.isfile(cand) and (os.name == "nt" or os.access(cand, os.X_OK)):
            yield os.path.realpath(cand)


def _iter_fallback_candidates(env: Mapping[str, str]) -> Iterator[str]:
    home = _home_dir(env)
    if os.name == "nt":
        bin_name, posix_bins = "node.exe", ()
    else:
        bin_name, posix_bins = "node", ("/opt/homebrew/bin/node", "/usr/local/bin/node")
    fixed = (
        os.path.join(home, ".cache", "codex-runtimes", "codex-primary-runtime", "dependencies", "node", "bin", bin_name),
        *posix_bins,
        os.path.join(home, ".nvm", "current", "bin", bin_name),
    )
    for cand in fixed:
        resolved = _anchor_candidate(cand, env)
        if resolved is not None:
            yield resolved
    versions_dir = os.path.join(home, ".nvm", "versions", "node")
    try:
        entries = sorted(os.listdir(versions_dir), reverse=True)
    except OSError:
        return
    for entry in entries:
        resolved = _anchor_candidate(os.path.join(versions_dir, entry, "bin", bin_name), env)
        if resolved is not None:
            yield resolved


def _execution_env(node_realpath: str, env: Optional[Mapping[str, str]] = None) -> Dict[str, str]:
    base = env if env is not None else os.environ
    exec_env = dict(base)
    cur_path = effective_path(base)
    node_dir = os.path.dirname(node_realpath)
    exec_env["PATH"] = f"{node_dir}{os.pathsep}{cur_path}" if cur_path else node_dir
    return exec_env


def _append_streams(header: str, stdout: str, stderr: str) -> str:
    parts: List[str] = []
    for name, text in (("stdout", stdout), ("stderr", stderr)):
        if text != "":
            body = text[:-2] if text.endswith("\r\n") else (text[:-1] if text.endswith("\n") else text)
            parts.append(f"{name}:\n{body}")
    return f"{header}:\n" + "\n".join(parts) if parts else header


def format_node_failure(returncode: int, stdout: str, stderr: str, label: str) -> str:
    sig_suffix = ""
    if returncode < 0:
        try:
            sig_suffix = f" ({signal.Signals(-returncode).name})"
        except ValueError:
            sig_suffix = f" (signal {-returncode})"
    header = f"{label} failed with returncode {returncode}{sig_suffix}"
    with_streams = _append_streams(header, stdout, stderr)
    return with_streams if with_streams != header else f"{header} (empty stdout and stderr)"


def _decode_stream(raw: Optional[bytes]) -> str:
    return "" if raw is None else raw.decode("utf-8", errors="replace")


def probe_node_version(
    node_realpath: str, env: Mapping[str, str], *, configured_node: Optional[str] = None
) -> Tuple[str, Tuple[int, int]]:
    label = f"Node version probe ({node_realpath})"
    try:
        completed = subprocess.run(
            [node_realpath, "--version"], env=_execution_env(node_realpath, env), capture_output=True, timeout=5
        )
    except subprocess.TimeoutExpired as exc:
        msg = _append_streams(f"{label} timed out after {exc.timeout}s", _decode_stream(exc.stdout), _decode_stream(exc.stderr))
        raise NodeProbeError(msg, configured_node=configured_node) from exc
    except OSError as exc:
        raise NodeProbeError(f"{label} failed: {exc}", configured_node=configured_node) from exc
    out_text = completed.stdout.decode("utf-8", errors="replace")
    err_text = completed.stderr.decode("utf-8", errors="replace")
    if completed.returncode != 0:
        raise NodeProbeError(format_node_failure(completed.returncode, out_text, err_text, label), configured_node=configured_node)
    value = out_text.strip()
    try:
        return value, parse_node_version(value)
    except NodeProbeError as exc:
        raise NodeProbeError(_append_streams(f"{exc} ({node_realpath})", "", err_text), configured_node=configured_node) from exc


def _is_path_spec(spec: str) -> bool:
    return (
        spec in (os.curdir, os.pardir)
        or os.path.sep in spec
        or (os.path.altsep is not None and os.path.altsep in spec)
        or spec.startswith("~")
        or bool(os.path.splitdrive(spec)[0])
    )


def _select_explicit_node(
    spec: str, path_value: str, env: Mapping[str, str], *, configured_node: Optional[str] = None
) -> SelectedNodeRuntime:
    if _is_path_spec(spec):
        realpath = _anchor_candidate(spec, env)
        if realpath is None:
            raise NodeNotFoundError(f"Node executable is not runnable: {spec}", configured_node=configured_node)
    else:
        realpath = next(_iter_path_candidates(spec, path_value), None)
        if realpath is None:
            raise NodeNotFoundError(f"Node executable not found: {spec}", configured_node=configured_node)
    version, major_minor = probe_node_version(realpath, env, configured_node=configured_node)
    return SelectedNodeRuntime(realpath, version, major_minor)


def _select_auto_node(path_value: str, env: Mapping[str, str]) -> SelectedNodeRuntime:
    seen: Set[str] = set()
    first_probe_error: Optional[NodeProbeError] = None
    for realpath in itertools.chain(_iter_path_candidates("node", path_value), _iter_fallback_candidates(env)):
        dedup_key = os.path.normcase(realpath)
        if dedup_key in seen:
            continue
        seen.add(dedup_key)
        try:
            version, major_minor = probe_node_version(realpath, env)
        except NodeProbeError as exc:
            if first_probe_error is None:
                first_probe_error = exc
            continue
        return SelectedNodeRuntime(realpath, version, major_minor)
    if first_probe_error is not None:
        raise first_probe_error
    raise NodeNotFoundError("Node executable not found")


def select_node_runtime(
    env: Optional[Mapping[str, str]] = None, *, explicit_node: Optional[Union[str, os.PathLike]] = None
) -> SelectedNodeRuntime:
    base_env = env if env is not None else os.environ
    path_value = effective_path(base_env)
    if explicit_node is not None:
        spec = os.fsdecode(explicit_node).strip()
        if not spec:
            raise NodeNotFoundError("Node executable is required")
        return _select_explicit_node(spec, path_value, base_env)
    wb = (base_env.get("WORKBENCH_NODE") or "").strip()
    return _select_explicit_node(wb, path_value, base_env, configured_node=wb) if wb else _select_auto_node(path_value, base_env)


def node_cli_args(node_realpath: str, major_minor: Tuple[int, int]) -> List[str]:
    major, minor = major_minor
    return [node_realpath, "--no-sparkplug"] if (major == 24 and minor < 22) else [node_realpath]


def execute_selected_node(
    runtime: SelectedNodeRuntime,
    args: Sequence[Union[str, os.PathLike]],
    *,
    input_text: Optional[str] = None,
    cwd: Optional[Union[str, os.PathLike]] = None,
    env: Optional[Mapping[str, str]] = None,
    timeout: Optional[float] = None,
) -> subprocess.CompletedProcess:
    cmd: List[Union[str, os.PathLike]] = [*node_cli_args(runtime.realpath, runtime.major_minor), *args]
    raw = subprocess.run(
        cmd,
        input=input_text.encode("utf-8") if input_text is not None else None,
        cwd=cwd,
        env=_execution_env(runtime.realpath, env),
        capture_output=True,
        timeout=timeout,
    )
    out_mode = "strict" if raw.returncode == 0 else "replace"
    return subprocess.CompletedProcess(
        cmd, raw.returncode, raw.stdout.decode("utf-8", errors=out_mode), raw.stderr.decode("utf-8", errors="replace")
    )


def anchor_node_env(env: Mapping[str, str]) -> Dict[str, str]:
    anchored = dict(env)
    cwd = os.getcwd()
    wb = anchored.get("WORKBENCH_NODE", "").strip()
    if wb and _is_path_spec(wb):
        expanded = _expand_user(wb, anchored)
        if not expanded:
            anchored["WORKBENCH_NODE"] = os.path.join(cwd, "")
        else:
            anchored["WORKBENCH_NODE"] = expanded if _has_root_anchor(expanded) else os.path.join(cwd, expanded)
    raw_path = anchored.get("PATH")
    if raw_path:
        anchored["PATH"] = os.pathsep.join(_anchor_path_entry(entry, cwd) for entry in raw_path.split(os.pathsep))
    return anchored
