"""Relation paging and qualification use one captured set of database facts."""

from flask import Blueprint, Flask, g

from core.infrastructure.transaction import TransactionManager
from core.services.workbench.resource.queries import WorkbenchResourceQueryService
from data.repositories.operator_qualification_repo import OperatorQualificationRepository
from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository
from tests._support.gantt_current_js import run_current_js
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
    op_type = identity_for(conn, "op_type")
    assert op_type is not None
    path = "/api/workbench/v1/entities/op_type/" + op_type.ref + "/relations"

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

    conn.execute("UPDATE Operators SET name='changed' WHERE operator_id='a-LEGACY'")
    conn.commit()
    stale_sql = []
    conn.set_trace_callback(stale_sql.append)
    stale = get(409, size=2, page=2, snapshot_ref=first["meta"]["snapshot_ref"])
    conn.set_trace_callback(None)
    assert stale["error"]["code"] == "snapshot_stale"
    assert not any("WITH selected AS" in statement or "FROM OperatorSkill" in statement for statement in stale_sql)

    conn.execute("UPDATE OpTypes SET category='both' WHERE op_type_id='OT1'")
    insert_row(conn, "Machines", {"machine_id": " M1 ", "name": "padded-lathe", "op_type_id": "OT1",
                                  "category": "precision", "status": "active"})
    insert_row(conn, "Operators", {"operator_id": " O1 ", "name": "padded-operator", "status": "active"})
    insert_row(conn, "OperatorMachine", {"operator_id": " O1 ", "machine_id": " M1 ",
                                         "skill_level": "expert", "is_primary": "yes"})
    insert_row(conn, "OperatorSkill", {"operator_id": " O1 ", "op_type_id": "OT1",
                                       "skill_level": "normal", "is_primary": "no"})
    insert_row(conn, "Suppliers", {"supplier_id": " S1 ", "name": "padded-supplier",
                                   "default_days": 2.0, "status": "active"})
    for supplier_id in ("S1", " S1 "):
        insert_row(conn, "WorkbenchSupplierOpTypes", {"supplier_id": supplier_id, "op_type_id": "OT1"})
    conn.commit()

    identities = WorkbenchIdentityRepository(conn)
    for relation, kind, padded, plain in (
        ("machines", "machine", " M1 ", "M1"),
        ("operators", "operator", " O1 ", "O1"),
        ("suppliers", "supplier", " S1 ", "S1"),
    ):
        payload = get(relation=relation)
        by_code = {row["business_code"]: row for row in payload["data"]["entities"]}
        assert padded in by_code and plain in by_code
        padded_identity = identities.find_active(kind, padded)
        plain_identity = identities.find_active(kind, plain)
        assert padded_identity is not None and plain_identity is not None
        assert by_code[padded]["ref"] == padded_identity.ref
        assert by_code[plain]["ref"] == plain_identity.ref
        assert by_code[padded]["ref"] != by_code[plain]["ref"]

    assert run_current_js(r"""
const origUseMemo = h.runtime.React.useMemo, origUseQuery = h.runtime.APSResourceSession.useQuery, slots = [];
let cursor = 0, originalReads = 0, entityMapCalls = 0;
const same = (a, b) => a && b && a.length === b.length && a.every((v, i) => v === b[i]);
h.runtime.React.useMemo = (fn, deps) => {
  const i = cursor++;
  if (!slots[i] || !same(slots[i].deps, deps)) slots[i] = { deps, value: fn() };
  return slots[i].value;
};
const refA = h.reference(1), refB = h.reference(2), missingRef = h.reference(3);
const entities = [
  { ref: refA, label: '车削', status: null, fields: { category: 'internal' } },
  { ref: refB, label: '铣削', status: null, fields: { category: 'both' } }
];
entities.map = function (...args) { entityMapCalls++; return Array.prototype.map.apply(this, args); };
const response = { meta: { snapshot_ref: h.reference(9) }, data: { entities, page: { number: 1, pages: 1, total: 2, size: 50 } } };
h.runtime.APSResourceSession.useQuery = () => ({ result: response, loading: false, error: null, reload() {} });
const original = {
  relationships: {
    skill_refs: [refA, missingRef],
    get skills() { originalReads++; return [{ ref: refA, label: '车削' }, { ref: missingRef, label: '原关联工种' }]; }
  }
};
const props = {
  adapter: {},
  field: { key: 'skill_refs', label: '可做工种', kind: 'op_type', category: 'internal', multiple: true },
  value: [refA, missingRef],
  original,
  onChange() {}
};
try {
  const knownState = {};
  cursor = 0;
  h.render(h.runtime.ResourceControls.Choice, props, { Choice: { 0: '', 4: knownState } });
  const readsBefore = originalReads, mapsBefore = entityMapCalls;
  for (const text of ['车', '车削', '车削精']) {
    cursor = 0;
    h.render(h.runtime.ResourceControls.Choice, props, { Choice: { 0: text, 4: knownState } });
  }
  assert.strictEqual(originalReads - readsBefore, 0, 'Choice search typing must not rebuild originalByRef');
  assert.strictEqual(entityMapCalls - mapsBefore, 0, 'Choice search typing must not rebuild options from response entities');
} finally {
  h.runtime.React.useMemo = origUseMemo;
  h.runtime.APSResourceSession.useQuery = origUseQuery;
}
return true;
""")["result"] is True


def test_padded_existing_resources_can_update_select_relations_and_delete_by_ref(resource_conn):
    conn = resource_conn
    insert_row(conn, "WorkbenchMachineGroups", {"group_id": "G1", "name": "group-plain", "status": "active", "remark": "g1-note"})
    insert_row(conn, "WorkbenchShiftProfiles", {
        "profile_id": "SP1", "name": "shift-plain", "anchor_date": "2026-09-09",
        "cycle_days": 1, "status": "active", "remark": "sp1-note",
    })
    insert_row(conn, "WorkbenchShiftPatternDays", {
        "profile_id": "SP1", "day_offset": 0, "is_rest": 0, "shift_start": "08:00", "shift_end": "16:00",
    })
    insert_row(conn, "OpTypes", {"op_type_id": "OT_INT", "name": "ot-int-plain", "category": "internal", "remark": "ot-int-note"})
    insert_row(conn, "OpTypes", {"op_type_id": "OT_EXT", "name": "ot-ext-plain", "category": "external", "remark": "ot-ext-note"})

    insert_row(conn, "WorkbenchMachineGroups", {"group_id": " G1 ", "name": "group-padded", "status": "active", "remark": "g1-pad"})
    insert_row(conn, "WorkbenchShiftProfiles", {
        "profile_id": " SP1 ", "name": "shift-padded", "anchor_date": "2026-09-09",
        "cycle_days": 1, "status": "active", "remark": "sp1-pad",
    })
    insert_row(conn, "WorkbenchShiftPatternDays", {
        "profile_id": " SP1 ", "day_offset": 0, "is_rest": 0, "shift_start": "08:00", "shift_end": "16:00",
    })
    insert_row(conn, "OpTypes", {"op_type_id": " OT1 ", "name": "ot1-padded", "category": "both", "remark": "ot1-pad"})
    insert_row(conn, "OpTypes", {"op_type_id": " OT_INT ", "name": "ot-int-padded", "category": "internal", "remark": "ot-int-pad"})
    insert_row(conn, "OpTypes", {"op_type_id": " OT_EXT ", "name": "ot-ext-padded", "category": "external", "remark": "ot-ext-pad"})
    insert_row(conn, "Machines", {"machine_id": " M1 ", "name": "machine-padded", "category": "general", "status": "active", "remark": "m1-pad"})
    insert_row(conn, "Operators", {"operator_id": " O1 ", "name": "operator-padded", "status": "active", "remark": "o1-pad"})
    insert_row(conn, "Suppliers", {"supplier_id": " S1 ", "name": "supplier-padded", "default_days": 2.0, "status": "active", "remark": "s1-pad"})
    conn.commit()

    identities = WorkbenchIdentityRepository(conn)
    sibling_specs = (
        ("machine_group", "WorkbenchMachineGroups", "group_id", "G1"),
        ("shift_profile", "WorkbenchShiftProfiles", "profile_id", "SP1"),
        ("op_type", "OpTypes", "op_type_id", "OT1"),
        ("op_type", "OpTypes", "op_type_id", "OT_INT"),
        ("op_type", "OpTypes", "op_type_id", "OT_EXT"),
        ("machine", "Machines", "machine_id", "M1"),
        ("operator", "Operators", "operator_id", "O1"),
        ("supplier", "Suppliers", "supplier_id", "S1"),
    )

    def capture_siblings():
        return {
            (kind, code): (
                dict(conn.execute(f'SELECT * FROM "{table}" WHERE "{key}"=?', (code,)).fetchone()),
                identities.find_active(kind, code),
            )
            for kind, table, key, code in sibling_specs
        }

    siblings_before = capture_siblings()
    g1_pad = identities.find_active("machine_group", " G1 ")
    sp1_pad = identities.find_active("shift_profile", " SP1 ")
    ot1_pad = identities.find_active("op_type", " OT1 ")
    ot_int_pad = identities.find_active("op_type", " OT_INT ")
    ot_ext_pad = identities.find_active("op_type", " OT_EXT ")
    m1_pad = identities.find_active("machine", " M1 ")
    o1_pad = identities.find_active("operator", " O1 ")
    s1_pad = identities.find_active("supplier", " S1 ")
    assert (
        g1_pad is not None
        and sp1_pad is not None
        and ot1_pad is not None
        and ot_int_pad is not None
        and ot_ext_pad is not None
        and m1_pad is not None
        and o1_pad is not None
        and s1_pad is not None
    )

    def execute_by_ref(kind, ref, action, payload):
        reader = WorkbenchResourceQueryService(conn, kind)
        normalized = reader.domain.normalize_input(action, payload)
        with TransactionManager(conn).transaction():
            preparation = reader.preparation_for(action, normalized, ref=ref)
            identity = preparation.identity(kind, ref)
            checked = preparation.state(kind, preparation.current(kind, identity).entity_key)
            change = reader.domain.prepare(action, normalized, checked, preparation)
            outcome = reader.domain.apply_prepared(change)
        assert outcome.result == "committed"
        return outcome

    # 6. 按永久 ref 更新带首尾空格的 op_type（名称/备注/合并规则）
    out_ot = execute_by_ref(
        "op_type",
        ot1_pad.ref,
        "update",
        {"label": "ot1-padded-v2", "fields": {"remark": "ot1-pad-v2", "default_merge_mode": "merged"}},
    )
    assert out_ot.data == {"entity_ref": ot1_pad.ref, "business_code": " OT1 "}
    ot1_row = dict(conn.execute("SELECT name, remark FROM OpTypes WHERE op_type_id=' OT1 '").fetchone())
    assert ot1_row == {"name": "ot1-padded-v2", "remark": "ot1-pad-v2"}
    assert conn.execute(
        "SELECT default_merge_mode FROM WorkbenchOpTypePolicies WHERE op_type_id=' OT1 '"
    ).fetchone()[0] == "merged"

    # 1, 2, 7. machine 关联选择带首尾空格的 machine_group (" G1 ") 与自制 op_type (" OT_INT ")，并按 ref 更新 machine（名称/状态/关联）
    out_m = execute_by_ref(
        "machine",
        m1_pad.ref,
        "update",
        {
            "label": "machine-padded-v2",
            "fields": {"status": "maintain", "remark": "m1-pad-v2"},
            "relationships": {"group_ref": g1_pad.ref, "op_type_refs": [ot_int_pad.ref]},
        },
    )
    assert out_m.data == {"entity_ref": m1_pad.ref, "business_code": " M1 "}
    m1_row = dict(conn.execute("SELECT name, status, remark, op_type_id FROM Machines WHERE machine_id=' M1 '").fetchone())
    assert m1_row == {"name": "machine-padded-v2", "status": "maintain", "remark": "m1-pad-v2", "op_type_id": " OT_INT "}
    assert conn.execute(
        "SELECT group_id FROM WorkbenchMachineGroupMembers WHERE machine_id=' M1 '"
    ).fetchone()[0] == " G1 "

    # 3, 4, 8. operator 关联选择带首尾空格的 shift_profile (" SP1 ") 与自制 op_type (" OT_INT ")，并按 ref 更新 operator（名称/状态/关联）
    out_o = execute_by_ref(
        "operator",
        o1_pad.ref,
        "update",
        {
            "label": "operator-padded-v2",
            "fields": {"status": "leave", "remark": "o1-pad-v2"},
            "relationships": {"shift_profile_ref": sp1_pad.ref, "skill_refs": [ot_int_pad.ref]},
        },
    )
    assert out_o.data == {"entity_ref": o1_pad.ref, "business_code": " O1 "}
    o1_row = dict(conn.execute("SELECT name, status, remark FROM Operators WHERE operator_id=' O1 '").fetchone())
    assert o1_row == {"name": "operator-padded-v2", "status": "inactive", "remark": "o1-pad-v2"}
    o1_prof = dict(conn.execute(
        "SELECT shift_profile_id, skills_declared, inactive_reason FROM WorkbenchOperatorProfiles WHERE operator_id=' O1 '"
    ).fetchone())
    assert o1_prof == {"shift_profile_id": " SP1 ", "skills_declared": 1, "inactive_reason": "leave"}
    assert [
        row[0] for row in conn.execute("SELECT op_type_id FROM OperatorSkill WHERE operator_id=' O1 '")
    ] == [" OT_INT "]

    # 5, 9. supplier 关联选择带首尾空格的外协 op_type (" OT_EXT ")，并按 ref 更新 supplier（名称/默认周期/状态/关联）
    out_s = execute_by_ref(
        "supplier",
        s1_pad.ref,
        "update",
        {
            "label": "supplier-padded-v2",
            "fields": {"default_days": 5.5, "status": "pending_review", "remark": "s1-pad-v2"},
            "relationships": {"op_type_refs": [ot_ext_pad.ref]},
        },
    )
    assert out_s.data == {"entity_ref": s1_pad.ref, "business_code": " S1 "}
    s1_row = dict(conn.execute("SELECT name, default_days, status, remark FROM Suppliers WHERE supplier_id=' S1 '").fetchone())
    assert s1_row == {"name": "supplier-padded-v2", "default_days": 5.5, "status": "inactive", "remark": "s1-pad-v2"}
    assert conn.execute(
        "SELECT inactive_reason FROM WorkbenchSupplierProfiles WHERE supplier_id=' S1 '"
    ).fetchone()[0] == "pending_review"
    assert [
        row[0] for row in conn.execute("SELECT op_type_id FROM WorkbenchSupplierOpTypes WHERE supplier_id=' S1 '")
    ] == [" OT_EXT "]

    # 解除关联后按永久 ref 删除带首尾空格的 machine / operator / supplier / op_type（10, 11, 12, 13）
    execute_by_ref("machine", m1_pad.ref, "update", {"relationships": {"group_ref": None, "op_type_refs": []}})
    execute_by_ref("operator", o1_pad.ref, "update", {"relationships": {"shift_profile_ref": None, "skill_refs": []}})
    execute_by_ref("supplier", s1_pad.ref, "update", {"relationships": {"op_type_refs": []}})

    for kind, ref, code, table, key in (
        ("machine", m1_pad.ref, " M1 ", "Machines", "machine_id"),
        ("operator", o1_pad.ref, " O1 ", "Operators", "operator_id"),
        ("supplier", s1_pad.ref, " S1 ", "Suppliers", "supplier_id"),
        ("op_type", ot1_pad.ref, " OT1 ", "OpTypes", "op_type_id"),
        ("op_type", ot_int_pad.ref, " OT_INT ", "OpTypes", "op_type_id"),
        ("op_type", ot_ext_pad.ref, " OT_EXT ", "OpTypes", "op_type_id"),
    ):
        deleted = execute_by_ref(kind, ref, "delete", {})
        assert deleted.data == {"entity_ref": ref, "business_code": code}
        assert conn.execute(f'SELECT 1 FROM "{table}" WHERE "{key}"=?', (code,)).fetchone() is None
        assert identities.find_active(kind, code) is None

    assert capture_siblings() == siblings_before
