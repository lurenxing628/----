from __future__ import annotations

import json
import os
import stat
from typing import Any, Optional

_O_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)


class UnsafeFixedFileError(OSError):
    """固定名运行文件不是普通文件时抛出，避免软链接借壳读写。"""


def _path_text(path: Any) -> str:
    return os.fspath(path)


def _is_regular_mode(mode: int) -> bool:
    return stat.S_ISREG(int(mode))


def _has_multiple_links(st: Any) -> bool:
    try:
        return int(getattr(st, "st_nlink", 1) or 1) > 1
    except (TypeError, ValueError):
        return False


def _raise_if_hardlinked(st: Any, path_s: str) -> None:
    if _has_multiple_links(st):
        raise UnsafeFixedFileError(f"拒绝处理硬链接固定文件：{path_s}")


def _guard_fixed_file_parent(path_s: str, *, ensure_parent: bool = False) -> None:
    """守护固定文件的【直接父目录】，并按需创建它。

    只拒绝【直接父目录】是软链接，不再逐级遍历整条祖先链：把数据/备份/日志根目录
    软链接到真实存储（外置盘、统一挂载点等）是常见且合法的部署，逐级否决祖先链会
    误伤正常运行（备份、启动契约、密钥写入会全部失败）。但直接父目录是软链接仍然
    拒绝——它无法与"借壳指向外部目录"区分，保持 fail-loud。固定文件【本身】被软链接
    或硬链接借壳，另由打开时 O_NOFOLLOW + 打开后 fstat 复核 + 前后 stat 比对兜住。
    """
    parent = os.path.dirname(os.path.abspath(path_s))
    if not parent:
        return
    if ensure_parent:
        os.makedirs(parent, exist_ok=True)
    try:
        st = os.lstat(parent)
    except FileNotFoundError:
        return
    if stat.S_ISLNK(st.st_mode):
        raise UnsafeFixedFileError(f"拒绝处理软链接目录中的固定文件：{path_s}")


def stat_regular_file(path: Any):
    path_s = _path_text(path)
    _guard_fixed_file_parent(path_s)
    st = os.lstat(path_s)
    if stat.S_ISLNK(st.st_mode):
        raise UnsafeFixedFileError(f"拒绝处理软链接固定文件：{path_s}")
    if not _is_regular_mode(st.st_mode):
        raise UnsafeFixedFileError(f"拒绝处理非普通固定文件：{path_s}")
    _raise_if_hardlinked(st, path_s)
    return st


def is_regular_file(path: Any) -> bool:
    try:
        stat_regular_file(path)
        return True
    except FileNotFoundError:
        return False
    except (OSError, TypeError, ValueError):
        return False


def _ensure_parent(path_s: str) -> None:
    _guard_fixed_file_parent(path_s, ensure_parent=True)


def _raise_if_fd_not_regular(fd: int, path_s: str) -> None:
    st = os.fstat(fd)
    if not _is_regular_mode(st.st_mode):
        raise UnsafeFixedFileError(f"拒绝处理非普通固定文件：{path_s}")
    _raise_if_hardlinked(st, path_s)


def _same_regular_file_stat(left: Any, right: Any) -> bool:
    try:
        return os.path.samestat(left, right)
    except (AttributeError, OSError, TypeError, ValueError):
        return (
            getattr(left, "st_dev", None) == getattr(right, "st_dev", None)
            and getattr(left, "st_ino", None) == getattr(right, "st_ino", None)
        )


def _fd_regular_stat(fd: int, path_s: str):
    st = os.fstat(fd)
    if not _is_regular_mode(st.st_mode):
        raise UnsafeFixedFileError(f"拒绝处理非普通固定文件：{path_s}")
    _raise_if_hardlinked(st, path_s)
    return st


def _raise_if_fd_is_not_expected_regular_file(fd: int, path_s: str, expected_stat: Any) -> None:
    fd_stat = _fd_regular_stat(fd, path_s)
    if not _same_regular_file_stat(fd_stat, expected_stat):
        raise UnsafeFixedFileError(f"固定文件在处理过程中被替换：{path_s}")


def _raise_if_path_is_not_expected_regular_file(path_s: str, expected_stat: Any) -> None:
    current = stat_regular_file(path_s)
    if not _same_regular_file_stat(current, expected_stat):
        raise UnsafeFixedFileError(f"固定文件在处理过程中被替换：{path_s}")


def read_fixed_bytes(path: Any) -> bytes:
    path_s = _path_text(path)
    expected_stat = stat_regular_file(path_s)
    fd = os.open(path_s, os.O_RDONLY | _O_NOFOLLOW)
    try:
        _raise_if_fd_is_not_expected_regular_file(fd, path_s, expected_stat)
        with os.fdopen(fd, "rb") as f:
            fd = -1
            return f.read()
    finally:
        if fd >= 0:
            os.close(fd)


def read_fixed_text(path: Any, *, encoding: str = "utf-8", errors: Optional[str] = None) -> str:
    data = read_fixed_bytes(path)
    return data.decode(encoding, errors=errors or "strict")


def read_fixed_json(path: Any, *, encoding: str = "utf-8") -> Any:
    return json.loads(read_fixed_text(path, encoding=encoding))


def _raise_if_existing_path_unsafe(path_s: str, *, replace_symlink: bool = False):
    _guard_fixed_file_parent(path_s)
    try:
        st = os.lstat(path_s)
    except FileNotFoundError:
        return None
    if stat.S_ISLNK(st.st_mode):
        if replace_symlink:
            os.remove(path_s)
            return None
        raise UnsafeFixedFileError(f"拒绝覆盖软链接固定文件：{path_s}")
    if not _is_regular_mode(st.st_mode):
        raise UnsafeFixedFileError(f"拒绝覆盖非普通固定文件：{path_s}")
    _raise_if_hardlinked(st, path_s)
    return st


def _open_new_fixed_file_for_write(path_s: str) -> int:
    fd = os.open(path_s, os.O_WRONLY | os.O_CREAT | os.O_EXCL | _O_NOFOLLOW, 0o600)
    try:
        fd_stat = _fd_regular_stat(fd, path_s)
        _raise_if_path_is_not_expected_regular_file(path_s, fd_stat)
        return fd
    except Exception:
        os.close(fd)
        raise


def _open_existing_fixed_file_for_write(path_s: str, expected_stat: Any, *, append: bool) -> int:
    flags = os.O_WRONLY | (os.O_APPEND if append else 0) | _O_NOFOLLOW
    fd = os.open(path_s, flags, 0o600)
    try:
        _raise_if_fd_is_not_expected_regular_file(fd, path_s, expected_stat)
        _raise_if_path_is_not_expected_regular_file(path_s, expected_stat)
        if not append:
            os.ftruncate(fd, 0)
            os.lseek(fd, 0, os.SEEK_SET)
        return fd
    except Exception:
        os.close(fd)
        raise


def open_fixed_file_for_write(
    path: Any,
    *,
    append: bool = False,
    ensure_parent: bool = True,
    replace_symlink: bool = False,
):
    path_s = _path_text(path)
    if ensure_parent:
        _ensure_parent(path_s)
    expected_stat = _raise_if_existing_path_unsafe(path_s, replace_symlink=replace_symlink)
    try:
        if expected_stat is None:
            fd = _open_new_fixed_file_for_write(path_s)
        else:
            fd = _open_existing_fixed_file_for_write(path_s, expected_stat, append=append)
    except FileExistsError as exc:
        raise UnsafeFixedFileError(f"固定文件在创建过程中被替换或占用：{path_s}") from exc
    try:
        mode = "a" if append else "w"
        f = os.fdopen(fd, mode, encoding="utf-8")
        fd = -1
        return f
    finally:
        if fd >= 0:
            os.close(fd)


def write_fixed_text(
    path: Any,
    text: Any,
    *,
    append: bool = False,
    ensure_parent: bool = True,
    replace_symlink: bool = False,
) -> None:
    # 固定运行文件统一以 UTF-8 落盘（open_fixed_file_for_write 内部固定 UTF-8）。
    path_s = _path_text(path)
    data = str(text)
    with open_fixed_file_for_write(
        path_s,
        append=append,
        ensure_parent=ensure_parent,
        replace_symlink=replace_symlink,
    ) as f:
        f.write(data)


def write_fixed_json(
    path: Any,
    payload: Any,
    *,
    ensure_ascii: bool = False,
    indent: Optional[int] = 2,
    sort_keys: bool = True,
    ensure_parent: bool = True,
    replace_symlink: bool = False,
) -> None:
    text = json.dumps(payload, ensure_ascii=ensure_ascii, indent=indent, sort_keys=sort_keys) + "\n"
    write_fixed_text(path, text, ensure_parent=ensure_parent, replace_symlink=replace_symlink)


def create_fixed_file_exclusive(path: Any, *, ensure_parent: bool = True) -> int:
    path_s = _path_text(path)
    if ensure_parent:
        _ensure_parent(path_s)
    else:
        _guard_fixed_file_parent(path_s)
    fd = os.open(path_s, os.O_CREAT | os.O_EXCL | os.O_WRONLY | _O_NOFOLLOW, 0o600)
    try:
        _raise_if_fd_not_regular(fd, path_s)
        return fd
    except Exception:
        os.close(fd)
        # 清理刚以 O_EXCL 创建、但安全校验未通过的残留空文件，避免污染后续独占创建。
        try:
            os.remove(path_s)
        except OSError:
            pass
        raise


def same_regular_file_stat(left: Any, right: Any) -> bool:
    return _same_regular_file_stat(left, right)


def assert_same_regular_file(path: Any, expected_stat: Any) -> None:
    path_s = _path_text(path)
    current = stat_regular_file(path_s)
    if not same_regular_file_stat(current, expected_stat):
        raise UnsafeFixedFileError(f"固定文件在处理过程中被替换：{path_s}")


def open_fixed_file_for_read_binary(path: Any):
    path_s = _path_text(path)
    expected_stat = stat_regular_file(path_s)
    fd = os.open(path_s, os.O_RDONLY | _O_NOFOLLOW)
    try:
        _raise_if_fd_is_not_expected_regular_file(fd, path_s, expected_stat)
        f = os.fdopen(fd, "rb")
        fd = -1
        return f
    finally:
        if fd >= 0:
            os.close(fd)


def remove_fixed_file(path: Any, *, missing_ok: bool = True, allow_symlink: bool = False) -> bool:
    path_s = _path_text(path)
    _guard_fixed_file_parent(path_s)
    try:
        st = os.lstat(path_s)
    except FileNotFoundError:
        if missing_ok:
            return False
        raise
    if stat.S_ISLNK(st.st_mode):
        if not allow_symlink:
            raise UnsafeFixedFileError(f"拒绝删除软链接固定文件：{path_s}")
        os.remove(path_s)
        return True
    if not _is_regular_mode(st.st_mode):
        raise UnsafeFixedFileError(f"拒绝删除非普通固定文件：{path_s}")
    _raise_if_hardlinked(st, path_s)
    os.remove(path_s)
    return True
