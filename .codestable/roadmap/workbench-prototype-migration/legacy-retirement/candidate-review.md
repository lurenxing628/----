# Candidate Patch 评审入口

- Main checkout 中仍未应用、未挂载、未删旧资产。原 patch 已在私有候选源码真实应用并通过 factory 验证；两者不能混为一谈，也不构成 17 后的正式挂载许可。
- 当前完整交接见 [handoff.md](handoff.md)，真实运行与失败记录见 [factory-acceptance.md](factory-acceptance.md) 和 [factory-verification.json](factory-verification.json)。

## Patch 边界

- `candidate-review.patch` 仍为 24 目标，SHA `a6c1a20dce70b241046b09ecfcd349fd7c8dddb7a6f00ee0ea644d916fabd0e2`；index SHA `8e4fbad3b665f3e81be9fb6835df31ebaec2d90acc74b4f32a323cc0b29106fa`。
- 12 个导入 helper、打印 route、手册 route 共 14 个 renderer 只改模板字符串；恢复字符串后的 AST 相等。其余 10 个目标为 dispatcher/presentation、6 个新模板和2个错误模板。没有 factory/pages/JS/schema/删除。
- 已实际存在的导航模块、SELECT 查询叶、纯日期叶与原 web 兼容导出不放进 patch 重复覆盖；实际文件 hash 见 handoff。
- 私有 `source/` 中全部 24 个 preimage/postimage 均核对。Main 正式应用时仍须重核，不能用本轮私有通过覆盖后续改动。

## 已验证

- 真实 `create_app` 配置全部 DB/log/backups/templates/journal/home/tmp 为私有目录，然后显式 `install_legacy_retirement(app)`。不使用 Flask stub、TESTING 特例或旧源码 sys.path 回落。
- candidate 和 baseline 均 12/12 导入链通过；51 页和39非页面 GET/HEAD、113 实际空表单 POST 两侧全跑。后者不是113条完整交易验收。
- 打印保留真实数据/身份警示/范围/空白备注，手册保留原文下载；三个真实 POST→旧 GET→canonical 消息路径通过，浏览器显示另待匹配构建。
- 查询层和目录环已修复：46 项正常 pytest、两种 scanner exit 0；旧 baseline 不变。Ruff/Pyright 通过。
- 原解析/确认/事务不因呈现 patch 改写；日期函数是原样提取，不改默认日期、校验文案和62天上限。

## 仍不覆盖

- 当前构建有49个源输入漂移，不能据其宣称浏览器消费、17/18、最终资产负向缺席或完整迁移通过。
- 所有导入 mode/replace/故障组合、全部113交易、Win7、全质量门禁、代码与 D1 数据回退仍需相应完整验收。
- Main 保有正式 factory 挂载和共享页面/JS/registry 的所有权。历史样稿/局部HTTP记录已归档，不再充当本轮 source-bound factory 结论。
