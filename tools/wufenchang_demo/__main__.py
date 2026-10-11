"""python -m tools.wufenchang_demo --database /new/folder/aps.db"""

import argparse
import json

from .builder import build_database


def main():
    parser = argparse.ArgumentParser(description="以正式资料写入流程建立可直接排产的五分厂数据库。")
    parser.add_argument("--database", required=True, help="新数据库路径；已有文件不会覆盖")
    parser.add_argument("--start-date", help="首个工作日，YYYY-MM-DD；默认今天，周末顺延")
    args = parser.parse_args()
    result = build_database(args.database, args.start_date)
    print(json.dumps({key: value for key, value in result.items() if key != "source_adoptions"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
