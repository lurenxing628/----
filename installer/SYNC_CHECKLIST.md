# Win7 安装脚本共同主体

`aps_win7.iss` 与 `aps_win7_legacy.iss` 都引用 `aps_win7_shared.iss`。安装配置、数据目录、迁移、停机及清理只有一份实现，修改共同主体即可，不再逐例程同步两份副本。

两个入口仅声明输出包名及 `LegacyFullInstaller`：

| 入口 | 输出包名 | 卸载浏览器行为 |
|---|---|---|
| `aps_win7.iss` | `APS_Main_Setup` | 关闭 APS 后端，独立 Chrome109 运行时由其自身卸载器处理 |
| `aps_win7_legacy.iss` | `APS_Legacy_Full_Setup` | 关闭 APS 后端和内置浏览器 |

对应卸载、安装完成文案在共同主体中按这项实际包差异选择。主程序与 legacy 的安装入口和输出文件名保持原值。

执行已有检查入口：

```powershell
python tests/gate_meta/verify_installer_iss_sync.py
```

该检查核对共同主体的引用及两个包的卸载职责。Inno 编译、Win7 安装/升级/卸载仍由对应构建和现场验收验证。
