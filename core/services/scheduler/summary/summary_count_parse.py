from __future__ import annotations

import math
from typing import Any, Dict, Optional, Tuple


def _meta_bool_state(meta: Dict[str, Any], key: str, *, default: bool) -> Tuple[bool, bool]:
    # R68 收口：resource_pool（schedule_summary_degradation）与 downtime（schedule_summary_downtime_
    # degradation）两条降级路径原各持一份逐字相同的副本，合一到本 parse 收口模块。返回二元组
    # (bool, parse_failed)——第二位是坏 meta 的 loud 降级标记（int 非 0/1、垃圾字符串、其他类型
    # 一律 (default, True)），绝不许压扁成单 bool 或静默吞掉，否则前端丢「降级因 meta 异常」提示。
    if key not in meta or meta.get(key) is None:
        return bool(default), False
    value = meta.get(key)
    if isinstance(value, bool):
        return value, False
    if isinstance(value, int) and not isinstance(value, bool):
        if value in (0, 1):
            return bool(value), False
        return bool(default), True
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"true", "1", "yes", "y", "on"}:
            return True, False
        if text in {"false", "0", "no", "n", "off"}:
            return False, False
        return bool(default), True
    return bool(default), True


def parse_summary_count(value: Any, *, field: str) -> Tuple[int, Optional[str]]:
    if value is None or value == "":
        return 0, None
    if isinstance(value, bool):
        return 0, f"{field} 不能是布尔值：{value!r}"
    try:
        if isinstance(value, float):
            if not math.isfinite(value) or not value.is_integer():
                return 0, f"{field} 必须是非负整数：{value!r}"
            number = int(value)
        else:
            text = str(value).strip()
            if not text:
                return 0, None
            if "." in text:
                fv = float(text)
                if not math.isfinite(fv) or not fv.is_integer():
                    return 0, f"{field} 必须是非负整数：{value!r}"
                number = int(fv)
            else:
                number = int(text)
    except Exception:
        return 0, f"{field} 必须是非负整数：{value!r}"
    if number < 0:
        return 0, f"{field} 不能为负数：{value!r}"
    return number, None
