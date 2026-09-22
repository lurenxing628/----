@echo off
chcp 65001 >nul 2>&1
setlocal EnableExtensions
pushd "%~dp0" >nul 2>&1
if errorlevel 1 exit /b 1
if exist ".venv-win7-build\Scripts\activate.bat" call ".venv-win7-build\Scripts\activate.bat"
powershell -NoProfile -ExecutionPolicy Bypass -File ".limcode\skills\aps-package-win7\scripts\package_win7.ps1"
set "RC=%ERRORLEVEL%"
popd >nul 2>&1
endlocal & exit /b %RC%
