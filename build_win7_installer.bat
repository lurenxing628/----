@echo off
rem Win7 main installer pipeline: onedir -> ISCC build

setlocal EnableExtensions
pushd "%~dp0" >nul 2>&1
if errorlevel 1 exit /b 1
chcp 65001 >nul 2>&1

set "PF=%ProgramFiles%"
set "PF86=%ProgramFiles(x86)%"
set "LOG_DIR=%CD%\installer\output"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" >nul 2>&1
set "LOG=%LOG_DIR%\build_win7_installer.log"

echo [installer] repo: %CD%
echo [installer] log : %LOG%
echo ===============================> "%LOG%"
echo [installer] %date% %time%>> "%LOG%"
echo [installer] repo=%CD%>> "%LOG%"
echo ===============================>> "%LOG%"

echo.
echo [installer] Step 1/2: PyInstaller onedir...
call build_win7_onedir.bat >> "%LOG%" 2>&1
if errorlevel 1 goto :onedir_failed

set "DIST_ROOT="
for /f "delims=" %%E in ('dir /b /s "%CD%\dist\*.exe" 2^>nul') do if not defined DIST_ROOT set "DIST_ROOT=%%~dpE"
if not defined DIST_ROOT goto :dist_missing

set "LAUNCHER_FILE=%CD%\assets\启动_排产系统_Chrome.bat"
if not exist "%LAUNCHER_FILE%" goto :launcher_missing
copy /y "%LAUNCHER_FILE%" "%DIST_ROOT%" >> "%LOG%" 2>&1
if errorlevel 1 goto :launcher_copy_failed

echo.
echo [installer] Step 2/2: build main setup.exe (Inno Setup)...
call :find_iscc
if not defined ISCC goto :iscc_missing

echo [installer] ISCC: "%ISCC%"
"%ISCC%" "installer\aps_win7.iss" >> "%LOG%" 2>&1
if errorlevel 1 goto :iscc_failed

echo.
echo [installer] DONE: installer\output\APS_Main_Setup.exe
echo [installer] done>> "%LOG%"
if exist "%CD%\installer\output\APS_Main_Setup.exe" start "" explorer.exe /select,"%CD%\installer\output\APS_Main_Setup.exe" >nul 2>&1
popd >nul 2>&1
endlocal & exit /b 0

:onedir_failed
echo [installer] onedir failed. See log: %LOG%
echo [installer] onedir_failed>> "%LOG%"
start "" notepad "%LOG%" >nul 2>&1
pause
popd >nul 2>&1
endlocal & exit /b 2

:dist_missing
echo [installer] dist output directory not found after onedir build. See log: %LOG%
echo [installer] dist_missing>> "%LOG%"
start "" notepad "%LOG%" >nul 2>&1
pause
popd >nul 2>&1
endlocal & exit /b 11

:launcher_missing
echo [installer] launcher file missing: %LAUNCHER_FILE%
echo [installer] launcher_missing>> "%LOG%"
start "" notepad "%LOG%" >nul 2>&1
pause
popd >nul 2>&1
endlocal & exit /b 13

:launcher_copy_failed
echo [installer] launcher copy failed. See log: %LOG%
echo [installer] launcher_copy_failed>> "%LOG%"
start "" notepad "%LOG%" >nul 2>&1
pause
popd >nul 2>&1
endlocal & exit /b 14

:iscc_missing
echo [installer] ISCC.exe not found.
echo [installer] Install Inno Setup 6.x or set INNO_HOME (folder contains ISCC.exe).
echo [installer] Example: set INNO_HOME="%PF86%\Inno Setup 6"
echo [installer] iscc_not_found>> "%LOG%"
start "" notepad "%LOG%" >nul 2>&1
pause
popd >nul 2>&1
endlocal & exit /b 10

:iscc_failed
echo [installer] ISCC failed. See log: %LOG%
echo [installer] iscc_failed>> "%LOG%"
start "" notepad "%LOG%" >nul 2>&1
pause
popd >nul 2>&1
endlocal & exit /b 12

:find_iscc
set "ISCC="
if defined ISCC_EXE if exist "%ISCC_EXE%" set "ISCC=%ISCC_EXE%" & goto :eof
if defined INNO_HOME if exist "%INNO_HOME%\ISCC.exe" set "ISCC=%INNO_HOME%\ISCC.exe" & goto :eof
if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" & goto :eof
if exist "%PF86%\Inno Setup 6\ISCC.exe" set "ISCC=%PF86%\Inno Setup 6\ISCC.exe" & goto :eof
if exist "%PF%\Inno Setup 6\ISCC.exe" set "ISCC=%PF%\Inno Setup 6\ISCC.exe" & goto :eof
for /f "delims=" %%I in ('where ISCC.exe 2^>nul') do if not defined ISCC set "ISCC=%%I"
goto :eof

