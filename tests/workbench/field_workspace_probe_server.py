"""Dedicated loopback test server. Never starts the production application."""

import argparse
import json
from pathlib import Path

from werkzeug.serving import make_server

from core.services.workbench.field_report_files_codec import encode_reports
from tests.workbench.execution_ledger_support import ledger_case
from tests.workbench.field_workspace_support import make_app


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('directory')
    args = parser.parse_args()
    directory = Path(args.directory).resolve()
    repo = Path(__file__).resolve().parents[2]
    if repo == directory or repo in directory.parents or directory.exists():
        raise ValueError('Provide a new temporary directory outside the checkout.')
    directory.mkdir(parents=True)
    fixture = ledger_case.__wrapped__(directory)
    case = next(fixture)
    ids = [case.op_id] + [case.op('UI-' + str(index), seq=index) for index in range(2, 27)]
    case.plan(2, ids)
    case.event(ids[2], 'start', version=2, time='2026-09-01T08:00:00')
    case.event(ids[2], 'finish', version=2, time='2026-09-01T10:00:00')
    case.install()
    case.command('create', case.task(2, ids[0]), {'actual_start': '2026-09-01T08:00:00'})
    case.command('create', case.task(2, ids[1]), case.values(10))
    for index in range(6):
        case.command('create', case.task(2, ids[3]), case.values(1,
            actual_start=f'2026-09-01T{index + 8:02d}:00:00', actual_end=f'2026-09-01T{index + 9:02d}:00:00', effective_processing_hours=0.5))
    path = case.conn.execute('PRAGMA database_list').fetchone()[2]
    file_rows = [{'report_no': 'UI-IMPORT-25', 'batch_id': 'B1', 'operation_label': '25 Turning', 'completed_quantity': 2,
        'actual_start': '2026-09-01T08:00:00', 'actual_end': '2026-09-01T10:00:00', 'effective_processing_hours': 1.25,
        'machine_label': 'Lathe', 'operator_label': 'Operator', 'remark': '真实临时库上传'}]
    (directory / 'import.xlsx').write_bytes(encode_reports(file_rows))
    (directory / 'conflict.xlsx').write_bytes(encode_reports([dict(file_rows[0], completed_quantity=3)]))
    app = make_app(path)
    server = make_server('127.0.0.1', 0, app)
    print(json.dumps({'url': 'http://127.0.0.1:' + str(server.server_port), 'db': path}), flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
        fixture.close()


if __name__ == '__main__':
    main()
