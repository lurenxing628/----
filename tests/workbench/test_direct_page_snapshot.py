"""Fresh calibration pagination keeps snapshot, detail and export bindings."""

import csv
from io import BytesIO, StringIO

import pytest
from flask import Blueprint, Flask, g
from openpyxl import load_workbook

from core.services.workbench.calibration.service import WorkbenchCalibrationService
from tests.workbench.template_lineage_support import ledger_fixture as _ledger_fixture  # noqa: F401
from tests.workbench.template_lineage_support import lineage_case as _lineage_case  # noqa: F401
from web import public_token_registry
from web.routes.workbench.calibration import register_calibration_routes


@pytest.mark.parametrize("suffix", ("", "/facets/operation_label"))
def test_calibration_captures_current_clock_in_snapshot_and_reuses_token_clock(lineage_case, monkeypatch, suffix):
    from tests.workbench.execution_ledger_support import NOW
    from web.routes.workbench import calibration, calibration_table

    case = lineage_case
    app = Flask("calibration-snapshot-clock")
    app.config.update(TESTING=True, SECRET_KEY="temporary-calibration-snapshot-clock")
    bp = Blueprint("calibration_snapshot_clock", __name__)
    register_calibration_routes(bp)
    app.register_blueprint(bp)

    @app.before_request
    def database():
        g.db = case.conn

    clocks = []

    def current_clock():
        clocks.append(case.conn.in_transaction)
        return NOW

    module = calibration_table if suffix else calibration
    monkeypatch.setattr(module, "current_snapshot_time", current_clock)
    client, path = app.test_client(), "/api/workbench/v1/calibration" + suffix
    initial = client.get(path)
    assert initial.status_code == 200, initial.get_json()
    body = initial.get_json()
    assert body["meta"]["as_of"] == NOW.isoformat(timespec="seconds")
    assert clocks == [True]
    repeated = client.get(path, query_string={"snapshot_ref": body["meta"]["snapshot_ref"]})
    assert repeated.status_code == 200, repeated.get_json()
    assert repeated.get_json()["data"] == body["data"]
    assert repeated.get_json()["meta"]["as_of"] == body["meta"]["as_of"]
    assert clocks == [True]


def test_calibration_restores_page_once_and_keeps_scope_source_and_expiry(lineage_case, monkeypatch, record_property):
    case = lineage_case
    case.conn.execute("INSERT INTO PartOperations(part_no,seq,op_type_id,op_type_name,source,setup_hours,unit_hours) "
                      "VALUES ('P1',2,'T1','second template','internal',0,2)")
    case.conn.commit()
    app = Flask("calibration-direct-page")
    app.config.update(TESTING=True, SECRET_KEY="temporary-calibration-direct-page")
    bp = Blueprint("calibration_direct_page", __name__)
    register_calibration_routes(bp)
    app.register_blueprint(bp)

    @app.before_request
    def database():
        g.db = case.conn

    client, path, calls = app.test_client(), "/api/workbench/v1/calibration", []
    original = WorkbenchCalibrationService.read

    def captured(reader, query, **kwargs):
        calls.append(query.number)
        return original(reader, query, **kwargs)

    query = {"page": 2, "size": 1}
    before = case.conn.total_changes
    with monkeypatch.context() as patch:
        patch.setattr(WorkbenchCalibrationService, "read", captured)
        response = client.get(path, query_string=query)
    assert response.status_code == 200, response.get_json()
    direct = response.get_json()
    assert calls == [2] and direct["data"]["page"]["number"] == 2
    assert direct["data"]["page"]["total"] == 2 and len(direct["data"]["items"]) == 1
    assert direct["meta"]["source"] == "production" and response.headers["Cache-Control"] == "no-store"
    record_property("direct_page", 2)
    record_property("fact_query_calls", len(calls))
    record_property("data_fields", sorted(direct["data"]))
    token = direct["meta"]["snapshot_ref"]
    from web.routes.workbench import read_context

    resolves, original_resolve = [], read_context.resolve_public_token

    def resolved(*args, **kwargs):
        resolves.append(args[1])
        return original_resolve(*args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(read_context, "resolve_public_token", resolved)
        repeated = client.get(path, query_string={**query, "snapshot_ref": token}).get_json()
    assert resolves == [token]
    assert repeated["data"] == direct["data"] and repeated["meta"].keys() == direct["meta"].keys()
    assert repeated["meta"]["request_ref"] != direct["meta"]["request_ref"]
    assert all(repeated["meta"][key] == value for key, value in direct["meta"].items() if key != "request_ref")
    selected = direct["data"]["items"][0]["suggestion_ref"]
    for target in (path + "/export", path + "/" + selected):
        missing = client.get(target, query_string=query)
        assert missing.status_code == 400 and missing.get_json()["error"]["code"] == "snapshot_required"
        bound = client.get(target, query_string={**query, "snapshot_ref": token})
        assert bound.status_code == 200, bound.get_json()
    for format_name in ("csv", "xlsx"):
        exported = client.get(path + "/export", query_string={**query, "snapshot_ref": token, "format": format_name})
        assert exported.status_code == 200
        if format_name == "csv":
            values = list(csv.reader(StringIO(exported.data.decode("utf-8-sig"))))
        else:
            workbook = load_workbook(BytesIO(exported.data), read_only=True)
            try:
                values = list(workbook.worksheets[0].values)
            finally:
                workbook.close()
        assert len(values[0]) == 22 and tuple(values[0][3:5]) == ("工序名称", "工序来源")
        assert len(values) == 3 and all(len(row) == 22 and row[4] == "自制" for row in values[1:])
    wrong_scope = client.get(path, query_string={**query, "source": "external", "snapshot_ref": token})
    assert wrong_scope.status_code == 409 and wrong_scope.get_json()["error"]["code"] == "snapshot_stale"
    now = public_token_registry.time.time()
    with monkeypatch.context() as patch:
        patch.setattr(public_token_registry.time, "time", lambda: now + 901)
        expired = client.get(path, query_string={**query, "snapshot_ref": token})
    assert expired.status_code == 409 and expired.get_json()["error"]["code"] == "snapshot_stale"
    assert case.conn.total_changes == before


def test_token_bindings_share_facts_preserve_types_and_own_their_lifetime(monkeypatch, record_property):
    from datetime import date

    import pytest

    from core.errors import ValidationError
    from core.models.content import content_text
    from core.models.workbench_command import WorkbenchCommandRejected
    from web.routes.workbench import read_context, write_context

    app = Flask("direct-token-values")
    clock = [1000.0]
    monkeypatch.setattr(public_token_registry.time, "time", lambda: clock[0])
    with app.app_context():
        class SharedFacts(str):
            equalities = 0
            __hash__ = str.__hash__

            def __eq__(self, other):
                SharedFacts.equalities += 1
                return str.__eq__(self, other)

        snapshot = SharedFacts(content_text({"facts": list(range(1000))}))
        issue_context = write_context.issue_write_context.for_snapshot(snapshot)
        tokens = [issue_context(str(index), ["save"])["write_token"] for index in range(100)]
        same_content = SharedFacts(snapshot)
        assert same_content is not snapshot
        SharedFacts.equalities = 0
        reopened = write_context.issue_write_context.for_snapshot(same_content)
        reused = [reopened(str(index), ["save"])["write_token"] for index in range(100)]
        assert reused == tokens and SharedFacts.equalities == 1
        record_property("shared_facts_equalities", SharedFacts.equalities)
        record_property("tokens_reused", reused == tokens)
        bindings = [public_token_registry.resolve_public_token(write_context._SCOPE, token, message="expired", field="token")
                    for token in tokens]
        assert all(binding.snapshot[1] is snapshot for binding in bindings)
        indexes = public_token_registry._registry()[write_context._SCOPE]["by_value"]
        assert len(indexes) == 1 and len(next(iter(indexes.values()))) == 100
        assert write_context.issue_write_context("0", ["save"], snapshot)["write_token"] == tokens[0]
        for old, new in ((True, 1), (1, 1.0), (1, "1"), (b"x", {"$sqlite_blob": "eA=="}),
                         (date(2026, 10, 15), {"storage_type": "date", "iso": "2026-10-15"})):
            token = write_context.issue_write_context("typed", ["save"], old)["write_token"]
            write_context.validate_write_context(token, "typed", "save", old)
            with pytest.raises(WorkbenchCommandRejected):
                write_context.validate_write_context(token, "typed", "save", new)
        # An independent retained reference survives expiry of the original read token.
        read = read_context.bind_read_snapshot({"kind": "source"}, snapshot)
        binding = read_context.resolve_read_snapshot(read["snapshot_ref"])
        clock[0] += 800
        retained = public_token_registry.issue_public_token("retained", binding, key="one", ttl_seconds=900)
        clock[0] += 101
        with pytest.raises(ValidationError):
            public_token_registry.resolve_public_token(read_context._SCOPE, read["snapshot_ref"], message="expired", field="token")
        assert public_token_registry.resolve_public_token("retained", retained, message="expired", field="token") is binding
        with pytest.raises(WorkbenchCommandRejected):
            write_context.validate_write_context(tokens[0], "0", "save", snapshot)


def test_direct_token_reissue_keeps_old_expiry_and_lru_drops_empty_groups(monkeypatch):
    import pytest

    from core.errors import ValidationError

    app = Flask("direct-token-expiry")
    clock = [1000.0]
    monkeypatch.setattr(public_token_registry.time, "time", lambda: clock[0])
    with app.app_context():
        value = object()
        issuer = public_token_registry.PublicTokenIssuer("values", group="facts", ttl_seconds=100)
        first, expiry = issuer.issue_with_expiry(value, key="row")
        clock[0] = 1060
        second, next_expiry = issuer.issue_with_expiry(value, key="row")
        assert first != second and expiry == 1100 and next_expiry == 1160
        assert public_token_registry.resolve_public_token("values", first, message="expired", field="token") is value
        clock[0] = 1100
        with pytest.raises(ValidationError):
            public_token_registry.resolve_public_token("values", first, message="expired", field="token")
        assert public_token_registry.resolve_public_token("values", second, message="expired", field="token") is value
        state = public_token_registry._registry()["values"]
        public_token_registry._drop_token(state, second)
        assert not state["by_value"]
        current, _ = public_token_registry.issue_public_token_with_expiry("values", value, key="row", group="facts", ttl_seconds=100)
        assert issuer.issue_with_expiry(value, key="row")[0] == current
        monkeypatch.setattr(public_token_registry, "_MAX_SCOPE_TOKENS", 2)
        public_token_registry.issue_public_token("lru", "old")
        clock[0] += 1
        active = public_token_registry.issue_public_token("lru", "active")
        clock[0] += 1
        public_token_registry.resolve_public_token("lru", active, message="expired", field="token")
        public_token_registry.issue_public_token("lru", "third")
        public_token_registry.issue_public_token("lru", "fourth")
        assert public_token_registry.resolve_public_token("lru", active, message="expired", field="token") == "active"


def test_new_read_times_and_write_subjects_share_one_registered_fact_text(monkeypatch):
    import pytest

    from core.models.workbench_command import WorkbenchCommandRejected
    from web.routes.workbench import read_context, write_context

    app, clock = Flask("canonical-binding-retention"), [1000.0]
    monkeypatch.setattr(public_token_registry.time, "time", lambda: clock[0])
    with app.app_context():
        text = "canonical manufacturing facts " * 1000
        read_tokens, write_tokens = [], []
        for index in range(6):
            copied = ("fresh:" + text)[6:]
            assert copied == text and copied is not text
            read = read_context.bind_read_snapshot({"kind": "batch"}, copied, as_of="2026-10-18T04:00:0" + str(index))
            read_tokens.append(read["snapshot_ref"])
            write_tokens.append(write_context.issue_write_context(str(index), ["save"], copied)["write_token"])
        reads = [read_context.resolve_read_snapshot(token) for token in read_tokens]
        writes = [public_token_registry.resolve_public_token(write_context._SCOPE, token, message="expired", field="token")
                  for token in write_tokens]
        assert len(set(read_tokens)) == len(read_tokens)
        assert all(row.fingerprint is reads[0].fingerprint for row in reads)
        assert all(row.snapshot is writes[0].snapshot for row in writes)
        assert reads[0].fingerprint[1] is writes[0].snapshot[1]
        for index, token in enumerate(write_tokens):
            write_context.validate_write_context(token, str(index), "save", text)
        with pytest.raises(WorkbenchCommandRejected):
            write_context.validate_write_context(write_tokens[0], "0", "save", text + " changed")
        assert read_context.bind_read_snapshot({"kind": "batch"}, text, read_tokens[0])["snapshot_ref"] == read_tokens[0]
        clock[0] = 1451.0
        refreshed = write_context.issue_write_context("0", ["save"], ("fresh:" + text)[6:])["write_token"]
        assert refreshed != write_tokens[0]
        renewed = public_token_registry.resolve_public_token(write_context._SCOPE, refreshed, message="expired", field="token")
        assert renewed.snapshot is writes[0].snapshot
        write_context.validate_write_context(write_tokens[0], "0", "save", text)
        clock[0] = 1900.0
        with pytest.raises(WorkbenchCommandRejected):
            write_context.validate_write_context(write_tokens[0], "0", "save", text)
        write_context.validate_write_context(refreshed, "0", "save", text)


def test_group_binding_uses_canonical_group_under_lock_and_failure_leaves_no_group(monkeypatch):
    import pytest

    app, held = Flask("canonical-binding-lock"), []
    original_lock = public_token_registry._LOCK

    class ObservedLock:
        def __enter__(self):
            original_lock.acquire()
            held.append(True)

        def __exit__(self, *args):
            held.pop()
            original_lock.release()

    monkeypatch.setattr(public_token_registry, "_LOCK", ObservedLock())
    with app.app_context():
        first = public_token_registry.PublicTokenIssuer("bound-lock", group=("facts", "same"))
        old, _ = first.issue_bound_with_expiry(lambda group: group, key="old")
        canonical = public_token_registry.resolve_public_token("bound-lock", old, message="expired", field="token")
        copied = tuple(["facts", "same"])
        assert copied == canonical and copied is not canonical
        second = public_token_registry.PublicTokenIssuer("bound-lock", group=copied)

        def bind(group):
            assert held and group is canonical
            return {"facts": group}

        new, _ = second.issue_bound_with_expiry(bind, key="new")
        assert public_token_registry.resolve_public_token("bound-lock", new, message="expired", field="token")["facts"] is canonical
        failed = public_token_registry.PublicTokenIssuer("bound-failure", group=("facts", "different"))

        def fail(_group):
            raise RuntimeError("binding failed")

        with pytest.raises(RuntimeError, match="binding failed"):
            failed.issue_bound_with_expiry(fail, key="row")
        state = public_token_registry._registry()["bound-failure"]
        assert not state["tokens"] and not state["by_value"]
        recovered, _ = failed.issue_bound_with_expiry(lambda group: group, key="row")
        assert public_token_registry.resolve_public_token("bound-failure", recovered, message="expired", field="token") == ("facts", "different")


@pytest.mark.parametrize("source,label", (("internal", "自制"), ("external", "外协"), ("unknown", "未确认"), (None, "未确认")))
def test_calibration_export_source_labels_are_shared_by_csv_and_xlsx(source, label):
    from core.services.workbench.calibration.export import COLUMNS, _export_values

    row = {key: None for key, _ in COLUMNS}
    row["source"] = source
    source_index = next(index for index, (key, _) in enumerate(COLUMNS) if key == "source")
    for format_name in ("csv", "xlsx"):
        values, = _export_values([row], "{}", format_name)
        assert len(values) == 22 and values[source_index] == label


_CALIBRATION_DUPLICATE = "筛选条件里有重复的列，请重新选择。"


@pytest.mark.parametrize("suffix,query,message", [
    ("/facets/operation_label", {"scope": '{"query": "a", "query": "b"}'}, _CALIBRATION_DUPLICATE),
    ("/facets/operation_label", {"scope": '{"query": NaN}'}, "列筛选内容读不出来，筛选没有变化。请点「清除筛选」后重新选择。"),
    ("/facet-selection/status", {"scope": '{"column_filters": {"part_no": {"mode": "include", "values": [1e999]}}}'},
     "列筛选内容读不出来，筛选没有变化。请点「清除筛选」后重新选择。"),
    ("", {"column_filters": '{"status": {"mode": "include", "values": []}, "status": {"mode": "exclude", "values": []}}'},
     _CALIBRATION_DUPLICATE),
    ("", {"column_filters": '{"status": {"mode": "include", "values": [Infinity]}}'},
     "列筛选内容读不出来，当前筛选没有变化。请点「清除筛选」后重新选择。"),
    ("/export", {"column_filters": '{"status": -Infinity}', "snapshot_ref": "x"},
     "列筛选内容读不出来，当前筛选没有变化。请点「清除筛选」后重新选择。"),
    ("", {"column_filters": '{"status": '}, "列筛选内容读不出来，当前筛选没有变化。请点「清除筛选」后重新选择。"),
])
def test_calibration_query_json_rejects_duplicate_keys_and_nonfinite_numbers_with_route_texts(suffix, query, message):
    app = Flask("calibration-strict-json")
    app.config.update(TESTING=True, SECRET_KEY="temporary-calibration-strict-json")
    bp = Blueprint("calibration_strict_json", __name__)
    register_calibration_routes(bp)
    app.register_blueprint(bp)
    response = app.test_client().get("/api/workbench/v1/calibration" + suffix, query_string=query)
    body = response.get_json()
    assert response.status_code == 400 and body["ok"] is False and body["error"]["code"] == "invalid_input", body
    assert body["error"]["message"] == message
