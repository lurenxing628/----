"""Win7-compatible process probes without spawning tasklist or PowerShell."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
from functools import lru_cache


def available() -> bool:
    return hasattr(ctypes, "WinDLL")


@lru_cache(maxsize=1)
def _kernel32():
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD),
    ]
    kernel.QueryFullProcessImageNameW.restype = wintypes.BOOL
    return kernel


def _open_process(kernel, pid: int, access: int):
    if pid <= 0 or pid > 0xFFFFFFFF:
        return None
    handle = kernel.OpenProcess(access, False, pid)
    if not handle:
        error = ctypes.get_last_error()
        if error == 87:  # ERROR_INVALID_PARAMETER: PID no longer exists.
            return None
        raise ctypes.WinError(error)
    return handle


def pid_exists(pid: int) -> bool:
    kernel = _kernel32()
    handle = _open_process(kernel, pid, 0x00100000)  # SYNCHRONIZE only.
    if not handle:
        return False
    try:
        result = kernel.WaitForSingleObject(handle, 0)
        if result == 0:  # Exited; the process object can outlive the process.
            return False
        if result == 258:  # WAIT_TIMEOUT: still running.
            return True
        raise ctypes.WinError(ctypes.get_last_error())
    finally:
        kernel.CloseHandle(handle)


def executable_path(pid: int) -> str:
    kernel = _kernel32()
    handle = _open_process(kernel, pid, 0x00101000)  # SYNCHRONIZE + QUERY_LIMITED_INFORMATION.
    if not handle:
        return ""
    try:
        state = kernel.WaitForSingleObject(handle, 0)
        if state == 0:
            return ""
        if state != 258:
            raise ctypes.WinError(ctypes.get_last_error())
        size = wintypes.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        if not kernel.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            raise ctypes.WinError(ctypes.get_last_error())
        if not size.value:
            raise OSError("Empty process image path")
        return buffer.value
    finally:
        kernel.CloseHandle(handle)
