from __future__ import annotations

import pytest

from web.viewmodels.system_logs_vm import OperationLogViewRowContractError, build_operation_log_view_rows


def test_unknown_operation_log_codes_keep_raw_values_visible() -> None:
    rows = build_operation_log_view_rows(
        [
            {
                "log_level": "TRACE",
                "module": "raw_mod",
                "action": "raw_act",
                "target_type": "raw_target",
                "detail": "",
            }
        ]
    )

    row = rows[0]

    assert row["log_level_label"] == "其他等级（TRACE）"
    assert row["module_label"] == "其他模块（raw_mod）"
    assert row["action_label"] == "其他操作（raw_act）"
    assert row["target_type_label"] == "其他对象（raw_target）"


def test_empty_operation_log_codes_stay_empty_state() -> None:
    rows = build_operation_log_view_rows(
        [
            {
                "log_level": "",
                "module": "",
                "action": "",
                "target_type": "",
                "detail": "",
            }
        ]
    )

    row = rows[0]

    assert row["log_level_label"] == "-"
    assert row["module_label"] == "-"
    assert row["action_label"] == "-"
    assert row["target_type_label"] == "-"


@pytest.mark.parametrize(
    ("detail", "state"),
    (
        ("", "empty"),
        (None, "empty"),
        ('{"ok": true}', "ok"),
        ("{bad json", "invalid_json"),
        ('["not", "object"]', "non_object"),
        ('"not object"', "non_object"),
    ),
)
def test_operation_log_detail_parse_state_is_visible(detail, state) -> None:
    rows = build_operation_log_view_rows(
        [
            {
                "log_level": "INFO",
                "module": "system",
                "action": "backup",
                "target_type": "backup",
                "detail": detail,
            }
        ]
    )

    row = rows[0]

    assert row["detail_parse_state"] == state
    if state == "ok":
        assert row["detail_obj"] == {"ok": True}
    else:
        assert row["detail_obj"] is None


def test_operation_log_to_dict_error_is_not_rendered_as_blank_row() -> None:
    class _BadRow:
        def to_dict(self):
            raise RuntimeError("broken row")

    with pytest.raises(OperationLogViewRowContractError, match="操作日志行无法转换"):
        build_operation_log_view_rows([_BadRow()])
