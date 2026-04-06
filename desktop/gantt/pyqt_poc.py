from __future__ import annotations

from typing import Any, Dict, List

from .contract_client import GanttDesktopDataProvider, GanttQuery

try:
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import (
        QApplication,
        QComboBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMainWindow,
        QMessageBox,
        QPushButton,
        QTableWidget,
        QTableWidgetItem,
        QVBoxLayout,
        QWidget,
    )

    PYQT_AVAILABLE = True
except Exception:
    PYQT_AVAILABLE = False


class GanttPyQtUnavailableError(RuntimeError):
    pass


def _safe_text(v: Any) -> str:
    if v is None:
        return ""
    return str(v)


if PYQT_AVAILABLE:

    class GanttPoCWindow(QMainWindow):
        """
        甘特图桌面 PoC（只读）。

        当前目标：验证 Web/PyQt 可消费同一契约，不做图形条形渲染。
        """

        def __init__(self, provider: GanttDesktopDataProvider):
            super().__init__()
            self._provider = provider
            self.setWindowTitle("APS Gantt PoC (Read-only)")
            self.resize(1200, 700)
            self._init_ui()
            self._refresh()

        def _init_ui(self) -> None:
            root = QWidget(self)
            self.setCentralWidget(root)
            layout = QVBoxLayout(root)

            ctrl = QHBoxLayout()
            self.view_combo = QComboBox()
            self.view_combo.addItems(["machine", "operator"])
            ctrl.addWidget(QLabel("View"))
            ctrl.addWidget(self.view_combo)

            self.week_start_edit = QLineEdit()
            self.week_start_edit.setPlaceholderText("week_start: YYYY-MM-DD")
            ctrl.addWidget(QLabel("Week Start"))
            ctrl.addWidget(self.week_start_edit)

            self.version_edit = QLineEdit()
            self.version_edit.setPlaceholderText("version (optional)")
            ctrl.addWidget(QLabel("Version"))
            ctrl.addWidget(self.version_edit)

            self.refresh_btn = QPushButton("Refresh")
            self.refresh_btn.clicked.connect(self._refresh)  # type: ignore[attr-defined]
            ctrl.addWidget(self.refresh_btn)
            ctrl.addStretch(1)
            layout.addLayout(ctrl)

            self.summary = QLabel("")
            self.summary.setWordWrap(True)
            self.summary.setTextInteractionFlags(Qt.TextSelectableByMouse)
            layout.addWidget(self.summary)

            self.table = QTableWidget()
            self.table.setColumnCount(10)
            self.table.setHorizontalHeaderLabels(
                [
                    "task_id",
                    "name",
                    "start",
                    "end",
                    "duration_min",
                    "batch",
                    "machine",
                    "operator",
                    "status",
                    "edge_type",
                ]
            )
            self.table.setSelectionBehavior(QTableWidget.SelectRows)
            self.table.setEditTriggers(QTableWidget.NoEditTriggers)
            self.table.setAlternatingRowColors(True)
            layout.addWidget(self.table, 1)

        def _build_query(self) -> GanttQuery:
            v = self.version_edit.text().strip()
            version = None
            if v:
                try:
                    version = int(v)
                except Exception:
                    version = None
            ws = self.week_start_edit.text().strip() or None
            return GanttQuery(
                view=self.view_combo.currentText().strip() or "machine",
                week_start=ws,
                version=version,
                include_history=False,
            )

        def _refresh(self) -> None:
            try:
                data = self._provider.fetch_contract(self._build_query())
            except Exception as e:
                QMessageBox.critical(self, "Load Failed", _safe_text(e))
                return
            self._render_contract(data)

        def _render_contract(self, contract: Dict[str, Any]) -> None:
            tasks: List[Dict[str, Any]] = list(contract.get("tasks") or [])
            cc = contract.get("critical_chain") or {}
            cc_count = len(cc.get("ids") or [])
            summary = (
                f"contract_version={contract.get('contract_version')} | "
                f"view={contract.get('view')} | version={contract.get('version')} | "
                f"range={contract.get('week_start')} ~ {contract.get('week_end')} | "
                f"tasks={len(tasks)} | critical_chain={cc_count}"
            )
            self.summary.setText(summary)

            self.table.setRowCount(len(tasks))
            for i, t in enumerate(tasks):
                meta = t.get("meta") or {}
                row_values = [
                    t.get("id"),
                    t.get("name"),
                    t.get("start"),
                    t.get("end"),
                    t.get("duration_minutes"),
                    meta.get("batch_id"),
                    meta.get("machine"),
                    meta.get("operator"),
                    meta.get("status"),
                    t.get("edge_type"),
                ]
                for c, v in enumerate(row_values):
                    self.table.setItem(i, c, QTableWidgetItem(_safe_text(v)))


def launch_gantt_poc(provider: GanttDesktopDataProvider) -> int:
    if not PYQT_AVAILABLE:
        raise GanttPyQtUnavailableError(
            "PyQt5 is not available. Install PyQt5 to run desktop gantt PoC."
        )
    app = QApplication.instance() or QApplication([])
    win = GanttPoCWindow(provider)
    win.show()
    return app.exec_()

