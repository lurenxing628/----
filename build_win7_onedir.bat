@echo off
rem Win7 build script (onedir)
rem Requirements:
rem - Python 3.8.x
rem - PyInstaller 4.10

setlocal EnableExtensions EnableDelayedExpansion
pushd "%~dp0" >nul 2>&1

rem Keep UTF-8 console for non-ASCII app name/path
chcp 65001 >nul 2>&1

echo [build] repo: %CD%

rem 1) Check PyInstaller
python -c "import PyInstaller; print(PyInstaller.__version__)" >nul 2>&1
if not %errorlevel%==0 (
  echo [build] PyInstaller not found. Please install: PyInstaller==4.10
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
if exist vendor (
  echo [build] include vendor directory.
  python -m PyInstaller --noconfirm --clean --onedir --windowed ^
    --add-data "templates;templates" ^
    --add-data "static;static" ^
    --add-data "web_new_test;web_new_test" ^
    --add-data "templates_excel;templates_excel" ^
    --add-data "plugins;plugins" ^
    --add-data "vendor;vendor" ^
    --add-data "schema.sql;." ^
    --name "排产系统" ^
    app.py
) else (
  echo [build] vendor 目录不存在，跳过 vendor 数据目录。
  python -m PyInstaller --noconfirm --clean --onedir --windowed ^
    --add-data "templates;templates" ^
    --add-data "static;static" ^
    --add-data "web_new_test;web_new_test" ^
    --add-data "templates_excel;templates_excel" ^
    --add-data "plugins;plugins" ^
    --add-data "schema.sql;." ^
    --name "排产系统" ^
    app.py
)
set "RC=%ERRORLEVEL%"

echo.
if %RC%==0 (
  echo [build] PASS. dist folder created.
  echo [build] Next: python validate_dist_exe.py
) else (
  echo [build] FAIL (exit=%RC%)
)

popd >nul 2>&1
endlocal & exit /b %RC%
