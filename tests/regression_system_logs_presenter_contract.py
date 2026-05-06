from __future__ import annotations

from web.viewmodels.system_logs_vm import build_operation_log_view_rows


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

