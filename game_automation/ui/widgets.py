from typing import List, Dict
import json
import os
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QComboBox, QLineEdit,
    QToolButton, QFileDialog, QMessageBox, QPushButton, QLabel, QTableWidgetItem,
    QListWidget, QListWidgetItem, QSplitter, QInputDialog
)

from ..core.actions import Action, ActionSequence, ActionType
from typing import get_args
from ..core.targets import TARGET_DEFINITIONS

# Base directory for JSON files (project root)
# All JSON persistence files (visual_scripts.json, resources.json) are stored at the project root.
# Legacy files like scripts.json and game_automation/*.json are deprecated and no longer used.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))


# ============================================================================
# LEGACY: ActionSequenceEditor
# ============================================================================
# This widget is considered legacy and is not currently integrated into the
# main MainWindow UI. The primary GUI uses VisualScriptEditor and ResourceSidebar
# for visual script editing. ActionSequenceEditor and AutomationController.run_sequence
# provide a lower-level JSON-based sequence API that may be used for testing or
# programmatic script creation, but is not exposed in the main user interface.
# ============================================================================
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
        try:
            combo.addItems(list(get_args(ActionType)))
        except Exception:
            combo.addItems(["click", "key", "sleep", "find_color"])
        idx = combo.findText(action.type)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        self.table.setCellWidget(row, 0, combo)

        # Create a container widget for Params (JSON input + Label dropdown)
        param_widget = QWidget()
        param_layout = QHBoxLayout(param_widget)
        param_layout.setContentsMargins(0, 0, 0, 0)
        param_layout.setSpacing(4)

        edit = QLineEdit()
        try:
            text = json.dumps(action.params, ensure_ascii=False)
        except Exception:
            text = "{}"
        edit.setText(text)
        
        label_combo = QComboBox()
        label_combo.setPlaceholderText("Select Label...")
        # Add an empty item to represent no selection
        label_combo.addItem("")
        # Sort keys for better usability
        label_combo.addItems(sorted(TARGET_DEFINITIONS.keys()))
        label_combo.setFixedWidth(120)
        label_combo.setToolTip("Select a label to auto-fill JSON params")

        def on_label_selected(text):
            if text:
                # Auto-fill JSON for label-based click
                new_params = {"mode": "label", "label": text, "button": "left"}
                edit.setText(json.dumps(new_params, ensure_ascii=False))
                # Reset combo to avoid confusion if user manually edits later? 
                # Or keep it? Keeping it is fine.

        label_combo.currentTextChanged.connect(on_label_selected)

        param_layout.addWidget(edit)
        param_layout.addWidget(label_combo)
        
        self.table.setCellWidget(row, 1, param_widget)

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
            
            # Retrieve QLineEdit from the composite widget in column 1
            param_widget: QWidget = self.table.cellWidget(row, 1)
            edit: QLineEdit = param_widget.findChild(QLineEdit)
            
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


class ResourceSidebar(QWidget):
    currentScriptChanged = Signal(str)
    scriptsChanged = Signal(list)
    templatesChanged = Signal(dict)
    scriptRenamed = Signal(str, str)  # old_name, new_name
    scriptDuplicated = Signal(str, str)  # base_name, new_name

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scripts: List[str] = []
        self._templates: Dict[str, str] = {}
        self._build_ui()
        self._load_persisted()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        # Scripts controls
        scripts_row = QHBoxLayout()
        btn_new_script = QPushButton("新增腳本", self)
        btn_rename_script = QPushButton("重命名", self)
        btn_dup_script = QPushButton("複製", self)
        btn_del_script = QPushButton("刪除", self)
        scripts_row.addWidget(btn_new_script)
        scripts_row.addWidget(btn_rename_script)
        scripts_row.addWidget(btn_dup_script)
        scripts_row.addWidget(btn_del_script)
        layout.addLayout(scripts_row)

        # Lists
        split = QSplitter(Qt.Vertical, self)
        self.list_scripts = QListWidget(self)
        self.list_templates = QListWidget(self)
        split.addWidget(self.list_scripts)
        split.addWidget(self.list_templates)
        layout.addWidget(split)

        # Template controls
        tmpl_row = QHBoxLayout()
        btn_new_tmpl = QPushButton("新增範本", self)
        btn_rename_tmpl = QPushButton("重命名", self)
        btn_dup_tmpl = QPushButton("複製", self)
        btn_del_tmpl = QPushButton("刪除", self)
        tmpl_row.addWidget(btn_new_tmpl)
        tmpl_row.addWidget(btn_rename_tmpl)
        tmpl_row.addWidget(btn_dup_tmpl)
        tmpl_row.addWidget(btn_del_tmpl)
        layout.addLayout(tmpl_row)

        # Connections
        self.list_scripts.itemSelectionChanged.connect(self._on_script_selected)

        btn_new_script.clicked.connect(self._on_new_script)
        btn_rename_script.clicked.connect(self._on_rename_script)
        btn_dup_script.clicked.connect(self._on_dup_script)
        btn_del_script.clicked.connect(self._on_del_script)

        btn_new_tmpl.clicked.connect(self._on_new_template)
        btn_rename_tmpl.clicked.connect(self._on_rename_template)
        btn_dup_tmpl.clicked.connect(self._on_dup_template)
        btn_del_tmpl.clicked.connect(self._on_del_template)

    def _on_script_selected(self):
        items = self.list_scripts.selectedItems()
        if items:
            self.currentScriptChanged.emit(items[0].text())

    def set_scripts(self, names: List[str]):
        self._scripts = names
        self.list_scripts.clear()
        for n in names:
            self.list_scripts.addItem(QListWidgetItem(n))
        self.scriptsChanged.emit(list(self._scripts))

    def set_templates(self, mapping: Dict[str, str]):
        self._templates = mapping
        self.list_templates.clear()
        for k in sorted(mapping.keys()):
            item = QListWidgetItem(k)
            # TODO: Add template thumbnail preview
            # TODO: Load image from mapping[k] and create thumbnail icon
            # TODO: Set item.setIcon() with scaled QIcon from template image
            self.list_templates.addItem(item)
        self.templatesChanged.emit(dict(self._templates))

    def _load_persisted(self):
        try:
            file_path = os.path.join(BASE_DIR, "resources.json")
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.set_templates(data.get("templates", {}))
        except Exception:
            pass

    def persist(self):
        try:
            file_path = os.path.join(BASE_DIR, "resources.json")
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump({"templates": self._templates}, f, ensure_ascii=False, indent=2)
            try:
                from ..core import targets as _targets
                _targets.reload_targets_from_resources(override=False)
            except Exception:
                pass
        except Exception:
            pass

    def _on_new_script(self):
        name, ok = QInputDialog.getText(self, "新增腳本", "名稱：")
        if not ok or not name.strip():
            return
        if name in self._scripts:
            QMessageBox.warning(self, "提示", "名稱已存在")
            return
        self._scripts.append(name)
        self.set_scripts(self._scripts)

    def _on_rename_script(self):
        items = self.list_scripts.selectedItems()
        if not items:
            return
        old = items[0].text()
        new, ok = QInputDialog.getText(self, "重命名腳本", f"將 {old} 重命名為：", text=old)
        if not ok or not new.strip():
            return
        if new != old and new in self._scripts:
            QMessageBox.warning(self, "提示", "名稱已存在")
            return
        idx = self._scripts.index(old)
        self._scripts[idx] = new
        self.set_scripts(self._scripts)
        self.scriptRenamed.emit(old, new)

    def _on_dup_script(self):
        items = self.list_scripts.selectedItems()
        if not items:
            return
        base = items[0].text()
        i = 1
        while True:
            cand = f"{base}_copy{i}"
            if cand not in self._scripts:
                break
            i += 1
        self._scripts.append(cand)
        self.set_scripts(self._scripts)
        self.scriptDuplicated.emit(base, cand)

    def _on_del_script(self):
        items = self.list_scripts.selectedItems()
        if not items:
            return
        name = items[0].text()
        self._scripts = [s for s in self._scripts if s != name]
        self.set_scripts(self._scripts)

    def _on_new_template(self):
        name, ok = QInputDialog.getText(self, "新增範本", "名稱：")
        if not ok or not name.strip():
            return
        if name in self._templates:
            QMessageBox.warning(self, "提示", "名稱已存在")
            return
        path, _ = QFileDialog.getOpenFileName(self, "選擇模板檔", "", "Image Files (*.png *.jpg *.jpeg);;All Files (*)")
        if not path:
            return
        self._templates[name] = path
        self.set_templates(self._templates)
        self.persist()  # Explicitly persist to ensure templates are available to TemplateMatcher

    def _on_rename_template(self):
        items = self.list_templates.selectedItems()
        if not items:
            return
        old = items[0].text()
        new, ok = QInputDialog.getText(self, "重命名範本", f"將 {old} 重命名為：", text=old)
        if not ok or not new.strip():
            return
        if new != old and new in self._templates:
            QMessageBox.warning(self, "提示", "名稱已存在")
            return
        val = self._templates.pop(old)
        self._templates[new] = val
        self.set_templates(self._templates)
        self.persist()  # Explicitly persist to ensure templates are available to TemplateMatcher

    def _on_dup_template(self):
        items = self.list_templates.selectedItems()
        if not items:
            return
        base = items[0].text()
        i = 1
        while True:
            cand = f"{base}_copy{i}"
            if cand not in self._templates:
                break
            i += 1
        self._templates[cand] = self._templates[base]
        self.set_templates(self._templates)
        self.persist()  # Explicitly persist to ensure templates are available to TemplateMatcher

    def _on_del_template(self):
        items = self.list_templates.selectedItems()
        if not items:
            return
        name = items[0].text()
        if name in self._templates:
            self._templates.pop(name)
            self.set_templates(self._templates)
            self.persist()  # Explicitly persist to ensure templates are available to TemplateMatcher
