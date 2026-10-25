"""Stored BatchOperations / Batches rows as the complete objects the scheduler's checks consume.

Workbench checks (trial estimates, held-arrangement timing, fixed qualifications, freeze/execution guards,
split scopes) recompute with the scheduler's own functions over rows they already read; the rows go in
whole, nothing is defaulted or validated here, so every existing rejection keeps its own place and wording.
"""

from dataclasses import fields

from core.algorithm_contracts.types import OpForScheduleAlgo
from core.models.batch import Batch
from core.models.batch_operation import BatchOperation


def stored_operation(row, group=None):
    """A BatchOperations row as the algorithm operation; only external work carries an external group."""
    return OpForScheduleAlgo(
        id=row["id"], op_code=row["op_code"], batch_id=row["batch_id"], piece_id=row["piece_id"], seq=row["seq"],
        op_type_id=row["op_type_id"], op_type_name=row["op_type_name"], source=row["source"],
        machine_id=row["machine_id"], operator_id=row["operator_id"], supplier_id=row["supplier_id"],
        setup_hours=row["setup_hours"], unit_hours=row["unit_hours"], ext_days=row["ext_days"],
        ext_group_id=None if group is None else group["group_id"],
        ext_merge_mode=None if group is None else group["merge_mode"],
        ext_group_total_days=None if group is None else group["total_days"],
    )


def stored_batch_operation(row):
    """A BatchOperations row as the batch operation model the freeze, execution and split checks take."""
    return BatchOperation(**{item.name: row[item.name] for item in fields(BatchOperation)})


def stored_batch(row):
    """A Batches row as the batch model."""
    return Batch(**{item.name: row[item.name] for item in fields(Batch)})
