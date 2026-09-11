# Candidate Patch 评审入口

- **未应用、未挂载、未删除源或资产。** Main 负责17完成后的应用窗口与最终挂载；本文件不构成挂载许可。
- `candidate-review.patch` 为apply_patch格式；`candidate-review-index.json`列出24个目标的前/后SHA。当前24个preimage核对通过，应用前仍须复核并行变化，不覆盖已存在的新文件。
- 24个目标：12个导入helper、打印route、说明书route仅改模板字符串；新增dispatcher/presentation及6个workbench模板，替换2个独立错误模板。14个Python旧renderer恢复模板字符串后的AST完全相同。没有factory、pages、JS、服务、schema或删除操作。

## 已完成代码

- 真实旧GET转换器已经在产品源码（未挂载）：`legacy_navigation.py`、`legacy_navigation_plan.py`、`legacy_page_contract.py`；不再是空的converter回调。精确接口、字段及不等价原因见`legacy-navigation-contract.md`。
- draft dispatcher有具体入口`install_legacy_retirement(app)`；51页清单来自单一合同，只有GET/HEAD适配，113旧POST与39旧非页面GET原函数保留。明确注册，无TESTING、URL开关或旧模板回退。
- 12个导入helper覆盖24个preview/confirm；新结果页保留原mode/filename/raw_rows_json/preview_baseline/strict/auto_generate与confirm URL。展示只取各自现有Excel模板表头与变化字段，不输出整份raw context/data JSON；隐藏确认载荷原样保留。
- print保留sheets/版本/角色/身份警示/重复页眉/范围/空白备注/打印操作。manual保留原文、章节定位、相关主题、返回/下载、缺失提示；正文不依赖JS；兼容旧slug章节锚点。错误页不依赖业务blueprint或旧static。
- 原业务parser、确认、事务和服务代码不变。验证包含真实旧GET、真实人员XLSX预检/过期拒绝/确认写入/重开回读、真实打印和手册原md下载字节相等。

## 验证边界

- 产品专项：parser12 + 旧GET/ref/SQLite18，联合30passed；8文件Pyright零错误/警告，Ruff通过。
- 呈现/dispatcher样稿15tests；私有候选HTTP5tests。113POST/39非页面GET函数身份未改变的证明，不等于113条业务的全量交易验收。
- 私有HTTP通过正常新注册函数加载，仅候选模板目标在内存替换；没有启动真实factory或触碰生产库/原preview。无宿主、服务器或浏览器在途。
- Main仍需：接入/完成规范boot与浏览器消费验收、登记新测试；17授权后复核preimage、应用此patch、显式安装dispatcher；按资源矩阵建立新候选交付并完成负向旧UI缺席检查、最终门禁与代码/新数据回退演练。
- patch不包含已实际存在的4个导航模块，避免重复覆盖；也不包含资源删除。其余11组导入的完整交易边界及浏览器确认、Win7/发布不是这组局部测试的通过结论。
