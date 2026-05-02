"""
可选插件：pandas/numpy Excel 后端（Win7 离线）。

启用方式：
1) 将依赖投放到交付目录 vendor/（或安装到 Python 环境）：
   - pandas==1.3.5
   - numpy==1.21.6
   - openpyxl==3.0.10（项目已内置）
2) 系统管理页将插件开关置为 enabled=yes，并重启应用

注册能力：
- excel_backend.pandas -> PandasBackend()
"""

PLUGIN_ID = "pandas_excel_backend"
PLUGIN_NAME = "Excel 高速读取组件"
PLUGIN_VERSION = "1.0"
PLUGIN_DEFAULT_ENABLED = "no"

COMPAT = {
    "pandas": "1.3.5",
    "numpy": "1.21.6",
    "openpyxl": "3.0.10",
}


def _require_version(mod, expect: str, name: str) -> None:
    ver = str(getattr(mod, "__version__", "") or "").strip()
    if ver != str(expect).strip():
        raise RuntimeError(f"{name} 版本不兼容：当前 {ver or 'unknown'}，期望 {expect}（Win7 离线锁定版本）")


def register(registry):
    try:
        import numpy as np  # noqa: F401
        import openpyxl as ox
        import pandas as pd
    except Exception as e:
        raise RuntimeError(
            "缺少可选依赖：请将 pandas/numpy 安装到环境或投放到 vendor/。"
            "（期望：pandas==1.3.5, numpy==1.21.6, openpyxl==3.0.10）"
        ) from e

    _require_version(pd, COMPAT["pandas"], "pandas")
    _require_version(np, COMPAT["numpy"], "numpy")
    _require_version(ox, COMPAT["openpyxl"], "openpyxl")

    from core.services.common.pandas_backend import PandasBackend

    registry.register("excel_backend.pandas", lambda: PandasBackend())
