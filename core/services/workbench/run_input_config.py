"""A validated one-run configuration copy with no bootstrap or write service."""

from dataclasses import replace

from core.services.scheduler.config.config_snapshot import build_schedule_config_snapshot
from data.repositories.config_repo import ConfigRepository


def candidate_config(conn, settings):
    snapshot = build_schedule_config_snapshot(ConfigRepository(conn), strict_mode=True)
    return replace(
        snapshot,
        enforce_ready_default="yes" if settings["ready_check"] else "no",
        auto_assign_enabled="yes" if settings["missing_resource_policy"] == "auto_assign" else "no",
        auto_assign_persist="no",
        graph_analysis_mode="on",
    )
