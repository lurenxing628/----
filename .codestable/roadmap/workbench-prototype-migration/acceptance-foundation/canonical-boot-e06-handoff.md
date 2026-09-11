---
doc_type: acceptance-report
status: passed-bound-snapshot-not-final-head
date: 2026-09-11
scope: B canonical navigation and boot contracts
---

# E06 全部 252 项验收交接

## 结论

**252/252 通过，完整收尾验证通过。** 固定为 canonical 212 + boot 40，四种尺寸/主题组合各 63 项。24 个原页面及其 context 跨宿主重启保留，原页面、URL、业务对象及读取范围未被替换。

本结果绑定 E06 封板源码与 `06ad...` V2 测试，不是最终 HEAD/clean-worktree proof，不是正式 5000 性能证明。旧 legacy 92（56 首屏 + 16 故障 + 4 新 PID + 16 交互）未在本轮重跑，没有与本次 252 项相加冒充同版 344 项。

## 执行身份

| 项目 | 实际值 |
| --- | --- |
| E SOURCE_ROOT | `/private/tmp/aps-final-e-sealed-read-after-20260911-06/source` |
| E source-manifest SHA | `ba451495b7edf2382794236913f3ab3b58574b75a5734e5af7218c957e390ce4` |
| E source 聚合 SHA | `2d6c6f12a3b2496d791cd9eb6f846b4dd26260facc334d568a68166561cff1d5` |
| B 独立副本 | `/private/tmp/aps-final-foundation-B.xYPahs/E06-copy-C1frJv/source` |
| B 独立资产 | `/private/tmp/aps-final-foundation-B.xYPahs/E06-copy-C1frJv/prebuilt/static/workbench` |
| build_id | `86bae55877b7574a7dbccad0a61c2f4b714a3105500908d614b531ae31f90a2e` |
| asset-manifest SHA | `09f624979b2d9db12fa527ad4c62f610d61a7709d2da9df34732ab4840848b66` |
| V2 12 文件集合 SHA | `06ad141125f5bd09672ea60dcebb6d19b9c292d6f8296989127bacb73266be61` |
| 实际新 fixture | `/private/tmp/aps-final-foundation-B.xYPahs/E06-copy-C1frJv/fixtures/aps-workbench-live-e3pcktu9` |
| 宿主 PID | `54621 → 57034` |
| 浏览器协调 PID | `54641` |
| 实际同一地址 | `http://127.0.0.1:51071`，测试结束后已关闭 |

- 第一次复制即通过，没有失败复制冒计成功。6532 源码文件共 319481080 bytes，全部文件 SHA/bytes/mode、目录 mode 与 E 原封板相等；复制前后 E 源码和资产不变。
- 资产为 223 个 manifest 条目加 manifest 本身，共 224 文件。315 个构建 input 全部匹配 B 源码，未重 build。
- E06 已包含同 SHA/mode 的全部 12 个 V2 文件。仍按明确清单机械覆盖到 B 副本，实际字节/mode 变更为 0，产品与资产变更为 0。
- E06 中四个 capacity guard 文件也已与交付版本相同；本 252 入口不加载它们，因此没有额外 guard overlay。原交付及 sourcewatch 未改。
- 本轮程序只从 B 自有副本启动，禁止回落原工作区及 E source/asset root；正常原 venv 与 stdlib 为只读依赖例外。未修改 E 原目录。

可复查复制与启动记录：

```text
/private/tmp/aps-final-foundation-B.xYPahs/E06-copy-C1frJv/provenance/copy-proof.json
/private/tmp/aps-final-foundation-B.xYPahs/E06-copy-C1frJv/provenance/planned-tests-only-overlay.json
/private/tmp/aps-final-foundation-B.xYPahs/E06-copy-C1frJv/provenance/preflight-source-guard.json
/private/tmp/aps-final-foundation-B.xYPahs/E06-copy-C1frJv/provenance/launch-canonical-boot.sh
/private/tmp/aps-final-foundation-B.xYPahs/E06-copy-C1frJv/provenance/post-verification.json
```

## 固定用例分母

| 合同类型 | 通过/总数 |
| --- | ---: |
| 6 个真实对象 × 直接打开/复制 URL 新标签/F5 语义重载/原页新 PID × 4 组合 | 96/96 |
| 24 个服务端 HTTP400 导航边界及实际恢复入口 × 4 | 96/96 |
| 5 个合法格式但不存在的对象，真实 404 与原对象重读 × 4 | 20/20 |
| 10 个受控 Boot 错误及恢复合同 × 4 | 40/40 |
| **合计** | **252/252** |

四种组合为 1392×924 light/dark、1920×1080 light/dark，每组 63。所有 `kind/state/name` 标识唯一，无丢项或从已运行部分缩小分母。Boot 40 是刻意注入的错误处理合同，不能称为 40 次业务交易成功。

完整逐例信息保存在原始 `foundation-browser.json`。新 [精简证据](canonical-boot-e06-evidence.json) 含案例分类、前后身份、四个报表请求和旧 36 项失败到本轮通过的逐项对应。

## 重启与旧失败闭环

- 保持 24 个原 page_id 和 context_id，核对启动协商 nonce 与浏览器 PID，再停止自有旧宿主；新宿主使用同端口、同一私有 DB/root。
- 新 PID 后每个原页实际重载，URL、原对象、范围、主题和 caption 与真实 DTO 对照通过。没有用新页面、清 history、删除旧状态或改 URL 来掩盖失败。
- 旧 ea5f 的 4 个报表新 PID 失败场景，本轮四组合均真实 GET200。请求不携带旧 `snapshot_ref`，同一正式计划、CAT-B 批次、日期与查询范围仍在，表头 caption 与实际响应相同。具体原始请求文件/哈希见精简证据的 `reports_new_pid`。
- 本轮真实 domain404 及原对象重读 20 项通过；未改 404/409 拒绝逻辑、未删除原负面用例。新 PID 的显式进入成功不意味着活跃旧 snapshot 可以自动回退，252 也不冒充旧 legacy 故障集或域内全部 409 边界的重新验证。
- 旧 32 个 trial 初始 history 观察失败，本轮相同 `kind/state/name` 全部通过。V2 只允许合法的空初始 history，仍检查实际 boot、DTO、范围与草稿身份，不伪造 history；不能把此项描述为 32 个旧产品缺陷。
- 旧 ea5f `216/252`、历史 92 结果与原始失败目录未改写；旧 browser SHA 仍是 `d13e22fabf989f88eb1a7e2cb5ef6e86b76172520ad40f3de41726d9fda43214`。本次使用新的 fixture，不跨库重放旧 refs。

## 收尾复核

- 两个宿主 returncode 均 0，managed runtime closed、pending 为空，runtime/DB 锁已释放；三个自有 PID 及该 B 包路径的进程检查均无残留。
- 协调器 `source_changes=[]`；两个宿主来源守卫违规均 0。记录的项目模块为 1103/1054，实际观察的 repo Python 文件为 1105/1056，逐项核对位于 B source 且 SHA 不变。
- 1183/79 次 SQLite 连接均为本私有 root 或内存库，不访问原生产 DB。
- 同阶段的业务 before/after 全等。跨重启全部旧行保留，只有 1 条正常 `plugins/load` 启动日志与对应 `sqlite_sequence` 前进；日志其余业务字段也逐项核对。
- 收尾再次对 B 固定副本核验 6532 源文件、224 资产的 SHA/mode；与复制时保存的 E 清单比较，不依赖随后可能变化的原工作区文档或未加载测试。
- 772 份原始 API 文件逐一核验 SHA 与原 body；408 张 PNG 逐一核验 SHA；51684 个正常浏览器资产响应核对实际 bytes/SHA 与 build manifest。正常错误和外连均为 0。
- B 人工查看了 4 张图片：报表新 PID 的 1392-light/1920-dark，已有 trial 草稿的 1392-dark 直接打开/1920-light 新 PID；caption、过滤范围与内容可见，没有观察到遮挡。其余图片有运行时几何/像素检查，不声称人工逐张看过全部 408 张，也不代替 Main V 签字。

## 原始文件 SHA

| 文件 | SHA-256 |
| --- | --- |
| `foundation-result.json` | `476f1774a9d8f92e0568f97e2253b715da8670d22d4abeb1c64c44e7371dd70b` |
| `foundation-browser.json` | `6abee5ab7f117d4624a43af0f8c76102d6f5d272f4d67046400d9abb85546f7a` |

两文件均在上述实际 fixture 根目录。所有原始输出、复制清单、源守卫、HTTP、截图和前后 DB 快照保留。

## 边界

- 本轮没有修改产品、Main CLI、12 份 V2 代码或四个 capacity guard，只新增交接文档与私有复制/验证记录；未暂存或提交，没有影响他人的 dirty/staged/untracked。
- 该矩阵只证明指定主框架、canonical 导航与 Boot 合同。分页深处、业务编辑/提交、完整报表导出等域内合同不从此矩阵推导，应引用 C/D/E/F 的相应实测。
- 未运行旧 F18、正式 5000、全仓质量门禁或原生 Win7。正式 5000 继续等待 Main 最终 HEAD、独立绑定和独占窗口。
- Main 后续针对 D 的 ANA001/003 授权只读 delta，不在本轮固定源中混入。后续最终完整源按明确窗口运行一次绑定的 `--groups all` 344 项，再按独占安排处理 5000；本轮交接后待命，不重复 E06，不追踪 moving 原树。
