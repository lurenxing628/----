@echo off
REM Launcher: start app first, then open URL with bundled Chrome109
REM Place next to app exe (after install: {app}\)

setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul 2>&1

cd /d "%~dp0"

set "PORT=5000"
set "URL=http://127.0.0.1:%PORT%/"
set "MAX_WAIT=45"

set "APP_EXE=%CD%\排产系统.exe"
set "CHROME_EXE=%CD%\tools\chrome109\chrome.exe"
if not exist "%CHROME_EXE%" set "CHROME_EXE=%CD%\tools\chrome109\App\chrome.exe"

if not exist "%APP_EXE%" (
  echo [launcher] 未找到：%APP_EXE%
  pause
  exit /b 1
)

if not exist "%CHROME_EXE%" (
  echo [launcher] 未找到 Chrome：%CD%\tools\chrome109\
  echo [launcher] 期望存在：tools\chrome109\chrome.exe（优先）或 tools\chrome109\App\chrome.exe（备用）
  pause
  exit /b 2
)

call :is_port_listening
if defined PORT_READY goto :OPEN_CHROME

echo [launcher] 启动排产系统...
start "" "%APP_EXE%"

echo [launcher] 等待端口 %PORT% 就绪（最多 %MAX_WAIT%s）...
for /l %%i in (1,1,%MAX_WAIT%) do (
  call :is_port_listening
  if defined PORT_READY goto :OPEN_CHROME
  timeout /t 1 /nobreak >nul
)

echo [launcher] 超时仍未就绪。请查看 logs\aps_error.log
pause
exit /b 3

:OPEN_CHROME
echo [launcher] 打开：%URL%
start "" "%CHROME_EXE%" --app="%URL%" --no-first-run --disable-default-apps --no-default-browser-check --disable-background-networking
exit /b 0

:is_port_listening
set "PORT_READY="
netstat -ano | findstr /I "LISTENING" | findstr /R /C:":%PORT% " >nul
if %errorlevel%==0 set "PORT_READY=1"
exit /b 0

