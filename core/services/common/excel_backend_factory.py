from __future__ import annotations

import logging
from typing import Any, Optional

from core.plugins import get_plugin_registry

from .openpyxl_backend import OpenpyxlBackend
from .tabular_backend import TabularBackend

_LOGGER = logging.getLogger(__name__)
_PANDAS_BACKEND_CAPABILITY = "excel_backend.pandas"


def _materialize_registered_backend(provider: Any, *, capability: str) -> TabularBackend:
    backend = provider() if callable(provider) else provider
    if not isinstance(backend, TabularBackend):
        raise TypeError(f"{capability} 提供者返回值不符合 TabularBackend 约定：{type(backend)!r}")
    return backend


def get_excel_backend(prefer: Optional[str] = None) -> TabularBackend:
    """
    获取 Excel 表格后端（默认 openpyxl；若已加载 pandas 插件则可自动切换）。

    说明：
    - prefer=None/"auto"：优先使用已注册的 pandas 后端；若其构造失败，则记录 warning 后降级为 openpyxl
    - prefer="openpyxl"：强制 openpyxl
    - prefer="pandas"：强制 pandas；若能力未注册或构造失败，则显式抛错
    - 其它取值：显式抛出 ValueError，避免静默回退掩盖调用方错误
    """
    pref = (prefer or "auto").strip().lower()
    if pref == "openpyxl":
        return OpenpyxlBackend()
    if pref not in ("auto", "pandas"):
        raise ValueError(
            f"prefer 取值不合法：{prefer!r}（允许值：None / 'auto' / 'openpyxl' / 'pandas'）"
        )

    reg = get_plugin_registry()
    provider = reg.get(_PANDAS_BACKEND_CAPABILITY)
    if provider is None:
        if pref == "pandas":
            raise RuntimeError(f"请求 pandas Excel 后端，但插件能力 {_PANDAS_BACKEND_CAPABILITY} 未注册。")
        return OpenpyxlBackend()

    try:
        return _materialize_registered_backend(provider, capability=_PANDAS_BACKEND_CAPABILITY)
    except Exception as exc:
        if pref == "pandas":
            raise RuntimeError(f"pandas Excel 后端初始化失败：{exc}") from exc
        _LOGGER.warning(
            "pandas Excel 后端初始化失败，已降级为 openpyxl：capability=%s err=%s",
            _PANDAS_BACKEND_CAPABILITY,
            exc,
        )
        return OpenpyxlBackend()

