from __future__ import annotations

from typing import Optional

from core.plugins import get_plugin_registry

from .openpyxl_backend import OpenpyxlBackend
from .tabular_backend import TabularBackend


def get_excel_backend(prefer: Optional[str] = None) -> TabularBackend:
    """
    获取 Excel 表格后端（默认 openpyxl；若已加载 pandas 插件则可自动切换）。

    说明：
    - prefer=None/"auto"：优先使用已注册的 pandas 后端，否则回退 openpyxl
    - prefer="openpyxl"：强制 openpyxl
    - prefer="pandas"：强制 pandas（若不可用则回退 openpyxl）
    """
    pref = (prefer or "auto").strip().lower()
    if pref == "openpyxl":
        return OpenpyxlBackend()

    reg = get_plugin_registry()
    provider = reg.get("excel_backend.pandas")
    if provider is not None and pref in ("auto", "pandas"):
        try:
            if callable(provider):
                return provider()  # type: ignore[misc]
            return provider  # type: ignore[return-value]
        except Exception:
            return OpenpyxlBackend()

    return OpenpyxlBackend()

