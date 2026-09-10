"""DB-owned route hook layered onto the existing isolated real CQ fixture."""

import json

from flask import Blueprint, g, request

from tests.workbench.trial_adoption_widgets_support import TrialAdoptionWidgetServer
from tests.workbench.trial_support import snapshot
from web.routes.workbench.trial_adoption_history import register_trial_adoption_history_routes


class TrialAdoptionHistoryWidgetServer(TrialAdoptionWidgetServer):
    def install_business(self):
        super().install_business()
        bp = Blueprint("db_adoption_history", __name__)
        register_trial_adoption_history_routes(bp)
        self.business.register_blueprint(bp)

        @self.business.before_request
        def history_before():
            if request.path.endswith("/adoption-history"):
                g.db_history_before = snapshot(g.db)

        @self.business.after_request
        def history_after(response):
            if hasattr(g, "db_history_before"):
                assert snapshot(g.db) == g.db_history_before
            return response

    def capture_proof(self):
        if self.path is None:
            return
        with self.connect() as conn:
            after = snapshot(conn)["WorkbenchDashboardItems"]
            before = self.before["WorkbenchDashboardItems"]
            current = {row[0]: row for row in after}
            assert all(current.get(row[0]) == row for row in before)
            old_ids = {row[1][1] for row in before}
            added = [dict(row) for row in conn.execute("SELECT * FROM WorkbenchDashboardItems") if row["item_ref"] not in old_ids]
            plans = [json.loads(row[0])["data"]["official_plan"]["plan_ref"] for row in conn.execute(
                "SELECT outcome_json FROM WorkbenchCommandReceipts WHERE action='trial.scenario.adopt'")]
            expected = {(kind, row[0]) for ref in plans for row in conn.execute(
                "SELECT ref FROM WorkbenchTaskRefs WHERE plan_ref=?", (ref,)) for kind in ("actual", "downtime")}
            assert {(row["category"], row["task_ref"]) for row in added} == expected
            assert len(added) == len(expected) and all(row["batch_ref"] is None for row in added)
        # CQ now checks the exact v29 task mapping delta against the real baseline.
        super().capture_proof()
