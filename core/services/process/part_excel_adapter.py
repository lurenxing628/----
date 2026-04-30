from __future__ import annotations

from typing import Any, Dict


def build_existing_for_excel_routes(part_repo: Any) -> Dict[str, Dict[str, Any]]:
    existing: Dict[str, Dict[str, Any]] = {}
    for part in part_repo.list():
        existing[part.part_no] = {"图号": part.part_no, "名称": part.part_name, "工艺路线字符串": part.route_raw}
    return existing
