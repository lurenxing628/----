"""运行日志读取层（纯函数，不依赖 Flask）。

职责：
- 尾部块读 + 时间戳锚点切分：把 logs/ 下的文件日志切成倒序条目供运行日志页展示；
- 诊断包构建：把白名单内的日志文件 + 环境信息 + 操作日志文本流式压缩进 zip。

读取边界规则（设计决策 2 钉死）：
- 二进制尾读，锚点匹配在字节层（时间戳锚点纯 ASCII，bytes 正则无歧义）；
- 字节层先拼接、后解码——解码只发生在完整条目字节段上，跨块多字节字符天然完整；
- decode("utf-8", errors="replace")：� 只代表磁盘上真实的坏字节；
- 截断切点在解码前回退合法 UTF-8 字符边界，不制造假 �。
"""

from __future__ import annotations

import fnmatch
import os
import re
import shutil
import zipfile
from typing import BinaryIO, Dict, List, Tuple

from core.infrastructure.safe_files import open_fixed_file_for_read_binary, stat_regular_file

# 页面白名单：只认三个固定文件名，严格相等匹配（目录遍历红线）
LOG_FILE_CHOICES = ("aps_error.log", "aps.log", "launcher.log")
MAX_ENTRIES = 200            # 页面单次最多条目
TAIL_BLOCK_SIZE = 64 * 1024  # 尾读块步进
MAX_ENTRY_BYTES = 256 * 1024  # 单条目内存硬上限：超长条目转「弃中段巡锚」，保头尾各半
ENTRY_HUNT_BUDGET_BYTES = 4 * 1024 * 1024  # 巡锚 IO 预算：超预算放弃头半，按无锚点兜底
_ANCHOR_SPAN_WINDOW = 24     # 锚点字节模式长 21，跨块检测窗口取 24

# 锚点匹配在 bytes 层——formatter 时间戳行首格式（logging.py 三 handler 同一 datefmt）
ENTRY_ANCHOR_RE = re.compile(rb"(?m)^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} \[")
_HEAD_LEVEL_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} \[([A-Z]+)\]")

# 诊断包白名单三类：*.log + 轮转分卷（仅数字后缀，拒 x.log.bak）+ 显式列名的启动失败证据
ROTATED_LOG_RE = re.compile(r"^.+\.log\.[0-9]+$")
DIAGNOSTIC_EXTRA_FILES = ("aps_launch_error.txt",)
# 安全红线（roadmap 第 34 条）：同目录 aps_secret_key.txt 永不进诊断包。
# 白名单本身收不到它；此处仍显式列出供守卫测试与读者对照。
SECRET_FILE_NAME = "aps_secret_key.txt"

TRUNCATION_MARKER = "……（条目过长，中段已截断）"
NO_ANCHOR_HEAD = "（无法按时间戳切分，原样显示尾部内容）"


def read_log_entries_tail(log_path: str, *, max_entries: int = MAX_ENTRIES) -> List[Dict[str, str]]:
    """从文件尾读取最近 max_entries 条日志条目，倒序返回（最新在前）。

    返回 [{"head": 首行, "body": 余下行, "level": "ERROR"}, ...]。
    文件不存在返回 []（路由层据此区分空态文案）；IO 失败抛 OSError，由路由层明示。

    拒绝软链接/非普通文件：与诊断包链路 list_diagnostic_log_names 同一道锁——白名单
    文件名只挡路径注入，挡不住「白名单名字指向任意文件」的软链接借壳，故读取前先核
    islink/isfile（页面查看日志与诊断打包共用此读原语，纵深防御一处补齐）。
    """
    try:
        f = open_fixed_file_for_read_binary(log_path)
    except FileNotFoundError:
        return []
    with f:
        regions = _scan_tail_regions(f, max_entries)
    return [_build_entry(region) for region in regions]


def _scan_tail_regions(f: BinaryIO, max_entries: int) -> List[Tuple]:
    """字节层扫描：返回倒序（最新在前）的条目区域列表。

    区域三态：("normal", bytes) / ("truncated", 头半段, 尾半段) / ("unanchored", bytes)。
    不变式：buffer 始终持有文件区间 [pos, pos + len(buffer))，右端是下一条目的结束边界。
    """
    f.seek(0, os.SEEK_END)
    pos = f.tell()
    buffer = b""
    regions: List[Tuple] = []
    while pos > 0 and len(regions) < max_entries:
        step = min(TAIL_BLOCK_SIZE, pos)
        pos -= step
        f.seek(pos)
        buffer = f.read(step) + buffer
        anchors = _valid_anchor_offsets(buffer, at_file_start=(pos == 0))
        if anchors:
            buffer = _consume_anchored(buffer, anchors, regions, max_entries)
        if len(buffer) > MAX_ENTRY_BYTES and len(regions) < max_entries:
            region, pos, buffer = _hunt_oversize_entry(f, pos, buffer)
            regions.append(region)
            if region[0] == "unanchored":
                return regions  # 巡锚失败：条目边界未知，无法继续向前切分
    if len(regions) < max_entries:
        # 收尾：巡锚成功返回的 buffer 可能以文件头锚点开场（主循环已退出收不到它），再切一次
        anchors = _valid_anchor_offsets(buffer, at_file_start=True)
        if anchors:
            buffer = _consume_anchored(buffer, anchors, regions, max_entries)
        if buffer.strip() and len(regions) < max_entries:
            # 文件头无锚点残段（轮转截断/非本系统格式），原样作一条呈现
            regions.append(("unanchored", buffer))
    return regions


def _valid_anchor_offsets(buffer: bytes, *, at_file_start: bool) -> List[int]:
    """buffer 内可信锚点偏移。偏移 0 的匹配只有在 buffer 起点就是文件起点时才算数——
    否则它可能是被块边界切出的行中段，等下一轮把前一块拼进来再判。"""
    return [
        m.start()
        for m in ENTRY_ANCHOR_RE.finditer(buffer)
        if m.start() > 0 or at_file_start
    ]


def _consume_anchored(
    buffer: bytes, anchors: List[int], regions: List[Tuple], max_entries: int
) -> bytes:
    """按锚点切出条目（靠后的更新、先收），返回首锚点之前的剩余字节。"""
    bounds = anchors + [len(buffer)]
    for i in range(len(anchors) - 1, -1, -1):
        if len(regions) >= max_entries:
            break
        regions.append(_region_for_entry(buffer[bounds[i]:bounds[i + 1]]))
    return buffer[: anchors[0]]


def _hunt_oversize_entry(f: BinaryIO, pos: int, buffer: bytes) -> Tuple[Tuple, int, bytes]:
    """超长条目的「弃中段巡锚」：buffer（无锚点、已超内存上限）是条目尾段。

    固定保留尾半，向前按块只为找条目起点锚点（每块仅留跨界窗口，中段即读即弃，
    内存恒 O(块)）；找到后回读头半——头行的时间戳/级别是排障关键，不能因超长丢失。
    巡锚 IO 超 ENTRY_HUNT_BUDGET_BYTES 或到文件头仍无锚点：放弃头半，按无锚点兜底。
    返回 (region, 新 pos, 新 buffer)。
    """
    half = MAX_ENTRY_BYTES // 2
    tail_half = buffer[-half:]
    window = buffer[:_ANCHOR_SPAN_WINDOW]
    hunted = len(buffer)
    while pos > 0 and hunted < ENTRY_HUNT_BUDGET_BYTES:
        step = min(TAIL_BLOCK_SIZE, pos)
        pos -= step
        f.seek(pos)
        block = f.read(step)
        hunted += step
        probe = block + window
        anchors = _valid_anchor_offsets(probe, at_file_start=(pos == 0))
        if anchors:
            anchor_abs = pos + anchors[-1]  # 最靠后的锚点即本条目起点
            f.seek(anchor_abs)
            head_half = f.read(half)  # 条目总长必 > MAX_ENTRY_BYTES，头尾半段不会重叠
            return ("truncated", head_half, tail_half), pos, probe[: anchors[-1]]
        window = probe[:_ANCHOR_SPAN_WINDOW]
    return ("unanchored", tail_half), pos, b""


def _region_for_entry(raw: bytes) -> Tuple:
    if len(raw) <= MAX_ENTRY_BYTES:
        return ("normal", raw)
    half = MAX_ENTRY_BYTES // 2
    return ("truncated", raw[:half], raw[-half:])


def _trim_partial_utf8_end(data: bytes) -> bytes:
    """裁掉末尾被切断的 UTF-8 多字节序列（最多回退 3 字节）；序列完整则原样保留。"""
    cut = len(data)
    back = 0
    while cut > 0 and back < 3 and (data[cut - 1] & 0xC0) == 0x80:
        cut -= 1
        back += 1
    if cut > 0 and data[cut - 1] >= 0xC0:
        lead = data[cut - 1]
        need = 2 if lead < 0xE0 else 3 if lead < 0xF0 else 4
        if len(data) - (cut - 1) >= need:
            return data  # 末尾序列完整
        cut -= 1
    return data[:cut]


def _skip_partial_utf8_start(data: bytes) -> bytes:
    """跳过开头残留的 UTF-8 延续字节（最多 3 个，即 4 字节字符被切后的最大残留）。"""
    skip = 0
    while skip < min(3, len(data)) and (data[skip] & 0xC0) == 0x80:
        skip += 1
    return data[skip:]


def _build_entry(region: Tuple) -> Dict[str, str]:
    kind = region[0]
    if kind == "unanchored":
        body = _skip_partial_utf8_start(region[1]).decode("utf-8", errors="replace")
        return {"head": NO_ANCHOR_HEAD, "body": body.strip("\n"), "level": "UNKNOWN"}
    if kind == "truncated":
        head_text = _trim_partial_utf8_end(region[1]).decode("utf-8", errors="replace")
        tail_text = _skip_partial_utf8_start(region[2]).decode("utf-8", errors="replace")
        text = head_text + "\n" + TRUNCATION_MARKER + "\n" + tail_text
    else:
        text = region[1].decode("utf-8", errors="replace")
    text = text.rstrip("\n")
    head, _, body = text.partition("\n")
    match = _HEAD_LEVEL_RE.match(head)
    level = match.group(1) if match else "UNKNOWN"
    return {"head": head, "body": body, "level": level}


def list_diagnostic_log_names(log_dir: str) -> List[str]:
    """诊断包白名单内的文件名（按名排序）。白名单是唯一进包通道——
    aps_secret_key.txt 结构性进不来（红线测试在 logs 目录播种假 secret 断言名单）。"""
    names = []
    for name in sorted(os.listdir(log_dir)):
        path = os.path.join(log_dir, name)
        # 拒绝 symlink：白名单文件名挡路径注入，islink 挡"白名单名字指向任意文件"
        if os.path.islink(path) or not os.path.isfile(path):
            continue
        if (
            fnmatch.fnmatch(name, "*.log")
            or ROTATED_LOG_RE.match(name)
            or name in DIAGNOSTIC_EXTRA_FILES
        ):
            names.append(name)
    return names


def build_diagnostic_zip(
    log_dir: str,
    zip_path: str,
    *,
    operation_logs_text: str,
    info_text: str,
    operation_logs_arcname: str = "operation_logs.txt",
) -> None:
    """把白名单日志 + 环境信息 + 操作日志文本写进 zip_path（流式压缩，内存 O(块)）。

    不返回 bytes：launcher.log 无轮转上限、分卷最坏数十 MB，全内存构包不可接受。
    zip_path 的生命周期由调用方负责（mkstemp + 响应关闭回调清理，见路由层）。
    operation_logs_arcname 由调用方按读取成败决定（成功 operation_logs.txt /
    失败 operation_logs_读取失败.txt，包内明示缺失而不中断导出）。
    """
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in list_diagnostic_log_names(log_dir):
            _write_fixed_file_to_zip(zf, os.path.join(log_dir, name), name)
        zf.writestr("diagnostic_info.txt", info_text)
        zf.writestr(operation_logs_arcname, operation_logs_text)


def _write_fixed_file_to_zip(zf: zipfile.ZipFile, path: str, arcname: str) -> None:
    with open_fixed_file_for_read_binary(path) as src:
        with zf.open(arcname, "w") as dst:
            shutil.copyfileobj(src, dst, length=TAIL_BLOCK_SIZE)
