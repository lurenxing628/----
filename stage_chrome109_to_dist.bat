@echo off
REM Stage offline Chrome109 into dist\排产系统\tools\chrome109
REM Requires: robocopy (built-in on Win7)

setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

REM Switch console to UTF-8 (optional)
chcp 65001 >nul 2>&1

set "SRC=%CD%\tools\Chrome.109.0.5414.120.x64"
set "DIST_ROOT=%CD%\dist\排产系统"
set "DST=%DIST_ROOT%\tools\chrome109"

echo [stage] repo: %CD%
echo [stage] src : %SRC%
echo [stage] dst : %DST%

if not exist "%DIST_ROOT%\排产系统.exe" (
  echo [stage] 未找到 dist 产物：%DIST_ROOT%\排产系统.exe
  echo [stage] 请先运行：build_win7_onedir.bat
  exit /b 2
)

if not exist "%SRC%\chrome.exe" (
  echo [stage] 未找到 Chrome 启动器：%SRC%\chrome.exe
  echo [stage] 请确认你已准备 Chrome 到 tools\Chrome.109.0.5414.120.x64\
  exit /b 3
)

if not exist "%DIST_ROOT%\tools" mkdir "%DIST_ROOT%\tools" >nul 2>&1

REM 覆盖式更新：先删旧目录，避免残留文件
if exist "%DST%" (
  echo [stage] 清理旧目录...
  rmdir /s /q "%DST%" >nul 2>&1
)

echo [stage] 复制中（可能需要一点时间）...
robocopy "%SRC%" "%DST%" /E /COPY:DAT /DCOPY:DAT /R:2 /W:1 /NFL /NDL /NJH /NJS /NP
set "RC=%ERRORLEVEL%"

REM robocopy: 0-7 视为成功；>=8 视为失败
if %RC% GEQ 8 (
  echo [stage] 复制失败（robocopy exit=%RC%）
  exit /b %RC%
)

if not exist "%DST%\chrome.exe" (
  echo [stage] 复制后仍未找到：%DST%\chrome.exe
  exit /b 4
)

echo [stage] 完成：%DST%
exit /b 0

