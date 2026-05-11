from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, cast

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from tools.quality_gate_support import (  # noqa: E402
    ENTRY_STATUS_VALUES,
    QualityGateError,
    delete_risk,
    load_ledger,
    load_ledger_for_test_debt_import,
    load_ledger_unvalidated,
    now_shanghai_iso,
    refresh_auto_fields,
    refresh_migrate_inline_facts,
    refresh_scan_startup_baseline,
    save_ledger,
    set_entry_fields,
    upsert_risk,
    validate_ledger_against_current_scan,
)
from tools.test_debt_registry import (  # noqa: E402
    baseline_candidate_nodeids,
    build_test_debt_ledger_from_baseline,
    load_full_test_debt_baseline,
    mark_test_debt_fixed,
    validate_current_candidate_payload,
)


def current_git_head_sha() -> str:
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return proc.stdout.strip()


def current_git_status_short() -> List[str]:
    proc = subprocess.run(
        ["git", "status", "--short"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return [line for line in proc.stdout.splitlines() if line.strip()]


def _short_text_summary(text: object, *, max_lines: int = 20, max_chars: int = 2000) -> str:
    raw = str(text or "")
    if not raw:
        return "<空>"
    lines = raw.splitlines()
    rendered = "\n".join(lines[:max_lines])
    if len(lines) > max_lines:
        rendered += f"\n... 另外 {len(lines) - max_lines} 行未显示"
    if len(rendered) > max_chars:
        rendered = rendered[:max_chars] + "...<截断>"
    return rendered


def _file_excerpt_head(text: str, *, max_chars: int = 1000) -> str:
    excerpt = str(text or "")[:max_chars]
    return excerpt if excerpt else "<空>"


def _file_excerpt_tail(text: str, *, max_chars: int = 1000) -> str:
    raw = str(text or "")
    excerpt = raw[-max_chars:] if raw else ""
    return excerpt if excerpt else "<空>"


def collect_current_test_debt_payload() -> Dict[str, object]:
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        [
            sys.executable,
            os.path.join(REPO_ROOT, "tools", "collect_full_test_debt.py"),
            "--baseline-kind",
            "after_main_style_isolation",
            "--",
            "tests",
            "-q",
            "--tb=short",
            "-ra",
            "-p",
            "no:cacheprovider",
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )
    try:
        payload = json.loads(str(proc.stdout or ""))
    except json.JSONDecodeError as exc:
        raise QualityGateError(
            "当前 full pytest dry-run 未输出可解析 JSON："
            f"returncode={proc.returncode}；"
            f"stdout 摘要：{_short_text_summary(proc.stdout)}；"
            f"stderr 摘要：{_short_text_summary(proc.stderr)}"
        ) from exc
    if not isinstance(payload, dict):
        raise QualityGateError("当前 full pytest dry-run 输出不是对象")
    return cast(Dict[str, object], payload)


def load_current_test_debt_payload(path: str) -> Dict[str, object]:
    payload_path = Path(os.path.abspath(path))
    try:
        text = payload_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise QualityGateError(f"current payload 读取失败：path={path}；原因：{exc}") from exc

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise QualityGateError(
            "current payload 不是合法 JSON："
            f"path={path}；原因={exc}；"
            f"文件开头：{_file_excerpt_head(text)}；"
            f"文件结尾：{_file_excerpt_tail(text)}"
        ) from exc

    if not isinstance(payload, dict):
        raise QualityGateError(f"current payload 顶层必须是对象：path={path}")
    return cast(Dict[str, object], payload)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="APS 技术债务治理台账同步脚本")
    subparsers = parser.add_subparsers(dest="command", required=True)

    check_parser = subparsers.add_parser("check", help="校验治理台账结构、引用完整性与样本点")
    check_parser.set_defaults(handler=_handle_check)

    refresh_parser = subparsers.add_parser("refresh", help="按受控模式刷新治理台账")
    refresh_parser.add_argument(
        "--mode",
        required=True,
        choices=["migrate-inline-facts", "scan-startup-baseline", "refresh-auto-fields"],
        help="刷新模式",
    )
    refresh_parser.set_defaults(handler=_handle_refresh)

    set_entry_parser = subparsers.add_parser("set-entry-fields", help="只更新主条目的人工治理字段")
    set_entry_parser.add_argument("--id", required=True, help="主条目 id")
    set_entry_parser.add_argument("--owner", help="责任人")
    set_entry_parser.add_argument("--batch", help="所属批次")
    set_entry_parser.add_argument("--status", choices=sorted(ENTRY_STATUS_VALUES), help="治理状态")
    set_entry_parser.add_argument("--notes", help="说明")
    set_entry_parser.add_argument("--exit-condition", help="退出条件")
    set_entry_parser.set_defaults(handler=_handle_set_entry_fields)

    upsert_risk_parser = subparsers.add_parser("upsert-risk", help="新增或覆盖 accepted_risks 条目")
    upsert_risk_parser.add_argument("--id", required=True, help="风险 id")
    upsert_risk_parser.add_argument("--entry-id", action="append", dest="entry_ids", required=True, help="引用的主条目 id，可重复传入")
    upsert_risk_parser.add_argument("--owner", required=True, help="责任人")
    upsert_risk_parser.add_argument("--reason", required=True, help="接受原因")
    upsert_risk_parser.add_argument("--review-after", required=True, help="复核时点")
    upsert_risk_parser.add_argument("--exit-condition", required=True, help="退出条件")
    upsert_risk_parser.add_argument("--notes", help="补充说明")
    upsert_risk_parser.set_defaults(handler=_handle_upsert_risk)

    delete_risk_parser = subparsers.add_parser("delete-risk", help="删除 accepted_risks 条目")
    delete_risk_parser.add_argument("--id", required=True, help="风险 id")
    delete_risk_parser.set_defaults(handler=_handle_delete_risk)

    import_test_debt_parser = subparsers.add_parser(
        "import-test-debt-baseline",
        help="把已核实的 full pytest 测试债务 baseline 受控导入治理台账",
    )
    import_test_debt_parser.add_argument("--baseline", required=True, help="full pytest P0 测试债务 baseline 文件")
    import_test_debt_parser.add_argument(
        "--current-payload",
        help="已有 full test debt current payload JSON，例如 evidence/QualityGate/current_full_test_debt.json",
    )
    import_test_debt_parser.set_defaults(handler=_handle_import_test_debt_baseline)

    mark_test_debt_fixed_parser = subparsers.add_parser(
        "mark-test-debt-fixed",
        help="把一条已修好的 full pytest 测试债务标记为 fixed 并同步下调 ratchet",
    )
    mark_test_debt_fixed_parser.add_argument("--debt-id", required=True, help="要关闭的测试债务 debt_id")
    mark_test_debt_fixed_parser.set_defaults(handler=_handle_mark_test_debt_fixed)
    return parser


def _print_summary(title: str, payload: Dict[str, object]) -> None:
    print(title)
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def _handle_check(_args: argparse.Namespace) -> int:
    ledger = load_ledger(required=True)
    summary = validate_ledger_against_current_scan(ledger)
    payload = {
        "checked_at": now_shanghai_iso(),
        "schema_version": int(ledger.get("schema_version") or 0),
        "oversize_count": len(ledger.get("oversize_allowlist") or []),
        "complexity_count": len(ledger.get("complexity_allowlist") or []),
        "silent_fallback_count": len((ledger.get("silent_fallback") or {}).get("entries") or []),
        "test_debt_count": len((ledger.get("test_debt") or {}).get("entries") or []),
        "accepted_risk_count": len(ledger.get("accepted_risks") or []),
        "samples": summary.get("samples"),
    }
    _print_summary("治理台账校验通过", payload)
    return 0


def _handle_refresh(args: argparse.Namespace) -> int:
    mode = str(args.mode)
    current = load_ledger_unvalidated(required=False) if mode in {"migrate-inline-facts", "scan-startup-baseline"} else None
    if mode == "migrate-inline-facts":
        next_ledger = refresh_migrate_inline_facts(current)
    elif mode == "scan-startup-baseline":
        next_ledger = refresh_scan_startup_baseline(current)
    elif mode == "refresh-auto-fields":
        current = load_ledger_unvalidated(required=True)
        next_ledger = refresh_auto_fields(current)
    else:  # pragma: no cover
        raise QualityGateError(f"未知 refresh 模式：{mode}")
    save_ledger(next_ledger)
    payload = {
        "mode": mode,
        "updated_at": next_ledger.get("updated_at"),
        "oversize_count": len(next_ledger.get("oversize_allowlist") or []),
        "complexity_count": len(next_ledger.get("complexity_allowlist") or []),
        "silent_fallback_count": len((next_ledger.get("silent_fallback") or {}).get("entries") or []),
        "test_debt_count": len((next_ledger.get("test_debt") or {}).get("entries") or []),
        "accepted_risk_count": len(next_ledger.get("accepted_risks") or []),
    }
    _print_summary("治理台账已刷新", payload)
    return 0


def _handle_set_entry_fields(args: argparse.Namespace) -> int:
    ledger = load_ledger(required=True)
    updates = {
        "owner": args.owner,
        "batch": args.batch,
        "status": args.status,
        "notes": args.notes,
        "exit_condition": args.exit_condition,
    }
    if all(value is None for value in updates.values()):
        raise QualityGateError("set-entry-fields 至少需要一个待更新字段")
    next_ledger = set_entry_fields(ledger, args.id, updates)
    save_ledger(next_ledger)
    _print_summary(
        "主条目人工字段已更新",
        {
            "id": args.id,
            "updated_fields": {key: value for key, value in updates.items() if value is not None},
            "updated_at": next_ledger.get("updated_at"),
        },
    )
    return 0


def _handle_upsert_risk(args: argparse.Namespace) -> int:
    ledger = load_ledger(required=True)
    next_ledger = upsert_risk(
        ledger,
        risk_id=args.id,
        entry_ids=list(args.entry_ids or []),
        owner=args.owner,
        reason=args.reason,
        review_after=args.review_after,
        exit_condition=args.exit_condition,
        notes=args.notes,
    )
    save_ledger(next_ledger)
    _print_summary(
        "accepted_risks 已更新",
        {
            "id": args.id,
            "entry_ids": list(args.entry_ids or []),
            "updated_at": next_ledger.get("updated_at"),
        },
    )
    return 0


def _handle_delete_risk(args: argparse.Namespace) -> int:
    ledger = load_ledger(required=True)
    next_ledger = delete_risk(ledger, args.id)
    save_ledger(next_ledger)
    _print_summary(
        "accepted_risks 已删除",
        {"id": args.id, "updated_at": next_ledger.get("updated_at")},
    )
    return 0


def _verified_head_sha_for_current_payload(current_payload: Dict[str, object], *, payload_path: Optional[str]) -> str:
    if not payload_path:
        return str(current_payload.get("head_sha") or current_git_head_sha())

    current_head_sha = current_git_head_sha()
    payload_head_sha = current_payload.get("head_sha")
    if not isinstance(payload_head_sha, str) or not payload_head_sha.strip():
        raise QualityGateError(
            "current payload 缺少 head_sha，不能作为当前验证证据："
            f"path={payload_path}；current_head_sha={current_head_sha}"
        )
    normalized_payload_head = payload_head_sha.strip()
    if normalized_payload_head != current_head_sha:
        raise QualityGateError(
            "current payload head_sha 与当前 git HEAD 不一致，拒绝导入："
            f"path={payload_path}；payload_head_sha={normalized_payload_head}；current_head_sha={current_head_sha}"
        )
    payload_clean_before = current_payload.get("worktree_clean_before")
    payload_status_before = current_payload.get("git_status_short_before")
    if payload_clean_before is not True:
        raise QualityGateError(
            "current payload 生成时工作区不是干净状态，不能作为当前验证证据："
            f"path={payload_path}；worktree_clean_before={payload_clean_before!r}"
        )
    if payload_status_before != []:
        raise QualityGateError(
            "current payload 生成时 git_status_short_before 必须存在且为空列表，不能作为当前验证证据："
            f"path={payload_path}；git_status_short_before={_short_text_summary(payload_status_before)}"
        )
    current_status = current_git_status_short()
    if current_status:
        raise QualityGateError(
            "当前工作区不干净，不能复用 --current-payload，避免把旧证据当成当前证据："
            f"path={payload_path}；git_status_short={_short_text_summary(current_status)}"
        )
    return current_head_sha


def _handle_import_test_debt_baseline(args: argparse.Namespace) -> int:
    ledger = load_ledger_for_test_debt_import()
    payload = load_full_test_debt_baseline(str(args.baseline))
    if args.current_payload:
        current_payload = load_current_test_debt_payload(str(args.current_payload))
    else:
        current_payload = collect_current_test_debt_payload()
    validate_current_candidate_payload(
        current_payload,
        expected_nodeids=baseline_candidate_nodeids(payload),
    )
    verified_head_sha = _verified_head_sha_for_current_payload(current_payload, payload_path=args.current_payload)
    next_ledger, summary = build_test_debt_ledger_from_baseline(
        ledger,
        payload,
        verified_head_sha=verified_head_sha,
        last_verified_at=now_shanghai_iso(),
    )
    save_ledger(next_ledger)
    _print_summary("测试债务 baseline 已导入治理台账", summary)
    return 0


def _handle_mark_test_debt_fixed(args: argparse.Namespace) -> int:
    ledger = load_ledger(required=True)
    next_ledger, summary = mark_test_debt_fixed(
        ledger,
        str(args.debt_id),
        fixed_at=now_shanghai_iso(),
    )
    save_ledger(next_ledger)
    _print_summary("测试债务已标记为 fixed", summary)
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.handler(args))
    except QualityGateError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
