"""Wrap verified portable 7z volumes in self-contained ZIPs below a byte limit."""
from __future__ import annotations

import argparse
import csv
import json
import shutil
import zipfile
import zlib
from pathlib import Path

from scripts.portable_release import payload_files

REPO = Path(__file__).resolve().parents[1]

README_TEXT = """APS 排产系统 · 离线分卷交付包

使用步骤（无需另装解压软件）：
1. 把全部编号 ZIP 保存到同一个本机文件夹，保持文件名不变。
2. 只需用 Windows 自带“全部提取”解压 01.zip。
3. 在解压出的文件夹内双击 Install.cmd。它会自动找到旁边的后续 ZIP，校验并完整解压。
   也可以先把全部 ZIP 解压到同一文件夹，再运行 Install.cmd。
4. 完成后双击 Application\\Start.cmd。

程序版本、目标运行环境及验收结果见交付人员提供的本次交付记录。
请完整下载全部 ZIP；任何文件缺失或校验失败都会停止，不会覆盖旧程序或旧数据。
请在当前账户可读写的本机目录部署，预留解压后程序所需空间，不要直接在 ZIP 内运行。

数据和升级：
首次启动建立空库，业务数据位于 Application\\APS_Portable\\user-data。
复杂排产样例默认关闭。双击 Application\\SampleOn.cmd 启用并打开样例，
首次会在独立 sample-context 中注入 100 批次、约 5000 道工序并实际排产，需要等待几分钟。
生成完成后，点击页面右上角“刷新”，查看已采用计划及样例。
双击 Application\\SampleOff.cmd 停用并返回原业务数据。
日常 Start.cmd 会打开当前选定的数据；样例页面标有“复杂样例 · 独立数据”。
样例数据保留在独立 sample-context 中，不复制或覆盖正式 user-data；再次启用可回读。
Excel 模板从各业务页的导入窗口下载，不要求目标机安装 Microsoft Office。
正常退出时，在当前运行实例的程序目录按住 Shift 并右键单击空白处，
选择“在此处打开命令窗口”，逐行执行：
  start /wait "" ".\\排产系统.exe" --runtime-stop . --stop-aps-chrome
  echo %ERRORLEVEL%
显示 0 后，可复制或迁移目录；非 0 时保留提示并联系交付人员。
正式程序目录为 Application\\APS_Portable，样例为 Application\\sample-context\\APS_Portable。
备份从系统维护页面操作。
升级时先在旧系统备份并正常退出，把新包部署到新的空目录，再复制旧 user-data，
或通过新系统的备份恢复功能导入。不要在运行中复制数据库，也不要覆盖原程序目录。
迁移时正常退出后复制整个 APS_Portable 文件夹。专用浏览器用于本机 APS 页面。
仅关闭浏览器窗口不代表后台服务已停止；再次启动会复用健康的本机实例。

遇到启动问题，保留 user-data\\logs\\launcher.log 和 aps_launch_error.txt 联系交付人员。
请不要删除运行锁来强行启动多个实例，也不要在同一份数据上同时运行多个用户。

本交付附带独立解压工具，工具版本、许可及说明位于 tools 目录。
压缩内容使用 ZIP/7z 自带的 CRC 完整性检查，解压后按文件清单核对大小。
7-Zip 官方许可、源码及下载：https://www.7-zip.org/ 。
"""


def crc32(file: Path) -> str:
    value = 0
    with file.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value = zlib.crc32(block, value)
    return f"{value & 0xffffffff:08x}"


def record(file: Path, relative: str) -> dict:
    return {"Path": relative, "CRC32": crc32(file), "Bytes": file.stat().st_size}


def csv_file(file: Path, rows: list) -> None:
    with file.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def archive(output: Path, files: list, maximum: int) -> None:
    with zipfile.ZipFile(str(output), "x", compression=zipfile.ZIP_STORED) as target:
        for source, relative in files:
            if not relative.isascii():
                raise ValueError("Outer ZIP names must support the Win7 built-in extractor")
            target.write(str(source), relative)
    if output.stat().st_size >= maximum:
        raise ValueError("ZIP reaches or exceeds the byte limit: " + str(output))
    with zipfile.ZipFile(str(output)) as target:
        if target.testzip():
            raise ValueError("ZIP integrity failure")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("payload", type=Path)
    parser.add_argument("volumes", type=Path)
    parser.add_argument("sevenzip", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--name", default="APS_Win7_x64")
    parser.add_argument("--maximum-bytes", type=int, default=80_000_000)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    bootstrap = args.output / "bootstrap"
    (bootstrap / "tools").mkdir(parents=True)
    (bootstrap / "payload").mkdir()
    if (args.payload / "sample-context").exists():
        raise ValueError("Portable payload contains a sample context")
    files = payload_files(args.payload)
    csv_file(bootstrap / "files.csv", [record(file, file.relative_to(args.payload).as_posix()) for file in files])
    for name in ("Install.cmd", "Install.ps1", "Start.cmd", "Start.ps1", "SampleOn.cmd", "SampleOff.cmd"):
        text = (REPO / "packaging/win7" / name).read_text(encoding="ascii")
        (bootstrap / name).write_bytes(text.replace("\r\n", "\n").replace("\n", "\r\n").encode("ascii"))
    shutil.copyfile(str(args.sevenzip / "x64/7za.exe"), str(bootstrap / "tools/7za.exe"))
    for name in ("License.txt", "readme.txt"):
        shutil.copyfile(str(args.sevenzip / name), str(bootstrap / "tools" / name))
    volumes = sorted(args.volumes.glob("APS_Portable.7z.*"))
    if not volumes or [file.suffix for file in volumes] != [f".{i + 1:03d}" for i in range(len(volumes))]:
        raise ValueError("Missing or non-contiguous payload volumes")
    rows, checks = [], []
    for index, volume in enumerate(volumes, 1):
        relative = "payload/" + volume.name
        row = dict(record(volume, relative), Zip="", ZipCRC32="", ZipBytes="")
        if index == 1:
            shutil.copyfile(str(volume), str(bootstrap / relative))
        else:
            output = args.output / (args.name + f"_{index:02d}.zip")
            archive(output, [(volume, relative)], args.maximum_bytes)
            archive_record = record(output, output.name)
            checks.append(archive_record)
            row.update(Zip=output.name, ZipCRC32=archive_record["CRC32"], ZipBytes=archive_record["Bytes"])
        rows.append(row)
    csv_file(bootstrap / "parts.csv", rows)
    readme = README_TEXT
    (bootstrap / "README.txt").write_text(readme, encoding="utf-8-sig")
    support = [file for file in bootstrap.rglob("*") if file.is_file()
               and file.name != "support.csv" and "payload" not in file.relative_to(bootstrap).parts]
    support_records = [record(file, file.relative_to(bootstrap).as_posix()) for file in sorted(support)]
    csv_file(bootstrap / "support.csv", support_records)
    first = args.output / (args.name + "_01.zip")
    archive(first, [(file, file.relative_to(bootstrap).as_posix()) for file in sorted(bootstrap.rglob("*"))
                    if file.is_file()], args.maximum_bytes)
    checks.insert(0, record(first, first.name))
    (args.output / "README.txt").write_text(readme, encoding="utf-8-sig")
    (args.output / "delivery.json").write_text(json.dumps({"maximum_bytes_exclusive": args.maximum_bytes,
        "original_payload_files": len(files), "original_payload_bytes": sum(file.stat().st_size for file in files),
        "integrity": "ZIP/7z CRC and extracted file-size list",
        "archives": checks, "sevenzip_exe_crc32": next(row["CRC32"] for row in support_records
                                                       if row["Path"] == "tools/7za.exe")}, indent=2), encoding="utf-8")
    print(json.dumps(checks))


if __name__ == "__main__":
    main()
