@echo off
REM 开发/调试启动脚本（目标机打包后直接运行 exe，不需要此脚本）

set APS_ENV=development
set FLASK_ENV=development

python app.py

