"""经办人与原因：三个入口共用一条“填了有效文字”的判定，上限、错误码和提示各留在本领域。"""

import pytest

from core.models.workbench_calibration_adoption import preview_input as calibration_input
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_outsourcing_input import normalize_input as outsourcing_input
from core.models.workbench_run_adoption import adoption_input as run_input
from core.shared.filled_text import is_filled_text
from core.shared.refs import new_ref

NOT_FILLED = [None, 7, b"reason", "", " \t\n", "a\x00b"]


def _run(reason, operator):
    return run_input({"confirm": True, "reason": reason, "declared_operator": operator})


def _calibration(reason, operator):
    return calibration_input({"reason": reason, "declared_operator": operator})


def _outsourcing(reason, operator):
    return outsourcing_input({"reason": reason, "declared_operator": operator, "outsourcing_ref": new_ref()})


RUN_MESSAGE = "采用原因或声明操作人为空、过长或含无效字符。"
CALIBRATION_MESSAGE = "请填写采用原因和经办人；原因最多 2000 字，经办人最多 100 字。"
# 入口、原因上限、经办人上限、本领域按字段的提示。
ENTRIES = {
    "run_adoption": (_run, 1000, 100, {"reason": RUN_MESSAGE, "declared_operator": RUN_MESSAGE}),
    "calibration_adoption": (_calibration, 2000, 100,
                             {"reason": CALIBRATION_MESSAGE, "declared_operator": CALIBRATION_MESSAGE}),
    "outsourcing": (_outsourcing, 2000, 200, {"reason": "请填写有效的本次核实或更正原因，不能留空或使用非文字内容。",
                                              "declared_operator": "请填写有效的经办人，不能留空或使用非文字内容。"}),
}


@pytest.mark.parametrize("value", NOT_FILLED + ["x" * 6])
def test_filled_text_rejects_non_strings_blank_nul_and_over_limit(value):
    assert not is_filled_text(value, 5)


def test_filled_text_accepts_padded_text_up_to_the_limit():
    assert is_filled_text(" 张三 ", 4) and is_filled_text("x" * 4, 4)


@pytest.mark.parametrize("entry", sorted(ENTRIES))
def test_each_entry_keeps_its_own_limits_and_stores_stripped_text(entry):
    normalize, reason_limit, operator_limit, _messages = ENTRIES[entry]
    result = normalize(" " + "r" * (reason_limit - 2) + " ", " " + "o" * (operator_limit - 2) + " ")
    assert result["reason"] == "r" * (reason_limit - 2)
    assert result["declared_operator"] == "o" * (operator_limit - 2)
    assert normalize("r" * reason_limit, "o" * operator_limit)["reason"] == "r" * reason_limit


@pytest.mark.parametrize("entry", sorted(ENTRIES))
@pytest.mark.parametrize("field", ["reason", "declared_operator"])
def test_each_entry_rejects_not_filled_or_over_limit_with_its_own_message(entry, field):
    normalize, reason_limit, operator_limit, messages = ENTRIES[entry]
    limit = reason_limit if field == "reason" else operator_limit
    for value in NOT_FILLED + ["x" * (limit + 1)]:
        values = {"reason": "核对来料", "declared_operator": "张三", field: value}
        with pytest.raises(WorkbenchCommandRejected) as rejected:
            normalize(values["reason"], values["declared_operator"])
        assert (rejected.value.code, rejected.value.status, str(rejected.value)) == ("invalid_input", 422, messages[field])
