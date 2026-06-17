"""首页备份健康提示 viewmodel（fusion-backup-health-hint）。

BACKUP_STALE_DAYS 是「多久没备份要提醒」阈值的唯一真相源——与 BackupManager
的 keep_days=7 是不同语义（那是清理保留期），值巧合相同，刻意不共享常量。

分两层：read_latest_backup_time 是 IO 读取层（纯只读扫描，OSError 穿透），
build_backup_health_hint 是纯决策层（四态：失败明示/从未备份/超期/健康）。
刻意不实例化 BackupManager——其 __init__ 有 os.makedirs 副作用，首页访问
创建目录违反只读契约，且会把「目录不存在」态偷改成「空目录」态。
"""

from __future__ import annotations

import os
import stat as stat_module
from datetime import datetime
from typing import Dict, Optional

BACKUP_STALE_DAYS = 7


class UnsafeBackupPathError(OSError):
    """备份目录/文件不是安全的普通目录或文件（软链接/硬链接借壳等）。

    刻意是 OSError 子类：首页路由统一 `except OSError` 接住并降级为「读取失败」明示；
    且本异常定义在 viewmodel 内，避免 viewmodel 导入 core.infrastructure（架构门禁
    禁止 viewmodel 导入 core 非 models 子包）。语义与 safe_files.UnsafeFixedFileError
    一致，但分属两层、互不依赖。
    """

_BACKUP_PREFIX = "aps_backup_"
_BACKUP_SUFFIX = ".db"

_GO_BACKUP_GUIDE = "请到「系统管理 → 数据备份」页执行备份。"


def read_latest_backup_time(backup_dir: str) -> Optional[datetime]:
    """纯只读扫描 backup_dir，返回 aps_backup_*.db 的最大 mtime；无备份返回 None。

    仅 os.listdir 的 FileNotFoundError 归「从未备份」（目录不存在与空目录对
    用户语义相同）；NotADirectoryError（路径被文件挡住=配置错误）、权限失败、
    单文件 stat 失败等其余 OSError 一律穿透——不许把读取失败洗成「从未备份」。
    刻意不用 os.path.isdir 先判：py38 的 isdir 内部吞 OSError 返回 False，
    会把权限失败伪装成目录不存在。
    """
    try:
        dir_info = os.lstat(backup_dir)
    except FileNotFoundError:
        return None
    if stat_module.S_ISLNK(dir_info.st_mode):
        raise UnsafeBackupPathError(f"备份目录不是安全目录：{backup_dir}")
    if not stat_module.S_ISDIR(dir_info.st_mode):
        raise NotADirectoryError(f"备份目录不是目录：{backup_dir}")

    try:
        names = os.listdir(backup_dir)
    except FileNotFoundError:
        return None

    latest_mtime: Optional[float] = None
    for name in names:
        if not (name.startswith(_BACKUP_PREFIX) and name.endswith(_BACKUP_SUFFIX)):
            continue
        info = os.lstat(os.path.join(backup_dir, name))
        if stat_module.S_ISLNK(info.st_mode):
            raise UnsafeBackupPathError(f"备份文件不是安全的普通文件：{name}")
        if not stat_module.S_ISREG(info.st_mode):
            continue  # 备份只会是普通文件；误放的同名目录不参与计时
        if int(getattr(info, "st_nlink", 1) or 1) > 1:
            raise UnsafeBackupPathError(f"备份文件不是安全的普通文件：{name}")
        if latest_mtime is None or info.st_mtime > latest_mtime:
            latest_mtime = info.st_mtime
    if latest_mtime is None:
        return None
    return datetime.fromtimestamp(latest_mtime)


def build_backup_health_hint(
    *,
    latest: Optional[datetime],
    read_error: Optional[str],
    now: datetime,
) -> Optional[Dict[str, str]]:
    """四态决策：读取失败明示 / 从未备份 / 超期 N 天 / 健康（None，首页零噪音）。

    天数用日历日差（date 相减）而非 86400 秒整除——「昨天备份的」显示 1 天
    而非 0 天，符合用户直觉；恰好 7 天不提示，第 8 天起提示（> 语义）。
    """
    if read_error:
        return {
            "title": "备份状态读取失败",
            "body": f"无法读取备份目录：{read_error}。请检查备份目录后重试。",
            "tone": "warning",
        }
    if latest is None:
        return {
            "title": "尚未发现任何备份",
            "body": "还没有任何数据库备份，建议尽快备份一次。" + _GO_BACKUP_GUIDE,
            "tone": "warning",
        }
    stale_days = (now.date() - latest.date()).days
    if stale_days <= BACKUP_STALE_DAYS:
        return None
    return {
        "title": f"已 {stale_days} 天未备份",
        "body": "最近一次备份是 {}。".format(latest.strftime("%Y-%m-%d %H:%M"))
        + _GO_BACKUP_GUIDE,
        "tone": "warning",
    }
