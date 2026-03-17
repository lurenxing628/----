@echo off
REM 开发/调试启动脚本（目标机打包后直接运行 exe，不需要此脚本）

setlocal EnableExtensions EnableDelayedExpansion

REM 统一编码，避免中文在 cmd 下乱码
chcp 65001 >nul 2>&1

set APS_ENV=development
set FLASK_ENV=development

REM 让 Python 控制台输出使用 UTF-8（避免中文日志乱码）
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

echo [start] 非破坏式开发启动，不再强制清理固定端口。
echo [start] 实际访问地址以 logs\aps_host.txt 和 logs\aps_port.txt 为准。

python app.py

