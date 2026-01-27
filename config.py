import os
import sys
from pathlib import Path


class Config:
    """应用配置（V1 最终）"""

    # 运行根目录：
    # - 开发/源码运行：仓库根目录（config.py 所在目录）
    # - PyInstaller onedir 打包后：exe 所在目录（确保 db/logs/backups/templates/static 等均落在交付目录中）
    try:
        BASE_DIR = str(Path(sys.executable).resolve().parent) if getattr(sys, "frozen", False) else str(Path(__file__).resolve().parent)
    except Exception:
        # 兜底：保证为绝对路径且不为空
        BASE_DIR = os.path.abspath(
            (os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(__file__ or "")) or "."
        )

    # 基础配置
    SECRET_KEY = os.environ.get("SECRET_KEY") or "aps-dev-key"

    # 应用名（用于日志等）
    APP_NAME = "APS"

    # 数据库
    # 说明：为便于测试/排障，允许用环境变量覆盖默认路径
    DATABASE_PATH = os.environ.get("APS_DB_PATH") or os.path.join(BASE_DIR, "db", "aps.db")

    # 日志
    LOG_DIR = os.environ.get("APS_LOG_DIR") or os.path.join(BASE_DIR, "logs")
    LOG_LEVEL = "INFO"  # DEBUG/INFO/WARNING/ERROR
    LOG_MAX_BYTES = 10 * 1024 * 1024  # 10MB
    LOG_BACKUP_COUNT = 5

    # 备份
    BACKUP_DIR = os.environ.get("APS_BACKUP_DIR") or os.path.join(BASE_DIR, "backups")
    BACKUP_KEEP_DAYS = 7

    # Excel模板
    EXCEL_TEMPLATE_DIR = os.environ.get("APS_EXCEL_TEMPLATE_DIR") or os.path.join(BASE_DIR, "templates_excel")

    # 排产默认配置（Phase 1 仅占位，后续模块会真正使用）
    DEFAULT_HOURS_PER_DAY = 8
    DEFAULT_SORT_STRATEGY = "priority_first"
    DEFAULT_PRIORITY_WEIGHT = 0.4
    DEFAULT_DUE_WEIGHT = 0.5
    DEFAULT_READY_WEIGHT = 0.1

    # 甘特图静态资源（Phase 1 不落地，但保留配置键）
    FRAPPE_GANTT_JS = os.path.join(BASE_DIR, "static", "js", "frappe-gantt.min.js")
    FRAPPE_GANTT_CSS = os.path.join(BASE_DIR, "static", "css", "frappe-gantt.css")


class DevelopmentConfig(Config):
    DEBUG = True
    LOG_LEVEL = "DEBUG"


class ProductionConfig(Config):
    DEBUG = False
    LOG_LEVEL = "INFO"


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}

