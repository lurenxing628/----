"""Lossless SQLite values retain their canonical wire representation."""

from datetime import date, datetime, timedelta, timezone

import pytest

from core.errors import ValidationError
from core.models.content import content_text, unpacked
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_dashboard_input import validate_handling
from core.models.workbench_downtime import normalize_downtime
from core.models.workbench_field_report_file import FIELDS as REPORT_FILE_FIELDS
from core.models.workbench_outsourcing_input import factory_time as outsourcing_factory_time
from core.models.workbench_preflight import normalize_preflight_input, stored_hold_window_valid
from core.models.workbench_run_candidate import local_time
from core.models.workbench_run_history import local_date, local_datetime
from core.services.workbench.execution.field_report_files_codec import decode_reports, encode_reports
from core.shared.local_datetime import parse_local_datetime
from core.shared.stored_dates import stored_date, stored_day, stored_local_iso_datetime


@pytest.mark.parametrize(("value", "expected"), [
    ({"rows": [None, True, False, 0, 1, -1, "中文", 1.0]},
     '{"rows":[null,true,false,0,1,-1,"中文",1.0]}'),
    (b"\x00\xff", '{"$sqlite_blob":"AP8="}'),
    (date(2026, 10, 18), '{"iso":"2026-10-18","storage_type":"date"}'),
    (datetime(2026, 10, 18, 8, 30), '{"iso":"2026-10-18T08:30:00","storage_type":"datetime"}'),
    (datetime(2026, 10, 18, 8, 30, 0, 500000), '{"iso":"2026-10-18T08:30:00.500000","storage_type":"datetime"}'),
    (datetime(2026, 10, 18, 8, 30, tzinfo=timezone(timedelta(hours=8))),
     '{"iso":"2026-10-18T08:30:00+08:00","storage_type":"datetime"}'),
])
def test_canonical_content_preserves_scalar_types_and_reserved_dictionaries(value, expected):
    import json

    assert content_text(value) == expected
    restored = unpacked(json.loads(expected))
    assert type(restored) is type(value) and restored == value


@pytest.mark.parametrize("document", [
    {"storage_type": "date", "iso": "20261018"},
    {"storage_type": "date", "iso": "2026-W42-7"},
    {"storage_type": "date", "iso": 20261018},
    {"storage_type": "datetime", "iso": "20261018T083000"},
    {"storage_type": "datetime", "iso": "2026-10-18T08:30:00Z"},
    {"storage_type": "datetime", "iso": "2026-10-18T08:30:00.5"},
    {"storage_type": "datetime", "iso": "2026-10-18T08:30:00.500"},
    {"storage_type": "datetime", "iso": "2026-10-18 08:30:00"},
    {"storage_type": "datetime", "iso": "2026-10-18T24:00:00"},
    {"storage_type": "datetime", "iso": "2026-10-18 24:00"},
    {"storage_type": "datetime", "iso": "2026-10-18T24:00:00.0"},
    {"storage_type": "datetime", "iso": "2026-10-18T24:00:00.000000"},
    {"storage_type": "datetime", "iso": "2026-10-18T08:30:00+24:00"},
])
def test_unpacked_rejects_non_canonical_iso_spellings_across_interpreters(document):
    with pytest.raises(ValueError):
        unpacked(document)


def test_stored_dates_accept_fractional_seconds_and_reject_relaxed_py311_forms():
    assert stored_day("2026-10-18") == date(2026, 10, 18)
    assert stored_day("20261018") is None
    assert stored_day(date(2026, 10, 18)) is None
    assert stored_date(date(2026, 10, 18)) == "2026-10-18"
    assert stored_date(datetime(2026, 10, 18, 8, 30)) is None
    assert stored_date("20261018") is None

    expected_half_sec = datetime(2026, 10, 18, 8, 30, 0, 500000)
    assert stored_local_iso_datetime("2026-10-18T08:30:00.5") == expected_half_sec
    assert local_time("2026-10-18T08:30:00.5") == expected_half_sec
    assert local_datetime("2026-10-18T08:30:00.12345") == datetime(2026, 10, 18, 8, 30, 0, 123450)
    assert local_date("2026-10-18") == date(2026, 10, 18)

    assert stored_local_iso_datetime("2026-10-18 08:30") is None
    assert stored_local_iso_datetime("2026-10-18 08:30", allow_space=True, allow_minutes_only=True) == datetime(
        2026, 10, 18, 8, 30
    )
    assert stored_local_iso_datetime("2026-10-18 08:30.5", allow_space=True, allow_minutes_only=True) is None
    for invalid in (
        "20261018T083000",
        "2026-10-18T08:30:00Z",
        "2026-10-18T08:30:00+08:00",
        "2026-10-18T08:30:00.1234567",
        "2026-10-18T24:00:00",
        "2026-10-18 24:00",
        "2026-10-18T24:00:00.0",
    ):
        assert stored_local_iso_datetime(invalid) is None
        assert stored_local_iso_datetime(invalid, allow_space=True, allow_minutes_only=True) is None
        with pytest.raises(ValueError):
            local_time(invalid)
        with pytest.raises(ValueError):
            local_datetime(invalid)


@pytest.mark.parametrize(("value", "error"), [
    (date(2026, 10, 18), TypeError), (datetime(2026, 10, 18), TypeError),
])
def test_json_input_rejects_sqlite_only_values_inside_collections(value, error):
    with pytest.raises(error):
        content_text({"rows": [value]}, json_input=True)


def test_encoding_reuses_unchanged_paths(monkeypatch):
    from core.models import content

    unchanged = {"rows": [{"values": [None, True, 1, 1.0]}]}
    source = {"unchanged": unchanged, "changed": {"blob": b"x", "kept": unchanged},
              "literal": {"$sqlite_dict": "original"}, "tuple": (1, True)}
    expected = content.json.dumps(content.packed(source), ensure_ascii=False, sort_keys=True,
                                  separators=(",", ":"), allow_nan=False)
    encoded, dump = [], content.json.dumps

    def capture(value, **kwargs):
        encoded.append(value)
        return dump(value, **kwargs)

    monkeypatch.setattr(content.json, "dumps", capture)
    assert content.content_text(source) == expected
    value = encoded[0]
    assert value is not source and value["changed"] is not source["changed"]
    assert value["unchanged"] is unchanged and value["changed"]["kept"] is unchanged
    assert value["tuple"] is source["tuple"]
    assert source["changed"]["blob"] == b"x" and source["literal"] == {"$sqlite_dict": "original"}
    content.content_text(unchanged)
    assert encoded[1] is unchanged


def _report_xlsx_bytes(actual_start: str) -> bytes:
    row = dict.fromkeys(REPORT_FILE_FIELDS, "")
    row.update(
        report_no="R-0001",
        batch_id="B1",
        operation_label="1 Turning",
        completed_quantity=1,
        actual_start=actual_start,
        actual_end="2026-09-10 10:30:00",
        effective_processing_hours=2.0,
        machine_label="M1",
        operator_label="O1",
        remark="normal",
        task_ref="a" * 48,
        operation_scope="共同",
        piece_id="",
    )
    return encode_reports([row], summaries=[], metadata=[])


@pytest.mark.parametrize(
    "raw_24h",
    [
        "2026-09-09 24:00:00",
        "2026-09-09T24:00:00",
        "2026-09-09 24:00:00.5",
        "2026-09-09 24:00:00.000000",
        "2026-09-09 24:00",
    ],
)
def test_parse_local_datetime_rejects_24h_spellings(raw_24h):
    assert parse_local_datetime(raw_24h) is None


@pytest.mark.parametrize(
    ("entry", "invalid_value", "expected_message"),
    [
        ("downtime", "2026-09-09 24:00", "停机日期或时刻不存在，请核对。"),
        ("downtime", "2026-09-09T24:00:00", "停机日期或时刻不存在，请核对。"),
        ("downtime", "2026-09-09", "停机起止须填写年月日和时分。"),
        ("outsourcing", "2026-09-09T24:00:00", "登记时间不是有效日期。"),
        ("outsourcing", "2026-09-09 24:00:00", "登记时间格式不对，请按 2026-09-13 08:30:00 这样填写。"),
        ("field_report_xlsx", "2026-09-09 24:00", "实际时间不是有效的日期时间。"),
        ("field_report_xlsx", "2026-09-09T24:00:00", "实际时间不是有效的日期时间。"),
        ("field_report_xlsx", "2026-09-09T08", "实际时间请按 2026-09-13 08:30 这样填，需要时可以带秒，例如 08:30:15。"),
        (
            "dashboard_handling",
            "2026-09-09T24:00:00",
            "完成时间格式不对，请按 2026-09-13 08:30:00 这样填写，而且不能晚于当前时间。",
        ),
        (
            "preflight_hold_window",
            "2026-09-09T24:00",
            "不重排时段要填完整的开始和结束时刻（精确到分），开始要早于结束，并且在排产日期范围内。",
        ),
    ],
)
def test_workbench_datetime_inputs_reject_hour_24_and_preserve_error_tiers(entry, invalid_value, expected_message):
    if entry == "downtime":
        with pytest.raises(WorkbenchCommandRejected) as exc:
            normalize_downtime(
                "create",
                {
                    "start_time": invalid_value,
                    "end_time": "2026-09-10 09:00",
                    "reason_code": "maintenance",
                    "reason_detail": None,
                },
            )
        assert exc.value.code == "invalid_input" and str(exc.value) == expected_message
    elif entry == "outsourcing":
        with pytest.raises(WorkbenchCommandRejected) as exc:
            outsourcing_factory_time(invalid_value)
        assert exc.value.code == "invalid_input" and str(exc.value) == expected_message
    elif entry == "field_report_xlsx":
        decoded = decode_reports(_report_xlsx_bytes(invalid_value))
        assert decoded[0]["errors"] == [{"row": 2, "field": "actual_start", "message": expected_message}]
    elif entry == "dashboard_handling":
        with pytest.raises(ValidationError) as exc:
            validate_handling(
                {
                    "status": "closed",
                    "owner": "O1",
                    "deadline": "2026-09-15",
                    "action": "replace bearing",
                    "completed_at": invalid_value,
                    "completion_evidence": "bearing #12 replaced and verified",
                    "evidence_reference_text": "WO-20260909-01",
                },
                datetime(2026, 9, 12, 12, 0, 0),
            )
        assert exc.value.field == "completed_at" and exc.value.message == expected_message
    elif entry == "preflight_hold_window":
        assert stored_hold_window_valid({"start": "2026-09-09T08:00", "end": invalid_value}) is False
        with pytest.raises(WorkbenchCommandRejected) as exc:
            normalize_preflight_input(
                {
                    "batch_refs": ["a" * 48],
                    "start_date": "2026-09-09",
                    "end_date": "2026-09-10",
                    "ready_check": True,
                    "missing_resource_policy": "auto_assign",
                    "completed_policy": "preserve_actuals",
                    "hold_window": {"start": "2026-09-09T08:00", "end": invalid_value},
                }
            )
        assert exc.value.code == "invalid_input" and str(exc.value) == expected_message
    else:
        raise AssertionError(f"Unhandled entry: {entry}")
