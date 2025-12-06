from typing import List
import json
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QComboBox, QLineEdit,
    QToolButton, QFileDialog, QMessageBox, QPushButton, QLabel, QTableWidgetItem
)

from core.actions import Action, ActionSequence, ActionType


class ActionSequenceEditor(QWidget):
    sequenceChanged = Signal(ActionSequence)
    logMessage = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sequence = ActionSequence()
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        title_row = QHBoxLayout()
        self.lbl_name = QLabel("Sequence name:")
        self.edit_name = QLineEdit(self._sequence.name)
        title_row.addWidget(self.lbl_name)
        title_row.addWidget(self.edit_name)
        layout.addLayout(title_row)

        self.table = QTableWidget(0, 3, self)
        self.table.setHorizontalHeaderLabels(["Action Type", "Params (JSON)", "Ops"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        layout.addWidget(self.table, 1)

        btn_row = QHBoxLayout()
        self.btn_add = QPushButton("Add Action")
        self.btn_load = QPushButton("Load JSON...")
        self.btn_save = QPushButton("Save JSON...")
        self.btn_save_md = QPushButton("Save Markdown...")
        self.btn_add.setMinimumWidth(110)
        btn_row.addWidget(self.btn_add)
        btn_row.addStretch()
        btn_row.addWidget(self.btn_load)
        btn_row.addWidget(self.btn_save)
        btn_row.addWidget(self.btn_save_md)
        layout.addLayout(btn_row)

        self.btn_add.clicked.connect(self.add_action_row)
        self.btn_load.clicked.connect(self.load_from_json_file)
        self.btn_save.clicked.connect(self.save_to_json_file)
        self.btn_save_md.clicked.connect(self.save_to_markdown_file)
        self.edit_name.textChanged.connect(self._on_name_changed)

    def set_sequence(self, seq: ActionSequence):
        self._sequence = seq
        self.edit_name.setText(seq.name)
        self._rebuild_table()

    def get_sequence(self) -> ActionSequence:
        name = self.edit_name.text().strip() or "Unnamed Sequence"
        actions = self._table_to_actions()
        return ActionSequence(name=name, actions=actions)

    def _rebuild_table(self):
        self.table.setRowCount(0)
        for action in self._sequence.actions:
            self._append_row_for_action(action)

    def _append_row_for_action(self, action: Action):
        row = self.table.rowCount()
        self.table.insertRow(row)

        combo = QComboBox()
        combo.addItems(["click", "key", "sleep"])
        idx = combo.findText(action.type)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        self.table.setCellWidget(row, 0, combo)

        edit = QLineEdit()
        try:
            text = json.dumps(action.params, ensure_ascii=False)
        except Exception:
            text = "{}"
        edit.setText(text)
        self.table.setCellWidget(row, 1, edit)

        ops_widget = QWidget()
        ops_layout = QHBoxLayout(ops_widget)
        ops_layout.setContentsMargins(0, 0, 0, 0)
        ops_layout.setSpacing(4)

        btn_up = QToolButton()
        btn_up.setText("↑")
        btn_down = QToolButton()
        btn_down.setText("↓")
        btn_del = QToolButton()
        btn_del.setText("✕")

        btn_up.clicked.connect(lambda: self._move_row_up(row))
        btn_down.clicked.connect(lambda: self._move_row_down(row))
        btn_del.clicked.connect(lambda: self._delete_row(row))

        ops_layout.addWidget(btn_up)
        ops_layout.addWidget(btn_down)
        ops_layout.addWidget(btn_del)
        self.table.setCellWidget(row, 2, ops_widget)

    def _table_to_actions(self) -> List[Action]:
        actions: List[Action] = []
        rows = self.table.rowCount()
        for row in range(rows):
            combo: QComboBox = self.table.cellWidget(row, 0)
            edit: QLineEdit = self.table.cellWidget(row, 1)
            action_type: ActionType = combo.currentText()  # type: ignore
            params_text = edit.text().strip()
            if not params_text:
                params = {}
            else:
                try:
                    params = json.loads(params_text)
                    if not isinstance(params, dict):
                        raise ValueError("params must be dict")
                except Exception as e:
                    params = {}
                    self.logMessage.emit(f"Row {row+1}: invalid JSON, using {{}}. Error: {e}")
            actions.append(Action(type=action_type, params=params))
        return actions

    def add_action_row(self):
        action = Action(type="click", params={"button": "left"})
        self._sequence.actions.append(action)
        self._rebuild_table()
        self._emit_changed()

    def _move_row_up(self, row: int):
        if row <= 0:
            return
        self._sequence.actions = self._table_to_actions()
        self._sequence.actions[row - 1], self._sequence.actions[row] = \
            self._sequence.actions[row], self._sequence.actions[row - 1]
        self._rebuild_table()
        self._emit_changed()

    def _move_row_down(self, row: int):
        rows = self.table.rowCount()
        if row >= rows - 1:
            return
        self._sequence.actions = self._table_to_actions()
        self._sequence.actions[row + 1], self._sequence.actions[row] = \
            self._sequence.actions[row], self._sequence.actions[row + 1]
        self._rebuild_table()
        self._emit_changed()

    def _delete_row(self, row: int):
        self._sequence.actions = self._table_to_actions()
        if 0 <= row < len(self._sequence.actions):
            del self._sequence.actions[row]
        self._rebuild_table()
        self._emit_changed()

    def load_from_json_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Action Sequence", "", "JSON Files (*.json);;All Files (*)"
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
            seq = ActionSequence.from_json(text)
            self.set_sequence(seq)
            self.logMessage.emit(f"Loaded sequence from {path}")
            self._emit_changed()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load JSON:\n{e}")

    def save_to_json_file(self):
        seq = self.get_sequence()
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Action Sequence", f"{seq.name}.json",
            "JSON Files (*.json);;All Files (*)"
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(seq.to_json(indent=2))
            self.logMessage.emit(f"Saved sequence to {path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save JSON:\n{e}")

    def save_to_markdown_file(self):
        seq = self.get_sequence()
        default_name = seq.name or "sequence"
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Action Sequence as Markdown",
            f"{default_name}.md",
            "Markdown Files (*.md);;All Files (*)"
        )
        if not path:
            return
        try:
            md_text = seq.to_markdown()
            with open(path, "w", encoding="utf-8") as f:
                f.write(md_text)
            self.logMessage.emit(f"Saved markdown to {path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save markdown:\n{e}")

    def _on_name_changed(self, text: str):
        self._sequence.name = text or "Unnamed Sequence"
        self._emit_changed()

    def _emit_changed(self):
        seq = self.get_sequence()
        self.sequenceChanged.emit(seq)

