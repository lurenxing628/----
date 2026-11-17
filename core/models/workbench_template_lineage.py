"""Typed, lossless template-copy helpers. Business codes are never identities."""

import json

COPY_COLUMNS = (
    "op_code",
    "batch_id",
    "piece_id",
    "seq",
    "op_type_id",
    "op_type_name",
    "source",
    "machine_id",
    "operator_id",
    "supplier_id",
    "setup_hours",
    "unit_hours",
    "ext_days",
    "status",
)


def typed_value(value):
    if value is None:
        return ["null", None]
    if type(value) is bytes:
        return ["blob", value.hex()]
    if type(value) is float:
        return ["real", value.hex()]
    if type(value) is int:
        return ["integer", str(value)]
    if type(value) is str:
        return ["text", value]
    raise TypeError("Unsupported SQLite lineage value: " + type(value).__name__)


def snapshot(row):
    return json.dumps(
        {key: typed_value(value) for key, value in row.items()},
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def operation_code(batch_id, sequence, piece):
    return batch_id + "_" + str(sequence).zfill(2) + ("_" + piece if piece is not None else "")


def copy_payload(row, batch_id, *, from_template):
    piece = None if from_template else row["piece_id"]
    code = operation_code(batch_id, row["seq"], piece)
    payload = {key: row.get(key) for key in COPY_COLUMNS}
    payload.update(batch_id=batch_id, piece_id=piece, op_code=code, status="pending")
    if from_template:
        payload.update(machine_id=None, operator_id=None)
    return payload
