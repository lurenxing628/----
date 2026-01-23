@echo off
REM Phase9（系统管理：备份/日志/历史）冒烟测试一键执行脚本
REM 作用：运行 tests\smoke_phase9.py，并自动生成 evidence\Phase9\smoke_phase9_report.md

setlocal
cd /d %~dp0

echo [Phase9] 开始运行冒烟测试...
echo - 项目目录：%cd%
echo.

python tests\smoke_phase9.py

echo.
if %errorlevel%==0 (
  echo [Phase9] 冒烟测试完成：通过
  echo - 报告：evidence\Phase9\smoke_phase9_report.md
) else (
  echo [Phase9] 冒烟测试完成：失败（错误码=%errorlevel%）
  echo - 请打开报告查看详情：evidence\Phase9\smoke_phase9_report.md
)

endlocal

