"""启动配置选择只解析环境；实际配置映射由 factory 装配入口传入。"""

from __future__ import annotations

import os
import sys


def resolve_config_class(config_map):
    # 默认环境：源码运行→development（便于调试）；PyInstaller 打包→production（避免 reloader 多进程与副作用）。
    env = (os.environ.get("APS_ENV") or "").strip().lower()
    if not env:
        env = "production" if getattr(sys, "frozen", False) else "default"
    return config_map.get(env) or config_map["default"]
