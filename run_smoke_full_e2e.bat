@echo off
REM Full E2E（从 Excel→排产→甘特/周计划→系统管理）冒烟测试一键执行脚本
REM 作用：运行 tests\smoke_e2e_excel_to_schedule.py，并生成 evidence\FullE2E\excel_to_schedule_report.md

setlocal
cd /d %~dp0

echo [FullE2E] 开始运行端到端冒烟测试...
echo - 项目目录：%cd%
echo.

python tests\smoke_e2e_excel_to_schedule.py

echo.
if %errorlevel%==0 (
  echo [FullE2E] 冒烟测试完成：通过
  echo - 报告：evidence\FullE2E\excel_to_schedule_report.md
) else (
  echo [FullE2E] 冒烟测试完成：失败（错误码=%errorlevel%）
  echo - 请打开报告查看详情：evidence\FullE2E\excel_to_schedule_report.md
)

endlocal

