"""Lazy NetworkX runtime boundary for scheduler graph analysis."""
from __future__ import annotations

import importlib
from typing import Any

_EXPECTED_VERSION = "3.1"
_REQUIREMENT_NAME = "networkx==3.1"
_OPTIONAL_REQUIREMENTS_FILE = "requirements-optimizer-lite-win7.txt"


class NetworkXUnavailable(RuntimeError):
    """Raised when optional NetworkX runtime is missing or incompatible."""


def expected_networkx_version() -> str:
    """Return the only NetworkX version accepted by the Win7/Python 3.8 runtime."""
    return _EXPECTED_VERSION


def optional_networkx_requirement() -> str:
    """Return the optional requirement pin used to install NetworkX support."""
    return _REQUIREMENT_NAME


def _module_version(module: Any) -> str:
    return str(getattr(module, "__version__", "") or "").strip()


def _missing_message() -> str:
    return (
        f"缺少可选依赖 {_REQUIREMENT_NAME}；"
        f"如需启用工序图分析 report/on 模式，请先安装 {_OPTIONAL_REQUIREMENTS_FILE}。"
    )


def _load_failed_message() -> str:
    return (
        f"加载可选依赖 {_REQUIREMENT_NAME} 失败；"
        f"请确认当前环境使用 Python 3.8 x64，并已按 {_OPTIONAL_REQUIREMENTS_FILE} 安装。"
    )


def _version_mismatch_message(version: str) -> str:
    return "NetworkX 版本不兼容：当前 {}，期望 {}。".format(version or "unknown", _EXPECTED_VERSION)


def import_networkx() -> Any:
    """
    Lazily import NetworkX.

    Design contract:
    - graph_analysis_mode=off must not require NetworkX to be installed.
    - report/on mode calls this function before using graph algorithms.
    - only networkx==3.1 is accepted for Python 3.8 / Win7 compatibility.
    """
    try:
        nx = importlib.import_module("networkx")
    except ImportError as exc:
        raise NetworkXUnavailable(_missing_message()) from exc
    except Exception as exc:
        raise NetworkXUnavailable(_load_failed_message()) from exc

    version = _module_version(nx)
    if version != _EXPECTED_VERSION:
        raise NetworkXUnavailable(_version_mismatch_message(version))

    return nx
