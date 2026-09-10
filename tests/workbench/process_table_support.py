"""Projected fixtures and independent table-order oracles, without database reads."""

from collections import defaultdict
from typing import Optional

from core.models.workbench_process_table_query import ProcessTablePageRequest
from core.services.workbench.process_projection import project_part

STAGES = ("route", "source", "hours", "ready")
LONG_NAME = "中文长名称带空格 零件名称完整保留 " * 80


def managed_workflow(stage):
    position = STAGES.index(stage)
    result = {"origin": "managed", "stage": stage, "ready": stage == "ready"}
    for index, key in enumerate(STAGES[:3]):
        confirmed = index < position
        result[key] = {"state": "confirmed" if confirmed else "unconfirmed" if index == position else "locked",
                       "confirmed_at": "2026-09-09T08:00:00" if confirmed else None, "confirmed_by": None}
    return result


def part_entity(index, *, code=None, label: Optional[str] = "轴套", count=1, stage=None,
                route_raw: Optional[str] = "10车削20检验"):
    row = {"ref": f"{index:048x}", "part_no": code if code is not None else f"P-{index:05d}",
           "part_name": label, "route_raw": route_raw, "route_parsed": "yes" if count else "no",
           "remark": None, "batch_count": 0}
    operations = [{"status": "active", "source": "internal"} for _ in range(count)]
    return project_part(row, operations, managed_workflow(stage) if stage is not None else None)


def small_entities():
    return [part_entity(6, label=LONG_NAME, count=3, stage="hours"),
            part_entity(3, label="轴套", count=2, stage="source"),
            part_entity(2, label="轴套", count=2),
            part_entity(7, label="AbC工件", count=10, stage="ready", route_raw="OnlyRouteToken"),
            part_entity(1, label=None, count=0),
            part_entity(5, label="", count=0),
            part_entity(4, label="轴套", count=1, stage="ready"),
            part_entity(8, label="0", count=0)]


def projected_parts(facts):
    grouped = defaultdict(list)
    for row in facts["operations"]:
        grouped[row["part_no"]].append(row)
    return [project_part(row, grouped[row["part_no"]], facts["workflow"][row["part_no"]]["workflow"])
            for row in facts["parts"]]


def conditions(column, keys, mode="include"):
    return {column: {"mode": mode, "values": list(keys)}}


def facet_key(table, column, label, query=None):
    options = table.facets(query or ProcessTablePageRequest(), column, size=200)["options"]
    return next(item["key"] for item in options if item["label"] == label)


def refs(rows):
    return [row["ref"] for row in rows]


def oracle_order(row, column):
    if column == "operation_count":
        value = row["relationships"][column]
    elif column == "stage":
        value = STAGES.index(row["workflow"]["stage"])
    else:
        value = row[column]
    return (0, "") if value is None else (1, value)
