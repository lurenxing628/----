"""Chrome109 editing preserves the real draft's fractional time string."""

import json
import os
import subprocess
from pathlib import Path

from tests.workbench.test_live_browser import runtime_tools
from tests.workbench.trial_support import create, official
from tests.workbench.trial_support import trial_case as trial_case


def test_resource_only_edit_and_microsecond_entry_preserve_time(trial_case, tmp_path):
    node, browser, modules = runtime_tools()
    case = trial_case
    case.conn.execute("UPDATE BatchOperations SET unit_hours=0.001 WHERE id=?", (case.op_id,))
    case.conn.commit()
    draft = create(case, official(case, start="2026-09-09T13:00:00.123456",
                                  end="2026-09-09T13:00:10.923456"))
    source = tmp_path / "draft.json"
    source.write_text(json.dumps(draft, ensure_ascii=False), encoding="utf-8")
    output = tmp_path / "microsecond-editor"
    result = subprocess.run(
        [node, str(Path(__file__).with_suffix(".cjs")), str(source), str(output)],
        env=dict(os.environ, WORKBENCH_BROWSER=browser, NODE_PATH=modules),
        capture_output=True, text=True, encoding="utf-8", timeout=90,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads((output / "result.json").read_text(encoding="utf-8"))
    assert report["resource_change_preserved_time"]
    assert report["one_microsecond_input_preserved"]
    assert report["invalid_date_not_submitted"]
