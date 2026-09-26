---
doc_type: explore
date: 2026-09-26
title: Win7 虚拟机控制失败调查与卸载准备
---

# 结果

> 历史记录归档（2026-09-27）：本文保留初始调查、验收失败及当时的判断；正文中的“未修复”“未提交”“尚未安装”等描述均为记录时的状态。后续修复已提交于 `0b9a682f` 至 `d1307cb8`，原 Win7 的安装、复验和交付结果以[最终验收记录](../issues/2026-09-26-win7-fixes-acceptance.md)为准。打包验收脚本及两份专测已包含在 `0b9a682f` 中。本文原存于 `codestable/`，现归档至 `.codestable/`；引用的本机日志、数据库和截图不随 Git 上传。

**后续状态说明：** 以下保留最初的虚拟机准备记录。随后已在原机安装并验证 VMware Tools 11.0.6，恢复来宾命令和文件传输通道；新版冻结程序已在原 Win7 上完成实际功能、界面、压力及恢复检查。文末“Tools 仍未运行”等限制仅适用于最初阶段。最终交付、账户恢复、临时辅助通道清理和验收结论见 [验收总报告](../../evidence/Win7Acceptance/20260926/ACCEPTANCE_REPORT.md)。

VMware Workstation 25.0.0 build-24995812，虚拟机为 `D:\windows 7 BK\Windows 7 x64.vmx`，Win7 x64 SP1。已用 VMware 自带 `vmcli` 的 MKS 通道完成旧程序卸载。

- “排产系统”卸载成功，程序文件和桌面快捷方式已移除。原安装目录只剩 `logs`。
- 两条 APS Chrome109 运行时 109.0.5414.120 安装记录（2026-05-02、2026-03-16）分别卸载成功；最终“程序和功能”列表已无 APS 项。
- 选择保留共享数据，并检查 `C:\ProgramData\APS\shared-data` 中仍有 `db`、`backups`、`logs`、`templates_excel`。桌面的 `批次信息.xlsx` 保留。
- 卸载前快照 `APS-before-cleanup-20260926` 已创建并通过 `vmrun listSnapshots` 确认存在。
- 新版本尚未安装或验证；此次只准备虚拟机。用户原有 `build_win7_onedir.bat` 修改未动。

# 控制失败的证据和边界

1. 同一 Computer Use 工具可以点击计算器并输入数字。VMware 中的模拟点击和按键则无可见效果，但 UIA 的搜索框 `set_value` 有效，说明不是整个控制服务失效。
2. VMware GUI、控制辅助进程和 Node 进程均为 Medium 完整性级别，未提升，未发现两者的权限级别差异。按官方建议释放修饰键也未解决问题。故将问题定位在原控制工具到 VMware 窗口的输入链路；尚未证明 VMware 内部过滤输入的具体机制。
3. 虚拟机日志明确出现 `VIX_E_TOOLS_NOT_RUNNING` 和 Tools 心跳超时。“程序和功能”也未见 VMware Tools。依赖 Tools 的来宾命令不能使用，重启没有恢复它。
4. `vmrun typeKeystrokesInGuest` 在此宿主返回 `Insufficient permissions in the host operating system`。不要把此错误与来宾账户密码混为一谈。
5. `vmcli MKS captureScreenshot`、`sendKeySequence` 和 `sendKeyEvent` 实测有效，无需为此次操作更改安全设置或开放远程端口。

# 已验证的命令

以下从宿主 PowerShell 执行。先观察来宾画面，再决定输入；命令退出码为 0 不能替代画面确认。

```powershell
$vmxPath = 'D:\windows 7 BK\Windows 7 x64.vmx'
$vmcliPath = 'D:\VMware\vmcli.exe'
& $vmcliPath $vmxPath MKS captureScreenshot "$env:TEMP\aps-win7-prep-20260926\screen.png"
# Ctrl+Esc：打开开始菜单
& $vmcliPath $vmxPath MKS sendKeyEvent 0x00290007 1
# sendKeySequence 输入的是文字；不要用字符串 ctrl-esc 表示组合键
& $vmcliPath $vmxPath MKS sendKeySequence 'C:\Program Files\APS\SchedulerApp'
# Enter
& $vmcliPath $vmxPath MKS sendKeyEvent 0x00280007 0
```

本次验证的 HID 编码为 `(usage << 16) | 7`；修饰键掩码 Ctrl=1、Alt=4。其他已验证按键：Alt+D=`0x00070007 4`，向下=`0x00510007 0`，Alt+Y=`0x001C0007 4`，Alt+N=`0x00110007 4`，F5=`0x003E0007 0`。输入后等待约 0.5–1 秒再截图。

截图证据保存在宿主 `%TEMP%\aps-win7-prep-20260926`：`uninstall-complete.png`、`data-preserved.png`、`chrome-complete.png`、`chrome-second-complete.png`、`final-programs.png`。

# 官方参考

- [Microsoft SendInput](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendinput)：完整性级别约束与现有键盘状态影响。
- [VMware 输入问题排查](https://techdocs.broadcom.com/us/en/vmware-cis/desktop-hypervisors/workstation-pro/25H2/using-vmware-workstation-pro/changing-workstation-pro-preference-settings/configuring-input-preference-settings/configuring-keyboard-and-mouse-settings/troubleshooting-input-problems.html)：释放 Shift、Ctrl、Alt 修饰键的方法。
- [VMware Tools 与来宾系统兼容性](https://knowledge.broadcom.com/external/article/313371/)：未来如安装 Tools，应先核实 Win7 补丁和对应 Tools 版本，不能直接套用最新版本。
- 本机权威语法：`D:\VMware\vmcli.exe MKS --help` 及各子命令 `--help`。

剩余限制：Tools 仍未运行，来宾文件传输和命令执行通道尚未恢复。当前已验证的 MKS 截图、文本和按键通道可继续用于安装界面操作。

## 收尾补充：空密码与自动化认证不是同一项验证

验收结束时，原 Administrator 的空密码恢复命令返回 0；随后 `LogonUser` 返回 1327。微软将该代码定义为账户限制，区别于用户名或密码错误的 1326；仅凭 1327 不能指定是哪一项本机策略触发。[官方错误码](https://learn.microsoft.com/en-us/windows/win32/debug/system-error-codes--1300-1699-)。

适用于 Win7 的微软策略说明明确区分远程认证和本机控制台：空密码使用限制不影响物理控制台的交互登录。本次没有更改账户安全策略，而是通过 VMware MKS 锁定原 Administrator 会话，仅按一次回车、未输入密码字符，实际回到原 APS 界面。[微软策略说明](https://learn.microsoft.com/en-us/previous-versions/windows/it-pro/windows-server-2012-r2-and-2012/jj852174(v=ws.11))。[实际控制台收据](../../evidence/Win7Acceptance/20260926/target/final-cleanup-20260926-1738/target-empty-password-console-unlock-receipt.json)。API 检查失败与控制台空密码验证成功分别保留，不能把前者当成用户未授权或仍需提供密码。
