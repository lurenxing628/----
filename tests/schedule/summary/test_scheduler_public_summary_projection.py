"""回归测试：守护 project_public_algo_summary 对 input_contract 的脱敏投影——只放行 degraded/降级事件 code/有效计数器/empty_reason 等白名单字段，剔除 raw_path、traceback、debug_payload 等私密键（输出中不得出现 secret/私密路径/Traceback），且 input_contract 非字典时降为空字典。"""

from __future__ import annotations

import json

from core.services.scheduler.summary.optimizer_public_summary import project_public_algo_summary


def test_public_algo_summary_input_contract_does_not_passthrough_unknown_fields() -> None:
    algo = {
        "input_contract": {
            "degraded": True,
            "degradation_events": [
                {"code": "input_fallback", "count": 1, "private": "/tmp/private.db"},
            ],
            "degradation_counters": {"input_fallback": 1, "zero": 0, "bad": "not-int"},
            "empty_reason": "no_operations",
            "raw_path": "/tmp/private.db",
            "traceback": "Traceback secret",
            "debug_payload": {"token": "secret"},
        }
    }

    public, _diagnostics = project_public_algo_summary(algo)

    contract = public["input_contract"]
    assert contract["degraded"] is True
    assert contract["degradation_counters"] == {"input_fallback": 1}
    assert contract["empty_reason"] == "no_operations"
    assert contract["degradation_events"][0]["code"] == "input_fallback"

    assert "raw_path" not in contract
    assert "traceback" not in contract
    assert "debug_payload" not in contract
    visible = json.dumps(public, ensure_ascii=False, sort_keys=True)
    assert "secret" not in visible.lower()
    assert "/tmp/private.db" not in visible
    assert "Traceback" not in visible


def test_public_algo_summary_input_contract_non_dict_becomes_empty_dict() -> None:
    public, _diagnostics = project_public_algo_summary({"input_contract": "Traceback /tmp/private.db"})

    assert public["input_contract"] == {}
