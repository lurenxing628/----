"""Explain exclusion along the existing per-batch, per-piece sequence chain."""

from collections import defaultdict

from core.models.workbench_preflight import issue
from core.services.workbench.preflight_checks import number


def predecessor_satisfied(row):
    if row["status"] in ("eligible", "auto_assign_required"):
        return True
    return (row["status"] == "protected" and row["execution"]["execution_state"] == "complete"
            and bool(row["execution"]["confirmed_finish"]) and row["execution"]["data_quality"] != "invalid")


def link_chain(chain):
    previous = None
    for row in sorted(chain, key=lambda item: item["sequence"]):
        if previous:
            row["predecessor_refs"] = [previous["operation_ref"]]
            if not predecessor_satisfied(previous) and row["status"] != "protected":
                if row["status"] != "blocked":
                    row["status"] = "skipped"
                row["issues"].append(issue("predecessor_excluded", "前序未进入本次排产且无可信完工证据，后序不能断链排入。",
                                           related_operation_ref=previous["operation_ref"], predecessor_sequence=previous["sequence"]))
        previous = row


def link_predecessors(rows):
    chains = defaultdict(list)
    for row in rows:
        chains[row["piece_id"] or ""].append(row)
    for chain in chains.values():
        invalid = any(not number(row["sequence"], integer=True, positive=True) for row in chain)
        duplicate = len({row["sequence"] for row in chain}) != len(chain)
        if invalid or duplicate:
            for row in chain:
                if row["status"] != "protected":
                    row["status"] = "blocked"
                    row["issues"].append(issue("dependency_ambiguous", "同一分件的工序顺序缺失或重复，无法确认前后序。"))
        else:
            link_chain(chain)
