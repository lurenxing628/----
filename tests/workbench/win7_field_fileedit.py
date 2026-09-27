"""Use the existing private-download editor without relaxing its path guard."""
import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("template", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--mode", choices=("pieces", "rejected"), default="pieces")
    args = parser.parse_args()
    source, target = args.template.resolve(), args.output.resolve()
    if source.parent != target.parent or target.exists():
        raise ValueError("Require a new sibling evidence file")
    with tempfile.TemporaryDirectory(prefix="aps-win7-fileedit-") as scratch:
        temporary = Path(scratch)
        original, edited = temporary / "download.xlsx", temporary / "edited.xlsx"
        shutil.copyfile(str(source), str(original))
        subprocess.run([sys.executable, "-B", "-m", "tests.workbench.final_execution_fileedit",
                        str(original), str(edited), "--mode", args.mode], check=True)
        shutil.copyfile(str(edited), str(target))


if __name__ == "__main__":
    main()
