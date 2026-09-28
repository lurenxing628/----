"""Frozen input seams: accessing an active template is a test failure."""

from types import SimpleNamespace

from core.services.scheduler.contracts.external_context import context_group_key


def snapshot(**updates):
    row = dict(operation_id=2, part_no="P001", sequence=20, template_operation_id=1,
               template_status="active", group_id=None, group_part_no=None,
               start_sequence=None, end_sequence=None, merge_mode=None, total_days=None,
               supplier_id=None, group_ref=None, template_operation_ref="c" * 48,
               origin="template_copy", captured_at="2026-09-28 12:00:00")
    row.update(updates)
    return row


def merged_snapshot(**updates):
    row = snapshot(group_id="G001", group_ref="a" * 48, group_part_no="P001",
                   start_sequence=20, end_sequence=20, merge_mode="merged", total_days=4)
    row.update(updates)
    return row


class NoLiveRepository:
    def get(self, *args):
        raise AssertionError("A batch must never query an active template: " + repr(args))


class SnapshotService:
    def __init__(self, row):
        self.part_op_repo = self.group_repo = NoLiveRepository()
        self._aps_schedule_input_cache = {"external_contexts": {row["operation_id"]: row} if row else {}}
        valid_key = row and isinstance(row.get("total_days"), (int, float)) and row.get("group_ref")
        self._aps_schedule_input_cache["external_members"] = ({("B001", context_group_key(row), None):
            {"supplier_id": "SUP01", "problem": None}} if valid_key else {})
        self._aps_schedule_input_cache["external_contexts_bound"] = True
        self.batch_calls = []

    def _get_batch_or_raise(self, batch_id):
        self.batch_calls.append(batch_id)
        return SimpleNamespace(batch_id=batch_id, part_no="P001")


def external_operation(**updates):
    row = dict(id=2, op_code="OP_EXT_01", batch_id="B001", seq=20, op_type_id="OT_EXT", op_type_name="外协",
               source="external", machine_id=None, operator_id=None, supplier_id="SUP01",
               setup_hours=0, unit_hours=0, ext_days=2.5)
    row.update(updates)
    return SimpleNamespace(**row)
