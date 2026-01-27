@echo off
REM Win7 installer pipeline: onedir -> stage Chrome109 -> ISCC build
REM Note: offline build; requires tools\Chrome.109.0.5414.120.x64\

setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
chcp 65001 >nul 2>&1

REM Cache common paths (avoid parentheses parsing issues inside blocks)
set "PF=%ProgramFiles%"
set "PF86=%ProgramFiles(x86)%"

echo [installer] repo: %CD%
set "LOG_DIR=%CD%\installer\output"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" >nul 2>&1
set "LOG=%LOG_DIR%\build_win7_installer.log"
echo [installer] log : %LOG%
echo ===============================> "%LOG%"
echo [installer] %date% %time%>> "%LOG%"
echo [installer] repo=%CD%>> "%LOG%"
echo ===============================>> "%LOG%"

echo.
echo [installer] Step 1/3: PyInstaller onedir...
call build_win7_onedir.bat >> "%LOG%" 2>&1
set "RC=%errorlevel%"
if not %RC%==0 (
  echo [installer] onedir 打包失败（exit=%RC%）。请查看日志：%LOG%
  echo [installer] onedir_failed exit=%RC%>> "%LOG%"
  start "" notepad "%LOG%" >nul 2>&1
  pause
  exit /b %RC%
)

echo.
echo [installer] Step 2/3: 注入 Chrome109 到 dist...
call stage_chrome109_to_dist.bat >> "%LOG%" 2>&1
set "RC=%errorlevel%"
if not %RC%==0 (
  echo [installer] 注入 Chrome 失败（exit=%RC%）。请查看日志：%LOG%
  echo [installer] stage_chrome_failed exit=%RC%>> "%LOG%"
  start "" notepad "%LOG%" >nul 2>&1
  pause
  exit /b %RC%
)

REM 额外：把启动器也放进 dist，方便你不做安装包时直接用 dist 目录运行
if exist "assets\启动_排产系统_Chrome.bat" (
  copy /y "assets\启动_排产系统_Chrome.bat" "dist\排产系统\启动_排产系统_Chrome.bat" >> "%LOG%" 2>&1
)

echo.
echo [installer] Step 3/3: Inno Setup 编译 setup.exe...
call :find_iscc
if not defined ISCC (
  echo [installer] 未找到 ISCC.exe
  echo [installer] 请安装 Inno Setup 6.x，或设置环境变量 INNO_HOME 指向安装目录（包含 ISCC.exe）
  echo [installer] 示例：set INNO_HOME="!PF86!\Inno Setup 6"
  echo [installer] iscc_not_found>> "%LOG%"
  start "" notepad "%LOG%" >nul 2>&1
  pause
  exit /b 10
)

echo [installer] ISCC: "%ISCC%"
"%ISCC%" "installer\aps_win7.iss" >> "%LOG%" 2>&1
set "RC=%errorlevel%"
if not %RC%==0 (
  echo [installer] ISCC 编译失败（exit=%RC%）。请查看日志：%LOG%
  echo [installer] iscc_failed exit=%RC%>> "%LOG%"
  start "" notepad "%LOG%" >nul 2>&1
  pause
  exit /b %RC%
)

echo.
echo [installer] DONE: installer\output\APS_Win7_Setup.exe
echo [installer] done>> "%LOG%"
if exist "%CD%\installer\output\APS_Win7_Setup.exe" (
  start "" explorer.exe /select,"%CD%\installer\output\APS_Win7_Setup.exe" >nul 2>&1
)
exit /b 0

:find_iscc
set "ISCC="

REM 允许用户覆盖
if defined ISCC_EXE (
  if exist "%ISCC_EXE%" set "ISCC=%ISCC_EXE%" & goto :eof
)
if defined INNO_HOME (
  if exist "%INNO_HOME%\ISCC.exe" set "ISCC=%INNO_HOME%\ISCC.exe" & goto :eof
)

REM 用户级安装（winget --silent 常见落点）
if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" & goto :eof

REM 常见默认安装路径
if exist "!PF86!\Inno Setup 6\ISCC.exe" set "ISCC=!PF86!\Inno Setup 6\ISCC.exe" & goto :eof
if exist "!PF!\Inno Setup 6\ISCC.exe" set "ISCC=!PF!\Inno Setup 6\ISCC.exe" & goto :eof

REM 兜底：PATH 里查找
for /f "delims=" %%I in ('where ISCC.exe 2^>nul') do (
  set "ISCC=%%I"
  goto :eof
)
goto :eof

