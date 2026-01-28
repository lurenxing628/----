@echo off
chcp 65001 >nul
echo 正在启动新前端测试服务器...
echo.
cd /d "%~dp0"
python app_new_ui.py
pause
