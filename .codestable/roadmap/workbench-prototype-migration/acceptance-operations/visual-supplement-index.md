# F 最小补图索引

结论：固定 source18/build16，4 个独立真实入口用例 PASS，20 张图已拍并由 F 逐图确认目标可见；尚待 Main 实际查看签 V。旧 209 图、55 delta 次序、原 228 action 和 Main 两份正式记录不改。

source `/private/tmp/aps-final-operations-F.TQejHX/F13-source18`；aggregate `e5d57c7785aed192c1cb15cc11277150621fb9eb5ff6159078aeb171cca6fee7`；build `5b4327b9c68a2f7e69c0df01f34df2c2087fd0c9968418e93a7d11150866c480`；build manifest SHA-256 `ac0e08e56a509627ddd6f220ee29e81895de6aa5ea90004a822fc2f9f521a325`。

[完整证据 JSON](/Users/lurenxing/GitHub/----/.codestable/roadmap/workbench-prototype-migration/acceptance-operations/visual-supplement-evidence.json)；[全部状态及 228 项反向映射](/Users/lurenxing/GitHub/----/.codestable/roadmap/workbench-prototype-migration/acceptance-operations/main-v-state-map.json)。

| 精确图片 | 视口/主题 | 目标状态 | SHA-256 |
|---|---|---|---|
| [F-ADD-01](/private/tmp/aps-final-operations-F.TQejHX/F-visual-supplement-run2/dashboard/probe-1392-light/handling-validation-retained-draft.png) | 1392/light | N01 handling-validation-retained-draft | `a1b210e58b4ca9087a2cd959b0d0681fead4a655e5f45f68827d07cc06111116` |
| [F-ADD-02](/private/tmp/aps-final-operations-F.TQejHX/F-visual-supplement-run2/dashboard/probe-1392-light/handling-close-incomplete.png) | 1392/light | N02 handling-close-incomplete | `75af15b2872a1ea5e49c1b06e4fc578b76b4ff8b82ddc2ddf752be129ff208f1` |
| [F-ADD-03](/private/tmp/aps-final-operations-F.TQejHX/F-visual-supplement-run2/dashboard/probe-1392-light/reopen-reason-required.png) | 1392/light | N03 reopen-reason-required | `2be08b152c880725d26285f71d9afaebe5493a97b21d482fabf975c33f01221b` |
| [F-ADD-04](/private/tmp/aps-final-operations-F.TQejHX/F-visual-supplement-run2/dashboard/probe-1392-light/handling-filter-empty.png) | 1392/light | N04 handling-filter-empty | `2742c6eb2f6c014508467d3e92554e1872ab25f5006187eae8ddcd5d4ff2d8df` |
| [F-ADD-05](/private/tmp/aps-final-operations-F.TQejHX/F-visual-supplement-run2/dashboard/probe-1392-light/actual-deviation-table.png) | 1392/light | N05 actual-deviation-table | `36d5167577f41a963b90f46a92509c6e5c80ecad01e2bb4c3371d6dd24b971db` |
| [F-ADD-06](/private/tmp/aps-final-operations-F.TQejHX/F-visual-supplement-run2/dashboard/probe-1392-light/actual-field-report-destination.png) | 1392/light | N06 actual-field-report-destination | `aef3c05a1fe089e4da05f65eb13d68013b9468230b0e3328d7d292b7d4ac9636` |
| [F-ADD-07](/private/tmp/aps-final-operations-F.TQejHX/F-visual-supplement-run2/dashboard/probe-1392-light/actual-no-independent-candidate.png) | 1392/light | N07 actual-no-independent-candidate | `12e9481a19313d05dcc9fad21ac353f7df9c1ea223672147e83ca12be26ea13f` |
| [F-ADD-08](/private/tmp/aps-final-operations-F.TQejHX/F-visual-supplement-run2/dashboard/probe-1392-light/actual-comparison-destination.png) | 1392/light | N08 actual-comparison-destination | `43b7c91f826b8912828b913801537bf660f22043110cb627b72b59558c6fe484` |
| [F-ADD-09](/private/tmp/aps-final-operations-F.TQejHX/F-visual-supplement-run2/dashboard/probe-1392-light/outsourcing-edit-required-fields.png) | 1392/light | N09 outsourcing-edit-required-fields | `55602086aa292c281f650e4d961d660e78e1a430de5b6be5e9aff5043a34c6d5` |
| [F-ADD-10](/private/tmp/aps-final-operations-F.TQejHX/F-visual-supplement-run2/dashboard/probe-1392-light/outsourcing-server-date-rejection.png) | 1392/light | N10 outsourcing-server-date-rejection | `a4665da27801f03bd17eb3d454dd526c95e3fd044065bfe74253c8bf00fde4e7` |
| [F-ADD-11](/private/tmp/aps-final-operations-F.TQejHX/F-visual-supplement-run2/system/probe-1920-dark/backup-create-confirmation.png) | 1920/dark | N11 backup-create-confirmation | `9b47a8bce410c26d5be7cfd9fae2162a0d609da02441f88dfbdd65af7f395823` |
| [F-ADD-12](/private/tmp/aps-final-operations-F.TQejHX/F-visual-supplement-run2/system/probe-1920-dark/backup-delete-confirmation.png) | 1920/dark | N12 backup-delete-confirmation | `dae7c0ced939f935a318718c632044f2d25593295d7a0a905a709ef0e96182cb` |
| [F-ADD-13](/private/tmp/aps-final-operations-F.TQejHX/F-visual-supplement-run2/system/probe-1920-dark/config-invalid-field.png) | 1920/dark | N13 config-invalid-field | `173d1b7e20b8a8c0218122dcd3a9bea5ec724fdf9183eabe054f663b10b32148` |
| [F-ADD-14](/private/tmp/aps-final-operations-F.TQejHX/F-visual-supplement-run2/system/probe-1920-dark/config-discard-confirmation.png) | 1920/dark | N14 config-discard-confirmation | `56872cc5e6677a72944f0b96a2502957ca0c0204fd0929f78a8f3712ec85ee92` |
| [F-ADD-15](/private/tmp/aps-final-operations-F.TQejHX/F-visual-supplement-run2/system/probe-1920-dark/config-live-rules-expanded.png) | 1920/dark | N15 config-live-rules-expanded | `e45587104d6007e89fb6912562b6f50a28b3b43eaf607583d972dce1165b687a` |
| [F-ADD-16](/private/tmp/aps-final-operations-F.TQejHX/F-visual-supplement-run2/system/probe-1920-dark/system-noncompact-log-rows.png) | 1920/dark | N16 system-noncompact-log-rows | `2ad648bd61052ccb2efe919731bfa50412b044ed643ba8a5c105779d25da5f14` |
| [F-ADD-17](/private/tmp/aps-final-operations-F.TQejHX/F-visual-supplement-run2/system/probe-1920-dark/config-sample-skipped-rule-expanded.png) | 1920/dark | N17 config-sample-skipped-rule-expanded | `34991a8d1df1260118f1c70defc80ce7e025a08fc8e2f15c36dc4cf5132ce83f` |
| [F-ADD-18](/private/tmp/aps-final-operations-F.TQejHX/F-visual-receipt-run1/probe-1392-dark/backup-file-operation-receipt.png) | 1392/dark | N18 真实创建成功回执，展开维护阶段 | `4ea3d9aa3afb00e6dec15017104a93d50d0a2758cf662681a9274d48d3931808` |
| [F-ADD-19](/private/tmp/aps-final-operations-F.TQejHX/F-visual-domain-receipt-run1/probe-1920-light/handling-confirmed-receipt.png) | 1920/light | N19 handling-confirmed-receipt | `77fc4e64844cd945c4b119e0651d2ae515f3980b878eaca7c25d3a559cc23602` |
| [F-ADD-20](/private/tmp/aps-final-operations-F.TQejHX/F-visual-domain-receipt-run1/probe-1920-light/outsourcing-confirmed-receipt.png) | 1920/light | N20 outsourcing-confirmed-receipt | `93a49f1abf9c716204c2644f813bf1a665f379b93008da632aa33aaf8795f33c` |

## 动作和边界

- **N01**：`WBP-DASH-003.reject-invalid`、`WBP-DASH-003.retain-failed-draft`。本轮真实输入的滚动视口；只覆盖截图内可见状态。
- **N02**：`WBP-DASH-004.reject-incomplete`。本轮真实输入的滚动视口；只覆盖截图内可见状态。
- **N03**：`WBP-DASH-005.open-reopen`、`WBP-DASH-005.require-reason`、`WBP-DASH-005.confirm-reopen`、`WBP-DASH-005.cancel-reopen`。确认按钮可见但本轮不执行重开；正向 K 仍引用既有生命周期。
- **N04**：`WBP-DASH-002.status-verification`、`WBP-DASH-002.status-new`、`WBP-DASH-002.status-closed`。实际筛选为待验证；其他无结果筛选只共享相同空表布局，不代表其像素已查看。
- **N05**：`WBP-DASH-008.deviation-table`。本轮真实输入的滚动视口；只覆盖截图内可见状态。
- **N06**：`WBP-DASH-008.field-report-navigation`。本轮真实输入的滚动视口；只覆盖截图内可见状态。
- **N07**：`WBP-DASH-014.no-independent-candidate`。本轮真实输入的滚动视口；只覆盖截图内可见状态。
- **N08**：`WBP-DASH-008.actual-comparison-navigation`。本轮真实输入的滚动视口；只覆盖截图内可见状态。
- **N09**：`WBP-DASH-009.open-registration`、`WBP-DASH-010.reject-missing-sent`、`WBP-DASH-010.reject-missing-planned`、`WBP-DASH-010.reject-reverse`、`WBP-DASH-010.reject-state-time`。实际触发缺少实际发出；其他客户端校验消息共用同一表单和错误区，其既有 K 不变。
- **N10**：`WBP-DASH-010.reject-future-sent`、`WBP-DASH-010.reject-future-return`。实际触发未来发出；未来回厂使用相同服务端错误区，旧分支 K 保留。
- **N11**：`WBP-SYS-008.create`。仅打开并取消；创建行为由既有 B/K/P 证明。
- **N12**：`WBP-SYS-010.confirm`、`WBP-SYS-010.cancel`。风险确认已勾选，确认按钮可见；仅取消，不执行删除。
- **N13**：`WBP-SYS-017.invalid-fields`。本轮真实输入的滚动视口；只覆盖截图内可见状态。
- **N14**：`WBP-SYS-017.discard-confirm`、`WBP-SYS-017.discard-cancel`。本轮真实输入的滚动视口；只覆盖截图内可见状态。
- **N15**：`WBP-SYS-019.scope`、`WBP-SYS-019.request-trigger`。本轮真实输入的滚动视口；只覆盖截图内可见状态。
- **N16**：`WBP-SYS-015.compact`。实际偏好为非紧凑；只代表行高，不代表 compact 产生数据库写入。
- **N17**：`WBP-SYS-019.skipped`。管理样例规则正文可见；不是实时发生了一次 skipped 事件。
- **N18**：`WBP-SYS-008.receipt`、`WBP-SYS-010.receipt`。直接证据为创建成功；删除成功使用同一 Outcome file_operation 分支，仅操作文案、代码、记录号、文件名和阶段数据不同，不声称已看到删除成功图片。
- **N19**：`WBP-DASH-003.submit`、`WBP-DASH-004.close`、`WBP-DASH-005.confirm-reopen`。真实确认保存后的核实弹窗，不用编辑表单或历史表代替。 实际为 following 保存，关闭/重开只共享 DashboardHandling.Receipt 与 Facts 布局，不冒称本次执行了关闭/重开。
- **N20**：`WBP-DASH-010.save`、`WBP-DASH-010.correct`、`WBP-DASH-010.original-receipt`。真实确认保存后的核实弹窗，不用编辑表单或历史表代替。 实际为新登记保存，更正仅共享同一 OutsourcingControls.Pending 结果布局；不是本轮又执行更正。

所有图都是滚动视口，不是全页。N01/N02/N09/N10 弹窗体内容可内部滚动，视口外尾部不列已看；O15/N18 分别为配置/文件操作不同结果分支，不能混用。N16 的真实日志包含资产版本读取警告，该图仅用于非紧凑行距，不据此宣称全局无警告。

17 图例：Dashboard 仅为重开框建立 following/closed 两条真实前置历史，10 张图；System 只读、校验和取消，7 张图。文件回执例只创建一个新测试备份，1 张图；另一个独立库完成 following/外协物流保存回执，2 张图。既有备份哈希不变，无删除、恢复或产品写入。四个进程的源码绑定分别检查 1113/1114/1114/1113 个已加载模块，0 违规，均已结束。

失败的 run1 仅是独立脚本等待错接口路径，排除出正式证据。已有 228 K / 222 B + 6 N/A / 227 P + 1 N/A 不被本次图数替代。
