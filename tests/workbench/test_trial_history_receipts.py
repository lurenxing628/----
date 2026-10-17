"""Lossless trial receipts share their permanent history instead of duplicating it."""

import json
import sqlite3
from collections import Counter

from flask import Blueprint

from core.models.workbench_command import canonical_json
from core.services.workbench.commands import WorkbenchCommandService
from data.repositories.workbench_command_repo import WorkbenchCommandRepository
from data.repositories.workbench_trial_repo import HISTORY_REFERENCE_FORMAT, WorkbenchTrialRepository
from tests.workbench.trial_support import api, change, create, service
from tests.workbench.trial_support import trial_case as trial_case
from web.routes.workbench.materials import register_material_routes


def test_change_receipts_replay_original_full_history_through_every_public_reader(trial_case):
    case = trial_case
    draft = create(case)
    first = change(case, draft, operator="O1", key="trial-history-change-01")
    second = change(case, first["data"], key="trial-history-change-02")
    unchanged = change(case, second["data"], key="trial-history-change-03")
    assert first["data"]["change_history"][0]["validation"]["issues"]
    assert len(second["data"]["change_history"]) == 2
    assert unchanged["result"] == "unchanged"
    repo = WorkbenchCommandRepository(case.conn)
    for key, original, revision in (("trial-history-change-01", first, 2),
                                    ("trial-history-change-02", second, 3),
                                    ("trial-history-change-03", unchanged, 3)):
        stored = repo.get(key)
        payload = json.loads(stored["outcome_json"])
        assert payload["data"]["change_history"] == {
            "format": HISTORY_REFERENCE_FORMAT, "draft_ref": draft["draft_ref"], "through_revision": revision}
        expected = dict(original, replayed=True)
        assert WorkbenchCommandService(case.conn).lookup(key) == expected
        assert service(case.conn).lookup(key) == expected
        # Old inline receipts retain the same complete public validation body.
        legacy = dict(stored, outcome_json=canonical_json({field: original[field] for field in ("result", "data", "warnings")}))
        assert repo.public_result(legacy, replayed=True) == expected
    assert change(case, draft, operator="O1", key="trial-history-change-01") == dict(first, replayed=True)

    client = api(case)
    generic = Blueprint("trial_generic_receipts", __name__)
    register_material_routes(generic)
    case.app.register_blueprint(generic)
    assert client.get("/api/workbench/v1/commands/trial-history-change-01").get_json() == dict(first, replayed=True)
    assert client.get("/api/workbench/v1/trial/commands/trial-history-change-01").get_json()["data"]["receipt"] == dict(first, replayed=True)

    # Permanent Changes and Receipts alone restore the result, even if the
    # original mutable workspace and its rows are no longer available.
    retained = sqlite3.connect(":memory:")
    retained.row_factory = sqlite3.Row
    try:
        for name in ("WorkbenchTrialChanges", "WorkbenchCommandReceipts"):
            declaration = case.conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone()[0]
            retained.execute(declaration)
            rows = case.conn.execute('SELECT * FROM "' + name + '"').fetchall()
            retained.executemany('INSERT INTO "' + name + '" VALUES (' + ",".join("?" for _ in rows[0]) + ")", rows)
        retained.commit()
        assert WorkbenchCommandService(retained).lookup("trial-history-change-01") == dict(first, replayed=True)
        assert service(retained).lookup("trial-history-change-01") == dict(first, replayed=True)
        value = {"task_ref": draft["tasks"][0]["task_ref"], "machine_ref": case.ref("machine", "M2"),
                 "operator_ref": case.ref("operator", "O1"), "start": "2026-09-09T13:00:00"}
        assert service(retained).change(draft["draft_ref"], value, "expired-token", "trial-history-change-01") == dict(first, replayed=True)
    finally:
        retained.close()


def test_repeated_historical_validation_is_decoded_once_per_read(trial_case, monkeypatch):
    from data.repositories import workbench_trial_repo

    case = trial_case
    draft = create(case)
    first = change(case, draft)["data"]
    change(case, first, start="2026-09-10T08:00:00", key="trial-history-change-02")
    texts = [row[0] for row in case.conn.execute("SELECT validation_json FROM WorkbenchTrialChanges ORDER BY revision")]
    assert len(texts) == 2 and texts[0] == texts[1]
    decoded, original = Counter(), workbench_trial_repo.load_object

    def load_once(text):
        decoded[text] += 1
        return original(text)

    monkeypatch.setattr(workbench_trial_repo, "load_object", load_once)
    history = WorkbenchTrialRepository(case.conn).public_history(draft["draft_ref"])
    assert len(history) == 2 and history[0]["validation"] == original(texts[0])
    assert decoded[texts[0]] == 1
    WorkbenchTrialRepository(case.conn).public_history(draft["draft_ref"])
    assert decoded[texts[0]] == 2  # Request-local reuse never masks later reads.
