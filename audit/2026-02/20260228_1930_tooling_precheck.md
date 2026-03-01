# Tooling 预检留痕（ruff / radon / vulture）

- 时间：2026-02-28 19:30
- 目的：确认综合体检/架构审计相关 dev 工具可用，避免出现 “SKIP 误判”。

## 环境信息

- Python：3.8.10
- 可执行文件：`D:\py3.8\python.exe`
- 平台：Windows-10-10.0.26100-SP0

## 工具可用性（版本）

- ruff：0.15.4（已安装）
- radon：6.0.1（已安装）
- vulture：2.14（已安装）

## 备注

- 本仓库 `requirements.txt` 固定运行依赖（Flask/openpyxl/dateutil）；ruff/radon/vulture 属于 dev 工具，未固定版本属于预期。
- 后续若更换虚拟环境/解释器，需要重新跑一次本预检并留痕。

