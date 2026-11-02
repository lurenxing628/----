"""The run data context of one request, bound to the maintenance directory that startup checked."""

from flask import current_app, g

from core.services.workbench.facts.run_data_context import RunDataContext


def request_data_context():
    return RunDataContext(g.db, current_app.config["WORKBENCH_SYSTEM_JOURNAL_DIR"])
