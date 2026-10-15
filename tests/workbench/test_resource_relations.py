"""Relation paging and qualification use one captured set of database facts."""

from flask import Blueprint, Flask, g

from data.repositories.operator_qualification_repo import OperatorQualificationRepository
from tests.workbench.identity_metadata_support import insert_row
from tests.workbench.resource_entity_support import identity_for, resource_database  # noqa: F401
from web.routes.workbench.resource_relations import register_resource_relation_routes


def test_relation_pages_reuse_captured_facts_and_keep_search_and_errors(resource_conn, monkeypatch):
    conn = resource_conn
    for code, label in (("a-LEGACY", "Alpha"), ("B-EMPTY", "Ä中文"), ("c-MISMATCH", "äother")):
        insert_row(conn, "Operators", {"operator_id": code, "name": label})
        insert_row(conn, "OperatorMachine", {"operator_id": code, "machine_id": "M1"})
    for code in ("B-EMPTY", "c-MISMATCH"):
        insert_row(conn, "WorkbenchOperatorProfiles", {"operator_id": code, "skills_declared": 1})
    insert_row(conn, "OperatorSkill", {"operator_id": "c-MISMATCH", "op_type_id": "OT2"})
    conn.commit()

    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY="resource-relation-fixture")
    bp = Blueprint("workbench", __name__)
    register_resource_relation_routes(bp)
    app.register_blueprint(bp)

    @app.before_request
    def isolated_connection():
        g.db = conn

    client = app.test_client()
    path = "/api/workbench/v1/entities/op_type/" + identity_for(conn, "op_type").ref + "/relations"

    def get(status=200, **query):
        response = client.get(path, query_string={"relation": "operators", **query})
        assert response.status_code == status, response.get_json()
        assert response.headers["Cache-Control"] == "no-store"
        return response.get_json()

    def unexpected_reread(*args, **kwargs):
        raise AssertionError("qualification facts were already captured by the relation snapshot")

    monkeypatch.setattr(OperatorQualificationRepository, "read_skill_facts", unexpected_reread)
    sql = []
    conn.set_trace_callback(sql.append)
    first = get(size=2)
    conn.set_trace_callback(None)
    assert sum("WITH selected AS" in statement for statement in sql) == 1
    assert not any("SELECT COUNT(*) FROM (" in statement or "SELECT business_code FROM (" in statement for statement in sql)
    assert sum("FROM OperatorSkill AS s" in statement for statement in sql) == 1
    assert not any("FROM Operators AS o" in statement for statement in sql)
    assert first["data"]["page"] == {"number": 1, "size": 2, "total": 4, "pages": 2,
                                      "sort": [{"field": "business_code", "direction": "asc"}]}
    assert [row["business_code"] for row in first["data"]["entities"]] == ["B-EMPTY", "O1"]
    assert [row["fields"]["qualification_basis"] for row in first["data"]["entities"]] == ["explicit_empty", "explicit_match"]
    second = get(size=2, page=2, snapshot_ref=first["meta"]["snapshot_ref"])
    assert [row["business_code"] for row in second["data"]["entities"]] == ["a-LEGACY", "c-MISMATCH"]
    assert [row["fields"]["qualification_basis"] for row in second["data"]["entities"]] == ["legacy_fallback", "explicit_mismatch"]

    for text, expected in (("ALPHA", ["a-LEGACY"]), ("b-empty", ["B-EMPTY"]), ("Ä", ["B-EMPTY"]),
                           ("ä", ["c-MISMATCH"]), ("中文", ["B-EMPTY"]), ("unmatched", [])):
        result = get(query=text)
        assert [row["business_code"] for row in result["data"]["entities"]] == expected
        assert result["data"]["page"]["total"] == len(expected)

    conn.execute("UPDATE Operators SET name=? WHERE operator_id='a-LEGACY'", (b"Alpha",))
    conn.commit()
    assert conn.execute("SELECT instr(lower(name),lower('unmatched')) FROM Operators WHERE operator_id='a-LEGACY'").fetchone()[0] == 0
    assert get(query="unmatched")["data"]["entities"] == []
    conn.execute("UPDATE Operators SET name='changed' WHERE operator_id='a-LEGACY'")
    conn.commit()
    stale = get(409, size=2, page=2, snapshot_ref=first["meta"]["snapshot_ref"])
    assert stale["error"]["code"] == "snapshot_stale"
    conn.execute("UPDATE OpTypes SET category='external' WHERE op_type_id='OT2'")
    conn.commit()
    invalid = get(500, query="unmatched")
    assert invalid["error"]["code"] == "storage_failure"
    assert invalid["error"]["message"] == "人员资格资料读不出来。请到资料总览核对后重试。"
    conn.execute("UPDATE OpTypes SET category='internal' WHERE op_type_id='OT2'")
    conn.commit()
    conn.execute("PRAGMA foreign_keys=OFF")
    insert_row(conn, "OperatorSkill", {"operator_id": "ORPHAN", "op_type_id": "OT1"})
    conn.commit()
    conn.execute("PRAGMA foreign_keys=ON")
    missing = get(500, query="unmatched")
    assert missing["error"]["code"] == "storage_failure"
    assert missing["error"]["message"].startswith("关联指向的资源已经不存在")
