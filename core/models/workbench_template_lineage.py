"""Typed, lossless template-copy evidence. Business codes are never identities."""

import json
from typing import NoReturn

from core.shared.strict_json import load_strict_json

OPERATION_COLUMNS = (
    "id", "op_code", "batch_id", "piece_id", "seq", "op_type_id", "op_type_name", "source",
    "machine_id", "operator_id", "supplier_id", "setup_hours", "unit_hours", "ext_days", "status", "created_at",
)
SEMANTIC_COLUMNS = ("piece_id", "seq", "op_type_id", "op_type_name", "source", "supplier_id",
                    "setup_hours", "unit_hours", "ext_days")
OWNER_COLUMNS = ("batch_ref", "part_ref", "quantity")
STATE_COLUMNS = OPERATION_COLUMNS + OWNER_COLUMNS
COPY_COLUMNS = OPERATION_COLUMNS[1:-1]
EVIDENCE_VERSION = "template-copy-v1"
_DECODERS = {"null": lambda _: None, "blob": bytes.fromhex, "real": float.fromhex,
             "integer": int, "text": lambda item: item}


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


def _signature_value(value):
    kind = type(value)
    if value is None or kind in (int, str, bytes):
        return (kind, value)
    if kind is float:
        return (float, value.hex())
    return tuple(typed_value(value))


def columns_signature(row, columns):
    return tuple(_signature_value(row[key]) for key in columns)


def snapshot(row):
    return json.dumps({key: typed_value(value) for key, value in row.items()},
                      ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":"))


def _not_typed_row() -> NoReturn:
    raise ValueError("Lineage snapshot must be a typed row.")


def restore_snapshot(text):
    values = load_strict_json(text, on_malformed=_not_typed_row, expected=dict)
    return {key: _DECODERS[kind](value) for key, (kind, value) in values.items()}


def state_snapshot(row):
    return snapshot({key: row[key] for key in STATE_COLUMNS})


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
