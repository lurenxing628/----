---
doc_type: feature-design
feature: 2026-09-12-wbui-a11y-sweep
roadmap: workbench-ui-refinement
roadmap_item: wbui-a11y-sweep
status: approved
summary: 统一表格语义、禁用原因及虚拟甘特键盘可达性
tags: [workbench, ui, accessibility]
---

批准依据为本轮路线图及审查修订。现状：多个数据表无caption/scope，部分禁用按钮原因只在title，虚拟甘特有隐藏表头或只能遍历当前可见项。变化：真实表格有可读名称和列/行表头关系；有禁用原因的业务按钮能看见并由辅助描述读取；内部引用不进入无障碍名称；Canvas/虚拟甘特通过业务对象键盘选择及滚动让全部数据可达。

职责：ResourceControls提供Button的reasonDisplay；各域owner给真实业务表、控件及Canvas接线；主线程核查全域残余并执行最终真实浏览器检查。共享代码不靠运行时批量补DOM掩盖消费者缺失。

不改变API、任务身份、筛选范围、排序或虚拟化数据集合。不把未渲染的内部行强塞屏幕DOM。选择变化只影响当前视图，不写业务事实。

结构健康度：共享可视原因位于现有Button，表格语义落原组件，键盘选择使用已有模型及独立辅助函数；不新造重复表格库。挂载点包括共享Button、各表头与caption、Canvas键盘事件与对象定位。

验收：关键列表正确名称/表头scope；禁用原因鼠标之外可读且视觉可见；新旧视图URL仍定位同一对象；键盘可到首尾和视口外对象并保持选择/滚动同步；没有哈希型aria-label；焦点环和Esc保持既有可用性。最终证据绑定本次build_id，不能只报源文本grep通过。
