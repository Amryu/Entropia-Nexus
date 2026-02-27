"""Inventory import dialog — paste or open file, parse TSV/JSON, preview diff, import."""

from __future__ import annotations

import json
import re

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QPlainTextEdit, QStackedWidget, QFileDialog, QTreeWidget,
    QTreeWidgetItem, QHeaderView, QMessageBox, QSizePolicy,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor

from ..theme import (
    PRIMARY, SECONDARY, HOVER, BORDER, ACCENT,
    TEXT, TEXT_MUTED, ERROR, TABLE_ROW_ALT,
)
from ...core.inventory_utils import format_ped
from ...core.logger import get_logger

log = get_logger("InventoryImport")

MAX_IMPORT_ITEMS = 30_000

# Colours for diff status badges
_CLR_ADDED = "#48b868"
_CLR_CHANGED = "#d4a030"
_CLR_REMOVED = "#e06060"
_CLR_SAME = TEXT_MUTED


# ---------------------------------------------------------------------------
# Background import worker
# ---------------------------------------------------------------------------

class _ImportWorker(QThread):
    finished = pyqtSignal(object, str)  # result_dict | None, error_message

    def __init__(self, nexus_client, items: list[dict]):
        super().__init__()
        self._nc = nexus_client
        self._items = items

    def run(self):
        try:
            result = self._nc.import_inventory(self._items, sync=True)
            if result is None:
                self.finished.emit(None, "Import failed — server returned no data.")
            else:
                self.finished.emit(result, "")
        except Exception as e:
            log.error("Import worker error: %s", e)
            self.finished.emit(None, str(e))


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _normalize_name(name: str) -> str:
    return re.sub(r'\s+', ' ', name).strip().lower()


def _generate_gender_aliases(name: str) -> list[str]:
    """Generate gendered name variants for Gender: Both items."""
    if not name:
        return []
    if re.search(r'\((M|F)\)', name) or re.search(r'\(M,', name) or re.search(r',\s*F\)', name):
        return []
    tag_match = re.match(r'^(.+?)(\s*\([^)]+\))$', name)
    if tag_match:
        base = tag_match.group(1).strip()
        tag_content = tag_match.group(2).strip()[1:-1]
        return [f"{base} (M, {tag_content})", f"{base} (F, {tag_content})"]
    return [f"{name} (M)", f"{name} (F)"]


def _build_name_lookup(slim_items: list[dict]) -> dict[str, int]:
    """Build case-insensitive name→item_id map from slim exchange items."""
    lookup: dict[str, int] = {}
    for s in slim_items:
        item_id = s.get('i')
        name = s.get('n')
        if item_id and name:
            lookup[_normalize_name(name)] = item_id
            # Gender aliases for Armor/Clothing with Both gender
            if s.get('t') in ('Armor', 'Clothing') and s.get('g') == 'Both':
                for alias in _generate_gender_aliases(name):
                    lookup[_normalize_name(alias)] = item_id
    return lookup


def _resolve_item_id(name: str, name_lookup: dict[str, int]) -> int:
    """Resolve an item name to its ID using the slim name lookup."""
    norm = _normalize_name(name)
    item_id = name_lookup.get(norm, 0)
    if item_id > 0:
        return item_id
    # Try stripping gender tags
    stripped = re.sub(r'\s*\((M|F)\)', '', name)
    item_id = name_lookup.get(_normalize_name(stripped), 0)
    if item_id > 0:
        return item_id
    # Try stripping " Pet" suffix
    if norm.endswith(' pet'):
        item_id = name_lookup.get(norm[:-4], 0)
    # Try removing apostrophes
    if item_id == 0 and "'" in norm:
        item_id = name_lookup.get(norm.replace("'", ""), 0)
    return item_id


# --- Container hierarchy helpers ---

def _resolve_storage_location(item_id, container_map: dict, visited: set) -> str | None:
    if item_id not in container_map:
        return None
    if item_id in visited:
        return None
    visited.add(item_id)
    entry = container_map[item_id]
    ref = entry.get('ref')
    if ref is None or ref not in container_map:
        return entry.get('container')
    return _resolve_storage_location(ref, container_map, visited)


def _extract_planet(storage: str | None) -> str | None:
    if not storage:
        return None
    m = re.match(r'^STORAGE \(([^)]+)\)$', storage, re.IGNORECASE)
    return m.group(1).strip() if m else None


def _build_container_path(item_id, container_map: dict, raw_data: list[dict]) -> str | None:
    """Walk the container hierarchy to build a full path string."""
    segments = []
    current = item_id
    visited = set()
    # Build a quick ID→raw-item lookup
    raw_by_id = {r.get('id'): r for r in raw_data if r.get('id') is not None}

    while current is not None and current in container_map:
        if current in visited:
            break
        visited.add(current)
        entry = container_map[current]
        raw_item = raw_by_id.get(current)
        name = (entry.get('container') or '') if raw_item is None else (
            raw_item.get('item_name') or raw_item.get('name') or
            raw_item.get('Name') or entry.get('container') or ''
        )
        name = re.sub(r'\s+', ' ', name).strip()
        if name:
            segments.insert(0, name)
        current = entry.get('ref')

    return ' > '.join(segments) if segments else None


# --- TSV parsing ---

def _parse_tsv_field(field: str) -> str:
    field = field.strip()
    if field.startswith('"') and field.endswith('"'):
        return field[1:-1].replace('""', '"')
    return field


def _detect_and_parse_tsv(text: str) -> list[dict] | None:
    lines = [l for l in text.split('\n') if l.strip()]
    if len(lines) < 2:
        return None

    header = lines[0].split('\t')
    if len(header) < 3:
        return None

    header_map: dict[str, int] = {}
    for i, h in enumerate(header):
        key = re.sub(r'[^a-z0-9]', '', h.strip().lower())
        header_map[key] = i

    name_idx = header_map.get('name', header_map.get('itemname', -1))
    qty_idx = header_map.get('quantity', header_map.get('qty', -1))
    if name_idx < 0 or qty_idx < 0:
        return None

    id_idx = header_map.get('id', -1)
    value_idx = header_map.get('valueped', header_map.get('value', -1))
    container_idx = header_map.get('container', -1)
    container_ref_idx = header_map.get('containerrefid', header_map.get('containerref', -1))

    items = []
    for i in range(1, len(lines)):
        cols = lines[i].split('\t')
        min_cols = max(name_idx, qty_idx) + 1
        if len(cols) < min_cols:
            continue
        name = _parse_tsv_field(cols[name_idx])
        if not name:
            continue

        try:
            qty = int(cols[qty_idx])
        except (ValueError, IndexError):
            qty = 1

        value = None
        if value_idx >= 0 and value_idx < len(cols):
            try:
                value = float(cols[value_idx])
            except ValueError:
                pass

        container = None
        if container_idx >= 0 and container_idx < len(cols):
            container = _parse_tsv_field(cols[container_idx]) or None

        ref_id = None
        if container_ref_idx >= 0 and container_ref_idx < len(cols):
            raw_ref = cols[container_ref_idx].strip()
            if raw_ref and raw_ref != 'null':
                try:
                    ref_id = int(raw_ref)
                except ValueError:
                    pass

        row_id = i
        if id_idx >= 0 and id_idx < len(cols):
            try:
                row_id = int(cols[id_idx])
            except ValueError:
                pass

        items.append({
            'id': row_id,
            'item_name': name,
            'quantity': qty,
            'value': value,
            'container': container,
            'containerRefId': ref_id,
        })

    return items if items else None


# --- Main processing pipeline ---

def _process_items(
    raw_data: list[dict],
    slim_items: list[dict],
) -> tuple[list[dict], list[dict], str | None]:
    """Parse, normalize, resolve, and combine items.

    Returns (resolved, unresolved, error_or_None).
    """
    if len(raw_data) > MAX_IMPORT_ITEMS:
        return [], [], f"Too many items ({len(raw_data):,}). Maximum {MAX_IMPORT_ITEMS:,}."

    # 1. Build container map
    container_map: dict[int, dict] = {}
    for raw in raw_data:
        rid = raw.get('id')
        if rid is not None:
            container_map[rid] = {
                'container': (raw.get('container') or raw.get('Container') or '').strip() or None,
                'ref': raw.get('containerRefId') or raw.get('container_ref_id'),
            }

    # 2. Normalize items
    normalized = []
    for raw in raw_data:
        item_name = (
            raw.get('item_name') or raw.get('ItemName') or
            raw.get('Name') or raw.get('name') or ''
        )
        if not item_name:
            continue
        item_name = re.sub(r'\s+', ' ', str(item_name)).strip()

        # Skip blueprint books
        if re.search(r'\(Vol\.\s*\d+\)', item_name) or item_name.startswith('Blueprints:'):
            continue

        qty = raw.get('quantity') or raw.get('Quantity') or raw.get('qty') or raw.get('Qty') or 1
        value = raw.get('value') or raw.get('Value')
        instance_key = raw.get('instance_key') or raw.get('InstanceKey') or raw.get('instanceKey')
        details = raw.get('details') or raw.get('Details')

        ref_id = raw.get('containerRefId') or raw.get('container_ref_id')
        explicit_container = raw.get('container') or raw.get('Container')

        # Resolve storage location
        storage = None
        if ref_id is not None:
            storage = _resolve_storage_location(ref_id, container_map, set())
        if not storage and isinstance(explicit_container, str):
            storage = explicit_container.strip() or None

        # Skip auction items
        if storage and storage.upper() == 'AUCTION':
            continue

        planet = _extract_planet(storage)

        # Build container path
        container_path = None
        if ref_id is not None:
            container_path = _build_container_path(ref_id, container_map, raw_data)
        elif storage:
            container_path = storage

        normalized.append({
            'item_name': item_name,
            'quantity': max(0, int(qty) if isinstance(qty, (int, float)) else 1),
            'value': float(value) if value is not None else None,
            'instance_key': instance_key or None,
            'details': details or None,
            'container': planet,
            'container_path': container_path,
        })

    # 3. Resolve name → item_id
    name_lookup = _build_name_lookup(slim_items)

    # 4. Combine stackable items
    stack_map: dict[str, dict] = {}
    individuals: list[dict] = []

    for item in normalized:
        item_id = _resolve_item_id(item['item_name'], name_lookup)

        if item['instance_key']:
            individuals.append({**item, '_item_id': item_id})
            continue

        if item_id > 0:
            key = f"{item_id}::{item.get('container') or ''}"
            if key in stack_map:
                existing = stack_map[key]
                existing['quantity'] += item['quantity'] or 1
                if item['value'] is not None:
                    existing['value'] = (existing['value'] or 0) + item['value']
            else:
                stack_map[key] = {**item, '_item_id': item_id, 'quantity': item['quantity'] or 1}
        else:
            individuals.append({**item, '_item_id': item_id})

    # 5. Split resolved / unresolved
    resolved = []
    unresolved = []
    for entry in list(stack_map.values()) + individuals:
        item_id = entry.pop('_item_id', 0)
        out = {
            'item_id': item_id,
            'item_name': entry['item_name'],
            'quantity': entry['quantity'],
            'value': entry.get('value'),
            'instance_key': entry.get('instance_key'),
            'details': entry.get('details'),
            'container': entry.get('container'),
            'container_path': entry.get('container_path'),
        }
        if item_id == 0:
            unresolved.append(out)
        else:
            resolved.append(out)

    # Deduplicate unresolved by lowercase name
    seen: set[str] = set()
    deduped_unresolved = []
    for u in unresolved:
        low = u['item_name'].lower()
        if low not in seen:
            seen.add(low)
            deduped_unresolved.append(u)

    return resolved, deduped_unresolved, None


def _compute_diff(
    parsed: list[dict],
    unresolved: list[dict],
    current_items: list[dict],
) -> dict[str, int]:
    """Compute diff summary between parsed and current inventory."""
    def diff_key(item):
        ik = item.get('instance_key')
        if ik:
            return f"{item.get('item_id', 0)}::{ik}"
        return f"{item.get('item_id', 0)}::{item.get('container') or ''}"

    current_map: dict[str, dict] = {}
    for item in current_items:
        current_map[diff_key(item)] = item

    added = changed = unchanged = 0
    new_keys: set[str] = set()

    for item in parsed + unresolved:
        key = diff_key(item)
        new_keys.add(key)
        existing = current_map.get(key)
        if not existing:
            item['_status'] = 'new'
            added += 1
        elif existing.get('quantity') != item.get('quantity'):
            item['_status'] = 'changed'
            item['_old_qty'] = existing.get('quantity')
            changed += 1
        else:
            item['_status'] = 'same'
            unchanged += 1

    removed = sum(1 for k in current_map if k not in new_keys)
    return {'added': added, 'changed': changed, 'removed': removed, 'unchanged': unchanged}


# ---------------------------------------------------------------------------
# Import dialog
# ---------------------------------------------------------------------------

class InventoryImportDialog(QDialog):
    """3-step import wizard: paste/file → preview → done."""

    def __init__(
        self,
        *,
        nexus_client,
        current_items: list[dict],
        slim_lookup: dict[int, dict],
        parent=None,
    ):
        super().__init__(parent)
        self._nc = nexus_client
        self._current_items = current_items
        # Flatten slim lookup back to list for name resolution
        self._slim_items = list(slim_lookup.values())
        self._worker: _ImportWorker | None = None
        self._parsed: list[dict] = []
        self._unresolved: list[dict] = []
        self._diff: dict[str, int] = {}

        self.setWindowTitle("Import Inventory")
        self.setMinimumSize(600, 480)
        self.resize(700, 560)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {SECONDARY};
            }}
        """)

        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 12, 16, 12)
        outer.setSpacing(10)

        # Title
        title = QLabel("Import Inventory")
        title.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {TEXT};")
        outer.addWidget(title)

        # Stacked pages
        self._stack = QStackedWidget()
        outer.addWidget(self._stack, 1)

        self._build_paste_page()
        self._build_preview_page()
        self._build_done_page()

    # --- Step 1: Paste / File ---

    def _build_paste_page(self):
        page = QVBoxLayout()
        w = _page_widget(page)

        # Mode toggle
        mode_row = QHBoxLayout()
        mode_row.setSpacing(8)

        self._btn_paste = QPushButton("Paste Text")
        self._btn_paste.setStyleSheet(_active_btn_css())
        self._btn_paste.clicked.connect(lambda: self._set_input_mode('text'))
        mode_row.addWidget(self._btn_paste)

        self._btn_file = QPushButton("Open File")
        self._btn_file.setStyleSheet(_inactive_btn_css())
        self._btn_file.clicked.connect(lambda: self._set_input_mode('file'))
        mode_row.addWidget(self._btn_file)

        mode_row.addStretch()

        # Help toggle
        help_btn = QPushButton("?")
        help_btn.setFixedSize(24, 24)
        help_btn.setToolTip("Supported formats")
        help_btn.setStyleSheet(f"""
            QPushButton {{
                background: {PRIMARY}; color: {TEXT_MUTED};
                border: 1px solid {BORDER}; border-radius: 12px;
                font-weight: bold; font-size: 12px;
            }}
            QPushButton:hover {{ background: {HOVER}; color: {TEXT}; }}
        """)
        help_btn.clicked.connect(self._toggle_help)
        mode_row.addWidget(help_btn)

        page.addLayout(mode_row)

        # Help text (hidden by default)
        self._help_label = QLabel(
            "Supported formats:\n"
            "  - TSV (tab-separated) with header: Name, Quantity, Id, Value, Container\n"
            "  - JSON array of items or {items: [...]}\n"
            "  - Each item needs at least a name field"
        )
        self._help_label.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 11px; background: {PRIMARY};"
            f" border: 1px solid {BORDER}; border-radius: 4px; padding: 8px;"
        )
        self._help_label.setWordWrap(True)
        self._help_label.hide()
        page.addWidget(self._help_label)

        # Text input
        self._text_input = QPlainTextEdit()
        self._text_input.setPlaceholderText(
            "Paste your inventory data here (TSV or JSON)..."
        )
        self._text_input.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: {PRIMARY};
                color: {TEXT};
                border: 1px solid {BORDER};
                border-radius: 4px;
                padding: 8px;
                font-size: 13px;
                font-family: monospace;
            }}
        """)
        page.addWidget(self._text_input, 1)

        # File picker (hidden by default)
        self._file_row = QHBoxLayout()
        file_btn = QPushButton("Choose File...")
        file_btn.clicked.connect(self._pick_file)
        self._file_row.addWidget(file_btn)
        self._file_label = QLabel("No file selected")
        self._file_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px;")
        self._file_row.addWidget(self._file_label, 1)
        self._file_widget = _page_widget(self._file_row)
        self._file_widget.hide()
        page.addWidget(self._file_widget)

        # Error label
        self._parse_error = QLabel()
        self._parse_error.setStyleSheet(f"color: {ERROR}; font-size: 12px;")
        self._parse_error.setWordWrap(True)
        self._parse_error.hide()
        page.addWidget(self._parse_error)

        # Button row
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        parse_btn = QPushButton("Parse")
        parse_btn.setObjectName("accentButton")
        parse_btn.clicked.connect(self._on_parse)
        btn_row.addWidget(parse_btn)
        page.addLayout(btn_row)

        self._stack.addWidget(w)

    # --- Step 2: Preview ---

    def _build_preview_page(self):
        page = QVBoxLayout()
        w = _page_widget(page)

        # Summary
        self._preview_summary = QLabel()
        self._preview_summary.setStyleSheet(f"color: {TEXT}; font-size: 13px;")
        page.addWidget(self._preview_summary)

        # Diff badges
        self._diff_row = QHBoxLayout()
        self._diff_row.setSpacing(6)
        self._badge_added = _make_badge("+0 added", _CLR_ADDED)
        self._badge_changed = _make_badge("~0 updated", _CLR_CHANGED)
        self._badge_removed = _make_badge("-0 removed", _CLR_REMOVED)
        self._badge_same = _make_badge("0 unchanged", _CLR_SAME)
        self._diff_row.addWidget(self._badge_added)
        self._diff_row.addWidget(self._badge_changed)
        self._diff_row.addWidget(self._badge_removed)
        self._diff_row.addWidget(self._badge_same)
        self._diff_row.addStretch()
        page.addLayout(self._diff_row)

        # Items table
        self._preview_tree = QTreeWidget()
        self._preview_tree.setHeaderLabels(["Status", "Name", "Qty", "Container"])
        self._preview_tree.setRootIsDecorated(False)
        self._preview_tree.setAlternatingRowColors(True)
        self._preview_tree.setStyleSheet(f"""
            QTreeWidget {{
                background-color: {PRIMARY};
                alternate-background-color: {TABLE_ROW_ALT};
                border: 1px solid {BORDER};
                border-radius: 4px;
            }}
            QTreeWidget::item {{
                padding: 1px 4px;
                min-height: 22px;
            }}
        """)
        hdr = self._preview_tree.header()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        page.addWidget(self._preview_tree, 1)

        # Unresolved section
        self._unresolved_label = QLabel()
        self._unresolved_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px;")
        self._unresolved_label.hide()
        page.addWidget(self._unresolved_label)

        # Import error
        self._import_error = QLabel()
        self._import_error.setStyleSheet(f"color: {ERROR}; font-size: 12px;")
        self._import_error.setWordWrap(True)
        self._import_error.hide()
        page.addWidget(self._import_error)

        # Button row
        btn_row = QHBoxLayout()
        back_btn = QPushButton("Back")
        back_btn.clicked.connect(self._go_back_to_paste)
        btn_row.addWidget(back_btn)
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        self._import_btn = QPushButton("Import")
        self._import_btn.setObjectName("accentButton")
        self._import_btn.clicked.connect(self._on_import)
        btn_row.addWidget(self._import_btn)
        page.addLayout(btn_row)

        self._stack.addWidget(w)

    # --- Step 3: Done ---

    def _build_done_page(self):
        page = QVBoxLayout()
        w = _page_widget(page)

        self._done_label = QLabel()
        self._done_label.setStyleSheet(f"color: {TEXT}; font-size: 14px;")
        self._done_label.setWordWrap(True)
        self._done_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        page.addWidget(self._done_label, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setObjectName("accentButton")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        page.addLayout(btn_row)

        self._stack.addWidget(w)

    # ------------------------------------------------------------------
    # Input mode
    # ------------------------------------------------------------------

    def _set_input_mode(self, mode: str):
        if mode == 'text':
            self._text_input.show()
            self._file_widget.hide()
            self._btn_paste.setStyleSheet(_active_btn_css())
            self._btn_file.setStyleSheet(_inactive_btn_css())
        else:
            self._text_input.hide()
            self._file_widget.show()
            self._btn_paste.setStyleSheet(_inactive_btn_css())
            self._btn_file.setStyleSheet(_active_btn_css())

    def _toggle_help(self):
        self._help_label.setVisible(not self._help_label.isVisible())

    def _pick_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Inventory File", "",
            "Inventory Files (*.tsv *.json *.txt);;All Files (*)",
        )
        if path:
            self._file_label.setText(path)
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    self._text_input.setPlainText(f.read())
            except Exception as e:
                self._show_parse_error(f"Failed to read file: {e}")

    # ------------------------------------------------------------------
    # Parse
    # ------------------------------------------------------------------

    def _on_parse(self):
        self._parse_error.hide()
        text = self._text_input.toPlainText().strip()
        if not text:
            self._show_parse_error("Please paste or load some data.")
            return

        raw_data = None

        # Try TSV first
        tsv = _detect_and_parse_tsv(text)
        if tsv:
            raw_data = tsv
        else:
            # Try JSON
            try:
                data = json.loads(text)
                if isinstance(data, dict):
                    for key in ('items', 'inventory', 'Items', 'Inventory'):
                        if isinstance(data.get(key), list):
                            data = data[key]
                            break
                    else:
                        self._show_parse_error(
                            'JSON must be an array or an object with an "items" array.'
                        )
                        return
                if not isinstance(data, list) or len(data) == 0:
                    self._show_parse_error("No items found in the pasted data.")
                    return
                raw_data = data
            except json.JSONDecodeError as e:
                self._show_parse_error(f"Could not parse input: {e}")
                return

        # Process items
        resolved, unresolved, error = _process_items(raw_data, self._slim_items)
        if error:
            self._show_parse_error(error)
            return

        if not resolved and not unresolved:
            self._show_parse_error("No valid items found after parsing.")
            return

        self._parsed = resolved
        self._unresolved = unresolved

        # Compute diff
        self._diff = _compute_diff(resolved, unresolved, self._current_items)
        self._show_preview()

    def _show_parse_error(self, msg: str):
        self._parse_error.setText(msg)
        self._parse_error.show()

    # ------------------------------------------------------------------
    # Preview
    # ------------------------------------------------------------------

    def _show_preview(self):
        total = len(self._parsed) + len(self._unresolved)
        self._preview_summary.setText(f"{total:,} items parsed")

        d = self._diff
        self._badge_added.setText(f"+{d['added']} added")
        self._badge_changed.setText(f"~{d['changed']} updated")
        self._badge_removed.setText(f"-{d['removed']} removed")
        self._badge_same.setText(f"{d['unchanged']} unchanged")

        # Populate preview tree
        self._preview_tree.clear()
        status_colors = {
            'new': QColor(_CLR_ADDED),
            'changed': QColor(_CLR_CHANGED),
            'same': QColor(TEXT_MUTED),
        }
        status_labels = {'new': 'New', 'changed': 'Changed', 'same': 'Same'}

        for item in self._parsed + self._unresolved:
            status = item.get('_status', 'new')
            row = QTreeWidgetItem()
            row.setText(0, status_labels.get(status, '?'))
            row.setForeground(0, status_colors.get(status, QColor(TEXT)))
            row.setText(1, item.get('item_name', ''))
            qty_text = str(item.get('quantity', 1))
            old_qty = item.get('_old_qty')
            if old_qty is not None and status == 'changed':
                qty_text = f"{old_qty} → {item.get('quantity', 1)}"
            row.setText(2, qty_text)
            row.setText(3, item.get('container') or item.get('container_path') or '')
            # Mark unresolved items
            if item.get('item_id', 0) == 0:
                row.setForeground(1, QColor(_CLR_CHANGED))
                row.setToolTip(1, "Unresolved — item not found in database")
            self._preview_tree.addTopLevelItem(row)

        if self._unresolved:
            self._unresolved_label.setText(
                f"{len(self._unresolved)} unresolved items (not found in database)"
            )
            self._unresolved_label.show()
        else:
            self._unresolved_label.hide()

        self._import_error.hide()
        self._stack.setCurrentIndex(1)

    def _go_back_to_paste(self):
        self._stack.setCurrentIndex(0)

    # ------------------------------------------------------------------
    # Import
    # ------------------------------------------------------------------

    def _on_import(self):
        self._import_btn.setEnabled(False)
        self._import_btn.setText("Importing...")
        self._import_error.hide()

        all_items = self._parsed + self._unresolved
        self._worker = _ImportWorker(self._nc, all_items)
        self._worker.finished.connect(self._on_import_finished)
        self._worker.start()

    def _on_import_finished(self, result: dict | None, error: str):
        self._worker = None
        self._import_btn.setEnabled(True)
        self._import_btn.setText("Import")

        if error or result is None:
            self._import_error.setText(error or "Import failed.")
            self._import_error.show()
            return

        # Show done page
        added = result.get('added', 0)
        updated = result.get('updated', 0)
        removed = result.get('removed', 0)
        total = result.get('total', 0)
        self._done_label.setText(
            f"Import complete!\n\n"
            f"{total:,} items total\n"
            f"+{added} added   ~{updated} updated   -{removed} removed"
        )
        self._stack.setCurrentIndex(2)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def closeEvent(self, event):
        if self._worker and self._worker.isRunning():
            self._worker.quit()
            self._worker.wait(2000)
        super().closeEvent(event)


# ---------------------------------------------------------------------------
# Style helpers
# ---------------------------------------------------------------------------

def _page_widget(layout) -> QLabel:
    """Create a QWidget wrapper for a layout to use in QStackedWidget."""
    from PyQt6.QtWidgets import QWidget
    w = QWidget()
    w.setLayout(layout)
    return w


def _active_btn_css() -> str:
    return f"""
        QPushButton {{
            background-color: {ACCENT}; color: #1a1a1a;
            border: 1px solid {ACCENT}; padding: 4px 12px;
            font-size: 12px; font-weight: bold; min-height: 18px;
        }}
    """


def _inactive_btn_css() -> str:
    return f"""
        QPushButton {{
            background-color: {SECONDARY}; color: {TEXT_MUTED};
            border: 1px solid {BORDER}; padding: 4px 12px;
            font-size: 12px; min-height: 18px;
        }}
        QPushButton:hover {{
            background-color: {HOVER}; color: {TEXT};
        }}
    """


def _make_badge(text: str, color: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"color: {color}; font-size: 12px; font-weight: 600;"
        f" background: transparent; padding: 2px 6px;"
    )
    return lbl
