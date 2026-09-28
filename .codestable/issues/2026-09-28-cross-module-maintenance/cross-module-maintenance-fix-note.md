---
doc_type: issue-fix
issue: cross-module-maintenance
path: fast-track
status: fixed
fix_date: 2026-09-28
tags: [material, batch, process, resource, calendar]
---

# 物料、工艺及资源维护闭环修复

用户授权修复已确认bug，并仅调用一个独立子代理复扫相同模块。唯一子代理 cross_module_independent_audit 只读；主代理实施。保留前轮204条工作区改动，不提交、不推送、不操作正式库。修改前快照 /tmp/aps-cross-module-fix-before-20260928.tar.gz 及同名JSON。

## 必须完成

- [x] 批次物料需求新增、数量维护、明确移除、重新确认齐套；空到料量不得当作到齐。
- [x] 复制保留物料需求但重置到料和齐套；数量改变须重新核对物料。
- [x] 设备停机时段登记、修改、撤销与并发/身份保护。
- [x] 归属页更换实际工种清除旧定额并守住校准锁。
- [x] 班次休息切回工作不能沿用自动00:00。
- [x] 全局日历的单次夜班起止可直接维护，保留一个连续窗口模型。
- [x] 批次物料数量、资源库存、供应商默认周期保留原精度。
- [x] 物料文件中文状态，兼容英文；已有批次文件支持稀疏增量维护。
- [x] 批次设备、人员、供应商候选显示能力匹配，不让用户提交后才试错。
- [x] 独立复扫：个人日历效率不因备注编辑被取整，清空结束时刻明确生效。
- [x] 独立复扫：日历文件分钟工时及效率无损往返。
- [x] 独立复扫：个人日历写令牌绑定原月份状态；范围清除绑定原范围及全部日期事实，范围改动使预检失效。
- [x] 独立复扫：跨午夜相邻窗口不重复计时，推进与累计共用有效优先级时间片。
- [x] 最后一次日常门禁通过，核对最终源码指纹并交付。
- [x] 独立复扫：单条及列表删除保护复用完整依赖目录，保留个人日历、设备授权、停机和执行记录。

## 明确暂缓

修复与复核完成后才向用户集中询问：分阶段/分工序用料与分次到料模型；多工种设备和同工种内外切换；一天多段班次及午休。这些不在本轮实施中扩展。

## 验证边界

- 子代理只读复扫确认 8 类遗漏，二次复核提出的旧草稿配新令牌、无关人员阻断候选、文件时刻截秒、日期上界溢出均已处理；最后定点复核 78 passed，无新具体遗漏。
- 跨夜独立 oracle 90 组及 12 组推进/计时往返复算通过。工时按日历小时统计，效率在原排产层使用，不重复相乘。
- 主链 Pyright 为 0 errors / 0 warnings；架构检查 20 passed。全仓 Ruff 通过。
- Chrome 109 实际隔离库验收 6 条流程全部通过（无页面错误、无隔离违规），包含资源库存/供应商周期精度、停机新增/编辑/取消、个人日历并发刷新/精度/清除结束、夜班工时及结束时刻、班次休息转工作、批次需求保存及小数显示。相关旧组件验收 2 passed（66+16 场景）；浏览器启动/导航合同 30 passed。
- 日常门禁首轮失败已逐项定位：新版行为的旧断言、浏览器路径未显式传入、列表与详情关联统计不一致、空需求复制触碰自增序列、两处新增私有导入及术语检查。业务缺口已修复，测试按新契约更新；最终日常门禁退出码 0：并行 11216 passed，串行 959 passed，重点冒烟 7 passed。
- 构建目标 Chrome 109，资源均本地打包，schema 仍为 v33；未对正式库排产或写数据，未提交或推送。不声明完整门禁或 clean-worktree proof。
- 原始证据在 `evidence/cross-module-maintenance-20260928/`，本轮文件变化和指纹见 `verification-source-final.json`；已有 204 条工作区改动保留在修改前快照中。

## 关键落点

- 批次需求：`core/services/workbench/batch/materials.py`、`frontend/workbench/app/BatchMaterialEditor.jsx`；复制及数量变化：`batch/bulk.py`、`batch/service.py`、`core/services/batch/copy_batch.py`。
- 停机：`core/services/workbench/resource/downtimes.py`、`web/routes/workbench/downtimes.py`、`frontend/workbench/app/MachineDowntimePanel.jsx`。复用永久停机引用和通用命令回执，没有新建第二套身份或事务。
- 工种换类：`core/services/workbench/process/stage_apply.py`；旧工时随实际工种改变清除，一次写入，校准锁在预检和写事务内均检查。
- 候选能力：`core/services/workbench/batch/resource_choices.py`；错误候选明确标不可用，外协不依赖人员技能资料。
- 关联保护：`data/repositories/workbench_resource_dependencies.py`，单条、文件及分页列表共用同一依赖目录。
- 日历：`core/services/scheduler/calendar/engine.py` 和 `working_hours.py` 共用自然日有效片；全局当前日窗口优先于前一夜班。个人日历令牌绑定原月份/原范围，前端另绑定编辑基底。
- 模板填写说明、用户说明书及系统速查表均同步；旧英文物料状态和完整批次模板继续兼容。


## 最终交付证据

- `evidence/cross-module-maintenance-20260928/daily-final.log`：整轮日常门禁通过，非完整/clean gate。
- `browser/opt-in-browser-20260928-170028.json` 及 `browser/final/`：6 条当前页面实际读写流程，5 张截图，隔离库与服务器关闭记录齐全。
- `final-targeted.log`：关键写入、复制、能力候选及架构 30 passed；`navigation-browser.log`：导航合同 30 passed；`batch-widgets.log`：Chrome109 2 passed、82 场景；`pyright-main.log`：0 errors。
- 最终构建 ID：`f0adc255e3c277fef29e5479e1c936abac650385fa2edd09c8e46ce7c6d257e6`。
- 门禁后只校正批次模板“交期可稍后补充”的填写说明，未改运行行为；描述符测试 73 passed，生成文档一致性及相关 Ruff 通过，见 `template-docs-final.log`。
- `git diff --check` 通过。工作区仍保留前轮与本轮修改，没有提交、推送或正式库写入，不声明 clean-worktree proof。
- 独立审查末次追加核对分页/详情关联统计、空需求复制和停机入口，均确认正确，无新具体遗漏。
