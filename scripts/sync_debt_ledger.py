from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Dict, List, Optional

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from tools.quality_gate_support import (  # noqa: E402
    ENTRY_STATUS_VALUES,
    QualityGateError,
    delete_risk,
    load_ledger,
    now_shanghai_iso,
    refresh_auto_fields,
    refresh_migrate_inline_facts,
    refresh_scan_startup_baseline,
    save_ledger,
    set_entry_fields,
    upsert_risk,
    validate_ledger_against_current_scan,
)


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
        "accepted_risk_count": len(ledger.get("accepted_risks") or []),
        "samples": summary.get("samples"),
    }
    _print_summary("治理台账校验通过", payload)
    return 0


def _handle_refresh(args: argparse.Namespace) -> int:
    mode = str(args.mode)
    current = load_ledger(required=False) if mode in {"migrate-inline-facts", "scan-startup-baseline"} else None
    if mode == "migrate-inline-facts":
        next_ledger = refresh_migrate_inline_facts(current)
    elif mode == "scan-startup-baseline":
        next_ledger = refresh_scan_startup_baseline(current)
    elif mode == "refresh-auto-fields":
        current = load_ledger(required=True)
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
