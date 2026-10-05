---
doc_type: audit-finding
audit: 2026-10-05-redundant-guards
finding_id: "9.6"
nature: bug
severity: P2
confidence: high
status: fixed
---

# 工作台构建验证内容与使用内容没有统一

修复前，`verify_snapshot` 读取每个文件 bytes 并核对已有清单，但只返回名称集合。构建 prototype/vendor 时重新读取路径，可能在两次读取之间使用变化后的未验证内容。构建末尾只复验 live inputs/styles/build-order，未对 prototype/vendor 提供同等保证。

共同入口应返回并使用同一份已验证字节快照，编译、复制和来源记录围绕它工作；仍保留 live 输入在编译子进程之后的变化检查、原子 replace 和 marker 最后发布。不新增哈希清单或第二套检查脚本。


## 实施结果

已完成对应源头修复；历史档案、公开契约及必要边界保留。具体实现、实际回归与日常门禁结果见 [修复记录](../../issues/2026-10-05-redundant-guards/redundant-guards-fix-note.md)。
