# Finding 22：Win7 离线包是否包含 NetworkX 还没有可审 proof

- 优先级：P2 / 证据不足
- 结论：CI 里安装 NetworkX 的方向正确，但本轮没有证据证明 Win7 离线交付包一定包含 NetworkX。由于默认图分析是 `on`，这块不能只靠“CI 能 pip install”来放行离线包。

## 根因

`.github/workflows/quality.yml` 覆盖的是托管环境测试依赖安装，不等于离线安装包内容。`build_win7_onedir.bat` 只有在 `vendor/` 存在时把整个目录作为 data 打进包，而 `vendor/**` 被 git 忽略，本轮无法从仓库内容判断 NetworkX wheel 或源码是否已进入交付物。

大白话说：CI 会联网装 NetworkX，不代表用户拿到的离线包里也有 NetworkX。

## 证据

- `core/models/schedule_config_runtime_snapshot.py:27`：`graph_analysis_mode` 默认是 `"on"`。
- `core/services/scheduler/graph/nx_runtime.py:13-18`：运行时缺 NetworkX 会报“请先安装 requirements-optimizer-lite-win7.txt”。
- `.github/workflows/quality.yml:37-46`：CI 安装 `requirements-optimizer-lite-win7.txt`。
- `build_win7_onedir.bat:39-46`：仅在 `vendor` 存在时 `--add-data "vendor;vendor"`。
- `.gitignore:45-47`：`vendor/**` 被忽略，只保留 `vendor/.gitkeep`。
- 主线程检查目标提交：`git ls-tree -r --name-only 313f6528 -- vendor requirements-optimizer-lite-win7.txt` 只显示 `requirements-optimizer-lite-win7.txt` 和 `vendor/.gitkeep`；当前工作区的 `vendor/wheels/` 是 ignored，本报告不能把它当成目标提交 proof。

## 影响

- Win7 离线用户可能装好程序后，默认排产链路触发 NetworkX 缺失错误。
- 这会和“目标机不要求安装 Python、Win7 x64 离线交付”的硬约束冲突。

## 建议

- 为 Win7 包产物增加可审清单：证明 NetworkX 3.1 已被 PyInstaller 收进包，或证明离线 wheel 已随包分发并能安装。
- 增加打包 smoke：在干净离线环境里启动默认配置并跑图分析最小路径。
- 如果短期无法证明包内含 NetworkX，需明确把 `graph_analysis_mode=off` 作为离线包默认配置，或让启动前检查给出阻塞提示。
