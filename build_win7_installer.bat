@echo off
rem Win7 main installer: package_win7.ps1 -MainOnly (ISCC, onedir, cold-start validation, Inno Setup).
chcp 65001 >nul 2>&1
setlocal EnableExtensions DisableDelayedExpansion
set "ERRORLEVEL="
if not "%1"=="" (
  >&2 echo [installer] build_win7_installer.bat takes no arguments.
  endlocal & exit /b 2
)
pushd "%~dp0" >nul 2>&1
if errorlevel 1 exit /b 1
rem package_win7.ps1 locates the build venv itself. -Command keeps the real exit code
rem even when this PowerShell cannot run the 5.1 packaging script.
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -NonInteractive -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; try { $global:LASTEXITCODE=0; & '.\.limcode\skills\aps-package-win7\scripts\package_win7.ps1' -MainOnly; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; exit 0 } catch { [Console]::Error.WriteLine('[installer] ERROR: ' + $_.Exception.Message); if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; exit 1 }"
set "RC=%ERRORLEVEL%"
popd >nul 2>&1
endlocal & exit /b %RC%
