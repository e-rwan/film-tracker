from PySide6.QtCore import Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget

from ui.segment_editor import SegmentEditor


class InfoPanel(QWidget):
	segmentSelected = Signal(object)
	moveUpRequested = Signal()
	moveDownRequested = Signal()
	deleteRequested = Signal()
	applyRequested = Signal(str, float)

	def __init__(self):
		super().__init__()
		self.editor = SegmentEditor()
		self._build_ui()
		self._connect_signals()

	def _build_ui(self):
		layout = QVBoxLayout(self)
		layout.setContentsMargins(0, 0, 0, 0)
		layout.addWidget(self.editor)

	def _connect_signals(self):
		self.editor.segmentSelected.connect(self.segmentSelected)
		self.editor.moveUpRequested.connect(self.moveUpRequested)
		self.editor.moveDownRequested.connect(self.moveDownRequested)
		self.editor.deleteRequested.connect(self.deleteRequested)
		self.editor.applyRequested.connect(self.applyRequested)

	def populate(self, rows):
		self.editor.populate(rows)

	def show_segment(self, segment):
		self.editor.select_segment(segment.id)
		self.editor.load_segment(segment)

	def clear_selection(self):
		self.editor.set_segment_enabled(False)

	def set_selected_segment(self, segment_id):
		self.editor.select_segment(segment_id)

	def is_table_focus(self, widget):
		return widget is not None and self.editor.tables_widget.isAncestorOf(widget)

	def is_editor_input(self, widget):
		return widget in (
			self.editor.name_edit,
			self.editor.length_spin,
		)

	@property
	def name_edit(self):
		return self.editor.name_edit

	@property
	def length_spin(self):
		return self.editor.length_spin
