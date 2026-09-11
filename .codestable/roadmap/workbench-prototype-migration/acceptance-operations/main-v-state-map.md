# F 待 Main 看的独立视觉状态

结论：Main 已签精确 54 图（原28 + delta26）；其余 29 张 delta 中只推荐再看 5 张代表图。另列 32 张旧独立状态主图及本轮 20 张补图，共 57 张待看的代表图。不是 228 个 action 的 V 通过数。

[首批6图](/Users/lurenxing/GitHub/----/.codestable/roadmap/workbench-prototype-migration/acceptance-operations/main-v-quick-index.md)；[新增20图及精确动作](/Users/lurenxing/GitHub/----/.codestable/roadmap/workbench-prototype-migration/acceptance-operations/visual-supplement-index.md)；[完整机器索引](/Users/lurenxing/GitHub/----/.codestable/roadmap/workbench-prototype-migration/acceptance-operations/main-v-state-map.json)。

209 张原图的 SHA-256 全部不同。本清单不做假字节去重；每个分组只是明示组件/状态代表，其他图仍未看。相同源的字段值、对象名、时间戳或状态标签变化不自动要求新一套四图。不同布局、警告分支和对象类型单列。

## 55 张 Delta 的最小增补

| 精确图片 | 视口/主题 | 目标状态 | SHA-256 |
|---|---|---|---|
| [F-OLD-156](/private/tmp/aps-final-operations-F.TQejHX/F13-final-delta1-pytest/test_final_operations_dashboar0/dashboard-new-process/probe-dashboard-restart-1392-light/dashboard-same-scope-page-two-selection-after-new-process.png) | 1392/light | D02 重启后的原筛选第二页及原选中详情 | `83ffdbad396ac03741d653363d77fcb3738267bcecc7c148c710df463945654c` |
| [F-OLD-159](/private/tmp/aps-final-operations-F.TQejHX/F13-final-delta1-pytest/test_final_operations_dashboar1/dashboard-new-process/probe-dashboard-restart-1392-dark/dashboard-same-scope-page-two-selection-after-new-process.png) | 1392/dark | D02 重启后的原筛选第二页及原选中详情 | `22937a62984486561b81c5ad7026ca64ac0b8aec55834fd3e7049afb9ca664a1` |
| [F-OLD-162](/private/tmp/aps-final-operations-F.TQejHX/F13-final-delta1-pytest/test_final_operations_dashboar2/dashboard-new-process/probe-dashboard-restart-1920-light/dashboard-same-scope-page-two-selection-after-new-process.png) | 1920/light | D02 重启后的原筛选第二页及原选中详情 | `54c1f031735c68f6c1c9e7900f113d20190839822ae173d98a6100fb0927511f` |
| [F-OLD-165](/private/tmp/aps-final-operations-F.TQejHX/F13-final-delta1-pytest/test_final_operations_dashboar3/dashboard-new-process/probe-dashboard-restart-1920-dark/dashboard-same-scope-page-two-selection-after-new-process.png) | 1920/dark | D02 重启后的原筛选第二页及原选中详情 | `e4f6bb5bd48199de7987904f611a5a4730b5ff7b7174a948f6d18c8f7b8e3662` |
| [F-OLD-177](/private/tmp/aps-final-operations-F.TQejHX/F13-final-delta1-pytest/test_final_operations_system_r3/system-new-process/probe-system-restart-1392-light/system-backups-page-two-after-process-restart.png) | 1392/light | D03 普通可操作备份二页详情 | `a6a3c6eb87d9c6d276d0ea8539ff19abfcc47751c7dd42057ab306a083115ca3` |

D02 的四张是原清单第二页选中详情，并非已看 D01 历史第二页。D03 index23 才是1392/light普通可操作备份详情；已看的index20属于D05 pending禁用。其他24张未看delta是同source18的before/inactive备用，完整JSON逐图记录，无自动签字。

| Delta状态 | 四组合/特殊代表的原始 index | Main精确已看 | 适用动作 |
|---|---|---|---|
| D01 重启后的处置历史第二页 | 1, 4, 7, 10 | 1, 4, 7, 10 | `WBP-DASH-006.open-history`、`WBP-DASH-006.select-history`、`WBP-DASH-006.reverse-order`、`WBP-DASH-006.expand-before-after`、`WBP-DASH-006.source-records`、`WBP-DASH-006.history-page`、`WBP-DASH-014.return-context` |
| D02 重启后的原筛选第二页及原选中详情 | 2, 5, 8, 11 |  | `WBP-DASH-002.status-all`、`WBP-DASH-002.status-open`、`WBP-DASH-002.status-new`、`WBP-DASH-002.status-following`、`WBP-DASH-002.status-verification`、`WBP-DASH-002.status-closed`、`WBP-DASH-002.search-batch`、`WBP-DASH-002.search-owner`、`WBP-DASH-002.search-action`、`WBP-DASH-002.search-remark`、`WBP-DASH-002.clear`、`WBP-DASH-006.history-page`、`WBP-DASH-014.return-context` |
| D03 普通可操作备份二页详情 | 23, 29, 35, 41 | 29, 35, 41 | `WBP-SYS-005.time`、`WBP-SYS-005.type`、`WBP-SYS-005.status`、`WBP-SYS-005.filename`、`WBP-SYS-005.size`、`WBP-SYS-005.detail`、`WBP-SYS-005.unread-state`、`WBP-SYS-006.search`、`WBP-SYS-006.type-manual`、`WBP-SYS-006.type-auto`、`WBP-SYS-006.type-before-restore`、`WBP-SYS-006.type-restore`、`WBP-SYS-006.type-cleanup`、`WBP-SYS-006.status`、`WBP-SYS-006.start-date`、`WBP-SYS-006.end-date`、`WBP-SYS-006.clear`、`WBP-SYS-007.previous`、`WBP-SYS-007.next`、`WBP-SYS-007.size-10`、`WBP-SYS-007.size-25`、`WBP-SYS-007.size-50`、`WBP-SYS-007.close-x`、`WBP-SYS-007.close-escape`、`WBP-SYS-007.full-body`、`WBP-SYS-007.validation-details`、`WBP-SYS-008.download-backup`、`WBP-SYS-009.select`、`WBP-SYS-010.select` |
| D04 日志二页原记录详情 | 26, 32, 38, 17 | 26, 32, 38, 17 | `WBP-SYS-011.runtime-source`、`WBP-SYS-011.operation-source`、`WBP-SYS-011.columns`、`WBP-SYS-011.detail`、`WBP-SYS-012.search-detail`、`WBP-SYS-012.search-file`、`WBP-SYS-012.type-runtime`、`WBP-SYS-012.type-operation`、`WBP-SYS-012.status`、`WBP-SYS-012.level`、`WBP-SYS-012.record-set`、`WBP-SYS-012.start-date`、`WBP-SYS-012.end-date`、`WBP-SYS-012.clear`、`WBP-SYS-012.page`、`WBP-SYS-012.detail` |
| D05 pending 配置下只读备份详情 | 20 | 20 | `WBP-SYS-018.unknown-result`、`WBP-SYS-019.pending` |
| D06 同名备份被替换后拒绝替代 | 13 | 13 | `WBP-SYS-005.detail`、`WBP-SYS-007.validation-details` |
| D07 旧 selection key 无稳定身份 | 15 | 15 | `WBP-SYS-005.detail`、`WBP-SYS-007.validation-details` |
| D08 无法定位导航确认 | 43, 46, 49, 52 | 43, 46, 49, 52 | `WBP-DASH-014.navigation-confirm`、`WBP-DASH-014.unlocatable` |
| D09 无 ref 甘特总览 | 44, 47, 50, 53 | 44, 47, 50, 53 | `WBP-DASH-014.unlocatable` |
| D10 返回原无法定位处置 | 45, 48, 51, 54 | 45, 48, 51, 54 | `WBP-DASH-014.return-context` |

## 旧图中仍需看的独立状态

| 精确图片 | 视口/主题 | 目标状态 | SHA-256 |
|---|---|---|---|
| [F-OLD-063](/private/tmp/aps-final-operations-F.TQejHX/F13-copy-matrix4-pytest/test_final_operations_main_con2/operations-1392-light/probe-normal-1392-light/dashboard-overview.png) | 1392/light | O01 值班台概况及筛选控件 | `154b08cab371f2de6034e9f8950121f1f0360932691c495ce22a3fe0f996221a` |
| [F-OLD-064](/private/tmp/aps-final-operations-F.TQejHX/F13-copy-matrix4-pytest/test_final_operations_main_con2/operations-1392-light/probe-normal-1392-light/delivery-following-form.png) | 1392/light | O02 处置编辑字段 | `a6fb885c28cc31d47027c0f27e8d27ac2632d0016ccbce0662a9be0c25c47548` |
| [F-OLD-005](/private/tmp/aps-final-operations-F.TQejHX/F13-copy-matrix4-pytest/test_final_operations_main_con0/operations-1920-light/probe-normal-1920-light/delivery-closed-risk-still-active.png) | 1920/light | O03 已关闭处置仍保留风险 | `d0822cb67bad6ae868f0f9a5b09d6832feeecf946f3be2acb5f903b22c235969` |
| [F-OLD-006](/private/tmp/aps-final-operations-F.TQejHX/F13-copy-matrix4-pytest/test_final_operations_main_con0/operations-1920-light/probe-normal-1920-light/delivery-reopen-history.png) | 1920/light | O04 处置历史旧新值与原始依据 | `3f236df76ce881312de112084ac055de6ea0a5701bc89b97b0a1fc21975b5765` |
| [F-OLD-072](/private/tmp/aps-final-operations-F.TQejHX/F13-copy-matrix4-pytest/test_final_operations_main_con2/operations-1392-light/probe-normal-1392-light/pending-batches-and-readiness.png) | 1392/light | O05 待排批次齐套表 | `90bc1acf6212dcbea0f1929357d96db9779fca578dfe92f3f67157422c2c6e2a` |
| [F-OLD-075](/private/tmp/aps-final-operations-F.TQejHX/F13-copy-matrix4-pytest/test_final_operations_main_con2/operations-1392-light/probe-normal-1392-light/candidate-directory.png) | 1392/light | O06 既有候选目录 | `921b889da0f5b0663a841eaf167e71c61a1b8bee77cdb7840f0ba45c0211bdb5` |
| [F-OLD-076](/private/tmp/aps-final-operations-F.TQejHX/F13-copy-matrix4-pytest/test_final_operations_main_con2/operations-1392-light/probe-normal-1392-light/create-preview.png) | 1392/light | O07 外协新增预览 | `eecc6e4cd2a0d55c31835221a01f11e25d7d8f2e65c3e4a895730a686ac1ad80` |
| [F-OLD-081](/private/tmp/aps-final-operations-F.TQejHX/F13-copy-matrix4-pytest/test_final_operations_main_con2/operations-1392-light/probe-normal-1392-light/correction-preview.png) | 1392/light | O08 外协更正旧新值预览 | `0b148f4fb3846804d149913bc216bf200a62ab6a51f4fd9914c4bc0195597b6c` |
| [F-OLD-078](/private/tmp/aps-final-operations-F.TQejHX/F13-copy-matrix4-pytest/test_final_operations_main_con2/operations-1392-light/probe-normal-1392-light/external-closed-risk-still-active.png) | 1392/light | O09 在途外协物流详情 | `571ef18de3552caf2fe6a21b2166ccb9ec19b40bcefd848c98478915bfe82634` |
| [F-OLD-019](/private/tmp/aps-final-operations-F.TQejHX/F13-copy-matrix4-pytest/test_final_operations_main_con0/operations-1920-light/probe-normal-1920-light/external-reopen-history.png) | 1920/light | O10 外协处置历史来源 | `8fb69abcb421dffb7a40e97f6b818398d3ecdba0d329e2411972008373d30345` |
| [F-OLD-082](/private/tmp/aps-final-operations-F.TQejHX/F13-copy-matrix4-pytest/test_final_operations_main_con2/operations-1392-light/probe-normal-1392-light/outsourcing-returned.png) | 1392/light | O11 外协已回厂结果表 | `6f7c1cb8b27d8b6390a77be11d2d94b221faab0c99e8f2f9c50126f720c21765` |
| [F-OLD-023](/private/tmp/aps-final-operations-F.TQejHX/F13-copy-matrix4-pytest/test_final_operations_main_con0/operations-1920-light/probe-normal-1920-light/outsourcing-history.png) | 1920/light | O12 外协物流事实历史 | `f25e6d6058bb0f12fdc98b9e61a6d7936e689635d7994599568bed6e6ba6ecd4` |
| [F-OLD-024](/private/tmp/aps-final-operations-F.TQejHX/F13-copy-matrix4-pytest/test_final_operations_main_con0/operations-1920-light/probe-normal-1920-light/system-overview.png) | 1920/light | O13 系统概况与八项自检 | `e91e77b24d4a4bebb2a8298d928ed9fafa267365e5c07b4f7abf1bdabfad8e04` |
| [F-OLD-086](/private/tmp/aps-final-operations-F.TQejHX/F13-copy-matrix4-pytest/test_final_operations_main_con2/operations-1392-light/probe-normal-1392-light/system-config-unknown.png) | 1392/light | O14 配置结果未知与原请求保留 | `9d85f31d4c47bbc8b095eacd281749bdc365eea681faf94e04f448569c86c635` |
| [F-OLD-057](/private/tmp/aps-final-operations-F.TQejHX/F13-copy-matrix4-pytest/test_final_operations_main_con1/operations-1920-dark/probe-normal-1920-dark/system-config-original-receipt.png) | 1920/dark | O15 配置原回执 | `d15cb4bdb77e4e38c105d45aa57b966ab4ba0ffca13e7526fac9dfbbb5ecc572` |
| [F-OLD-029](/private/tmp/aps-final-operations-F.TQejHX/F13-copy-matrix4-pytest/test_final_operations_main_con0/operations-1920-light/probe-normal-1920-light/system-logs.png) | 1920/light | O16 日志筛选、来源和导出反馈 | `638cb41110f252f9f722643d26f68f0e69f3740a0f11c6857815174779f602be` |
| [F-OLD-030](/private/tmp/aps-final-operations-F.TQejHX/F13-copy-matrix4-pytest/test_final_operations_main_con0/operations-1920-light/probe-normal-1920-light/system-backup-created.png) | 1920/light | O17 备份筛选及下载反馈 | `a5e696d49b1bae7d7e98b793c52386d4f144153d9cd21a9e67c1e267a5469e72` |
| [F-OLD-031](/private/tmp/aps-final-operations-F.TQejHX/F13-copy-matrix4-pytest/test_final_operations_main_con0/operations-1920-light/probe-normal-1920-light/system-backup-deleted.png) | 1920/light | O18 删除后无选中详情的备份表 | `d026dba904ed634a473033062c3c15bf198e0fefec6d2e2708bddf0276a08471` |
| [F-OLD-032](/private/tmp/aps-final-operations-F.TQejHX/F13-copy-matrix4-pytest/test_final_operations_main_con0/operations-1920-light/probe-read-controls-1920-light/config-restarted-process-readback.png) | 1920/light | O19 重启读取已保存配置 | `46dbf1dd6c8404451627c610f4f490994b9ba5fc3bab12ddfcdb67ef961ffba8` |
| [F-OLD-001](/private/tmp/aps-final-operations-F.TQejHX/F13-copy-matrix4-pytest/test_final_operations_history_0/operation-edges/probe-edges-1392-light/invalid-stored-config-is-not-silently-saved.png) | 1392/light | O20 旧存配置异常显式提示 | `56550fad2ff27e5b1e24046b3b4ff7d870fe0c28306a0b761b8640ae64182941` |
| [F-OLD-002](/private/tmp/aps-final-operations-F.TQejHX/F13-copy-matrix4-pytest/test_final_operations_history_0/operation-edges/probe-edges-1392-light/real-backup-storage-failure-retains-original-request.png) | 1392/light | O21 备份存储失败保留原请求 | `334c8f22a83c14bef95409dcdd0f301c499cdcbecb63dd8d0dd9399132512f85` |
| [F-OLD-123](/private/tmp/aps-final-operations-F.TQejHX/F13-copy-matrix4-pytest/test_final_operations_pending_0/cold-restore/probe-cold-1392-light/cold-pending-readonly.png) | 1392/light | O22 冷启动未完成维护 | `757b530598c3872745a61a53ebf27cedd70becd1444b6b3dff26805bba55085e` |
| [F-OLD-124](/private/tmp/aps-final-operations-F.TQejHX/F13-copy-matrix4-pytest/test_final_operations_pending_1/cold-restore/probe-cold-1392-light/cold-corrupt-readonly.png) | 1392/light | O23 冷启动损坏维护记录 | `3547fd9a177c3f9e1f911803bba8dd6b792010191a0997c79ac33d10e104816d` |
| [F-OLD-125](/private/tmp/aps-final-operations-F.TQejHX/F13-copy-matrix4-pytest/test_final_operations_real_cle0/maintenance-read-controls/probe-read-controls-1392-light/real-cleanup-event-without-file-capabilities.png) | 1392/light | O24 真实清理事件正文 | `fec6641abed3fea71cc66b05f57cef3b0233dc8a6b25f3bb48f7a59171a846ca` |
| [F-OLD-126](/private/tmp/aps-final-operations-F.TQejHX/F13-copy-matrix4-pytest/test_final_operations_real_cle0/maintenance-read-controls/probe-read-controls-1392-light/sample-validation-is-explicitly-unsaved.png) | 1392/light | O25 样例校验通过但未保存 | `e8a2b8e58be82f7b8136276679bbb135ae6b829c297dfd40056db47ddf078174` |
| [F-OLD-137](/private/tmp/aps-final-operations-F.TQejHX/F13-copy-matrix4-pytest/test_final_operations_restore_2/restore-host/probe-restore-1392-light/restore-result-readonly.png) | 1392/light | O26 成功恢复的 warm 阶段展开 | `01feb4ef9b58aa36f983bec83534dc690bf25306ef202d45f952635681524ac2` |
| [F-OLD-127](/private/tmp/aps-final-operations-F.TQejHX/F13-copy-matrix4-pytest/test_final_operations_restore_0/restore-host/probe-read-controls-1920-light/real-restore-event-after-process-restart.png) | 1920/light | O27 新进程真实恢复事件详情 | `4db9705f8480f35e0651387ab76b217d74cba9913ddb6cf0f179b3c5db74c2f3` |
| [F-OLD-144](/private/tmp/aps-final-operations-F.TQejHX/F13-copy-matrix4-pytest/test_final_operations_restore_4/restore-failure/probe-restore-1392-dark/restore-result-readonly.png) | 1392/dark | O28 恢复失败已回滚 warm | `91f00d0aa9176b1585a1a5597e7d200ea678a8ada79ce1df8c41f90b1cd99a52` |
| [F-OLD-145](/private/tmp/aps-final-operations-F.TQejHX/F13-copy-matrix4-pytest/test_final_operations_restore_4/restore-failure/probe-restore-1392-dark/restore-refresh-still-readonly.png) | 1392/dark | O29 已回滚冷刷新只读 | `145409594bd99f19957c2abf8a770092ffc8a7a4addc6c3700d019bed90e984f` |
| [F-OLD-147](/private/tmp/aps-final-operations-F.TQejHX/F13-copy-matrix4-pytest/test_final_operations_restore_5/restore-failure/probe-restore-1392-dark/restore-result-readonly.png) | 1392/dark | O30 回滚失败 warm | `f46057c5b6f31ecf3fa542bb580f9935fcefa98b024ff655078801c6b4fbb4ae` |
| [F-OLD-148](/private/tmp/aps-final-operations-F.TQejHX/F13-copy-matrix4-pytest/test_final_operations_restore_5/restore-failure/probe-restore-1392-dark/restore-refresh-still-readonly.png) | 1392/dark | O31 回滚失败冷刷新只读 | `139ccd172c65ca10a3285f7bffdf9260c137357c5e19f118d9ec8ff862b4c834` |
| [F-OLD-151](/private/tmp/aps-final-operations-F.TQejHX/F13-inflight1-pytest/test_final_operations_restore_0/restore-inflight/probe-restore-1392-light/restore-waits-for-inflight-http-and-real-worker.png) | 1392/light | O32 等待真实在途请求和 worker | `a736eea934ee1df05aa1c97db00da030dc852ad70579529fbd60174ce2121d5b` |

## 旧图适用范围

- **O01 值班台概况及筛选控件**：`WBP-DASH-001.metric-delivery`、`WBP-DASH-001.metric-pressure`、`WBP-DASH-001.metric-external`、`WBP-DASH-001.metric-actual`、`WBP-DASH-001.metric-pending`、`WBP-DASH-001.card-delivery`、`WBP-DASH-001.card-actual`、`WBP-DASH-001.card-external`、`WBP-DASH-001.card-downtime`、`WBP-DASH-001.card-material`、`WBP-DASH-001.card-candidate`、`WBP-DASH-001.category-select`、`WBP-DASH-001.tab-items`、`WBP-DASH-001.tab-analysis`、`WBP-DASH-001.tab-compare`、`WBP-DASH-001.tab-records`、`WBP-DASH-001.keyboard-tabs`、`WBP-DASH-002.status-all`、`WBP-DASH-002.status-open`、`WBP-DASH-002.status-new`、`WBP-DASH-002.status-following`、`WBP-DASH-002.status-verification`、`WBP-DASH-002.status-closed`、`WBP-DASH-002.search-batch`、`WBP-DASH-002.search-owner`、`WBP-DASH-002.search-action`、`WBP-DASH-002.search-remark`、`WBP-DASH-002.clear`。指标、类别、页签、搜索与默认列表。仅控件布局；点击、键盘、不同查询结果不是一张图证明。
- **O02 处置编辑字段**：`WBP-DASH-003.edit-status`、`WBP-DASH-003.edit-owner`、`WBP-DASH-003.edit-deadline`、`WBP-DASH-003.edit-action`、`WBP-DASH-003.edit-remark`、`WBP-DASH-003.submit`、`WBP-DASH-003.cancel`、`WBP-DASH-004.edit-completed-at`、`WBP-DASH-004.edit-evidence-ref`、`WBP-DASH-004.edit-completion-result`、`WBP-DASH-004.close`。表单字段与按钮；不包括错误、重开原因框或提交回执。
- **O03 已关闭处置仍保留风险**：`WBP-DASH-004.view-closed`、`WBP-DASH-004.retain-risk-facts`。已关闭标记、责任和完成字段、原始风险。数据库事实未改仍看 B/P。
- **O04 处置历史旧新值与原始依据**：`WBP-DASH-005.preserve-closed-history`、`WBP-DASH-006.open-history`、`WBP-DASH-006.select-history`、`WBP-DASH-006.reverse-order`、`WBP-DASH-006.expand-before-after`、`WBP-DASH-006.source-records`。展开的历史旧新字段和交期来源；第二页重进另见 D01。
- **O05 待排批次齐套表**：`WBP-DASH-001.metric-pending`、`WBP-DASH-012.batch`、`WBP-DASH-012.quantity`、`WBP-DASH-012.due-date`、`WBP-DASH-012.ready-status`、`WBP-DASH-012.ready-date`、`WBP-DASH-012.constraints`。批次、数量、交期、齐套状态和日期；约束区实际为当前未选定，不冒称某个批次约束详情已展示。
- **O06 既有候选目录**：`WBP-DASH-014.existing-candidates`。既有运行与候选目录入口，不代表为当前问题生成了独立候选。
- **O07 外协新增预览**：`WBP-DASH-010.preview`、`WBP-DASH-010.save`、`WBP-DASH-010.cancel`。新增物流登记核对弹窗，非生产完工回执。
- **O08 外协更正旧新值预览**：`WBP-DASH-010.correct`、`WBP-DASH-010.preview`。更正预览的旧新值布局；回厂预览为同组件值/文案 alternate，回厂实际时间分支仍看既有 K。
- **O09 在途外协物流详情**：`WBP-DASH-009.filter-awaiting`、`WBP-DASH-009.filter-overdue`、`WBP-DASH-009.tracking-basis`、`WBP-DASH-014.return-context`。图片实际是外协物流在途/超期汇总与详情，不因文件名带 closed 就证明处置关闭。
- **O10 外协处置历史来源**：`WBP-DASH-005.preserve-closed-history`、`WBP-DASH-006.source-records`。外协来源块与历史旧新值；物流来源字段与交期来源不同，单列。
- **O11 外协已回厂结果表**：`WBP-DASH-009.filter-returned`、`WBP-DASH-009.tracking-basis`。已回厂筛选及物流事实，不等同工序完工。
- **O12 外协物流事实历史**：`WBP-DASH-009.tracking-basis`、`WBP-DASH-010.correct`、`WBP-DASH-010.original-receipt`。物流事实三条历史及展开的原值、新值、原因；不是确认保存瞬间的回执弹窗，直接回执见 N20。
- **O13 系统概况与八项自检**：`WBP-SYS-001.source-current`、`WBP-SYS-001.source-sample`、`WBP-SYS-001.tab-overview`、`WBP-SYS-001.tab-backups`、`WBP-SYS-001.tab-logs`、`WBP-SYS-001.tab-config`、`WBP-SYS-001.keyboard-tabs`、`WBP-SYS-001.metric-page`、`WBP-SYS-001.metric-source`、`WBP-SYS-001.metric-database`、`WBP-SYS-001.metric-backup`、`WBP-SYS-002.row-backups`、`WBP-SYS-002.row-logs`、`WBP-SYS-002.row-config`、`WBP-SYS-003.check-runtime`、`WBP-SYS-003.check-scripts`、`WBP-SYS-003.check-ui`、`WBP-SYS-003.check-icons`、`WBP-SYS-003.check-styles`、`WBP-SYS-003.check-model`、`WBP-SYS-003.check-download`、`WBP-SYS-003.check-theme`、`WBP-SYS-003.rerun`、`WBP-SYS-003.timestamp`、`WBP-SYS-004.download-json`。宽屏完整八项检查表；下载 JSON 的内容正确性不是像素证明。
- **O14 配置结果未知与原请求保留**：`WBP-SYS-018.unknown-result`、`WBP-SYS-018.lookup`、`WBP-SYS-019.pending`、`WBP-SYS-019.unverified`。真实丢失响应后的待核实原请求、只读字段和查询动作。
- **O15 配置原回执**：`WBP-SYS-018.save`、`WBP-SYS-018.original-receipt`、`WBP-SYS-018.lookup`、`WBP-SYS-018.reload`。配置原请求号和回执；不与 file_operation 回执正文混用。顶部存在原截图的滚动留白，未改图。
- **O16 日志筛选、来源和导出反馈**：`WBP-SYS-011.runtime-source`、`WBP-SYS-011.operation-source`、`WBP-SYS-011.columns`、`WBP-SYS-011.detail`、`WBP-SYS-012.search-detail`、`WBP-SYS-012.search-file`、`WBP-SYS-012.type-runtime`、`WBP-SYS-012.type-operation`、`WBP-SYS-012.status`、`WBP-SYS-012.level`、`WBP-SYS-012.record-set`、`WBP-SYS-012.start-date`、`WBP-SYS-012.end-date`、`WBP-SYS-012.clear`、`WBP-SYS-012.page`、`WBP-SYS-012.detail`、`WBP-SYS-013.export`、`WBP-SYS-014.build-zip`、`WBP-SYS-014.download-zip`。筛选控件、来源可用/为空/缺失、下载提示及表头/部分行；完整正文见 D04。
- **O17 备份筛选及下载反馈**：`WBP-SYS-005.time`、`WBP-SYS-005.type`、`WBP-SYS-005.status`、`WBP-SYS-005.filename`、`WBP-SYS-005.size`、`WBP-SYS-005.detail`、`WBP-SYS-005.unread-state`、`WBP-SYS-006.search`、`WBP-SYS-006.type-manual`、`WBP-SYS-006.type-auto`、`WBP-SYS-006.type-before-restore`、`WBP-SYS-006.type-restore`、`WBP-SYS-006.type-cleanup`、`WBP-SYS-006.status`、`WBP-SYS-006.start-date`、`WBP-SYS-006.end-date`、`WBP-SYS-006.clear`、`WBP-SYS-007.previous`、`WBP-SYS-007.next`、`WBP-SYS-007.size-10`、`WBP-SYS-007.size-25`、`WBP-SYS-007.size-50`、`WBP-SYS-007.close-x`、`WBP-SYS-007.close-escape`、`WBP-SYS-007.full-body`、`WBP-SYS-007.validation-details`、`WBP-SYS-008.download-backup`、`WBP-SYS-010.select`。实际是下载提示、备份表及选中文件详情；不是创建成功原回执，底部文件操作不全部在此宽屏视口内。
- **O18 删除后无选中详情的备份表**：`WBP-SYS-010.filesystem-removal`。表内已无被删文件及展开详情；旧下载提示仍在，不能称其为删除回执。磁盘删除由 B/P 证明。
- **O19 重启读取已保存配置**：`WBP-SYS-016.read-snapshot`、`WBP-SYS-018.restart`、`WBP-SYS-009.preserve-new-data`。正式配置读回状态；source11 的 73 与 source10 的 37 是同组件数据差异，保留不同进程证据，不虚称图片相同。
- **O20 旧存配置异常显式提示**：`WBP-SYS-016.unknown-values`。旧值异常、原值和缺省值均可见；不等同普通输入校验错误。
- **O21 备份存储失败保留原请求**：`WBP-SYS-008.failure`、`WBP-SYS-019.failure`、`WBP-SYS-019.pending`。真实存储故障后维护只读、原请求与未知结果；不同于已完成回执。
- **O22 冷启动未完成维护**：`WBP-SYS-019.blocked`、`WBP-SYS-019.pending`、`WBP-SYS-009.restored-readonly`。未完成维护的冷启动入口、查原结果；不代表 warm busy 或成功恢复。
- **O23 冷启动损坏维护记录**：`WBP-SYS-019.blocked`、`WBP-SYS-019.failure`。记录损坏明确警告及来源缺失；不能折叠为正常 pending 文案。
- **O24 真实清理事件正文**：`WBP-SYS-006.type-cleanup`、`WBP-SYS-007.full-body`、`WBP-SYS-007.validation-details`。清理事件正文；没有下载/恢复/删除文件能力，不冒充备份文件。
- **O25 样例校验通过但未保存**：`WBP-SYS-001.source-sample`、`WBP-SYS-017.validate`、`WBP-SYS-017.unsaved-preview`。八字段样例草稿预览和未保存提示；展开规则正文另用 N17。
- **O26 成功恢复的 warm 阶段展开**：`WBP-SYS-009.protection-backup`、`WBP-SYS-009.verify`、`WBP-SYS-009.restored-readonly`。成功结果、保护副本和展开阶段的可见部分；时间线超出视口的尾部不是已看。
- **O27 新进程真实恢复事件详情**：`WBP-SYS-006.type-restore`、`WBP-SYS-007.full-body`、`WBP-SYS-007.validation-details`、`WBP-SYS-009.restart`。实际恢复事件正文，禁用文件型操作能力。
- **O28 恢复失败已回滚 warm**：`WBP-SYS-009.rollback`、`WBP-SYS-019.failure`。恢复失败已回滚的 warm 文案、保护副本与阶段；不是成功恢复。
- **O29 已回滚冷刷新只读**：`WBP-SYS-009.rollback`、`WBP-SYS-009.restored-readonly`、`WBP-SYS-019.blocked`。冷刷新仍保持已回滚、重启要求和独立查询结构。
- **O30 回滚失败 warm**：`WBP-SYS-009.rollback-failure`、`WBP-SYS-019.rollback-failure`。需人工核查、数据来源未知、停止使用；不能用已回滚分支代表。
- **O31 回滚失败冷刷新只读**：`WBP-SYS-009.rollback-failure`、`WBP-SYS-009.restored-readonly`、`WBP-SYS-019.rollback-failure`、`WBP-SYS-019.blocked`。冷启动入口仍要求人工核查，未恢复普通业务视图。
- **O32 等待真实在途请求和 worker**：`WBP-SYS-009.drain`、`WBP-SYS-019.pending`。真实 warm 等待阶段；只有 1392/light，不人为添加四图门槛。

## 代表关系和未覆盖部分

- O02 处置字段代表同source10的交期/外协处置表单；外协来源事实结构另列O09/O10。O08更正预览代表回厂预览的相同旧新值组件，其他PNG不算已看。
- D03/D04按四组合将正常before/after/inactive选择归到同source18相同组件；D05禁用状态、D06替换警告、D07旧key警告分开。
- A06/A07、O19/O26包含source11备用图时，保留不同全源绑定；机器索引核对组件SHA是否相同，不把旧Main签字扩展给这些图。
- R01的material/downtime/actual旧图只拍到泛型详情或专业表标题，不把文件名当明细可见证据。R02旧翻页图实际已回第一页；R03旧日志detail另存备用，当前D04是独立精确Main签图。
- 配置回执O15与文件操作回执N18是不同正文分支，分别给图。处置保存核实用N19，外协保存核实用N20；不会再用表单或历史表冒充回执弹窗。
- JSON/SQLite/CSV/ZIP内容、跨页总行、键盘行为、SQL保留、重启PID及文件系统删除仍由B/K/P证明。228项反向索引都存在，不因此删action、改分母或自动标V N/A。
- 本轮列出的独立缺图状态已有代表图。相同结果组件仅数据变化的动作分支明示共用理由与未直接执行部分；本文件没有宣称全部V已经闭合。

原 runtime-evidence.json、action-evidence.json、source-hashes.json、b-shared-source.json 和 Main两份V记录均保持原SHA。源/资产只读核验，无产品改动、无旧快照重写、无fullsnapshot重抓、无全量门禁或clean-worktree proof。
