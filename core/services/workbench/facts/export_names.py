"""Shared filename presentation for strict factory-local snapshot timestamps."""

from datetime import datetime


def export_stamp(as_of):
    """Format a strict local second-resolution timestamp as a filename minute."""
    if type(as_of) is not str:
        raise ValueError("导出文件名需要形如 2026-09-21T16:46:05 的数据截至时间。")
    try:
        parsed = datetime.strptime(as_of, "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        raise ValueError("导出文件名需要形如 2026-09-21T16:46:05 的数据截至时间。") from None
    if parsed.strftime("%Y-%m-%dT%H:%M:%S") != as_of:
        raise ValueError("导出文件名需要形如 2026-09-21T16:46:05 的数据截至时间。")
    return parsed.strftime("%Y-%m-%d_%H%M")
