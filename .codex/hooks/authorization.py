"""Keep explicit user authorizations scoped to a repository and Codex session."""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlsplit, urlunsplit

DENY_PATTERNS = (
    (re.compile(r"\bgit\s+reset\s+--hard\b"), "会直接丢掉未提交改动"),
    (re.compile(r"\bgit\s+clean\b.*\s-[^\n]*[fdx]"), "会删除未跟踪文件，容易误删本地资料"),
    (re.compile(r"\bgit\s+checkout\s+(-f|--force)\b"), "强制切换可能覆盖当前工作区"),
    (re.compile(r"\bgit\s+switch\s+(-f|--force)\b"), "强制切换可能覆盖当前工作区"),
    (re.compile(r"\brm\s+(-[^\n]*r[^\n]*f|-[^\n]*f[^\n]*r)\b"), "递归强删风险太高"),
    (re.compile(r"\bchmod\s+-R\b"), "递归改权限可能污染大量文件"),
    (re.compile(r"\bchown\s+-R\b"), "递归改属主可能污染大量文件"),
)


def command_risks(command: str) -> List[str]:
    try:
        tokens = shlex.split(command)
    except ValueError:
        tokens = command.split()
    risks = [reason for pattern, reason in DENY_PATTERNS if pattern.search(command)]
    if re.search(r"\bgit\b[^\n;&|]*\bpush\b", command) and any(
        token in {"--force", "-f", "--force-with-lease", "--force-if-includes"}
        or token.startswith(("--force-with-lease=", "+")) for token in tokens
    ):
        risks.append("force_push")
    first = next((token for token in tokens if token and not token.startswith("-")), None)
    if first in {"rm", "mv", "cp"} and any(path in tokens for path in {"/", "~", "$HOME"}):
        risks.append("目标路径过大，可能影响整个用户目录或系统目录")
    return risks


class AuthorizationError(ValueError):
    pass


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(cwd), *args], capture_output=True, text=True, timeout=2
    )
    if result.returncode:
        raise AuthorizationError("授权目标的 Git 仓库或远端无法核对")
    return result.stdout.strip()


def _remote_urls(root: Path, remote: str) -> List[str]:
    values = _git(root, "remote", "get-url", "--push", "--all", remote).splitlines()
    destinations = []
    for value in values:
        url = urlsplit(value)
        # Bind actual push destinations without copying configured credentials.
        destinations.append(
            urlunsplit(url._replace(netloc=url.netloc.rsplit("@", 1)[-1]))
            if url.scheme and url.netloc else value
        )
    return destinations


def _context(payload: Dict[str, Any]) -> Tuple[Path, str, Path]:
    session = payload.get("session_id", "")
    cwd = payload.get("cwd", "")
    if not isinstance(session, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", session):
        raise AuthorizationError("缺少可核对的会话标识")
    if not isinstance(cwd, str) or not cwd:
        raise AuthorizationError("缺少可核对的仓库路径")
    root = Path(_git(Path(cwd), "rev-parse", "--show-toplevel")).resolve()
    git_dir = Path(_git(root, "rev-parse", "--absolute-git-dir"))
    return root, session, git_dir / "codex-hook-authorizations" / (session + ".json")


def _empty(root: Path, session: str) -> Dict[str, Any]:
    return {"session_id": session, "repo_root": str(root), "push": {}, "commands": []}


def _user_lines(prompt: str) -> Iterable[str]:
    """References and examples describe commands; they don't authorize them."""
    prompt = re.sub(r"<([A-Za-z_][\w:-]*)\b[^>]*>.*?</\1\s*>", "", prompt, flags=re.S)
    fenced = False
    for line in prompt.splitlines():
        line = line.strip()
        if line.startswith(("```", "~~~")):
            fenced = not fenced
            continue
        if fenced or not line or line.startswith((">", "<")):
            continue
        if re.search(r"示例|例如|比如|假设|是否|能否|如何|怎么|可以吗|他说|她说|原话|引用", line, re.I):
            continue
        yield line


def _normalized(command: str) -> List[str]:
    lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|()<>")
    lexer.whitespace_split = True
    lexer.commenters = ""
    return list(lexer)


def _branch(line: str, root: Path) -> Optional[str]:
    match = re.search(r"(?:到|至|\bto\s)\s*[`\"']?(?:origin/)?([A-Za-z0-9_][\w./-]*)\b", line, re.I)
    if not match:
        match = re.search(r"(?:强推|force\s+push)\s+(main|master)\b", line, re.I)
    if match:
        name = match.group(1)
        return name if name.startswith("refs/heads/") else "refs/heads/" + name
    if "主分支" in line:
        head = _git(root, "symbolic-ref", "refs/remotes/origin/HEAD")
        return "refs/heads/" + head[len("refs/remotes/origin/") :]
    return None


def _refuses_push(line: str) -> bool:
    for match in re.finditer(
        r"(?:不要|别|禁止|未授权|未经授权|没有授权|没有同意|拒绝|不(?:同意|批准|打算|想|允许|再|继续|执行|要)?|撤销|取消|收回)([^，,。;；?？]{0,20})(?:强推|force\s*push)",
        line, re.I,
    ):
        if not re.search(r"确认|询问|问我|再问", match.group(1)):
            return True
    return False


def _apply_prompt(state: Dict[str, Any], prompt: str, root: Path) -> None:
    for line in _user_lines(prompt):
        if re.search(r"(?:撤销|取消|收回)\s*(?:全部|所有|本次|这次)?授权|只读|只做检查|只检查|停止执行|暂停执行", line):
            state["push"] = {}
            state["commands"] = []
            continue
        if _refuses_push(line):
            try:
                branch = _branch(line, root)
            except AuthorizationError:
                branch = None
            if branch:
                state["push"].pop(branch, None)
            else:
                state["push"] = {}
            continue
        revoke = re.search(r"(?:不要|别|禁止|撤销|取消|收回|不再|不允许|不同意|不批准|拒绝|没有同意|未授权|未经授权|没有授权)\s*(?:你)?(?:再|继续)?(?:授权)?(?:执行|运行)?\s*`([^`]+)`", line)
        if revoke:
            command = _normalized(revoke.group(1))
            state["commands"] = [saved for saved in state["commands"] if saved != command]
            continue
        exact = re.search(r"(?:授权(?:你)?(?:执行|运行)?|请(?:直接)?(?:执行|运行)|(?:直接)?(?:执行|运行))\s*`([^`]+)`", line)
        if exact and not re.search(r"不要|禁止|未授权|未经授权|没有授权|没有同意|不同意|不批准|拒绝|不允许|不再", line[: exact.start()]):
            command = _normalized(exact.group(1))
            if command_risks(exact.group(1)) and command not in state["commands"]:
                state["commands"].append(command)
        # Inline quoted commands are handled above; prose grants use an explicit target.
        prose = re.sub(r"`[^`]*`|[\"'“‘][^\"'”’]*[\"'”’]", "", line)
        for clause in re.split(r"[，,。;；]", prose):
            clause = clause.strip()
            if re.search(r"研究|检查|审查|分析|评估|讨论|解释|说明|看看|风险|[?？]", clause):
                continue
            if not re.search(
                r"(?:明确授权|授权|批准|同意|请|直接|立即|现在|然后|开始|帮我|我想|要求|需要|再|把|将)[^?？]{0,20}(?:强推|force\s+push)|^(?:全部(?:改动)?|本次|这次)?\s*(?:强推|force\s+push)",
                clause, re.I,
            ):
                continue
            branch = _branch(clause, root)
            if branch:
                state["push"][branch] = {"remote": "origin", "urls": _remote_urls(root, "origin")}


def _bootstrap(payload: Dict[str, Any], root: Path, session: str) -> Dict[str, Any]:
    state = _empty(root, session)
    transcript = payload.get("transcript_path")
    if not transcript:
        return state
    try:
        with Path(transcript).open(encoding="utf-8") as source:
            first = json.loads(next(source))
            meta = first.get("payload", {})
            if first.get("type") != "session_meta" or meta.get("id") != session:
                raise AuthorizationError("授权记录与当前会话不一致")
            if Path(meta.get("cwd", "")).resolve() != root:
                raise AuthorizationError("授权记录与当前仓库不一致")
            for line in source:
                item = json.loads(line)
                message = item.get("payload", {})
                if item.get("type") != "response_item" or message.get("type") != "message" or message.get("role") != "user":
                    continue
                kinds = message.get("internal_chat_message_metadata_passthrough", {}).get("content_item_kinds")
                if kinds is not None and "user.text" not in kinds:
                    continue
                text = "\n".join(
                    block["text"] for block in message.get("content", [])
                    if block.get("type") == "input_text" and isinstance(block.get("text"), str)
                )
                _apply_prompt(state, text, root)
    except (OSError, StopIteration, TypeError, json.JSONDecodeError) as exc:
        raise AuthorizationError("会话授权记录无法读取，请检查 hook 的记录来源") from exc
    return state


def _load(payload: Dict[str, Any], root: Path, session: str, path: Path) -> Dict[str, Any]:
    if not path.exists():
        return _bootstrap(payload, root, session)
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
        if state.get("session_id") != session or state.get("repo_root") != str(root):
            raise AuthorizationError("保存的授权与当前仓库、会话不一致")
        if not isinstance(state.get("push"), dict) or not isinstance(state.get("commands"), list):
            raise AuthorizationError("保存的授权格式错误")
        return state
    except (OSError, AttributeError, json.JSONDecodeError) as exc:
        raise AuthorizationError("保存的授权无法读取") from exc


def _save(state: Dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as target:
        json.dump(state, target, ensure_ascii=False)
        temporary = target.name
    os.replace(temporary, path)


def record_user_prompt(payload: Dict[str, Any]) -> None:
    prompt = payload.get("prompt")
    if not isinstance(prompt, str):
        return
    root, session, path = _context(payload)
    try:
        state = _load(payload, root, session, path)
        _apply_prompt(state, prompt, root)
        _save(state, path)
    except (AuthorizationError, OSError, subprocess.SubprocessError, ValueError, TypeError, AttributeError, KeyError):
        # A failed update must not leave a previous grant usable after a revocation.
        _save(_empty(root, session), path)
        raise


def _push_target(command: str, cwd: Path) -> Optional[Tuple[Path, str, str]]:
    tokens = _normalized(command)
    if not tokens or any(re.search(r"[;&|()<>$`\n]", token) for token in tokens):
        return None
    if tokens[0] == "caffeinate":
        tokens.pop(0)
        while tokens and tokens[0] in {"-i", "-s", "-d", "-u"}:
            tokens.pop(0)
    if not tokens or tokens.pop(0) != "git":
        return None
    while len(tokens) > 1 and tokens[0] == "-C":
        cwd = (cwd / tokens[1]).resolve()
        tokens = tokens[2:]
    if not tokens or tokens.pop(0) != "push":
        return None
    positional = []
    for token in tokens:
        if token in {"--force", "-f", "--force-with-lease", "--force-if-includes", "-v", "--verbose", "--porcelain", "--dry-run", "-n", "--atomic", "-u", "--set-upstream"} or token.startswith("--force-with-lease="):
            continue
        if token.startswith("-"):
            return None
        positional.append(token)
    if len(positional) != 2:
        return None
    remote, refspec = positional
    source, separator, branch = refspec.lstrip("+").partition(":")
    if not separator or not re.fullmatch(r"[\w./-]+", branch):
        return None
    branch = branch if branch.startswith("refs/heads/") else "refs/heads/" + branch
    if source not in {"HEAD", branch, branch[len("refs/heads/") :]}:
        return None
    root = Path(_git(cwd, "rev-parse", "--show-toplevel")).resolve()
    return root, remote, branch


def is_authorized(payload: Dict[str, Any], command: str, risks: List[str]) -> bool:
    root, session, path = _context(payload)
    state = _load(payload, root, session, path)
    if not path.exists():
        _save(state, path)
    tool_input = payload.get("tool_input", {})
    cwd = Path(tool_input.get("workdir") or tool_input.get("cwd") or payload["cwd"])
    if Path(_git(cwd, "rev-parse", "--show-toplevel")).resolve() != root:
        return False
    if _normalized(command) in state["commands"]:
        return True
    if risks != ["force_push"]:
        return False
    target = _push_target(command, cwd)
    if not target:
        return False
    target_root, remote, branch = target
    grant = state["push"].get(branch)
    return bool(
        target_root == root and isinstance(grant, dict) and remote == grant.get("remote")
        and _remote_urls(root, remote) == grant.get("urls")
    )
