from __future__ import annotations

from typing import Any, Dict, List


def build_route_rows(by_part: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    route_rows: List[Dict[str, Any]] = []
    for part_no in sorted(by_part.keys()):
        recs = sorted(by_part[part_no], key=lambda x: int(x["seq"]))
        part_name = str(recs[0].get("part_name") or part_no)
        route_string = "".join([f"{int(r['seq'])}{str(r.get('final_name') or '')}" for r in recs])
        route_rows.append({"图号": part_no, "名称": part_name, "工艺路线字符串": route_string})
    return route_rows


def build_part_operation_hours_rows(by_part: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for part_no in sorted(by_part.keys()):
        recs = sorted(by_part[part_no], key=lambda x: int(x["seq"]))
        for rec in recs:
            if not rec.get("source_internal"):
                continue
            rows.append(
                {
                    "图号": part_no,
                    "工序": int(rec["seq"]),
                    "换型时间(h)": float(rec.get("setup_hours") or 0.0),
                    "单件工时(h)": float(rec.get("unit_hours") or 0.0),
                }
            )
    return rows
