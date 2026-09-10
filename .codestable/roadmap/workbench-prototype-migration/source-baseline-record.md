# 原界面与相关源码备份记录

- 类型：修改前源码基线；不包括业务数据库备份，不是完整系统镜像。
- 日期：2026-09-09，按本机Asia/Shanghai记录；manifest另存实际UTC采集时刻。
- 路径：`/Users/lurenxing/GitHub/----/output/workbench-migration/baselines/source-RauBC6/`。
- 归档：`source.tar.gz`，20,386,110 bytes。
- SHA-256：`5cf4ecc190bcafc11fb80bdccb40733e0e93624d86d8c2fc45854a224b900b3b`。
- 文件数：2273，包含当前未提交修改及被Git忽略的整个前端设计源码/资源树，不是只保存HEAD。
- 范围：templates、static、web、core、data、assets、installer、plugins、tools、scripts、tests、前端设计，以及入口/config/schema/requirements/打包/AGENTS等明确根文件。完整路径与每个文件大小、模式、哈希见manifest。
- 排除：数据库及WAL/SHM、日志、上传目录、密钥文件、缓存、依赖安装目录和output等。没有读取真实业务数据库，没有运行备份恢复服务或触发schema变更。

## 实际验证

使用本目录 `capture-source-baseline.cjs` 生成归档，再解压到同一备份目录的`restore-check/`，逐个核对2273文件的大小、权限模式与SHA-256，并核对恢复文件集合完全一致。随后再次对原源码核验哈希，并比较备份前后的Git状态、staged补丁和unstaged补丁；全部一致。

原始证据：

- `manifest.json`：源目录、HEAD、捕获时间、选中/排除范围、逐文件指纹、归档指纹及恢复核验结果。
- `staged.patch` / `unstaged.patch`：原有修改的辅助记录，不是恢复时可以无条件反向套用的命令；原始内容以归档为准。
- `restore-check/`：已独立恢复且逐文件核验的源码副本。没有导入app、打开业务库或验证产品启动，因此不能称为运行恢复演练通过。

备份目录为Git忽略的output目录，不进入Web静态根或正常交付资产清单；目录权限为0700。未执行git reset/checkout/revert，原有暂存`test_frozen_bundle_contract.py`的200行修改保持不动。

## 后续边界

这个结果完成了“当前原界面及相关源码已备份并能还原文件”的前置工作。尚未开始移植；正式数据备份、跨schema恢复、安装包及Win7运行恢复、切换后新增数据保全仍须按总体方案另行验证。禁止仅凭本记录下线旧页或拿旧库覆盖切换后的新数据。

本归档不随新增方案文档自动更新。若用户在实施开始前又修改任何被归档源码，需核对差异并追加新基线，不覆盖或冒用本归档。
