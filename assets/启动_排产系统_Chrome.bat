@echo off
REM Launcher: start app first, then open URL with APS browser runtime
REM Place next to app exe (after install: {app}\)

setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul 2>&1

cd /d "%~dp0"

set "HOST=127.0.0.1"
set "PORT=5000"
if defined APS_HOST set "HOST=%APS_HOST%"
if defined APS_PORT set "PORT=%APS_PORT%"
set "MAX_WAIT=45"
set "PORT_FILE=%CD%\logs\aps_port.txt"
set "HOST_FILE=%CD%\logs\aps_host.txt"

set "APP_EXE=%CD%\排产系统.exe"
set "CHROME_EXE="
set "CHROME_SOURCE="
set "CHROME_DIR="
set "CHROME_PROFILE_DIR=%LOCALAPPDATA%\APS\Chrome109Profile"
if not defined LOCALAPPDATA set "CHROME_PROFILE_DIR=%CD%\chrome109_profile"

if not exist "%APP_EXE%" (
  echo [launcher] 未找到主程序：%APP_EXE%
  pause
  exit /b 1
)

if defined APS_CHROME_EXE (
  set "CHROME_EXE=%APS_CHROME_EXE:"=%"
  if exist "%CHROME_EXE%" (
    set "CHROME_SOURCE=APS_CHROME_EXE"
  ) else (
    echo [launcher] APS_CHROME_EXE 无效：%APS_CHROME_EXE%
    echo [launcher] 请修正 APS_CHROME_EXE，或清除该变量后改用 APS_CHROME_DIR / APS_Chrome109_Runtime.exe。
    pause
    exit /b 4
  )
)

if not defined CHROME_SOURCE if defined APS_CHROME_DIR (
  set "CHROME_DIR=%APS_CHROME_DIR:"=%"
  if exist "%CHROME_DIR%\chrome.exe" (
    set "CHROME_EXE=%CHROME_DIR%\chrome.exe"
    set "CHROME_SOURCE=APS_CHROME_DIR"
  )
)

if not defined CHROME_SOURCE if defined APS_CHROME_DIR (
  set "CHROME_DIR=%APS_CHROME_DIR:"=%"
  if exist "%CHROME_DIR%\App\chrome.exe" (
    set "CHROME_EXE=%CHROME_DIR%\App\chrome.exe"
    set "CHROME_SOURCE=APS_CHROME_DIR\App"
  )
)

if not defined CHROME_SOURCE if exist "%CD%\tools\chrome109\chrome.exe" (
  set "CHROME_EXE=%CD%\tools\chrome109\chrome.exe"
  set "CHROME_SOURCE=legacy tools\chrome109"
)

if not defined CHROME_SOURCE if exist "%CD%\tools\chrome109\App\chrome.exe" (
  set "CHROME_EXE=%CD%\tools\chrome109\App\chrome.exe"
  set "CHROME_SOURCE=legacy tools\chrome109\App"
)

if not defined CHROME_SOURCE (
  echo [launcher] 未找到浏览器运行时。
  echo [launcher] 处理方式：
  echo [launcher] 1. 安装 APS_Chrome109_Runtime.exe（推荐）
  echo [launcher] 2. 或设置 APS_CHROME_DIR=^<浏览器目录^>
  echo [launcher] 3. 或设置 APS_CHROME_EXE=^<chrome.exe 完整路径^>
  pause
  exit /b 2
)

if not exist "%CHROME_PROFILE_DIR%" mkdir "%CHROME_PROFILE_DIR%" >nul 2>&1

REM 若端口/host 文件存在，优先按文件指向的“真实端口/真实 host”打开
REM - 端口：避免端口自动回退后仍按 5000 打开
REM - host：避免 APS_HOST 不可绑定回退到 127.0.0.1 后仍按旧 host 打开
call :read_host_file
call :read_port_file
call :is_port_listening
if defined PORT_READY goto :OPEN_CHROME

echo [launcher] 启动排产系统...
REM 删除旧的端口/host 文件，避免读取到上次启动残留信息
del /f /q "%PORT_FILE%" >nul 2>&1
del /f /q "%HOST_FILE%" >nul 2>&1
start "" "%APP_EXE%"

echo [launcher] 等待服务就绪（最多 %MAX_WAIT%s）...
for /l %%i in (1,1,%MAX_WAIT%) do (
  call :read_host_file
  call :read_port_file
  call :is_port_listening
  if defined PORT_READY goto :OPEN_CHROME
  timeout /t 1 /nobreak >nul
)

echo [launcher] 超时仍未就绪。请查看 logs\aps_error.log
pause
exit /b 3

:OPEN_CHROME
set "URL=http://%HOST%:%PORT%/"
echo [launcher] 浏览器来源：%CHROME_SOURCE%
echo [launcher] 打开：%URL%
start "" "%CHROME_EXE%" --user-data-dir="%CHROME_PROFILE_DIR%" --app="%URL%" --no-first-run --disable-default-apps --no-default-browser-check --disable-background-networking
exit /b 0

:is_port_listening
set "PORT_READY="
netstat -ano | findstr /I "LISTENING" | findstr /R /C:":%PORT% " >nul
if %errorlevel%==0 set "PORT_READY=1"
exit /b 0

:read_host_file
REM 说明：应用启动后会写入 logs\aps_host.txt（一行 host），这里读取它以获得实际可访问 host。
if exist "%HOST_FILE%" (
  set /p HOST=<"%HOST_FILE%"
  REM 去掉可能的空格（注意：括号块内必须用 delayed expansion，否则会拿到旧的 %HOST%）
  set "HOST=!HOST: =!"
  if "!HOST!"=="" set "HOST=127.0.0.1"
)
exit /b 0

:read_port_file
REM 说明：应用启动后会写入 logs\aps_port.txt（仅数字），这里读取它以获得实际端口。
if exist "%PORT_FILE%" (
  set /p PORT=<"%PORT_FILE%"
  REM 去掉可能的空格（注意：括号块内必须用 delayed expansion，否则会拿到旧的 %PORT%）
  set "PORT=!PORT: =!"
)
exit /b 0

