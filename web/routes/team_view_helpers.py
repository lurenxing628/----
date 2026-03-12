from __future__ import annotations

from typing import Any, Dict, List

from flask import g

from core.services.personnel import ResourceTeamService


def load_team_options() -> List[Dict[str, Any]]:
    return ResourceTeamService(g.db, op_logger=getattr(g, "op_logger", None)).list_options(status=None)


def build_team_name_map(team_options: List[Dict[str, Any]]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for item in team_options:
        team_id = str(item.get("team_id") or "").strip()
        name = str(item.get("name") or "").strip()
        if team_id:
            out[team_id] = name
    return out
