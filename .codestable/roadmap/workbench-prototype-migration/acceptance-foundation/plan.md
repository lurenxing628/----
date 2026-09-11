---
doc_type: acceptance-plan
status: snapshot-passed
date: 2026-09-10
scope: B-owned Main foundation browser verification
---

# Main Foundation 真实验收

## 范围和边界

- B 仅写 `tests/workbench/final_foundation_live*.py`、`final_foundation_live*.cjs`、`test_final_foundation_live.py` 和本目录。复用 Main 的 `final_foundation_host.py`，不修改产品、宿主或 capacity 冻结文件。
- 使用真实 factory、managed runtime、独立临时数据库和 mixed seed。按 manifest 严格复制 Main 的完整预构建到该 fixture 的 `full-build/`，逐项核验资产字节及输入；不改全局 `static/workbench`，不访问旧 53144 宿主。
- 这是真实 Main 壳层和只读闭环验收；C/D/E/F 的领域业务流程仍由各自验收，不用壳层首屏或故障注入代替。
- 当前工作区有既有脏改，所有结果仅绑定记录下来的源码、构建及模板散列，不是最终 HEAD 或 clean-worktree proof。

## 已执行矩阵

| 项目 | 操作及断言 | 数量 | 当前状态 |
|---|---|---:|---|
| 首屏 | 1392x924、1920x1080，各浅/深色；逐个点击真实 14 项侧栏，核对导航顺序、完整标题、当前项、document title、真实读取和布局 | 56 | 56 passed |
| 正式方案 | 从真实目录 radio 选择 current official，caption 对照实际响应的名称、身份、版本及范围 | 4 | 4 passed |
| 交付风险 | 实际按钮进入 delay，14 项侧栏中 analysis 为父级当前项，再返回方案 | 4 | 4 passed |
| 输入及路由 | 使用真实 trusted key 输入 CAT-B，不使用 fill；核对单一甘特 DOM、query、焦点、跨页、后退、侧栏返回、reload 和鼠标滚动恢复 | 4 | 4 passed |
| 主题及刷新 | 实际主题按钮、Tab/Shift+Tab/Enter 焦点；刷新所选计划后保持 query 和 durable plan_ref | 4 | 4 passed |
| 冷启动故障 | Playwright route 实际带版本参数的 main/React URL，或只替换实际 boot JSON；注入必须命中；可读失败及真正重新加载 | 12 | 12 passed |
| 渲染故障 | 仅在测试响应中包装真实 PlanWorkspace 抛错，14 项导航仍可用；跨页、后退、同一对象重试 | 4 | 4 passed |
| 新宿主进程 | 4 个原 page/context 保活；只停止自有宿主并以新 PID、同端口、同 private root 启动；原页 reload 核对引用、query、主题和滚动 | 4 | 4 passed |
| 数据保留 | 两进程内只读前后全部行相等；跨启动只允许 plugins/load 审计及对应 sqlite_sequence 递增，原行不丢失 | 1 | passed |

空的执行排产表单尚未选择 scope，因此首屏 API 读取记为不适用，核对实际 preflight 表单和选择批次控件，不伪造一次排产成功。重启检查前通过真实“刷新所选计划”移除进程内 snapshot_ref；不得扩大成所有旧 snapshot token 都能跨进程使用的结论。

## 证据

- 每个 case 保存 viewport PNG、body 文本和像素非空检查；正常页面另查全局横向溢出、侧栏覆盖、标题/caption/控件重叠、外链。
- 保存真实生产 API 响应原文和 SHA-256、浏览器实际取得的构建资源散列、trusted key 及逐键 DOM/query/focus 状态。
- 故障和正常阶段日志分开；故障响应保存原/注入 SHA-256 和命中次数，不列为业务成功证据。
- 构建报告记录全部 manifest files/inputs 的逐项校验；动态 Jinja 模板另记录复制前后的散列，不声称其属于 manifest inputs。
- 重启证据包括 nonce、browser PID、4 个存活 page、两个宿主 PID、同 origin、两个正常退出记录、锁释放、不可变资产及数据库快照。

## 完成情况

- [x] 自有 probe 实现完整矩阵和同页跨进程 IPC。
- [x] 4 个 CJS 通过 Node 语法检查。
- [x] 3 个 Python 文件 Ruff 通过、Pyright 0 errors / 0 warnings。
- [x] 预构建复制、manifest/payload 变动拒绝、已登记输入变动拒绝的 4 项单元测试通过。
- [x] 保留 69ab 构建的中断尝试及真实输入异常，详见 `interrupted-attempt.md`。
- [x] D 完成同层 React key 修复，Main 的 64b6 完整构建经逐项校验后使用。
- [x] 新 fixture 完整执行矩阵，92/92 cases passed，108 张截图，156 次正常 production response。
- [x] B 人工抽检四组合各一张首屏及两张注入图；全部 56 首屏通过自动像素和 Main 几何检查。
- [x] 通知 Main 释放已加载产品集成写入；报告和分账证据在本目录。
- [ ] Main/V 逐页视觉终审及最终 HEAD 验证，由 Main 统筹，不冒称本轮已完成。

通过根为 `/private/tmp/aps-final-foundation-B.xYPahs/aps-workbench-live-2y19rdw0`，仅为 `unchanged_snapshot_not_final_HEAD`。本轮源漂移为空；没有把授权的未挂载叶笼统排除出守护。历史中断和采证修订轮均保留，不改写原结果。详见 `handoff.md` 和 `snapshot-evidence.json`。
