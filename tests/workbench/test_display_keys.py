"""Display identities preserve exact values, file positions and saved read state."""

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.models.workbench_calibration import normalize_calibration_filters
from core.models.workbench_master_overview import MasterOverviewScope
from core.models.workbench_process_table_query import normalize_process_column_filters
from core.models.workbench_resource_table_query import normalize_column_filters
from core.services.system import runtime_log_reader
from core.services.workbench.facts.system_reads import _runtime_rows, backup_records
from core.services.workbench.facts.table_cells import number_cell, relation_cell, text_cell
from core.services.workbench.facts.table_index import ResourceTableIndex
from core.services.workbench.master.overview import MasterOverviewService
from core.services.workbench.master.overview_graph import MasterOverviewGraph
from core.services.workbench.system.maintenance_records import _event
from core.shared.strict_json import canonical_json
from tests.workbench.node_runtime_support import node_runtime

ROOT = Path(__file__).resolve().parents[2]


def browser(data, program):
    bootstrap = r"""
const assert=require('node:assert/strict'), fs=require('node:fs'), path=require('node:path'), vm=require('node:vm');
const data=JSON.parse(fs.readFileSync(0,'utf8')), window={ResourceControls:{},MasterOverviewTable:{}}, React={};
const plain=value=>JSON.parse(JSON.stringify(value)), app='frontend/workbench/app/';
for(const file of ['transport.js','resource-contract.js','ResourceTableFilterModel.js','ProcessContract.js','ProcessReadView.js',
  'CalibrationAPI.js','MasterOverviewContract.js','SystemMaintenanceAPI.js'])
  vm.runInNewContext(fs.readFileSync(app+file,'utf8'),{window,React});
const {compile}=require('./scripts/workbench/compile.cjs');
const jsx=['ResourceWorkspace.jsx','MasterOverviewWorkspace.jsx'];
for(const file of compile({babel_path:path.resolve('frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'),
  sources:jsx.map(name=>({path:name,code:fs.readFileSync(app+name,'utf8')}))}).outputs)
  vm.runInNewContext(file.code,{window,React});
const raw=data=>({ok:true,schema_version:1,meta:{source:'production',time_basis:'factory_local',snapshot_ref:'snapshot',
  request_ref:'request',as_of:'2026-10-13T08:00:00'},warnings:[],data});
"""
    result = subprocess.run([node_runtime(), "-e", bootstrap + program], input=json.dumps(data),
                            text=True, capture_output=True, cwd=str(ROOT), timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


def test_exact_issue_and_cell_keys_filter_and_restore_the_same_business_values():
    ref, operation = "b" * 48, "c" * 48
    graph = MasterOverviewGraph(SimpleNamespace(ref=lambda *_: ref))
    entity = graph.add("part", "P1", "P1", "Part")
    issue = graph.issue(entity, "hours.missing", "缺工时", "没有工时", operation_ref=operation)
    assert graph.issue(entity, "hours.missing", "同一项", "补充说明", operation_ref=operation) is issue
    graph.issue(entity, "hours.missing", "相关项", "关联不同", operation_ref=operation, related_ref="d" * 48)
    assert json.loads(issue["issue_ref"]) == [entity["key"], "hours.missing", operation, None, None]
    assert len(graph._issue_index) == 2 and all(isinstance(key, tuple) for key in graph._issue_index)
    service = MasterOverviewService(None)
    service.graph, service.entities = graph, graph.finalize()
    service.entity_by_key = {(row["domain"], row["ref"]): row for row in service.entities}
    service.facts = SimpleNamespace(available=lambda *_: True, gaps=[])
    service.issues = [{**row, "issue_count": entity["issue_count"], "relation_count": entity["relation_count"]}
                      for row in entity["issues"]]
    master = service.page(MasterOverviewScope())

    cell = text_cell("  e\u0301 \t A  ")
    assert cell.key == text_cell("é A").key == canonical_json({"type": "text", "value": "é A"})
    assert number_cell(7.0, " 小时 ").key == number_cell(7, "小时").key
    assert number_cell(7, "小时").key != number_cell(7, "件").key
    assert relation_cell([" B ", "A"]).key == relation_cell(["A", "B"]).key
    assert text_cell(None).key != text_cell("").key != number_cell(None).key
    cells = {"first": {"label": cell}, "second": {"label": text_cell("other")}}
    index = ResourceTableIndex({key: {"code": key} for key in cells}, cells)
    condition = {"label": {"mode": "include", "values": [cell.key]}}
    filters = normalize_column_filters(condition, "machine")
    query = SimpleNamespace(kind="machine", category=None, column_filters=filters, sort="label", direction="asc")
    assert index.matching_keys(query) == ["first"]
    query.column_filters = normalize_process_column_filters({"label": {"mode": "exclude", "values": [cell.key]}})
    assert index.matching_keys(query) == ["second"]
    assert normalize_calibration_filters({"part_no": condition["label"]})["part_no"]["values"] == [cell.key]
    browser({"master": master, "facets": index.facets(query, "label", size=2),
             "selection": index.facet_selection(query, "label", size=2), "key": cell.key, "ref": ref}, r"""
const C=window.APSMasterOverviewContract, M=window.ResourceTableFilterModel, ref=data.ref, fresh=data.key;
C.list(raw(data.master), data.master.scope);
const broken=plain(data.master); broken.rows[0].entity_ref='display-only'; assert.throws(()=>C.list(raw(broken)));
M.facets(raw(data.facets),{column:'label',page:1,size:2});
M.selection(raw(data.selection),{column:'label',expected_total:data.selection.total});
const filters={spec:{mode:'exclude',values:[fresh]}}, label={mode:'include',values:[fresh]};
assert.deepEqual(plain(M.rules({spec:{mode:'exclude',values:[fresh,fresh]},label})),{label,spec:filters.spec});
assert.throws(()=>M.rule({mode:'include',values:['']}));
const resourceView={scope:{query:'保留范围',status:'active',page:3,size:20,sort:'business_code',direction:'asc',column_filters:filters},
  selected_refs:[ref],sort_active:true,detail:null};
const resource=window.ResourceWorkspace.navigation({source:'production',kind:'material',read_view:resourceView});
assert(!resource.error); assert.equal(resource.context.read_view.scope.page,3);
assert.deepEqual(plain(resource.context.read_view.scope.column_filters),filters);
assert.deepEqual(plain(resource.context.read_view.selected_refs),[ref]); assert.equal(resource.context.read_view.scope.query,'保留范围');
const processView={scope:{query:'保留工艺',page:5,size:20,sort:[],stage:'route',column_filters:{label}},selected_refs:[ref],entity_ref:ref};
const process=window.ResourceWorkspace.navigation({source:'production',kind:'part',read_view:processView});
assert(!process.error); assert.equal(process.context.read_view.scope.page,5);
assert.deepEqual(plain(process.context.read_view.selected_refs),[ref]); assert.equal(process.context.read_view.entity_ref,ref);
const calibration=window.CalibrationAPI.initial({scope:{query:'保留校准',part_ref:ref,column_filters:{part_no:label}},
  table:{page:4,size:20,sort:'part_no',direction:'asc'},selected:ref});
assert.equal(calibration.page,4); assert.equal(calibration.part_ref,ref);
assert.deepEqual(plain(calibration.column_filters),{part_no:label});
const saved={scope:plain(C.scope({view:'issues',domain:'part',query:'保留资料'})),page:6,detail_page:3,section:'relations',
  selected:{domain:'part',entity_ref:ref,issue_ref:'e'.repeat(48)}};
const restored=window.MasterOverviewWorkspace.readContext({read_view:saved});
assert.deepEqual(plain(restored.selected),saved.selected); assert.equal(restored.page,6);
assert.equal(restored.detailPage,3); assert.deepEqual(plain(restored.scope),saved.scope);
const current=window.MasterOverviewWorkspace.readContext({read_view:{...saved,selected:{...saved.selected,issue_ref:data.master.rows[0].issue_ref}}});
assert.equal(current.selected.entity_ref,ref); assert.equal(current.selected.issue_ref,data.master.rows[0].issue_ref);
const empty=window.MasterOverviewWorkspace.readContext({read_view:{...saved,selected:null}});
assert.equal(empty.selected,null);
""")


def test_runtime_file_origins_distinguish_duplicates_and_survive_append_and_truncation(tmp_path, monkeypatch):
    path = tmp_path / "aps.log"
    prefix = "前言\n".encode()
    entry = "2026-10-13 08:00:00 [INFO] 同一行\n正文\n".encode()
    path.write_bytes(prefix + entry + entry)
    public = runtime_log_reader.read_log_entries_tail(str(path))
    assert all(set(row) == {"head", "body", "level"} for row in public)
    origins = runtime_log_reader.read_log_entries_tail(str(path), include_origin=True)
    assert [row["_origin"]["offset"] for row in origins] == [len(prefix) + len(entry), len(prefix), 0]
    before, _ = _runtime_rows(str(tmp_path), path.name)
    assert len({row["key"] for row in before}) == 3
    with path.open("ab") as stream:
        stream.write(entry)
    after, _ = _runtime_rows(str(tmp_path), path.name)
    assert [row["key"] for row in after[1:]] == [row["key"] for row in before]
    assert all("_origin" not in row and "offset" not in row for row in after)
    assert json.loads(after[0]["key"])[2]["offset"] == len(prefix) + 2 * len(entry)
    monkeypatch.setattr(runtime_log_reader, "TAIL_BLOCK_SIZE", 64)
    monkeypatch.setattr(runtime_log_reader, "MAX_ENTRY_BYTES", 128)
    long_entry = entry + ("长正文" * 200).encode("utf-8") + b"\n"
    path.write_bytes(prefix + long_entry + entry)
    truncated = runtime_log_reader.read_log_entries_tail(str(path), include_origin=True)
    assert truncated[0]["_origin"]["offset"] == len(prefix) + len(long_entry)
    assert truncated[1]["_origin"]["offset"] == len(prefix)
    assert runtime_log_reader.TRUNCATION_MARKER in truncated[1]["body"]
    assert truncated[-1]["_origin"]["offset"] == 0
    monkeypatch.setattr(runtime_log_reader, "ENTRY_HUNT_BUDGET_BYTES", 256)
    path.write_bytes(b"x" * 1000)
    unanchored = runtime_log_reader.read_log_entries_tail(str(path), include_origin=True)
    assert unanchored[0]["head"] == runtime_log_reader.NO_ANCHOR_HEAD
    assert unanchored[0]["_origin"]["offset"] == 1000 - 128 // 2


def test_system_display_keys_use_file_metadata_and_event_identity_and_restore_saved_selection(tmp_path):
    path = tmp_path / "aps_backup_manual.db"
    path.write_bytes(b"metadata-only")
    before, issues = backup_records(str(tmp_path))
    assert not issues and len(before) == 1
    key = json.loads(before[0]["key"])
    assert key == ["backup_file", path.name, before[0]["_signature"]]
    assert backup_records(str(tmp_path))[0][0]["key"] == before[0]["key"]
    path.write_bytes(b"metadata-changed")
    assert backup_records(str(tmp_path))[0][0]["key"] != before[0]["key"]
    event = _event("cleanup", "operation_audit", 7, "2026-10-13T08:00:00", "succeeded", "清理", {"count": 1})
    changed = _event("cleanup", "operation_audit", 7, "2026-10-13T09:00:00", "failed", "清理", {"error": "changed"})
    assert event["key"] == changed["key"] == canonical_json(["operation_audit", "7"])
    assert _event("cleanup", "latest_job_state_only", 7, None, "unknown", "最近状态", {})["key"] != event["key"]
    file = {name: value for name, value in before[0].items() if not name.startswith("_")}
    file.update(record_kind="backup_file", backup_ref="fixture-backup", write_context={"write_token": "fixture-write"})
    browser({"file": file, "event": event}, r"""
const A=window.SystemMaintenanceAPI, rows=[data.file,data.event], filters={query:'保留',file:'aps.log'};
A.collection(raw({rows,page:{number:1,size:10,total:2,pages:1},sources:[],scope:'backup-files-and-maintenance-events',
  capabilities:{create:true,delete:true,restore:false,blocked_reason:'',restore_reason:'预检'},create_context:{write_token:'create'}}),'backups');
for(const kind of ['logs','backups']) {
  const saved={filters,page:3,selection:{key:data.file.key,...(kind==='backups'?{record_kind:'backup_file'}:{})}};
  const result=A.pageContext({tab:kind,records:{[kind]:saved}}).records[kind];
  assert.deepEqual(plain(result.selection),saved.selection); assert.equal(result.page,3);
  assert.equal(result.filters.query,'保留'); assert.equal(result.filters.file,'aps.log');
}
// The only writer (SystemMaintenanceRecords) saves { key, record_kind }; a selection carrying anything else is refused.
assert.throws(()=>A.recordContext({filters,page:3,selection:{key:data.file.key,record_kind:'backup_file',backup_ref:'old-token'}},'backups'),/失效/);
const selected=A.recordContext({filters,page:3,selection:{key:data.file.key,record_kind:'backup_file'}},'backups');
assert.equal(selected.selection.key,data.file.key);
""")


@pytest.mark.parametrize("damaged", ("part_name", "shift_name"))
def test_overview_labels_and_evidence_show_non_text_names_without_concatenating_raw_values(schema_conn, damaged):
    from tests.workbench.identity_metadata_support import seed_resources

    conn = schema_conn
    seed_resources(conn)
    blob = b"\x01"
    conn.execute("UPDATE Parts SET part_name=? WHERE part_no='P1'", (blob if damaged == "part_name" else "part",))
    conn.execute("INSERT INTO WorkbenchShiftProfiles(profile_id,name,cycle_days,anchor_date,status) VALUES ('SP-BLOB',?,1,'2026-09-01','inactive')",
                 (blob if damaged == "shift_name" else "night",))
    conn.execute("INSERT INTO WorkbenchOperatorProfiles(operator_id,shift_profile_id) VALUES ('O1','SP-BLOB')")
    conn.commit()
    overview = MasterOverviewService(conn)
    with overview.read_snapshot():
        route = next(row for row in overview.entities if row["domain"] == "route" and row["business_code"] == "P1")
        person = next(row for row in overview.entities if row["domain"] == "personnel" and row["business_code"] == "O1")
    shift = next(row["evidence"] for row in person["issues"] if row["rule"] == "shift.inactive")
    # 名称不是有效文本时路线回退用图号；班次名照资料总览的显示规则转成可读文本。
    assert route["label"] == ("P1" if damaged == "part_name" else "part") + " · 工艺路线"
    assert shift.startswith("所在班次是" + ('{"hex": "01", "storage_type": "blob"}' if damaged == "shift_name" else "night") + "，")
