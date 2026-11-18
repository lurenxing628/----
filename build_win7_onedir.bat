@echo off
rem Win7 build script (onedir)
rem Requirements:
rem - Python 3.8.x x64 in the isolated build venv created by setup_win7_build.bat
rem - PyInstaller 4.10

setlocal EnableExtensions DisableDelayedExpansion
set "ERRORLEVEL="
pushd "%~dp0" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Failed to switch to repository root: "%~dp0"
    exit /b 1
)

rem Keep UTF-8 console for non-ASCII app name/path
chcp 65001 >nul 2>&1

echo [build] repo: "%CD%"

rem 1) The isolated build venv is the only build interpreter; preflight and PyInstaller both use it by absolute path
set "APS_BUILD_PYTHON=%CD%\.venv-win7-build\Scripts\python.exe"
if not exist "%APS_BUILD_PYTHON%" (
  echo [build] .venv-win7-build\Scripts\python.exe not found. Run setup_win7_build.bat first.
  popd >nul 2>&1
  endlocal & exit /b 2
)
set "VIRTUAL_ENV=%CD%\.venv-win7-build"
set "PATH=%CD%\.venv-win7-build\Scripts;%PATH%"
set "PYTHONHOME="
echo [build] python: "%APS_BUILD_PYTHON%"

rem 2) Check Python, offline dependencies, SQLite JSON1, and vendor wheels before deleting build artifacts
"%APS_BUILD_PYTHON%" scripts\check_win7_build.py
if not %errorlevel%==0 (
  echo [build] Win7 build preflight failed. Run setup_win7_build.bat first.
  popd >nul 2>&1
  endlocal & exit /b 2
)

rem 3) Clean old artifacts
if exist build rmdir /s /q build >nul 2>&1
if exist build (
  echo [build] Failed to remove the build directory.
  popd >nul 2>&1
  endlocal & exit /b 3
)
if exist dist rmdir /s /q dist >nul 2>&1
if exist dist (
  echo [build] Failed to remove the dist directory.
  popd >nul 2>&1
  endlocal & exit /b 4
)

rem 4) Build
echo [build] Run PyInstaller (onedir)...
echo [build] include vendor\wheels directory.
"%APS_BUILD_PYTHON%" -m PyInstaller --noconfirm --clean --onedir --windowed ^
  --add-data "templates;templates" ^
  --add-data "static;static" ^
  --add-data "templates_excel;templates_excel" ^
  --add-data "vendor\wheels;vendor\wheels" ^
  --add-data "schema.sql;." ^
  --hidden-import networkx ^
  --name "排产系统" ^
  app.py
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" goto :report
copy /y "assets\启动_排产系统_Chrome.bat" "dist\排产系统\启动_排产系统_Chrome.bat" >nul
if errorlevel 1 set "RC=8"
copy /y "assets\aps-launcher.ps1" "dist\排产系统\aps-launcher.ps1" >nul
if errorlevel 1 set "RC=8"
if not "%RC%"=="0" goto :report
"%APS_BUILD_PYTHON%" scripts\portable_release.py check-sqlite "dist\排产系统"
if not "%ERRORLEVEL%"=="0" set "RC=9"

:report
echo.
if %RC%==0 (
  echo [build] PASS. dist folder created.
  echo [build] Next: "%APS_BUILD_PYTHON%" validate_dist_exe.py
) else (
  echo [build] FAIL ^(exit=%RC%^)
)

popd >nul 2>&1
endlocal & exit /b %RC%
