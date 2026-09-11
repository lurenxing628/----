# L5 五文件修复交接

- 授权两组已实现：仅延期页显示同一 occupancy 快照的资源重叠明细；Trial 五项只读偏好按原草稿/场景身份持久保存。没有第六个产品文件，未改后端、算法、schema 或写命令。
- 精确小包：`/private/tmp/aps-final-d-l5-ready-QWzvK6/manifest.json`；SHA256 `9ebe445830e87368de12715265e8e4004a0bc6c311a57a6879a040940ade48b3`。含 5 产品、2 合同测试、4 原文件 preimage 和全部 SHA/大小/权限。
- 一次定点检查：`/tmp/aps-final-d-l5-contract.xml`，1 passed / 1.08s，31 个合同断言；Chrome109 目标源码编译通过。这是合同验证，不是真实浏览器或完整入口证明。
- 新 global 为 `TrialViewState`；读取 React/TrialContract/TrialControls，加载在 TrialContract.js、TrialControls.jsx 后及 TrialGantt.jsx、TrialResults.jsx 前。四个显式 fixture 列表的精确插入位置在 manifest；其余改动须保留。
- Main 接统一 build-order、fixture 插入、构建和最终验证。四 K/七 P 完整探针未执行；旧 ANA、旧 959 capsule 与旧证明均保留。本轮未暂存/提交，未操作原库。
