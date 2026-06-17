# Finding 10：本地安装文档漏掉默认图分析所需的 NetworkX 依赖

- 优先级：P2
- 结论：CI 的 NetworkX 安装是对的，但 README 的本地安装步骤和 CI 不一致。

## 根因

`quality.yml` 明确额外安装 `requirements-optimizer-lite-win7.txt`，其中固定 `networkx==3.1`。README 和开发文档的源码开发启动只安装 `requirements.txt` 和 `requirements-dev.txt`。而当前默认 `graph_analysis_mode` 是 `on`，默认路径需要图分析依赖。

## 证据

- `.github/workflows/quality.yml:37-46`：CI 安装运行依赖、开发依赖，并额外安装 `requirements-optimizer-lite-win7.txt`。
- `requirements-optimizer-lite-win7.txt:1-6`：固定 `networkx==3.1`，说明兼容 Win7 x64 + Python 3.8。
- `README.md:25-28`：本地安装只写 `requirements.txt` 和 `requirements-dev.txt`。
- `开发文档/README.md:23-25`：开发基线同样只写 `requirements.txt` 和 `requirements-dev.txt`。
- `.codestable/architecture/ARCHITECTURE.md:84`：目标提交里仍写 `graph_analysis_mode=off` 是默认关闭模式。
- `core/models/schedule_config_runtime_snapshot.py:27`：`graph_analysis_mode: str = "on"`。
- `core/services/scheduler/config/config_snapshot.py:44`：默认也是 `"on"`。
- `tests/candidate/test_scheduler_candidate_config_contract.py:198`：测试断言默认值是 `"on"`。

## 影响

- 新环境照 README 安装，可能比 CI 少装 NetworkX。
- 默认图分析开启时，本地运行排产链路可能触发“请先安装 NetworkX”的守卫。

## 建议

- README 和开发文档的安装命令补上 `-r requirements-optimizer-lite-win7.txt`，或明确说明默认图分析开启时必须安装该文件。
- 同步架构文档里关于 `graph_analysis_mode` 默认值的旧口径。
