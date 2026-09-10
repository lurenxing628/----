"""Fill only downloaded test templates and inspect the actual downloaded export."""

import argparse
import json
from pathlib import Path

from core.services.workbench.field_report_files_codec import decode_reports
from tests.workbench.test_round1_field_piece_files_support import PIECES, fill_template, report_values


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('fill', 'verify'))
    parser.add_argument('source', type=Path)
    parser.add_argument('destination', type=Path, nargs='?')
    args = parser.parse_args()
    content = args.source.read_bytes()
    if args.action == 'fill':
        assert args.destination is not None
        values = {piece: report_values() for piece in (None, PIECES[0], '0')}
        args.destination.write_bytes(fill_template(content, values))
    else:
        rows = decode_reports(content)
        assert len(rows) == 3 and all(not row['errors'] for row in rows)
        assert {row['values']['piece_id'] for row in rows} == {'', PIECES[0], '0'}
        assert all(row['values']['completed_quantity'] == row['values']['effective_processing_hours'] == 0 for row in rows)
        assert all(row['values']['task_ref'] and row['values']['remark'] == '中文现场报工' for row in rows)
        print(json.dumps({'export_rows': len(rows), 'identity_and_zero_preserved': True}))


if __name__ == '__main__':
    main()
