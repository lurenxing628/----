@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM 统一编码，避免中文在 cmd 下乱码
chcp 65001 >nul 2>&1

cd /d "%~dp0"

set APS_ENV=development
set FLASK_ENV=development

REM 让 Python 控制台输出使用 UTF-8（避免中文日志乱码）
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

echo 正在启动新前端测试服务器...
echo 提示：若端口 5000 被占用/受限，系统会自动选择可用端口（以 logs\aps_port.txt 为准）。
echo.

python app_new_ui.py
pause
