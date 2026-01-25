@echo off
REM 开发/调试启动脚本（目标机打包后直接运行 exe，不需要此脚本）

setlocal EnableExtensions EnableDelayedExpansion

REM 统一编码，避免中文在 cmd 下乱码
chcp 65001 >nul 2>&1

REM 启动前：若 5000 端口被占用，自动结束占用进程（仅匹配“本地端口=5000”的 LISTENING 行）
set PORT=5000
set FOUND_ANY=
set KILLED_PIDS= 

for /f "tokens=1,2,3,4,5" %%A in ('netstat -ano ^| findstr /I "LISTENING"') do (
    REM %%B = Local Address, %%E = PID
    echo %%B | findstr /R /C:":%PORT%$" >nul
    if not errorlevel 1 (
        set PID=%%E
        set FOUND_ANY=1

        REM 去重：同一 PID 可能出现多条监听记录（IPv4/IPv6）
        echo !KILLED_PIDS! | findstr /C:" !PID! " >nul
        if errorlevel 1 (
            if "!PID!"=="4" (
                echo [start] 端口 %PORT% 可能被系统 HTTP.SYS 占用（PID=4），无法自动结束；请关闭占用服务或改端口。
            ) else (
                echo [start] 端口 %PORT% 被占用，尝试关闭 PID=!PID! ...
                taskkill /PID !PID! /T /F >nul 2>&1
            )
            set KILLED_PIDS=!KILLED_PIDS!!PID! 
        )
    )
)

REM 若尝试关闭后仍被占用，则提示并退出（避免启动失败/反复重启）
for /f "tokens=1,2,3,4,5" %%A in ('netstat -ano ^| findstr /I "LISTENING"') do (
    echo %%B | findstr /R /C:":%PORT%$" >nul
    if not errorlevel 1 (
        echo [start] 端口 %PORT% 仍被占用（PID=%%E）。请先关闭占用进程后再启动。
        exit /b 1
    )
)

set APS_ENV=development
set FLASK_ENV=development

REM 让 Python 控制台输出使用 UTF-8（避免中文日志乱码）
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

python app.py

