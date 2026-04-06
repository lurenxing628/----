"""回归测试：Excel 路由层数值校验必须与服务层契约一致。"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def test_parse_seq_rejects_bool_and_scientific() -> None:
    """_parse_seq 必须拒绝布尔值和科学计数法字符串。"""
    from web.routes.process_excel_part_operation_hours import _parse_seq

    assert _parse_seq(True) is None, "True 应被拒绝"
    assert _parse_seq(False) is None, "False 应被拒绝"
    assert _parse_seq("5e0") is None, '"5e0" 应被拒绝'
    assert _parse_seq("1E2") is None, '"1E2" 应被拒绝'

    assert _parse_seq(5) == 5
    assert _parse_seq("10") == 10
    assert _parse_seq(3.0) == 3


def test_supplier_default_days_rejects_invalid_numeric() -> None:
    """_normalize_supplier_default_days 必须拒绝布尔值与非有限数字。"""
    from web.routes.process_excel_suppliers import _normalize_supplier_default_days

    assert _normalize_supplier_default_days({"默认周期": True}) is not None, "True 应被拒绝"
    assert _normalize_supplier_default_days({"默认周期": False}) is not None, "False 应被拒绝"
    assert _normalize_supplier_default_days({"默认周期": float("nan")}) is not None, "NaN 应被拒绝"
    assert _normalize_supplier_default_days({"默认周期": float("inf")}) is not None, "Inf 应被拒绝"

    assert _normalize_supplier_default_days({"默认周期": 5.0}) is None


if __name__ == "__main__":
    test_parse_seq_rejects_bool_and_scientific()
    test_supplier_default_days_rejects_invalid_numeric()
    print("OK")
