"""Resource eligibility for the operation being edited, matching the write guards."""

from core.models.resource_capabilities import machine_type_index
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.personnel.operator_qualification import OperatorQualificationError, OperatorQualificationService
from data.repositories.supplier_repo import SupplierRepository


def operation_choices(reader, batch_ref, operation_ref, choices):
    batch, facts = reader.batch(batch_ref), reader.load()
    op = next((row for row in facts['BatchOperations'] if row['batch_id'] == batch['batch_id']
               and facts['operation_refs'][row['id']] == operation_ref), None)
    if op is None:
        raise WorkbenchCommandRejected('entity_not_found', '这道工序已失效或不属于当前批次，请刷新后重新选择。', 404)
    machines = machine_type_index(facts['Machines'], facts.get('MachineOpTypes', []))
    skills, skill_errors = ({}, {})
    if op['source'] == 'internal':
        skills, skill_errors = _skills(reader, [row['operator_id'] for row in facts['Operators'] if row['status'] == 'active'])
    suppliers = {(row['supplier_id'], row['op_type_id']) for row in SupplierRepository(reader.conn).list_capabilities(status='active')
                 if not row['missing_supplier']} if op['source'] == 'external' else set()
    for kind, name in (('machine', 'machines'), ('operator', 'operators'), ('supplier', 'suppliers')):
        for row in choices[name]:
            reason = _reason(kind, row, op, machines, skills, skill_errors, suppliers)
            row['eligible'] = not reason
            row['unavailable_reason'] = reason
    return choices


def _skills(reader, codes):
    service = OperatorQualificationService(reader.conn)
    try:
        return service.load(codes), {}
    except OperatorQualificationError:
        # Isolate invalid candidate records without treating their missing facts as eligibility.
        good, bad = {}, {}
        for code in codes:
            try:
                good.update(service.load([code]))
            except OperatorQualificationError as exc:
                bad[code] = str(exc)
        return good, bad


def _reason(kind, row, op, machines, skills, errors, suppliers):
    code = row['business_code']
    if row['status'] != 'active':
        return '当前不可用'
    if (kind == 'supplier') != (op['source'] == 'external'):
        return '不适用于此工序归属'
    if kind == 'operator':
        if code in errors:
            return '资格资料异常：' + errors[code]
        capable = skills[code] is None or op['op_type_id'] in skills[code]
    else:
        capable = (op['op_type_id'] in machines[code] if kind == 'machine'
                   else (code, op['op_type_id']) in suppliers)
    return '' if capable else '未具备该工序工种能力'
