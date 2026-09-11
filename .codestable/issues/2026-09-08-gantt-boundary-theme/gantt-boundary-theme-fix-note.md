---
doc_type: issue-fix
date: 2026-09-08
slug: gantt-boundary-theme
status: implemented
scope: local workbench prototype
clean_worktree_proof: false
---

# 甘特边界与跨页主题修复

## 用户问题

- 交付优先方案中，018与024加工条相邻时像是左条压住右条，要求处理同类遮挡。
- 主工作台已经开启深色，进入方案试调却自动变成浅色。
- 后续反馈新增的白色高亮边框过于突兀，需要与原有选中样式一致。

## 事实与根因

1. 1392×924实测：018时间占位425–617px，024占位617–761px，结束/开始均为12:00，没有真实时间重叠。但原色块没有视觉间隔。
2. 短条存在真实遮挡：渲染器强制至少0.4%的时间宽度，加上按钮边框和内边距，2分钟、3分钟工序都被撑为10px；实际应约1.6px、2.4px，造成约8.41px重叠。
3. 选条重绘会重建时间区，横向滚动80px后点击可见任务，旧实现回到0，焦点也丢失。浏览器原生焦点滚动没有扣除冻结列宽度。
4. 现场甘特极短条的负偏移outline仍会越界；Tab也能聚焦完全被冻结列覆盖的报工条。子代理提供Chrome像素与原生Tab复现。
5. 试调恢复使用整个方案快照的旧theme，盖过`aps_kit_theme`；试调主题按钮只更新方案里的theme，没有写入全局偏好。试调HTML也缺少首次绘制前的主题初始化。

## 实际修改

| 文件（原型目录内） | 修改 |
| --- | --- |
| `trial-sample-views.js` | 移除强制时间宽度；真实时间占位与内部色块分离；复用冻结行列感知的焦点显示/恢复函数 |
| `trial-sample.css` | 色块左右各内收最多2px，保留原标签可用宽度；选中/焦点标记在内部裁剪；时间轨道建立自己的层叠上下文，不覆盖冻结列 |
| `PlanShared.jsx` | 选择工序后恢复时间区滚动及键盘焦点；Tab进入任务时扣除冻结行列 |
| `field-gantt.css` | 现场甘特焦点/关键链改为内部阴影，标记线着色不撑宽、不提层级 |
| `fg-screen-hooks.jsx`、`FieldGanttScreen.jsx` | 在原定位hook内补足焦点滚动，只调整当前条的可见性，不缩放、不跳过Tab顺序、不改选择/业务数据 |
| `trial-sample.js` | 恢复时全局主题优先；主题按钮写全局偏好，不保存/重写方案；同步storage、pageshow和窗口focus；主题保存失败单独报错，保留计划恢复错误 |
| `app.jsx` | 同步其他标签页和返回页面后的全局主题 |
| `trial-sample.html`、`index.html` | 试调在样式前初始化全局主题；更新10处本轮资源版本为内容哈希 |

原型目录：`前端设计/ui_kits/workbench/`。

新增测试：原型内 `tests/trial-gantt-boundaries.cjs`、`tests/workbench-theme-navigation.cjs`；仓库内 `tests/field-gantt-focus-boundaries.cjs`。更新原型 `tests/trial-sample-text.cjs`，继续逐个检查strong/small标签，不将新外观容器误当标签。

保留方案里的旧theme字段以兼容现有记录，但不再用它决定主题。进入试调、切换主题及跨标签页同步时，原方案JSON保持字节一致，含草稿、采用版本和历史。损坏的原记录也不覆盖。

白框反馈后进一步收敛：此前深色正文色被用作焦点描边，并与金色选中圈叠加。最终选中任务只保留原有金色标记，键盘焦点进入未选任务时用`--ui-primary`的1px内阴影；不另画白色圈或第二层outline。现场甘特的焦点与关键链按钮也使用同一蓝色细内标记，保留关键链本身的金色含义。对照截图：`evidence/focus-before-after.png`。

## 验证

| 实际运行 | 结果 |
| --- | --- |
| 计划甘特/独立试调边界Chrome | 最终810项通过；两尺寸×双主题×两入口，检查真实占位、实际分隔像素、点击/键盘、短条、真冲突分轨、冻结列与滚动保持，并锁住金色选中/蓝色细焦点、不叠白框 |
| 主题跨页Chrome | 110项通过；旧主题相反、真实链接进入/返回、浏览器返回、已打开标签页双向同步、草稿/采用记录保留、损坏记录与偏好写失败 |
| 现场甘特焦点Chrome | 最终435项通过；390/1024/1440px、深浅主题、极短原计划/实际/剩余条、原生Tab及Shift+Tab、条外像素不变，焦点及起止标记使用同一蓝色而非白框 |
| 最终入口全页/跨页Chrome | 247项通过、56截图；14页×两尺寸×双主题；无运行时错误、外部请求、资源加载失败或整页横向溢出 |
| 试调标签Chrome | 12组合、192标签通过，含390px；标签与真实条长没有退步 |
| 试调原有交互Chrome | 51项通过 |
| 本地模型 | 47个用例通过，计算、冲突、采用与数据保存合同保持 |
| 共享业务交互JSDOM | 140断言通过 |
| 本地资源与语法 | 234项通过，未新增生产依赖或远程资源 |

短条前后实测：2分钟由10px恢复为1.59375px，3分钟由10px恢复为2.390625px；相邻重叠从8.40625px变为0。长条仍按原真实时间比例占位，内部间隔不是调整生产开始或结束时间。真实冲突仍另分轨并显示风险，未通过位移时间掩盖。

子代理在白框反馈前的9项定向回归共12,214条断言通过（包括当时现场焦点399项，不与最终435项重复相加）。两个既有旧测试修改前亦失败，未通过修改断言掩盖：`tests/field-gantt-plan-a.cjs`在修改前现场报`Rows has no private hover or click state`；原型`tests/field-gantt-complex.integration.cjs`使用修改前六文件快照仍报`Chain node strip is available: 0 !== 7`。这两项不作通过声明，也不等同于新发现的运行时缺陷。原始命令结果摘录在`evidence/field-regression-outputs.json`。

## 证据

- 主线程修改前文件及短条前后测量：`/tmp/aps-gantt-boundaries-wdM79y/`。
- 最终边界：`/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-gantt-boundary-qa-5EyyCL/`。
- 最终主题：`/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-theme-navigation-KfABPC/`。
- 最终全页：`/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-workflow-qa-hdcU5J/`。
- 最终标签：`/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-trial-text-etrCn3/`。
- 现场复现：`/tmp/field-gantt-occlusion-evidence/`；最终蓝色细焦点：`/tmp/field-gantt-blue-focus-final/`。
- 同目录`evidence/`保留精选截图和JSON；临时目录不保证系统清理后仍存在。

本轮使用1个真实subagent检查并修复现场甘特，主线程负责计划/试调、主题及整合。浏览器均为隔离上下文，未读取或重写用户浏览器里的生产/示例记录。

## 边界

未改后端、排产模型或Win7/Python3.8运行时，未引入网络依赖。现有工作区仍有大量其他未提交内容，保持不动；既有暂存`tests/gate_meta/test_frozen_bundle_contract.py`的200行新增未变化。本轮未提交。未跑生产Python整仓门禁或Win7实机，本记录是原型局部证明，不是clean-worktree proof。
