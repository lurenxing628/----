import os

from core.models.workbench_table_descriptor import DEFAULT_IMPORT_BYTE_LIMIT


class Config:
    """应用配置（V1 最终）"""

    # 基础配置
    # 注意：不提供弱默认值（如 "aps-dev-key"）。
    # SECRET_KEY 将由环境变量 SECRET_KEY 或 app.create_app() 内的运行时逻辑确保。
    SECRET_KEY = os.environ.get("SECRET_KEY")

    # 应用名（用于日志等）
    APP_NAME = "APS"

    # 日志
    LOG_LEVEL = "INFO"  # DEBUG/INFO/WARNING/ERROR
    LOG_MAX_BYTES = 10 * 1024 * 1024  # 10MB
    LOG_BACKUP_COUNT = 5

    # 备份
    BACKUP_KEEP_DAYS = 7

    # Excel模板
    # 上限的唯一来源是表描述协议：各表自己声明 byte_limit（批次 10MB、报工 8MB、
    # 其余按默认 16MB），传输层只需要放行其中最大的那个。原来这里独立写 16MB，
    # 说明书跟着写"统一 16MB"，而批次和报工在自己的读取器里另有更小的值，三处各说各的。
    EXCEL_MAX_UPLOAD_BYTES = DEFAULT_IMPORT_BYTE_LIMIT  # 16MB（Excel 文件本体）
    # multipart/form-data 会包含 boundary/header 等额外开销，请求体上限需略大于文件本体上限。
    MAX_CONTENT_LENGTH = EXCEL_MAX_UPLOAD_BYTES + 1 * 1024 * 1024


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

