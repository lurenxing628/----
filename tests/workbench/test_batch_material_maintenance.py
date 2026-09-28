"""Material requirements remain explicit across editing, copying and quantity changes."""

from io import BytesIO

import openpyxl

from tests.workbench.batch_support import BASE, assert_error, batch_database, detail, post, ref_for
from tests.workbench.test_batch_actions import confirm, preview
from tests.workbench.test_batch_files import confirm as confirm_file
from tests.workbench.test_batch_files import uploaded

_batch_fixture = batch_database


def add(client, required=12.375, available=0.04, key="materials-create-request-01"):
    conn = client.batch_conn
    conn.execute("UPDATE Materials SET status='active' WHERE material_id='MAT1'")
    conn.commit()
    return post(client, "materials_update", {"rows": [{"row_key": None, "material_ref": ref_for(client, "material", "MAT1"),
                "required_quantity": required, "available_quantity": available}], "removed_keys": []}, key=key)


def stored(client, code="FREE-001"):
    return [dict(row) for row in client.batch_conn.execute("SELECT * FROM BatchMaterials WHERE batch_id=?", (code,))]


def test_explicit_arrival_precision_replay_stale_and_removal(batch_client):
    client = batch_client
    assert add(client).status_code == 200
    assert [(r['required_qty'], r['available_qty']) for r in stored(client)] == [(12.375, .04)]
    entity = detail(client)['data']
    row = entity['materials']['requirements'][0]
    assert row['row_key'] and row['required_quantity'] == 12.375 and row['available_quantity'] == .04
    payload = {'rows': [{'row_key': row['row_key'], 'material_ref': row['material_ref'],
                        'required_quantity': 12.375, 'available_quantity': 12.375}], 'removed_keys': []}
    token = entity['write_context']
    first = post(client, 'materials_update', payload, context=token, key='materials-ready-request-01')
    assert first.status_code == 200, first.get_json()
    replay = post(client, 'materials_update', payload, context=token, key='materials-ready-request-01')
    assert replay.get_json()['replayed'] is True
    assert detail(client)['data']['fields']['ready_status'] == 'yes'
    assert_error(post(client, 'materials_update', payload, context=token, key='materials-stale-request-01'), 'stale_write')
    # Omission is not deletion; only named row keys remove requirements.
    assert post(client, 'materials_update', {'rows': [], 'removed_keys': []}, key='materials-empty-request-01').status_code == 200
    assert len(stored(client)) == 1
    assert post(client, 'materials_update', {'rows': [], 'removed_keys': [row['row_key']]}, key='materials-remove-request-01').status_code == 200
    assert stored(client) == [] and detail(client)['data']['fields']['ready_status'] == 'no'


def test_copy_preserves_demand_without_inheriting_arrivals_or_readiness(batch_client):
    assert add(batch_client, 5, 5).status_code == 200
    p = preview(batch_client, 'copy')
    assert p['rows'][0]['after']['fields']['ready_status'] == 'no'
    response = confirm(batch_client, p)
    assert response.status_code == 200, response.get_json()
    assert [(r['required_qty'], r['available_qty'], r['ready_status']) for r in stored(batch_client, 'FREE-002')] == [(5, 0, 'no')]
    row = detail(batch_client, ref_for(batch_client, key='FREE-002'))['data']['fields']
    assert row['ready_status'] == 'no' and row['ready_date'] is None


def test_quantity_change_requires_material_review_and_manual_yes_cannot_bypass(batch_client):
    assert add(batch_client, 5, 5).status_code == 200
    assert post(batch_client, 'update', {'fields': {'quantity': 10}}, key='quantity-change-request-01').status_code == 200
    assert detail(batch_client)['data']['fields']['ready_status'] == 'no'
    assert_error(post(batch_client, 'update', {'fields': {'ready_status': 'yes'}}, key='manual-ready-request-01'), 'constraint_conflict')
    assert stored(batch_client)[0]['required_qty'] == 5  # no invented per-piece consumption ratio


def test_sparse_batch_file_changes_due_without_reentering_part_or_quantity(batch_client):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(['批次号', '交期'])
    ws.append(['FREE-001', '2028-03-21'])
    output = BytesIO()
    wb.save(output)
    wb.close()
    result = uploaded(batch_client, [], content=output.getvalue())
    assert result.status_code == 200, result.get_json()
    response = confirm_file(batch_client, result.get_json()['data'])
    assert response.status_code == 200, response.get_json()
    fields = detail(batch_client)['data']['fields']
    assert fields['quantity'] == 5 and fields['due_date'] == '2028-03-21'


def test_operation_choices_mark_wrong_work_type_and_declared_empty_skills(batch_client):
    conn = batch_client.batch_conn
    conn.execute("INSERT INTO OpTypes(op_type_id,name,category) VALUES ('MILL','铣削','internal')")
    conn.execute("INSERT INTO Machines(machine_id,name,op_type_id,status) VALUES ('MILL1','铣床','MILL','active')")
    conn.execute("DELETE FROM OperatorSkill WHERE operator_id='O1'")
    conn.execute("INSERT INTO WorkbenchOperatorProfiles(operator_id,skills_declared) VALUES ('O1',1)")
    conn.commit()
    entity = detail(batch_client)['data']
    result = batch_client.get(BASE + '/choices', query_string={'batch_ref': entity['ref'], 'operation_ref': entity['operations'][0]['ref']})
    assert result.status_code == 200, result.get_json()
    data = result.get_json()['data']
    assert next(row for row in data['machines'] if row['business_code'] == 'MILL1')['eligible'] is False
    assert next(row for row in data['operators'] if row['business_code'] == 'O1')['eligible'] is False


def test_unrelated_invalid_inactive_operator_does_not_block_operation_choices(batch_client):
    conn = batch_client.batch_conn
    conn.execute("INSERT INTO OpTypes(op_type_id,name,category) VALUES ('EXTBAD','外协旧工种','external')")
    conn.execute("INSERT INTO Operators(operator_id,name,status) VALUES ('BAD','错误旧资料','inactive')")
    conn.execute("INSERT INTO OperatorSkill(operator_id,op_type_id) VALUES ('BAD','EXTBAD')")
    conn.commit()
    entity = detail(batch_client)['data']
    response = batch_client.get(BASE + '/choices', query_string={'batch_ref': entity['ref'], 'operation_ref': entity['operations'][0]['ref']})
    assert response.status_code == 200, response.get_json()
    data = response.get_json()['data']
    assert next(row for row in data['operators'] if row['business_code'] == 'BAD')['eligible'] is False
    assert next(row for row in data['machines'] if row['business_code'] == 'M1')['eligible'] is True
