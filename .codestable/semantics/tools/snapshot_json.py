"""自写 JSON snapshot helper —— 锁住“对外语义长什么样”，而非测算法正确性。

设计取舍：不用 syrupy 而自写，因为本项目对离线/稳定/Python 3.8 兼容敏感，
自写 helper 行为完全可控、零第三方依赖、3.8 与 3.14 下行为一致。

更新基线：APS_UPDATE_SEMANTIC_SNAPSHOTS=1 时写入；否则只断言不写。
缺失 snapshot 一律失败(不静默通过) —— 符合“坏数据不准静默兜底”灵魂线。
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

# 易变键：快照时归一成占位符，避免时间戳/路径/版本号造成假阳性 diff。
_VOLATILE_KEYS = {
    "created_at", "updated_at", "generated_at", "timestamp", "run_id", "abs_path",
}


def normalize_snapshot(value: Any) -> Any:
    if isinstance(value, dict):
        out = {}
        for key, item in sorted(value.items(), key=lambda pair: str(pair[0])):
            key_text = str(key)
            out[key_text] = "<volatile>" if key_text in _VOLATILE_KEYS else normalize_snapshot(item)
        return out
    if isinstance(value, (list, tuple)):
        return [normalize_snapshot(item) for item in value]
    return value


def assert_json_snapshot(actual: Any, snapshot_path: str) -> None:
    path = Path(snapshot_path)
    normalized = normalize_snapshot(actual)

    if os.environ.get("APS_UPDATE_SEMANTIC_SNAPSHOTS") == "1":
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(normalized, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return

    if not path.exists():
        raise AssertionError(
            "缺少 snapshot：" + snapshot_path + "\n"
            "如确认这是新语义基线，设置 APS_UPDATE_SEMANTIC_SNAPSHOTS=1 后重跑。"
        )

    expected = json.loads(path.read_text(encoding="utf-8"))
    assert normalized == expected, (
        "语义快照漂移：" + snapshot_path + "\n"
        "若是有意的语义变更，请先更新 concept-registry.yaml 并说明原因，再用 "
        "APS_UPDATE_SEMANTIC_SNAPSHOTS=1 重建快照。"
    )
