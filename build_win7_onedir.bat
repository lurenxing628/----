@echo off
rem Win7 build script (onedir)
rem Requirements:
rem - Python 3.8.x
rem - PyInstaller 4.10

setlocal EnableExtensions DisableDelayedExpansion
pushd "%~dp0" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Failed to switch to repository root: "%~dp0"
    exit /b 1
)

rem Keep UTF-8 console for non-ASCII app name/path
chcp 65001 >nul 2>&1

echo [build] repo: %CD%

rem 1) Check Python, offline dependencies, and vendor wheels before deleting build artifacts
python scripts\check_win7_build.py
if not %errorlevel%==0 (
  echo [build] Win7 build preflight failed. Run setup_win7_build.bat first.
  popd >nul 2>&1
  endlocal & exit /b 2
)

rem 2) Clean old artifacts (optional)
if exist build rmdir /s /q build >nul 2>&1
if exist build (
  echo [build] 清理 build 目录失败。
  popd >nul 2>&1
  endlocal & exit /b 3
)
if exist dist rmdir /s /q dist >nul 2>&1
if exist dist (
  echo [build] 清理 dist 目录失败。
  popd >nul 2>&1
  endlocal & exit /b 4
)

rem 3) Build
echo [build] Run PyInstaller (onedir)...
echo [build] include vendor\wheels directory.
python -m PyInstaller --noconfirm --clean --onedir --windowed ^
  --add-data "templates;templates" ^
  --add-data "static;static" ^
  --add-data "templates_excel;templates_excel" ^
  --add-data "plugins;plugins" ^
  --add-data "vendor\wheels;vendor\wheels" ^
  --add-data "schema.sql;." ^
  --hidden-import networkx ^
  --name "排产系统" ^
  app.py
set "RC=%ERRORLEVEL%"
if %RC%==0 (
  rem The onedir payload owns the launcher consumed by smoke tests and every installer.
  copy /y "assets\启动_排产系统_Chrome.bat" "dist\排产系统\启动_排产系统_Chrome.bat" >nul
  if errorlevel 1 set "RC=8"
  copy /y "assets\aps-launcher.ps1" "dist\排产系统\aps-launcher.ps1" >nul
  if errorlevel 1 set "RC=8"
)

echo.
if %RC%==0 (
  echo [build] PASS. dist folder created.
  echo [build] Next: python validate_dist_exe.py
) else (
  echo [build] FAIL (exit=%RC%)
)

popd >nul 2>&1
endlocal & exit /b %RC%
