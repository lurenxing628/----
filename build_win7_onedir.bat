@echo off
REM Win7 打包脚本（onedir）
REM 说明：
REM - 必须在 Win7 环境使用 Python 3.8.x + PyInstaller 4.10 执行
REM - 目标机（交付机）无需安装 Python
REM - 本脚本不会联网；请提前准备好离线依赖（pip wheelhouse 或已安装环境）

setlocal EnableExtensions EnableDelayedExpansion
cd /d %~dp0

REM 统一编码，避免中文在 cmd 下乱码
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
pyinstaller --noconfirm --clean --onedir --windowed ^
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

