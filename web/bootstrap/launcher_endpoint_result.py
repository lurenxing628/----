from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Tuple

from core.infrastructure.safe_files import read_fixed_text

from .launcher_observability import launcher_log_warning
from .launcher_paths import state_contract_paths

ENDPOINT_STATUS_MISSING = "missing"
ENDPOINT_STATUS_VALID = "valid"
ENDPOINT_STATUS_INVALID = "invalid"
ENDPOINT_STATUS_UNREADABLE = "unreadable"
ENDPOINT_STATUS_EMPTY = "empty"


@dataclass(frozen=True)
class RuntimeEndpointReadResult:
    host: str
    port: int
    host_status: str
    port_status: str
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

def read_runtime_endpoint_files_result(state_dir: str) -> RuntimeEndpointReadResult:
    host_path, port_path, _db_path, _contract_path = state_contract_paths(state_dir)
    host, host_status, host_error = _read_host_file(host_path)
    port, port_status, port_error = _read_port_file(port_path)
    return RuntimeEndpointReadResult(
        host=host,
        port=port,
        host_status=host_status,
        port_status=port_status,
        host_error=host_error,
        port_error=port_error,
    )


def _read_host_file(path: str) -> Tuple[str, str, str]:
    value, error = _read_endpoint_text(path)
    if error == "missing":
        return "", ENDPOINT_STATUS_MISSING, ""
    if error:
        return "", ENDPOINT_STATUS_UNREADABLE, error
    if not value:
        return "", ENDPOINT_STATUS_EMPTY, "host_empty"
    return value, ENDPOINT_STATUS_VALID, ""


def _read_port_file(path: str) -> Tuple[int, str, str]:
    value, error = _read_endpoint_text(path)
    if error == "missing":
        return 0, ENDPOINT_STATUS_MISSING, ""
    if error:
        return 0, ENDPOINT_STATUS_UNREADABLE, error
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


def _read_endpoint_text(path: str) -> Tuple[str, str]:
    try:
        return read_fixed_text(path).strip(), ""
    except FileNotFoundError:
        return "", "missing"
    except (OSError, UnicodeError) as exc:
        launcher_log_warning(None, "读取运行时端点文件失败：path=%s error=%s", path, exc, state_dir=os.path.dirname(path))
        return "", str(exc)
