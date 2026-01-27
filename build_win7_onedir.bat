@echo off
REM Win7 build script (onedir)
REM Notes:
REM - Run on Win7 with Python 3.8.x + PyInstaller 4.10
REM - Target machine does not require Python
REM - No network access; prepare offline dependencies in advance

setlocal EnableExtensions EnableDelayedExpansion
cd /d %~dp0

REM Switch console to UTF-8 (optional)
chcp 65001 >nul 2>&1

echo [build] 项目目录：%cd%

REM 1) 检查 PyInstaller 版本（必须 4.x）
python -c "import PyInstaller, sys; print(PyInstaller.__version__)" >nul 2>&1
if not %errorlevel%==0 (
  echo [build] 未检测到 PyInstaller。请先在打包机安装：PyInstaller==4.10
  exit /b 2
)

REM 2) 清理历史构建产物（可选）
if exist build rmdir /s /q build >nul 2>&1
if exist dist rmdir /s /q dist >nul 2>&1

REM 3) 开始打包
echo [build] 开始执行 PyInstaller（onedir）...
python -m PyInstaller --noconfirm --clean --onedir --windowed ^
  --add-data "templates;templates" ^
  --add-data "static;static" ^
  --add-data "templates_excel;templates_excel" ^
  --add-data "plugins;plugins" ^
  --add-data "vendor;vendor" ^
  --add-data "schema.sql;." ^
  --name "排产系统" ^
  app.py

echo.
if %errorlevel%==0 (
  echo [build] 打包完成：dist\排产系统\
  echo [build] 下一步建议执行：python validate_dist_exe.py "dist\排产系统\排产系统.exe"
) else (
  echo [build] 打包失败（错误码=%errorlevel%）
)

endlocal

