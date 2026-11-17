"""Lossless SQLite values retain their canonical wire representation; each stored value has one strict reader."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, getcontext

import pytest

from core.errors import ValidationError
from core.models.content import StoredJsonCorrupt, content_text, read_stored_json, unpacked
from core.models.hours import (
    HourTotals,
    exact_hours_text,
    hours_text,
    public_hours,
    stored_exact_hours,
    stored_hours,
    sum_hours,
)
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_dashboard_input import validate_handling
from core.models.workbench_downtime import normalize_downtime
from core.models.workbench_field_report_file import FIELDS as REPORT_FILE_FIELDS
from core.models.workbench_outsourcing_input import factory_time as outsourcing_factory_time
from core.models.workbench_preflight import normalize_preflight_input
from core.models.workbench_run_candidate import local_time
from core.models.workbench_run_history import local_date, local_datetime
from core.services.workbench.execution.field_report_files_codec import decode_reports, encode_reports
from core.shared.local_datetime import datetime_to_us, parse_local_datetime, us_to_datetime
from core.shared.stored_dates import stored_date, stored_day, stored_local_iso_datetime
from core.shared.strict_json import canonical_json
from core.shared.strict_parse import (
    is_exact_non_negative_number,
    is_exact_positive_int,
    is_external_days,
    is_stored_number,
    is_stored_time_us,
)
from tests.workbench.execution_ledger_support import ledger_case as ledger_fixture  # noqa: F401


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
            outsourcing_factory_time(invalid_value, "sent")
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


def test_read_stored_json_admits_strict_text_documents_of_the_expected_type():
    assert read_stored_json('{"rows":[0,2.5,null,false]}', dict) == {"rows": [0, 2.5, None, False]}
    assert read_stored_json("[]", list) == []


@pytest.mark.parametrize(("raw", "expected"), [
    (b"{}", dict),
    ("", dict),
    ("{", dict),
    ('{"a":1,"a":2}', dict),
    ('{"a":NaN}', dict),
    ("[1e400]", list),
    ("[]", dict),
    ("{}", list),
    ("1", dict),
])
def test_read_stored_json_rejects_every_corrupt_column_as_one_storage_failure(raw, expected):
    with pytest.raises(StoredJsonCorrupt) as exc:
        read_stored_json(raw, expected)
    assert isinstance(exc.value, WorkbenchCommandRejected)
    assert (exc.value.code, exc.value.status) == ("storage_failure", 500)


_INSTANT_MIN, _INSTANT_MAX = datetime_to_us(datetime.min), datetime_to_us(datetime.max)


@pytest.mark.parametrize(("value", "identity", "count", "instant"), [
    (1, True, True, True),
    (0, False, True, True),
    (-1, False, False, True),
    ((1 << 53) - 1, True, True, True),
    (1 << 53, True, False, True),
    (_INSTANT_MAX, True, False, True),
    (_INSTANT_MAX + 1, True, False, False),
    (_INSTANT_MIN, False, False, True),
    (_INSTANT_MIN - 1, False, False, False),
    ((1 << 63) - 1, True, False, False),
    (1 << 63, False, False, False),
    (True, False, False, False),
    (1.0, False, False, False),
    (float("nan"), False, False, False),
    (float("inf"), False, False, False),
    ("1", False, False, False),
])
def test_stored_integers_are_admitted_by_meaning(value, identity, count, instant):
    assert (is_exact_positive_int(value), is_stored_number(value, integer=True), is_stored_time_us(value)) == (
        identity, count, instant)


def test_stored_instant_bounds_are_the_instants_a_datetime_holds():
    assert us_to_datetime(_INSTANT_MIN) == datetime.min and us_to_datetime(_INSTANT_MAX) == datetime.max


@pytest.mark.parametrize(("value", "admitted"), [
    (36500, True), (36500.0, True), (0.25, True), (1e-9, True),
    (0, False), (0.0, False), (-1, False), (36500.5, False), (36501, False),
    (float("inf"), False), (float("nan"), False), (True, False), ("3", False), (None, False),
])
def test_external_days_are_admitted_in_one_century_range(value, admitted):
    """外协周期、合并周期与供应商默认周期写入共用的值域：(0, 36500] 天的 int/float；NaN 进库会成 NULL，只能这里拒。"""
    assert is_external_days(value) is admitted


@pytest.mark.parametrize(("text", "value"), [
    ("0", 0), ("0.0", 0.0), ("2", 2), ("2.5", 2.5), ("1e-20", 1e-20), (str((1 << 53) - 1), (1 << 53) - 1),
])
def test_stored_hours_reads_back_the_written_int_or_float(text, value):
    read = stored_hours(text)
    assert type(read) is type(value) and read == value and hours_text(read) == text


@pytest.mark.parametrize("text", ["-1", "-0.5", str(1 << 53), "9007199254740992.0", "nan", "inf", "1e400", "abc", "", b"2"])
def test_stored_hours_rejects_corrupt_text_as_storage_failure(text):
    with pytest.raises(WorkbenchCommandRejected) as exc:
        stored_hours(text)
    assert (exc.value.code, exc.value.status) == ("storage_failure", 500)


# Every spelling the report write chain stores: ints, decimals, the exponent forms of tiny floats (largest is 1e-05,
# smallest the subnormal 5e-324), negative zero, and the one-entry maximum as int and float. Within that maximum
# (< 1e16) str() never writes a large value with an exponent.
_WRITTEN_HOURS = (0, 2, (1 << 53) - 1, 0.0, -0.0, 0.1, 2.5, 0.0001, 9007199254740991.0,
                  1e-05, 1.5e-07, 2.2250738585072014e-308, 5e-324)


def _stored_report_hours(case, operation_ref):
    """The active report rows' hours column as stored, and as the ledger's report read admits it."""
    stored = [row[0] for row in case.conn.execute(
        "SELECT effective_processing_hours FROM WorkbenchProductionReports ORDER BY report_no")]
    with case.ledger.read_snapshot() as scope:
        projection = case.ledger.project_loaded(
            case.ledger.load(scope, [operation_ref], include_history=False), include_history=False)[0]
    return stored, [report.effective_processing_hours for report in sorted(projection.reports, key=lambda row: row.report_no)]


def test_every_hours_text_the_report_write_chain_stores_reads_back_as_its_value(ledger_case):
    case = ledger_case
    task = case.task(1, case.op_id)
    for hours in _WRITTEN_HOURS:
        created = case.command("create", task, case.values(
            None, actual_start=None, actual_end=None, effective_processing_hours=hours))
        assert created["result"] == "committed"
    stored, read = _stored_report_hours(case, created["data"]["rows"][0]["operation_ref"])
    assert stored == [hours_text(hours) for hours in _WRITTEN_HOURS]
    assert [(type(value), repr(value)) for value in read] == [(type(hours), repr(hours)) for hours in _WRITTEN_HOURS]


@pytest.mark.parametrize("text", [
    "-1e-9999",            # float() gives -0.0
    "1.0000000000000001",  # float() rounds to 1.0
    "9007199254740991.1",  # float() rounds onto the one-entry maximum
    "1.50", " 2", "+2", "02", "1E-05",
])
def test_report_row_hours_text_other_than_its_value_text_is_storage_failure(ledger_case, text):
    """A stored hours text is the admitted value's ``hours_text``; any other spelling in the report row, even
    one that converts to an admissible number, is a corrupt row, never a silently rounded value."""
    case = ledger_case
    created = case.command("create", case.task(1, case.op_id), case.values(effective_processing_hours=1.5))
    saved = created["data"]["rows"][0]
    case.conn.execute("UPDATE WorkbenchProductionReports SET effective_processing_hours = ? WHERE report_ref = ?",
                      (text, saved["report_ref"]))
    with pytest.raises(WorkbenchCommandRejected) as exc:
        _stored_report_hours(case, saved["operation_ref"])
    assert (exc.value.code, exc.value.status) == ("storage_failure", 500)


def test_sum_hours_is_exact_and_keeps_unknown_apart_from_zero():
    precision = getcontext().prec
    assert sum_hours([]) == HourTotals(None, 0) and sum_hours([]).total is None
    assert sum_hours([None, None]) == HourTotals(None, 2) and sum_hours([None, None]).total is None
    assert sum_hours([0]).total == Decimal(0)
    assert sum_hours([0, None]) == HourTotals(Decimal(0), 1) and sum_hours([0, None]).total is None
    partial = sum_hours([0.1, None, 0.2])
    assert partial == HourTotals(Decimal("0.3"), 1) and partial.total is None and public_hours(partial.total) is None
    complete = sum_hours([0.1, 0.2])
    assert complete.total == Decimal("0.3") and public_hours(complete.total) == 0.3
    beyond_28_digits = sum_hours([(1 << 53) - 1, 1e-20])
    assert exact_hours_text(beyond_28_digits.known) == "9007199254740991.00000000000000000001"
    assert getcontext().prec == precision


@pytest.mark.parametrize(("amount", "text"), [
    (0, "0"), (0.0, "0"), (-0.0, "0"), (Decimal("0.000"), "0"), (2.0, "2"), (Decimal("1.50"), "1.5"),
    (1e16, "10000000000000000"), (1e-20, "0.00000000000000000001"), (Decimal("1E+2"), "100"),
])
def test_exact_hours_text_is_canonical_decimal_text(amount, text):
    assert exact_hours_text(amount) == text and stored_exact_hours(text) == sum_hours([amount]).known


def test_totals_and_derived_hours_are_not_held_to_the_one_entry_bound():
    largest = (1 << 53) - 1
    quantity, setup, unit_hours = 2, 0, largest
    derived = quantity * unit_hours + setup
    assert not is_stored_number(derived) and is_exact_non_negative_number(derived)
    saved = read_stored_json(canonical_json({"processing_standard_hours": derived}), dict)
    assert type(saved["processing_standard_hours"]) is int and saved["processing_standard_hours"] == derived
    total_text = exact_hours_text(sum_hours([largest, largest]).total)
    assert total_text == "18014398509481982" and stored_exact_hours(total_text) == Decimal(derived)


@pytest.mark.parametrize("text", ["NaN", "sNaN", "Infinity", "-1", "-0.1", "1" + "0" * 400, "abc", "", b"1"])
def test_stored_exact_hours_rejects_corrupt_totals_as_storage_failure(text):
    with pytest.raises(WorkbenchCommandRejected) as exc:
        stored_exact_hours(text)
    assert (exc.value.code, exc.value.status) == ("storage_failure", 500)
