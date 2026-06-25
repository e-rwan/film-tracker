# ui/segment_editor.py

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
	QWidget,
	QVBoxLayout,
	QHBoxLayout,
	QPushButton,
	QLineEdit,
	QDoubleSpinBox,
	QTableWidget,
	QTableWidgetItem,
	QLabel,
	QAbstractItemView,
	QGroupBox,
	QHeaderView
)

from utils.lang import lang
from ui.widget import create_vline

ZONE_QUEUE = "queue"
ZONE_PROCESSING = "processing"
ZONE_RECEIVING = "receiving"

class SegmentEditor(QWidget):

	segmentSelected = Signal(object)

	moveUpRequested = Signal()
	moveDownRequested = Signal()

	deleteRequested = Signal()

	applyRequested = Signal(
		str,
		float
	)

	def __init__(self):
		super().__init__()

		self.build_ui()

	def build_ui(self):

		layout = QVBoxLayout(self)

		## Toolbar
		toolbar = QHBoxLayout()

		self.btn_up = QPushButton("▲")
		self.btn_down = QPushButton("▼")

		toolbar.addWidget(self.btn_up)
		toolbar.addWidget(self.btn_down)

		toolbar.addWidget(create_vline())

		toolbar.addWidget(
			QLabel(lang.tr("name"))
		)

		self.name_edit = QLineEdit()

		toolbar.addWidget(
			self.name_edit
		)

		toolbar.addWidget(create_vline())

		toolbar.addWidget(
			QLabel(lang.tr("length"))
		)

		self.length_spin = QDoubleSpinBox()
		self.length_spin.setMaximum(100000)

		toolbar.addWidget(
			self.length_spin
		)

		toolbar.addWidget(create_vline())

		self.btn_apply = QPushButton(
			lang.tr("apply")
		)

		self.btn_delete = QPushButton(
			lang.tr("delete")
		)

		toolbar.addWidget(
			self.btn_apply
		)

		toolbar.addWidget(
			self.btn_delete
		)

		toolbar.addStretch()

		layout.addLayout(
			toolbar
		)

		## Tables
		self.queue_table, queue_group = (
			self.create_table_group(lang.tr(ZONE_QUEUE))
		)

		self.processing_table, processing_group = (
			self.create_table_group(lang.tr(ZONE_PROCESSING))
		)

		self.receiving_table, receiving_group = (
			self.create_table_group(lang.tr(ZONE_RECEIVING))
		)

		self.tables = [
			self.queue_table,
			self.processing_table,
			self.receiving_table
		]

		tables_layout = QHBoxLayout()
		tables_layout.setSpacing(0)

		tables_layout.addWidget(queue_group, 1)
		tables_layout.addWidget(processing_group, 1)
		tables_layout.addWidget(receiving_group, 1)

		layout.addLayout(
			tables_layout
		)

		# Disabled by default
		self.set_segment_enabled(False)

		# Signals
		self.btn_up.clicked.connect(
			self.moveUpRequested
		)

		self.btn_down.clicked.connect(
			self.moveDownRequested
		)

		self.btn_delete.clicked.connect(
			self.deleteRequested
		)

		self.btn_apply.clicked.connect(
			self._emit_apply
		)

	def _emit_apply(self):

		self.applyRequested.emit(
			self.name_edit.text(),
			self.length_spin.value()
		)

	def create_table_group(self, title):

		table = QTableWidget()

		table.setSelectionBehavior(
			QAbstractItemView.SelectionBehavior.SelectRows
		)

		table.setEditTriggers(
			QAbstractItemView.EditTrigger.NoEditTriggers
		)

		table.setSelectionMode(
			QAbstractItemView.SelectionMode.SingleSelection
		)

		table.setColumnCount(4)

		table.setHorizontalHeaderLabels(
			[
				lang.tr("name"),
				lang.tr("type"),
				lang.tr("total"),
				lang.tr("eta")
			]
		)

		table.horizontalHeader().setSectionResizeMode(
			QHeaderView.ResizeMode.Stretch
		)
		table.verticalHeader().hide()
		table.verticalHeader().setDefaultSectionSize(
			22
		)

		table.setStyleSheet("""
			QTableView::item {
				padding: 1px 5px;
			}
			QTableView::item:selected {
				background-color: lightgray;
				color: black;
				font-weight: bold;
			}
			QTableView::item:selected:active {
				background-color: lightgray;
				color: black;
				font-weight: bold;
			}

			QTableView::item:selected:!active {
				background-color: lightgray;
				color: black;
				font-weight: bold;
			}
		""")

		header = table.horizontalHeader()
		header.setSectionResizeMode(
			0,
			QHeaderView.ResizeMode.Stretch
		)
		header.setSectionResizeMode(
			1,
			QHeaderView.ResizeMode.ResizeToContents
		)
		header.setSectionResizeMode(
			2,
			QHeaderView.ResizeMode.ResizeToContents
		)
		header.setSectionResizeMode(
			3,
			QHeaderView.ResizeMode.ResizeToContents
		)

		table.itemSelectionChanged.connect(
			lambda t=table:
			self._selection_changed(t)
		)

		group = QGroupBox(title)

		group_layout = QVBoxLayout(group)
		group_layout.setContentsMargins(0, 0, 0, 0)

		group_layout.addWidget(table)

		return table, group

	def populate(self, rows):

		queue_rows = [
			r
			for r in rows
			if r["zone"] == ZONE_QUEUE
		]

		processing_rows = [
			r
			for r in rows
			if r["zone"] == ZONE_PROCESSING
		]

		receiving_rows = [
			r
			for r in rows
			if r["zone"] == ZONE_RECEIVING
		]

		self.populate_table(
			self.queue_table,
			queue_rows
		)

		self.populate_table(
			self.processing_table,
			processing_rows
		)

		self.populate_table(
			self.receiving_table,
			receiving_rows
		)

	def populate_table(
		self,
		table,
		rows
	):

		table.clearSpans()
		table.setRowCount(
			len(rows)
		)

		for row_index, row in enumerate(rows):

			segment = row["segment"]

			if segment.is_separator:
				values = [
					f"──── {segment.name} ────",
					"",
					"",
					""
				]
			else:
				values = [
					segment.name or "",
					segment.type,
					f"{row['visible']:.1f}m ({segment.length:.1f}m)",
					row["eta"]
				]

			for col, value in enumerate(values):

				item = QTableWidgetItem(
					str(value)
				)

				if segment.is_separator:
					font = item.font()
					font.setBold(True)
					item.setFont(font)
					item.setTextAlignment(
						int(Qt.AlignmentFlag.AlignCenter)
					)
					item.setBackground(
						QColor("#666666")
					)
					table.setSpan(
						row_index,
						0,
						1,
						4
					)

				item.setData(
					Qt.ItemDataRole.UserRole,
					segment
				)

				table.setItem(
					row_index,
					col,
					item
				)

	def set_segment_enabled(self, enabled):

		self.btn_up.setEnabled(enabled)
		self.btn_down.setEnabled(enabled)

		self.name_edit.setEnabled(enabled)

		self.length_spin.setEnabled(
			enabled
		)

		self.btn_apply.setEnabled(
			enabled
		)

		self.btn_delete.setEnabled(
			enabled
		)

	def _selection_changed(self, table):

		if table is None:
			return

		items = table.selectedItems()

		if not items:
			return

		item = table.item(
			items[0].row(),
			0
		)

		if item is None:
			return

		segment = item.data(
			Qt.ItemDataRole.UserRole
		)

		self.load_segment(segment)

		self.segmentSelected.emit(
			segment.id
		)

	def select_segment(self, segment_id):

		for table in self.tables:
			table.blockSignals(True)

		try:
			for table in self.tables:

				table.clearSelection()

				for row in range(table.rowCount()):

					item = table.item(row, 0)

					if item is None:
						continue

					row_segment = item.data(
						Qt.ItemDataRole.UserRole
					)

					if row_segment.id == segment_id:
						table.selectRow(row)
						break

		finally:
			for table in self.tables:
				table.blockSignals(False)

	def load_segment(self, segment):

		self.set_segment_enabled(True)

		if segment.is_film:
			self.name_edit.setEnabled(True)
			self.length_spin.setEnabled(True)
			self.name_edit.setText(segment.name)

		elif segment.is_separator:
			self.name_edit.setEnabled(True)
			self.length_spin.setEnabled(False)
			self.name_edit.setText(segment.name)

		else:
			self.name_edit.setEnabled(False)
			self.length_spin.setEnabled(True)
			self.name_edit.setText(
				lang.tr("leader")
			)

		self.length_spin.setValue(
			segment.length
		)
