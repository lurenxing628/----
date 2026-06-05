# 逐簇爆炸对抗 r1 — 簇 C-NAV-PLANID（主透镜：承重误删）

> skeptic 第1轮 / 只读不改任何 .py / 行号 2026-06-05 实盘 rg 回盘（不信旧值）。
> 成员债 [R42, R60, R64, R65, R66]。本档默认怀疑：找不到爆点才算绿。
> 本簇 5 债自身全非承重（load_bearing=false / owner_pending=false），承重门控全来自**毗邻已 fixed 护栏 + 跨簇 R54**。

---

## 实盘回盘坐实（关键爆点行号，全部当前命中）

| 锚点 | 实盘 file:line | 用途 |
|---|---|---|
| C1 承重夹击（常规分支） | `scheduler_workbench_link_query.py:117 version / :118 plan_id / :119 plan_role / :120 scenario_id` | plan_id 被三个真身份参数**前后夹住**，误伤即 URL 丢身份 |
| C1 承重夹击（exec_review 分支） | `scheduler_workbench_link_query.py:153 version / :154 plan_id / :155 plan_role`（分支 :152 `if plan_style=="execution_review"`） | 第二处 emit，同构夹击 |
| R56 承重禁区 | `navigation_context.py:79 plan_role=plan_role if plan_role in VALID_PLAN_ROLES else ROLE_ADOPTED` / :80 scenario_id | 与 :78 plan_id 同调用不同 kwarg，语法独立 |
| R65 TARGET_PAGE_PATHS 陷阱 | `scheduler_navigation_links.py:7` import，真用在 `:177 build_report_navigation_links` | **绝不可删**（最大误删爆点） |
| R65 可删孤儿 import | `:4 urlencode`（唯一其他用 :76）/ `:6 query_for_target`（唯一其他用 :75） | 删 def 后成孤儿，可删 |
| R65 化简点 | `:160 plain_url or _target_url(...)`；specs 9/9 第3字段全非空字面量（:144-152） | 短路恒真，化简等价**仅依赖此不变量** |
| R66 LIVE 同名异签 | `scheduler_workbench_links.py:258 _context_summary(context, target_page, view=None)`，:404 build_workbench_link 调 | 禁误删；死副本在 reports_workbench.py:150 |
| R54 前置坐实 | `scheduler_workbench_links.py:206 guardrail_text:str="" / :207 guardrail_reason_type:str=""`；plan_id 形参 :191 | R42 删 :191 须 rebase 在 R54 新签名后 |
| R66 R54 上方符号 | `reports_workbench.py:36 _copy_plan_guard_fields`（R54 改），在死函数 :150 上方 | R54 落地漂移 :150，R66 须按 suffix 符号重定位 |
| roadmap 制度化 | `aps-frontend-workbench-items.yaml:289`（唯一真实，acceptance/checklist 是幻觉） | F 门 owner 对齐 |

---

## Q1 承重误删（主透镜，逐债）

- **R42**🟡：核心爆点 C1。删 `link_query:118/:154` plan_id emit 行时，**若以「DRY/对齐 _append_param 调用」名义连片删或上下错位**，会误伤紧邻 :117/:119/:120（version/plan_role/scenario_id）→ URL 丢真身份参数 → version 解析**静默错位**（无报错，报表打开错版本）。承重不对称落点=这三行是真消费、plan_id 是死叶子，**符号删 plan_id 单行、绝不连片**即可控。同理删 `navigation_context.py:78` 时禁碰 :79（R56 adopted 强制）/:80。
- **R60**🟡：字段表删行爆点。三张表（`navigation_links.py:12` / `:52` / `export_support.py:14`）删 plan_id 时，**若「对齐/统一元组」误删相邻承重透传键**（:13 back_to / scope_*/date_*/resource_* / :51 version / :63 plan_role）→ 隐藏表单/导出 URL 丢上下文 → 跨页跳转静默丢 date_range/resource/scope（high 级回归）。只删 plan_id 一行即可控。
- **R64/R65/R66**🟢（Q1 维度）：均非承重、纯删除，无承重不对称落点。R65 化简 :160 是等价替换（见 Q5）。

## Q2 分层导入环
全簇🟢：5 债全是**删除**操作（web/viewmodels、web/routes 内），不新增 import、不新建模块，不可能制造跨层 import 或导入环。R65 删 :4/:6 孤儿 import 是**减依赖**。0 AST 违规保持。

## Q3 迁移耦合
全簇🟢：plan_id 全链 `git grep core/ data/`=0，不进任何 resolver/query/v18·v19 DB CHECK。与 adopted-only 下沉 v19 CHECK（effective_plan_role=adopted）**无耦合**——plan_id 死叶子从不参与 plan_role 判定。改码不改迁移无启动探针炸。

## Q4 灵魂线热路径
全簇🟢：5 债全 P6 死码直删，**非 P4**，无 raise 改造、无静默回退、无新增兜底/except 吞错。与 LB03 latest_executable_official_version 热路径无交集。R65 化简是短路去冗余，不引兜底。

## Q5 收口行为等价
- **R65** :160 化简 `plain_url or _target_url(...)` → `plain_url`：9/9 specs 第3字段全为非空字面量（`/scheduler/...`），短路恒返回 plain_url，`_target_url` 永不求值，逐分支等价**成立**。⚠️但等价**只依赖「specs 第3字段恒非空」不变量**，无护栏=未来有人加 `plain_url=''` spec 即静默丢动态构造（旧:_target_url / 新:空 url）。
- R42/R60/R64/R66 纯删无新旧两路，不涉等价。

## Q6 测试迁移序
- **R42+R60 共享**同一组断言 `regression_reports_workbench_navigation_contract.py:109/:122/:126`（plan_id），**保留 :123/:127 back_to**。序：**先迁测试（去 plan_id 留 back_to）→ 再删生产 → 跑测试自证**。序错=中间态 CI 红（显式，可控）。两债 MUST 由合并 PR 一次迁，禁各改一遍。
- R64/R65/R66 测试零耦合（tests 零命中），无迁移序。

---

## 判定汇总

| 债 | 判定 | 核心依据 |
|---|---|---|
| **R42** | 🟡 | C1 承重夹击（link_query:117-120 / :153-155）；须符号删单行+rebase 在 R54 :206-207 后+迁测试在前 |
| **R60** | 🟡 | 字段表删行误伤相邻承重透传键（back_to/scope_*/version/plan_role）；MUST 与 R42 同提交，emit:118/154 归 R42 |
| **R64** | 🟢 | `_has_navigation_date_range:66-67` 零引用纯删；唯一隐患手滑碰相邻活函数（操作失误非债爆炸面） |
| **R65** | 🟡 | 三件套硬原子（缺一 NameError）；最大爆点误删 :7 TARGET_PAGE_PATHS（:177 真用）；化简等价缺不变量护栏 |
| **R66** | 🟢 | 死副本 :150 纯删；须按 suffix 符号重定位（R54 漂移）+ 禁误删 LIVE workbench_links.py:258 |

## 灾难链（红/黄债完整链）
- **R42-C1**：以 DRY 名义连片删 link_query:118 → 误删/错位 :117 version → URL 丢 version → 报表静默打开错版本（无报错）。
- **R60-C2**：统一元组误删 :13 back_to / export scope_* → 隐藏表单丢透传键 → 跨页跳转静默丢 date_range/resource/scope（high）。
- **R60-半截**：R60 单删字段表而 R42 留读存 → plan_id 仍写 context+emit 仍读 → 链接挂死键、表不认（新 P3）。
- **R65-误删 :7**：误判 TARGET_PAGE_PATHS 为孤儿删 → :177 build_report_navigation_links NameError → 报表导航条全挂。
- **R65-漏化简**：删 _target_url 不化简 :160 → import/lint NameError → 导航条全挂。

## 修正建议（前置/顺序/禁区）
1. **R54 先落（Batch-2）** → 门控 R42 删 :191 形参（rebase 在 :206-207 后）+ R66 按 suffix 重定位 :150。
2. **R42⇔R60 强制单次提交**；emit `link_query:118/:154` 唯一归 R42 删，R60 不重复删。
3. **禁区行**：link_query:117/119/120 + :153/155；navigation_context.py:79/80；reports_page_support LB06 adopted/scenario 强制分支；navigation_links.py:7 TARGET_PAGE_PATHS；三张表非 plan_id 键。
4. **R65** 只删 :4/:6 import（保 :7）；删 def 与化简 :160 同次；**补不变量护栏** `test_all_nav_specs_have_nonempty_plain_url` 钉死化简前提。
5. 测试迁移：plan_id 断言先退、back_to 断言保留、先测试后生产。
6. F 门：items.yaml:289 与 in-progress workbench roadmap owner 对齐后再删。

## 漏项（本轮新发现，计划未覆盖）
- **A. R65 不变量护栏缺位**：簇文件/dossier 把化简列为「逐分支等价、安全」，但**未把「补 specs 非空护栏测试」列为 R65 必做前置**。无护栏=化简正确性靠口头不变量，未来加 falsy spec 即静默回归。建议升级为 R65 硬前置（与三件套同提交）。
- **B. link_query:266 `_EXECUTION_REVIEW_FORBIDDEN_EXTRA_PARAMS` 相邻禁参逻辑**：execution_review 链有一套禁参白名单（:266 `if target_page=="execution_review" and _text(key) in _EXECUTION_REVIEW_FORBIDDEN_EXTRA_PARAMS`），dossier/簇文件**全未提及**。R42 删 plan_id emit 时须确认 plan_id 不在该禁参集内、且删 plan_id 不改变该分支语义——新承重相邻面，建议执行前 rg 该常量集核对。
