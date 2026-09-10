"""启动期配置解析：create_app 与"锁先于 create_app"的双开防线共用同一 config 源头。

锁的归属判定（should_own_runtime_resources）需要 DEBUG 标志，而它必须在 app 创建之前完成——
故配置类解析独立成模块，供 factory.create_app_core 与 entrypoint 启动期共用，杜绝两处口径分叉。
"""

from __future__ import annotations

import os
import sys

from config import config as config_map


def resolve_config_class():
    # 默认环境：源码运行→development（便于调试）；PyInstaller 打包→production（避免 reloader 多进程与副作用）。
    env = (os.environ.get("APS_ENV") or "").strip().lower()
    if not env:
        env = "production" if getattr(sys, "frozen", False) else "default"
    return config_map.get(env) or config_map["default"]


def resolve_startup_debug_flag() -> bool:
    # 运行时锁必须在 create_app 的一切共享库副作用（ensure_schema 迁移、atexit 退出备份注册）之前获取，
    # 而锁的归属判定需要 DEBUG 标志——此刻 app 尚未创建，故从 create_app 同一 config 源头独立解析。
    return bool(getattr(resolve_config_class(), "DEBUG", False))
