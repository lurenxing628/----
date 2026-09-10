"""Typed, lossless template-copy evidence. Business codes are never identities."""

import hashlib
import json

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
    return json.dumps({key: typed_value(value) for key, value in row.items()},
                      ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":"))


def restore_snapshot(text):
    values = json.loads(text)
    if not isinstance(values, dict):
        raise ValueError("Lineage snapshot must be a typed row.")
    result = {}
    for key, (kind, value) in values.items():
        decoders = {"null": lambda _: None, "blob": bytes.fromhex, "real": float.fromhex,
                    "integer": int, "text": lambda item: item}
        result[key] = decoders[kind](value)
    if snapshot(result) != text:
        raise ValueError("Noncanonical lineage snapshot.")
    return result


def fingerprint(text):
    return hashlib.sha256(text.encode("ascii")).hexdigest()


def state_snapshot(row):
    return snapshot({key: row[key] for key in STATE_COLUMNS})


def copy_payload(row, batch_id, *, from_template):
    piece = None if from_template else row["piece_id"]
    code = batch_id + "_" + str(row["seq"]).zfill(2) + ("_" + piece if piece is not None else "")
    payload = {key: row.get(key) for key in COPY_COLUMNS}
    payload.update(batch_id=batch_id, piece_id=piece, op_code=code, status="pending")
    if from_template:
        payload.update(machine_id=None, operator_id=None)
    return payload
