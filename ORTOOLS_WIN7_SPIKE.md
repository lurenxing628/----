# OR-Tools（Win7 + Python3.8 离线）可行性验证结论（Spike）

## 结论（先给结论）

- **不建议把 OR-Tools 作为 Win7 离线交付的“必选依赖”**：官方仅声明/测试 **Windows 10 x64**，且 Windows 侧依赖 VC++ 运行库；Win7 兼容性属于高风险项。
- **作为“可选插件/可选依赖”保留入口是可行的**：项目已经具备 `vendor/` 注入与 `plugins/` 动态加载，可做到 **存在即用、缺失回退**，不影响主流程。

## 关键事实（证据）

1) **官方安装文档（Windows）只测试 Win10**

- Google 官方文档说明：仅在 **Windows 10 64-bit** 上测试，并要求安装 **Microsoft Visual C++ Redistributable for Visual Studio 2022 (x64)**  
  参考：`https://developers.google.com/optimization/install/python/binary_windows`

同时，官方“从源码构建（Windows）”指南也仅测试 **Windows 10 x64**，并要求 **Visual Studio 2022+**（Win7 环境基本不可行）：  
参考：`https://developers.google.com/optimization/install/python/source_windows`

2) **OR-Tools 新版本已不满足 Python3.8**

- PyPI 最新版 `ortools 9.15.6755 (2026-01-14)`：`Requires: Python >=3.9`（因此 **不适配 Python3.8**）  
  参考：`https://pypi.org/project/ortools/`

3) **存在“可安装到 Python3.8 的 Windows wheel”（但不等于 Win7 可用）**

- PyPI `ortools 9.8.3296 (2023-11-15)`：`Requires: Python >=3.8`，并提供 `cp38 win_amd64` wheel  
  参考：`https://pypi.org/project/ortools/9.8.3296/`
- PyPI `ortools 9.6.2534 (2023-03-13)`：提供 `cp38 win_amd64` wheel  
  参考：`https://pypi.org/project/ortools/9.6.2534/`

> 说明：wheel 名称为 `win_amd64` 不会声明“最低 Windows 版本”，因此 **是否能在 Win7 正常加载 DLL** 只能靠 Win7 实机验证。

## 建议的 Win7 实机验收步骤（离线）

在 Win7（建议 SP1）上新建干净 Python3.8 x64 环境后：

1. 安装合适的 VC++ 运行库（v14 系列，具体版本需与 wheel 依赖匹配；可能需要使用较旧的可安装版本/离线安装包）
2. 离线安装 `ortools` wheel（优先从 `ortools==9.6.2534` 或 `ortools==9.8.3296` 开始试）
3. 运行探活：

```bat
python -c "import ortools; print(ortools.__version__)"
```

- 若 **ImportError / DLL load failed**：基本可判定 Win7 不可用（或运行库版本不匹配）
- 若可 import：再进一步验证 **CP-SAT** / **MIP** 的简单示例（避免只 import 成功但求解崩溃）

## 项目内落地方式（建议）

- 继续将 OR-Tools 定位为 **可选求解器插件**：缺失时默认走启发式（贪心 + 后续 multi-start/LNS），并把“是否启用/可用/报错原因”展示在系统页（目前已具备）。
- 为方便现场判断，已提供一个 **探测插件**（见 `plugins/ortools_probe_plugin.py`）：启用后会尝试 `import ortools`，成功则注册能力，失败则在系统页展示错误堆栈（不影响主流程）。

