from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Tuple

from .launcher_observability import launcher_log_warning
from .launcher_paths import state_contract_paths

ENDPOINT_STATUS_MISSING = "missing"
ENDPOINT_STATUS_VALID = "valid"
ENDPOINT_STATUS_INVALID = "invalid"
ENDPOINT_STATUS_UNREADABLE = "unreadable"
ENDPOINT_STATUS_EMPTY = "empty"


@dataclass(frozen=True)
class RuntimeEndpointReadResult:
    state_dir: str
    host: str
    port: int
    host_status: str
    port_status: str
    host_path: str
    port_path: str
    host_error: str = ""
    port_error: str = ""

    @property
    def host_present(self) -> bool:
        return self.host_status != ENDPOINT_STATUS_MISSING

    @property
    def port_present(self) -> bool:
        return self.port_status != ENDPOINT_STATUS_MISSING

    @property
    def incomplete(self) -> bool:
        return self.host_present != self.port_present

    @property
    def both_missing(self) -> bool:
        return not self.host_present and not self.port_present

    @property
    def uncertain(self) -> bool:
        uncertain_statuses = {
            ENDPOINT_STATUS_EMPTY,
            ENDPOINT_STATUS_INVALID,
            ENDPOINT_STATUS_UNREADABLE,
        }
        return (
            self.incomplete
            or self.host_status in uncertain_statuses
            or self.port_status in uncertain_statuses
        )

    def as_legacy_dict(self) -> Dict[str, Any]:
        return {
            "host": self.host,
            "port": self.port,
            "host_exists": os.path.exists(self.host_path),
            "port_exists": os.path.exists(self.port_path),
        }


def read_runtime_endpoint_files_result(state_dir: str) -> RuntimeEndpointReadResult:
    host_path, port_path, _db_path, _contract_path = state_contract_paths(state_dir)
    host, host_status, host_error = _read_host_file(host_path)
    port, port_status, port_error = _read_port_file(port_path)
    return RuntimeEndpointReadResult(
        state_dir=str(state_dir),
        host=host,
        port=port,
        host_status=host_status,
        port_status=port_status,
        host_path=host_path,
        port_path=port_path,
        host_error=host_error,
        port_error=port_error,
    )


def read_runtime_endpoint_files(state_dir: str) -> Dict[str, Any]:
    return read_runtime_endpoint_files_result(state_dir).as_legacy_dict()


def _read_host_file(path: str) -> Tuple[str, str, str]:
    if not os.path.exists(path):
        return "", ENDPOINT_STATUS_MISSING, ""
    value, error = _read_existing_endpoint_text(path)
    if error:
        return "", ENDPOINT_STATUS_UNREADABLE, error
    value = value.strip()
    if not value:
        return "", ENDPOINT_STATUS_EMPTY, "host_empty"
    return value, ENDPOINT_STATUS_VALID, ""


def _read_port_file(path: str) -> Tuple[int, str, str]:
    if not os.path.exists(path):
        return 0, ENDPOINT_STATUS_MISSING, ""
    value, error = _read_existing_endpoint_text(path)
    if error:
        return 0, ENDPOINT_STATUS_UNREADABLE, error
    value = value.strip()
    if not value:
        launcher_log_warning(None, "运行时端口文件为空：path=%s", path, state_dir=os.path.dirname(path))
        return 0, ENDPOINT_STATUS_EMPTY, "port_empty"
    if not value.isdecimal():
        launcher_log_warning(None, "运行时端口文件内容非法：path=%s value=%r", path, value, state_dir=os.path.dirname(path))
        return 0, ENDPOINT_STATUS_INVALID, "port_not_integer"
    port = int(value)
    if port <= 0:
        launcher_log_warning(None, "运行时端口文件内容不是正端口：path=%s value=%r", path, value, state_dir=os.path.dirname(path))
        return 0, ENDPOINT_STATUS_INVALID, "port_not_positive"
    return port, ENDPOINT_STATUS_VALID, ""


def _read_existing_endpoint_text(path: str) -> Tuple[str, str]:
    try:
        with open(path, encoding="utf-8") as f:
            return (f.read() or "").strip(), ""
    except Exception as exc:
        launcher_log_warning(None, "读取运行时端点文件失败：path=%s error=%s", path, exc, state_dir=os.path.dirname(path))
        return "", str(exc)
