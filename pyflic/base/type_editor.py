"""The Experiment Type Editor: build and edit the types a lab runs (ADR-0019).

An Experiment Type is a definition, not code: a layout, the light it
expects, its Control Comparisons, its factor names, the Analysis Modules it
combines, the plots its report draws and its default ``constants:``.  This
window edits one at a time, beside the list of the types there are — the
shipped ones, read-only, and the lab library's — and shows what stops the
one on screen from running as it is typed, so nothing that cannot run is
ever saved.  *New from…* copies any type as a starting point, because types
are flat: none is built on another.

The library is the folder :func:`~pyflic.base.experiment_types.library.
library_dir` names; the window shows it and can change it.  Copies beside
the data are not this window's business: the Design editor and the Config
Editor write them when they save a config that names a lab type.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

import yaml
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .analysis_modules import MODULES
from .experiment_types import library
from .experiment_types.definition import (
    FORMAT,
    LAYOUT_EITHER,
    LIGHT_ANY,
    LIGHT_NONE,
    PARADIGM_TYPE_NAMES,
    ROLES,
    TypeDefinition,
    definition_problems,
    dump_definition,
    parse_definition,
)
from .gui_env import sanitize_input_method_environment
from .ui import Card, Category, TopBar, apply_theme, icon
from .ui import settings as ui_settings

#: The layout combo: (label, definition value).
_LAYOUTS: tuple[tuple[str, str], ...] = (
    ("Either — each config states it", LAYOUT_EITHER),
    ("Two wells (6 chambers)", "two_well"),
    ("Single well (12 chambers)", "single_well"),
)
#: The light radio buttons: (label, value); a set of Paradigm types is the third.
_LIGHT_SET = "set"
#: A list row's data: (kind, name), kind ``"shipped"`` or ``"lab"``.
_ROLE_DATA = Qt.ItemDataRole.UserRole


def _plain(value: Any) -> Any:
    """*value* with tuples made lists, so yaml's safe dumper can write it."""
    return json.loads(json.dumps(value))


def _split(text: str) -> list[str]:
    return [part.strip() for part in str(text or "").split(",") if part.strip()]


class ExperimentTypeEditor(QMainWindow):
    """Build, edit, copy and delete Experiment Types (ADR-0019)."""

    #: A type was saved to, or deleted from, the library (its name), or the
    #: library's folder changed (``""``): the type lists elsewhere are stale.
    typesChanged = pyqtSignal(str)
    #: The window closed.
    closed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None, name: str | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Experiment Type Editor")
        self.resize(1120, 840)
        self._loading = False
        self._dirty = False
        self._read_only = False
        #: The library name of the type on screen, or ``None`` for a new one.
        self._original_name: str | None = None
        #: The type's own Plot Specs, by plot id, as plain mappings.
        self._plot_specs: dict[str, Any] = {}
        ## Widgets built early fire their signals while later ones do not
        ## exist yet; nothing reacts until the form is whole.
        self._loading = True
        self._build()
        self._loading = False
        self._reload_list()
        if name:
            self.open_type(name)
        else:
            self.new_type()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build(self) -> None:
        central = QWidget()
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        top = TopBar("Experiment Type Editor")
        self.new_btn = self._top_button(top, "New", "new", self.new_type)
        self.new_from_btn = self._top_button(top, "New from…", "add",
                                             lambda: self.new_from())
        self.save_btn = self._top_button(top, "Save to library", "save",
                                         self.save_to_library)
        self.delete_btn = self._top_button(top, "Delete", "delete", self.delete_type)
        outer.addWidget(top)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_list_side())
        splitter.addWidget(self._build_form_side())
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([280, 840])
        outer.addWidget(splitter, 1)
        self.setCentralWidget(central)

    @staticmethod
    def _top_button(top: TopBar, text: str, icon_name: str, handler) -> QPushButton:
        button = QPushButton(text)
        button.setIcon(icon(icon_name))
        button.clicked.connect(lambda _checked=False: handler())
        top.add_right(button)
        return button

    def _build_list_side(self) -> QWidget:
        side = QWidget()
        layout = QVBoxLayout(side)
        layout.setContentsMargins(10, 10, 6, 10)
        layout.setSpacing(6)
        layout.addWidget(QLabel("<b>Types</b>"))
        self.type_list = QListWidget()
        self.type_list.currentItemChanged.connect(self._on_list_selection)
        layout.addWidget(self.type_list, 1)

        card = Card("Lab library", Category.TOOLS, icon_name="project",
                    subtitle="Where the lab's types are kept.  Point it at a shared "
                             "drive to share them.")
        self.library_label = QLabel("")
        self.library_label.setWordWrap(True)
        self.library_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        card.add_body(self.library_label)
        change = QPushButton("Change folder…")
        change.setIcon(icon("open"))
        change.clicked.connect(self._choose_library_folder)
        card.add_body(change)
        layout.addWidget(card)
        return side

    def _build_form_side(self) -> QWidget:
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(6, 10, 10, 10)
        layout.setSpacing(8)
        self.read_only_note = QLabel(
            "<b>Shipped with pyflic — read-only.</b>  Use <i>New from…</i> to start "
            "a lab type from it.")
        self.read_only_note.setWordWrap(True)
        self.read_only_note.setVisible(False)
        layout.addWidget(self.read_only_note)
        self._form_cards: list[Card] = [
            self._build_identity_card(),
            self._build_shape_card(),
            self._build_light_card(),
            self._build_modules_card(),
            self._build_control_card(),
            self._build_plots_card(),
            self._build_facets_card(),
            self._build_constants_card(),
        ]
        for card in self._form_cards:
            layout.addWidget(card)
        layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(body)

        side = QWidget()
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(0, 0, 0, 0)
        side_layout.setSpacing(0)
        side_layout.addWidget(scroll, 1)
        side_layout.addWidget(self._build_problems_card())
        return side

    def _build_identity_card(self) -> Card:
        card = Card("Type", Category.LOAD, icon_name="settings",
                    subtitle="What experiment_type: names, and how menus and the "
                             "report cover say it.")
        try:
            from ..help import HelpButton

            card.add_title_widget(HelpButton(
                "concepts-experiment-types",
                tooltip="Experiment Types, Analysis Modules and the light they expect"))
        except Exception:  # noqa: BLE001 - help is optional, the editor is not
            pass
        form = QFormLayout()
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. HedonicClosedLoop  (letters, digits, _)")
        form.addRow("Name:", self.name_edit)
        self.display_edit = QLineEdit()
        self.display_edit.setPlaceholderText("e.g. Hedonic Feeding, closed loop")
        form.addRow("Display name:", self.display_edit)
        self.description_edit = QPlainTextEdit()
        self.description_edit.setPlaceholderText(
            "One paragraph for the report cover: what the assay is and how to read it.")
        self.description_edit.setMaximumHeight(80)
        form.addRow("Description:", self.description_edit)
        card.add_body(form)
        for widget in (self.name_edit, self.display_edit):
            widget.textChanged.connect(self._on_edited)
        self.description_edit.textChanged.connect(self._on_edited)
        return card

    def _build_shape_card(self) -> Card:
        card = Card("Layout, wells and factors", Category.ANALYZE)
        form = QFormLayout()
        self.layout_combo = QComboBox()
        for label, value in _LAYOUTS:
            self.layout_combo.addItem(label, value)
        self.layout_combo.currentIndexChanged.connect(self._on_edited)
        form.addRow("Chamber layout:", self.layout_combo)
        wells = QWidget()
        wells_row = QHBoxLayout(wells)
        wells_row.setContentsMargins(0, 0, 0, 0)
        self.well_a_check = QCheckBox("Well A")
        self.well_b_check = QCheckBox("Well B")
        for check in (self.well_a_check, self.well_b_check):
            check.toggled.connect(self._on_edited)
            wells_row.addWidget(check)
        wells_row.addStretch(1)
        form.addRow("Wells named:", wells)
        self.factors_edit = QLineEdit()
        self.factors_edit.setPlaceholderText(
            "e.g. Genotype, Diet — the Design declares them and their levels")
        self.factors_edit.textChanged.connect(self._on_factors_edited)
        form.addRow("Factor names:", self.factors_edit)
        card.add_body(form)
        return card

    def _build_light_card(self) -> Card:
        card = Card("Light", Category.QC,
                    subtitle="What the Opto Program may run.  A recording whose program "
                             "runs anything else fails to load; OpenLoop and dark "
                             "intervals may run beside a set of Paradigm types.")
        self.light_group = QButtonGroup(self)
        row = QHBoxLayout()
        self.light_buttons: dict[str, QRadioButton] = {}
        for value, label in ((LIGHT_NONE, "No light"), (LIGHT_ANY, "Any light or none"),
                             (_LIGHT_SET, "These Paradigm types:")):
            button = QRadioButton(label)
            self.light_group.addButton(button)
            self.light_buttons[value] = button
            button.toggled.connect(self._on_light_toggled)
            row.addWidget(button)
        row.addStretch(1)
        card.add_body(row)
        grid = QGridLayout()
        self.paradigm_checks: dict[str, QCheckBox] = {}
        for index, name in enumerate(PARADIGM_TYPE_NAMES):
            check = QCheckBox(name)
            check.toggled.connect(self._on_edited)
            self.paradigm_checks[name] = check
            grid.addWidget(check, index // 3, index % 3)
        card.add_body(grid)
        return card

    def _build_modules_card(self) -> Card:
        card = Card("Analysis Modules", Category.ANALYZE,
                    subtitle="The analyses pyflic provides that this type runs.  Each "
                             "states what it needs; the problems below say when a "
                             "choice cannot run.")
        self.module_checks: dict[str, QCheckBox] = {}
        for module in MODULES:
            check = QCheckBox(f"{module.title}  ({module.id})")
            check.toggled.connect(self._on_edited)
            self.module_checks[module.id] = check
            card.add_body(check)
            summary = QLabel(module.summary)
            summary.setObjectName("PyflicCardSubtitle")
            summary.setWordWrap(True)
            summary.setContentsMargins(24, 0, 0, 4)
            card.add_body(summary)
        return card

    def _build_control_card(self) -> Card:
        card = Card("Control comparisons", Category.ANALYZE,
                    subtitle="What the report leads with.  Both are optional; with both, "
                             "the Role comparison comes first.")
        grid = QGridLayout()
        self.role_check = QCheckBox("Role comparison:")
        self.role_check.toggled.connect(self._on_edited)
        self.role_a_combo = QComboBox()
        self.role_b_combo = QComboBox()
        for combo in (self.role_a_combo, self.role_b_combo):
            combo.addItems(list(ROLES))
            combo.currentIndexChanged.connect(self._on_edited)
        self.role_b_combo.setCurrentIndex(1)
        grid.addWidget(self.role_check, 0, 0)
        grid.addWidget(self.role_a_combo, 0, 1)
        grid.addWidget(QLabel("against"), 0, 2)
        grid.addWidget(self.role_b_combo, 0, 3)
        self.treatment_check = QCheckBox("Treatment control:")
        self.treatment_check.toggled.connect(self._on_edited)
        self.treatment_combo = QComboBox()
        self.treatment_combo.currentIndexChanged.connect(self._on_edited)
        grid.addWidget(self.treatment_check, 1, 0)
        grid.addWidget(self.treatment_combo, 1, 1, 1, 3)
        grid.setColumnStretch(4, 1)
        card.add_body(grid)
        note = QLabel("Every level of the factor is compared with a control level, "
                      "which each Design names (control_level), since levels change "
                      "from study to study.")
        note.setObjectName("PyflicCardSubtitle")
        note.setWordWrap(True)
        card.add_body(note)
        return card

    def _build_plots_card(self) -> Card:
        from .pubfigures import PLOT_TYPES

        card = Card("Plots", Category.PLOTS,
                    subtitle="The built-in figures the type's report draws, after its "
                             "modules' own.  A figure the layout cannot draw is "
                             "skipped.")
        self.plot_list = QListWidget()
        for plot_id, info in PLOT_TYPES.items():
            if info.get("module"):
                continue  # a module's figure comes with the module
            item = QListWidgetItem(f"{info.get('display', plot_id)}  ({plot_id})")
            item.setData(_ROLE_DATA, plot_id)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.plot_list.addItem(item)
        self.plot_list.setMaximumHeight(180)
        self.plot_list.itemChanged.connect(self._on_edited)
        card.add_body(self.plot_list)

        card.add_section_label("Plot Specs of its own")
        hint = QLabel("Labels, colours and order made in the Plot Editor, copied from a "
                      "Project's plot_specs.yaml.  A new Project of this type starts "
                      "with them.")
        hint.setObjectName("PyflicCardSubtitle")
        hint.setWordWrap(True)
        card.add_body(hint)
        self.spec_list = QListWidget()
        self.spec_list.setMaximumHeight(100)
        card.add_body(self.spec_list)
        row = QHBoxLayout()
        self.import_specs_btn = QPushButton("Import from a Project…")
        self.import_specs_btn.setIcon(icon("load"))
        self.import_specs_btn.clicked.connect(lambda _c=False: self._choose_spec_project())
        self.remove_spec_btn = QPushButton("Remove")
        self.remove_spec_btn.setIcon(icon("remove"))
        self.remove_spec_btn.clicked.connect(self._remove_spec)
        row.addWidget(self.import_specs_btn)
        row.addWidget(self.remove_spec_btn)
        row.addStretch(1)
        card.add_body(row)
        return card

    def _build_facets_card(self) -> Card:
        card = Card("Facets", Category.ANALYZE,
                    subtitle="The default minute cutoffs and their names.  A module "
                             "whose Facets come from the data (the Ratio analysis) "
                             "overrides them.")
        form = QFormLayout()
        self.cutoffs_edit = QLineEdit()
        self.cutoffs_edit.setPlaceholderText("e.g. 10, 70  (minutes; blank for none)")
        self.cutoffs_edit.textChanged.connect(self._on_edited)
        form.addRow("Cutoffs:", self.cutoffs_edit)
        self.fixed_check = QCheckBox("Fixed — a config may not change them")
        self.fixed_check.toggled.connect(self._on_edited)
        form.addRow("", self.fixed_check)
        self.labels_edit = QLineEdit()
        self.labels_edit.setPlaceholderText("e.g. Acclimation, Experiment, Cooldown")
        self.labels_edit.textChanged.connect(self._on_edited)
        form.addRow("Names:", self.labels_edit)
        card.add_body(form)
        return card

    def _build_constants_card(self) -> Card:
        card = Card("Default constants", Category.ANALYZE,
                    subtitle="Defaults under each config's constants: block, such as the "
                             "auto-removal cutoffs.  A config's own value wins.")
        self.constants_table = QTableWidget(0, 2)
        self.constants_table.setHorizontalHeaderLabels(["Constant", "Value"])
        self.constants_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch)
        self.constants_table.verticalHeader().setVisible(False)
        self.constants_table.setMaximumHeight(170)
        self.constants_table.itemChanged.connect(self._on_edited)
        card.add_body(self.constants_table)
        row = QHBoxLayout()
        self.add_constant_btn = QPushButton("Add")
        self.add_constant_btn.setIcon(icon("add"))
        self.add_constant_btn.clicked.connect(lambda _c=False: self._add_constant_row())
        self.remove_constant_btn = QPushButton("Remove")
        self.remove_constant_btn.setIcon(icon("remove"))
        self.remove_constant_btn.clicked.connect(self._remove_constant_row)
        row.addWidget(self.add_constant_btn)
        row.addWidget(self.remove_constant_btn)
        row.addStretch(1)
        card.add_body(row)
        return card

    def _build_problems_card(self) -> Card:
        card = Card("Problems", Category.QC, icon_name="warning")
        self.problems_label = QLabel("")
        self.problems_label.setWordWrap(True)
        self.problems_label.setTextFormat(Qt.TextFormat.RichText)
        card.add_body(self.problems_label)
        self.problems_card = card
        return card

    # ------------------------------------------------------------------
    # The list of types
    # ------------------------------------------------------------------

    def _reload_list(self, select: str | None = None) -> None:
        self._loading = True
        try:
            self.type_list.clear()
            self._list_heading("Shipped with pyflic")
            for definition in library.shipped_definitions():
                self._list_entry(definition, "shipped")
            self._list_heading("Lab library")
            lab, problems = library.library_definitions()
            for definition in lab:
                self._list_entry(definition, "lab")
            if not lab:
                self._list_heading("  (none yet)", italic=True)
            if problems:
                item = QListWidgetItem(f"⚠ {len(problems)} file(s) cannot be used")
                item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                item.setToolTip("\n\n".join(problems))
                self.type_list.addItem(item)
            self.library_label.setText(str(library.library_dir()))
            if select:
                self._select_in_list(select)
        finally:
            self._loading = False

    def _list_heading(self, text: str, *, italic: bool = False) -> None:
        item = QListWidgetItem(text)
        font = item.font()
        font.setBold(not italic)
        font.setItalic(italic)
        item.setFont(font)
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        self.type_list.addItem(item)

    def _list_entry(self, definition: TypeDefinition, kind: str) -> None:
        item = QListWidgetItem(f"   {definition.label}")
        item.setData(_ROLE_DATA, (kind, definition.name))
        item.setToolTip(f"{definition.name} — {definition.light_text()}")
        self.type_list.addItem(item)

    def _select_in_list(self, name: str | None) -> None:
        key = library.name_key(name or "")
        for row in range(self.type_list.count()):
            data = self.type_list.item(row).data(_ROLE_DATA)
            if data and library.name_key(data[1]) == key:
                self.type_list.setCurrentRow(row)
                return
        self.type_list.setCurrentRow(-1)

    def list_names(self) -> list[str]:
        """The type names the list shows, shipped first."""
        names = []
        for row in range(self.type_list.count()):
            data = self.type_list.item(row).data(_ROLE_DATA)
            if data:
                names.append(data[1])
        return names

    def _on_list_selection(self, current, _previous) -> None:
        if self._loading or current is None:
            return
        data = current.data(_ROLE_DATA)
        if not data:
            return
        if not self.open_type(data[1]):
            self._loading = True
            self._select_in_list(self._original_name)
            self._loading = False

    # ------------------------------------------------------------------
    # Opening, new, new from
    # ------------------------------------------------------------------

    def _discard_ok(self) -> bool:
        return not self._dirty or self._confirm(
            "The type on screen has changes that are not saved.  Discard them?")

    def open_type(self, name: str) -> bool:
        """Show the type *name*: a shipped one read-only, a lab one to edit."""
        if not self._discard_ok():
            return False
        shipped = library.shipped_definition(name)
        definition = shipped or library.library_definition(name)
        if definition is None:
            self._warn(f"No type named '{name}' is shipped or in the library.")
            return False
        self._original_name = None if shipped is not None else definition.name
        self._load_definition(definition, read_only=shipped is not None)
        self._select_quietly(definition.name)
        return True

    def new_type(self) -> bool:
        """Start a type from nothing: either layout, any light, no modules."""
        if not self._discard_ok():
            return False
        self._original_name = None
        self._load_definition(TypeDefinition(name=""), read_only=False)
        self._select_quietly(None)
        self.name_edit.setFocus()
        return True

    def new_from(self, name: str | None = None) -> bool:
        """Start a lab type from the one on screen, renamed *name* (asked for
        when not given).  Nothing links the two afterwards."""
        data = self.definition_data()
        if name is None:
            base = data.get("name") or "Type"
            name, ok = QInputDialog.getText(self, "New from…",
                                            "Name of the new type:", text=f"{base}Copy")
            if not ok:
                return False
        name = str(name).strip()
        data["name"] = name or "NewType"
        definition, _problems = parse_definition(data)
        if definition is None:
            definition = TypeDefinition(name=name)
        self._original_name = None
        self._load_definition(definition.with_name(definition.name), read_only=False)
        self._dirty = True
        self._select_quietly(None)
        return True

    def _select_quietly(self, name: str | None) -> None:
        self._loading = True
        self._select_in_list(name)
        self._loading = False

    # ------------------------------------------------------------------
    # The form ↔ a definition
    # ------------------------------------------------------------------

    def _load_definition(self, definition: TypeDefinition, *, read_only: bool) -> None:
        data = dump_definition(definition) if definition.name else {}
        self._loading = True
        try:
            self.name_edit.setText(definition.name)
            self.display_edit.setText(definition.display_name)
            self.description_edit.setPlainText(definition.description)
            layout = definition.chamber_layout or LAYOUT_EITHER
            self.layout_combo.setCurrentIndex(max(self.layout_combo.findData(layout), 0))
            self.well_a_check.setChecked("A" in definition.required_wells)
            self.well_b_check.setChecked("B" in definition.required_wells)
            self.factors_edit.setText(", ".join(definition.factors))
            self._refresh_treatment_choices()
            light = definition.light
            key = light if light in (LIGHT_NONE, LIGHT_ANY) else _LIGHT_SET
            self.light_buttons[key].setChecked(True)
            chosen = set(definition.paradigm_types)
            for name, check in self.paradigm_checks.items():
                check.setChecked(name in chosen)
            for module_id, check in self.module_checks.items():
                check.setChecked(module_id in definition.modules)
            self.role_check.setChecked(definition.roles is not None)
            roles = definition.roles or (ROLES[0], ROLES[1])
            self.role_a_combo.setCurrentText(roles[0])
            self.role_b_combo.setCurrentText(roles[1])
            self.treatment_check.setChecked(definition.treatment_control is not None)
            if definition.treatment_control:
                self.treatment_combo.setCurrentText(definition.treatment_control)
            picked = set(definition.plots)
            for row in range(self.plot_list.count()):
                item = self.plot_list.item(row)
                item.setCheckState(Qt.CheckState.Checked
                                   if item.data(_ROLE_DATA) in picked
                                   else Qt.CheckState.Unchecked)
            self._plot_specs = _plain(dict(definition.plot_specs))
            self._refresh_spec_list()
            facets = data.get("facets") or {}
            self.cutoffs_edit.setText(", ".join(str(v) for v in facets.get("cutoffs") or []))
            self.fixed_check.setChecked(bool(facets.get("fixed")))
            self.labels_edit.setText(", ".join(definition.facet_labels))
            self.constants_table.setRowCount(0)
            for key, value in (definition.constants or {}).items():
                self._add_constant_row(key, value)
        finally:
            self._loading = False
        self._read_only = read_only
        self.read_only_note.setVisible(read_only)
        for card in self._form_cards:
            card.setEnabled(not read_only)
        self.save_btn.setEnabled(not read_only)
        self._dirty = False
        self._sync_light_checks()
        self._refresh_problems()

    def definition_data(self) -> dict:
        """The yaml mapping the form says, as :func:`parse_definition` reads it."""
        data: dict[str, Any] = {"format": FORMAT, "name": self.name_edit.text().strip()}
        if self.display_edit.text().strip():
            data["display_name"] = self.display_edit.text().strip()
        if self.description_edit.toPlainText().strip():
            data["description"] = self.description_edit.toPlainText().strip()
        data["chamber_layout"] = self.layout_combo.currentData() or LAYOUT_EITHER
        if self.light_buttons[LIGHT_NONE].isChecked():
            data["light"] = LIGHT_NONE
        elif self.light_buttons[_LIGHT_SET].isChecked():
            data["light"] = [n for n, c in self.paradigm_checks.items() if c.isChecked()]
        else:
            data["light"] = LIGHT_ANY
        wells = [w for w, c in (("A", self.well_a_check), ("B", self.well_b_check))
                 if c.isChecked()]
        if wells:
            data["required_wells"] = wells
        factors = _split(self.factors_edit.text())
        if factors:
            data["factors"] = factors
        modules = [m for m, c in self.module_checks.items() if c.isChecked()]
        if modules:
            data["modules"] = modules
        control: dict[str, Any] = {}
        if self.role_check.isChecked():
            control["roles"] = [self.role_a_combo.currentText(),
                                self.role_b_combo.currentText()]
        if self.treatment_check.isChecked():
            control["treatment"] = self.treatment_combo.currentText()
        if control:
            data["control"] = control
        plots = [self.plot_list.item(r).data(_ROLE_DATA)
                 for r in range(self.plot_list.count())
                 if self.plot_list.item(r).checkState() == Qt.CheckState.Checked]
        if plots:
            data["plots"] = plots
        if self._plot_specs:
            data["plot_specs"] = _plain(self._plot_specs)
        facets: dict[str, Any] = {}
        cutoffs = _split(self.cutoffs_edit.text())
        if cutoffs:
            facets["cutoffs"] = [self._number(v) for v in cutoffs]
        if self.fixed_check.isChecked():
            facets["fixed"] = True
        labels = _split(self.labels_edit.text())
        if labels:
            facets["labels"] = labels
        if facets:
            data["facets"] = facets
        constants = self._constants()
        if constants:
            data["constants"] = constants
        return data

    @staticmethod
    def _number(text: str):
        """A number from *text*, or the text itself for the definition's
        reader to report."""
        try:
            value = float(text)
        except ValueError:
            return text
        return int(value) if value == int(value) else value

    def _constants(self) -> dict:
        out: dict[str, Any] = {}
        for row in range(self.constants_table.rowCount()):
            key_item = self.constants_table.item(row, 0)
            value_item = self.constants_table.item(row, 1)
            key = key_item.text().strip() if key_item else ""
            if not key:
                continue
            text = value_item.text().strip() if value_item else ""
            try:
                out[key] = yaml.safe_load(text) if text else None
            except yaml.YAMLError:
                out[key] = text
        return out

    def current(self) -> tuple[TypeDefinition | None, list[str]]:
        """``(definition, problems)`` for what the form says: reading
        problems, what stops the modules running together, and a name a lab
        type may not take."""
        data = self.definition_data()
        problems: list[str] = []
        for value in (data.get("facets") or {}).get("cutoffs") or []:
            if isinstance(value, str):
                problems.append(f"'facets.cutoffs' must be numbers, got {value!r}")
        definition, read = parse_definition(data)
        problems += read
        if definition is not None:
            problems += definition_problems(definition)
            if not self._read_only and library.is_shipped_name(definition.name):
                problems.append(f"'{definition.name}' is a shipped type's name; a lab "
                                f"type needs a name of its own")
        return definition, list(dict.fromkeys(problems))

    # ------------------------------------------------------------------
    # Reacting to edits
    # ------------------------------------------------------------------

    def _on_edited(self, *_args) -> None:
        if self._loading:
            return
        self._dirty = True
        self._refresh_problems()

    def _on_light_toggled(self, *_args) -> None:
        self._sync_light_checks()
        self._on_edited()

    def _sync_light_checks(self) -> None:
        on = self.light_buttons[_LIGHT_SET].isChecked() and not self._read_only
        for check in self.paradigm_checks.values():
            check.setEnabled(on)

    def _on_factors_edited(self, *_args) -> None:
        self._refresh_treatment_choices()
        self._on_edited()

    def _refresh_treatment_choices(self) -> None:
        current = self.treatment_combo.currentText()
        was = self._loading
        self._loading = True
        self.treatment_combo.clear()
        self.treatment_combo.addItems(_split(self.factors_edit.text()))
        if current:
            self.treatment_combo.setCurrentText(current)
        self._loading = was

    def _refresh_problems(self) -> list[str]:
        if self._read_only:
            self.problems_label.setText(
                "A shipped type is read-only; <i>New from…</i> copies it.")
            self.save_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)
            return []
        _definition, problems = self.current()
        if problems:
            items = "".join(f"<li>{p}</li>" for p in problems)
            self.problems_label.setText(
                f"<span style='color:#dc2626'><b>{len(problems)} problem"
                f"{'' if len(problems) == 1 else 's'}</b> — fix "
                f"{'it' if len(problems) == 1 else 'them'} to save.</span>"
                f"<ul style='margin:2px'>{items}</ul>")
        else:
            self.problems_label.setText(
                "<span style='color:#16a34a'><b>No problems</b> — this type can run.</span>")
        self.save_btn.setEnabled(not self._read_only and not problems)
        self.delete_btn.setEnabled(not self._read_only and self._original_name is not None)
        return problems

    # ---- Plot Specs and constants --------------------------------------

    def _choose_spec_project(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self, "Choose the Project whose plot_specs.yaml to copy")
        if directory:
            self.import_plot_specs(directory)

    def import_plot_specs(self, project_dir) -> list[str]:
        """Copy every Plot Spec in *project_dir*'s ``plot_specs.yaml`` into
        the type, replacing ones of the same plot id; returns their ids."""
        from .pubfigures import load_project_specs, specs_path

        if not os.path.isfile(specs_path(str(project_dir))):
            self._warn(f"{project_dir} has no plot_specs.yaml: make its figures in the "
                       f"Plot Editor first.")
            return []
        specs = load_project_specs(str(project_dir))
        for plot_id, spec in specs.plots.items():
            self._plot_specs[plot_id] = _plain(spec.to_dict())
        self._refresh_spec_list()
        self._on_edited()
        return list(specs.plots)

    def _refresh_spec_list(self) -> None:
        self.spec_list.clear()
        for plot_id in self._plot_specs:
            self.spec_list.addItem(plot_id)

    def _remove_spec(self) -> None:
        item = self.spec_list.currentItem()
        if item is None:
            return
        self._plot_specs.pop(item.text(), None)
        self._refresh_spec_list()
        self._on_edited()

    def _add_constant_row(self, key: str = "", value: Any = None) -> None:
        row = self.constants_table.rowCount()
        was = self._loading
        self._loading = True
        self.constants_table.insertRow(row)
        self.constants_table.setItem(row, 0, QTableWidgetItem(str(key)))
        text = "" if value is None and not key else yaml.safe_dump(
            value, default_flow_style=True).strip().removesuffix("...").strip()
        self.constants_table.setItem(row, 1, QTableWidgetItem(text))
        self._loading = was
        if not was:
            self._on_edited()

    def _remove_constant_row(self) -> None:
        row = self.constants_table.currentRow()
        if row >= 0:
            self.constants_table.removeRow(row)
            self._on_edited()

    # ------------------------------------------------------------------
    # Saving and deleting
    # ------------------------------------------------------------------

    def save_to_library(self) -> bool:
        """Write the type on screen to the library; ``False`` with a reason
        shown when it has a problem, is shipped, or the user declines."""
        if self._read_only:
            return False
        definition, problems = self.current()
        if definition is None or problems:
            self._warn("This type cannot be saved yet:\n\n  • " + "\n  • ".join(
                problems or ["it needs a name"]))
            return False
        existing = library.library_definition(definition.name)
        same = (self._original_name is not None and library.name_key(self._original_name)
                == library.name_key(definition.name))
        if existing is not None and not same and not self._confirm(
                f"The library already has a type named '{existing.name}'.  Replace it?"):
            return False
        try:
            path = library.save_to_library(definition)
        except (OSError, ValueError) as err:
            self._warn(f"Could not save the type:\n{err}")
            return False
        self._original_name = definition.name
        self._dirty = False
        self._reload_list(select=definition.name)
        self.statusBar().showMessage(f"Saved {path}", 6000)
        self._refresh_problems()
        self.typesChanged.emit(definition.name)
        return True

    def delete_type(self) -> bool:
        """Remove the lab type on screen from the library, after asking."""
        name = self._original_name
        if self._read_only or not name:
            return False
        if not self._confirm(
                f"Delete '{name}' from the lab library?\n\nData that carries a copy of "
                f"it beside its config keeps analysing with that copy."):
            return False
        library.delete_from_library(name)
        self._dirty = False
        self._reload_list()
        self.new_type()
        self.typesChanged.emit(name)
        return True

    # ---- The library folder -------------------------------------------

    def _choose_library_folder(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self, "Choose the lab library's folder", str(library.library_dir()))
        if directory:
            self.set_library_folder(directory)

    def set_library_folder(self, directory) -> None:
        """Keep the lab library in *directory* from now on (``ui.json``)."""
        library.set_library_dir(directory)
        self._reload_list(select=self._original_name)
        self.typesChanged.emit("")

    # ------------------------------------------------------------------
    # Small things
    # ------------------------------------------------------------------

    def _warn(self, message: str) -> None:
        QMessageBox.warning(self, self.windowTitle(), message)

    def _confirm(self, message: str) -> bool:
        answer = QMessageBox.question(
            self, self.windowTitle(), message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        return answer == QMessageBox.StandardButton.Yes

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt's name
        if not self._discard_ok():
            event.ignore()
            return
        super().closeEvent(event)
        self.closed.emit()


#: Editors opened without a parent, kept alive until they close.
_OPEN: list[ExperimentTypeEditor] = []


def open_type_editor(parent: QWidget | None = None, name: str | None = None
                     ) -> ExperimentTypeEditor:
    """Show an Experiment Type Editor on *name* (a new type when ``None``)
    and return it; connect its ``typesChanged`` to refresh a type list."""
    editor = ExperimentTypeEditor(parent, name=name)
    if parent is None:
        _OPEN.append(editor)
        editor.closed.connect(lambda: _OPEN.remove(editor) if editor in _OPEN else None)
    editor.show()
    editor.raise_()
    editor.activateWindow()
    return editor


def main() -> None:
    """``pyflic-types [name]``: the editor on its own."""
    sanitize_input_method_environment()
    app = QApplication.instance() or QApplication(sys.argv)
    apply_theme(app, mode=ui_settings.get("theme", "auto"))
    name = sys.argv[1] if len(sys.argv) > 1 else None
    window = ExperimentTypeEditor(name=name)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":  # pragma: no cover
    main()
