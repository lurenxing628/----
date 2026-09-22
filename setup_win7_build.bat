@echo off
chcp 65001 >nul 2>&1
setlocal EnableExtensions
pushd "%~dp0" >nul 2>&1
if errorlevel 1 exit /b 1
rem Run after installing Python 3.8 x64 on the BUILD machine only.
python -c "import sys,struct; sys.exit(0 if sys.version_info[:2]==(3,8) and struct.calcsize('P')==8 else 1)"
if errorlevel 1 goto :fail
python scripts\prepare_win7_offline.py verify
if errorlevel 1 goto :fail
if not exist ".venv-win7-build\Scripts\python.exe" python -m venv .venv-win7-build
if errorlevel 1 goto :fail
".venv-win7-build\Scripts\python.exe" -m pip install --no-index --find-links offline\win7\wheels --require-hashes -r requirements-win7-build.txt
if errorlevel 1 goto :fail
".venv-win7-build\Scripts\python.exe" scripts\check_win7_build.py
if errorlevel 1 goto :fail
copy /b /y "offline\win7\tools\ungoogled-chromium_109.0.5414.120-1.1_windows_x64.zip" "tools\ungoogled-chromium_109.0.5414.120-1.1_windows_x64.zip" >nul
if errorlevel 1 goto :fail
echo [setup] Ready. Run build_win7_portable.bat next.
popd >nul 2>&1
endlocal & exit /b 0
:fail
echo [setup] FAILED. See the error above. No package was built.
popd >nul 2>&1
endlocal & exit /b 1
