from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
	QDoubleSpinBox,
	QHBoxLayout,
	QLabel,
	QLineEdit,
	QPushButton,
	QVBoxLayout,
	QWidget,
)

from ui.widget import clear_layout, create_vline
from utils.lang import lang


class SettingsPanel(QWidget):
	addTankRequested = Signal()
	saveRequested = Signal()
	tankNameChanged = Signal(int, str)
	tankLengthChanged = Signal(int, float)
	tankColorRequested = Signal(int)
	tankMoveRequested = Signal(int, int)
	tankRemoveRequested = Signal(int)

	def __init__(self):
		super().__init__()
		self.speed_presets_edits = []
		self.tank_rows = []
		self._build_ui()

	def _build_ui(self):
		layout = QVBoxLayout(self)

		preset_row = QHBoxLayout()
		preset_row.addWidget(QLabel(lang.tr("speed_presets")))
		preset_row.addWidget(create_vline(False, 10))

		for _ in range(4):
			spin = QDoubleSpinBox()
			spin.setMaximum(30)
			spin.setSuffix(" ft/min")
			spin.setMaximumWidth(120)
			self.speed_presets_edits.append(spin)
			preset_row.addWidget(spin)

		preset_row.addStretch()
		layout.addLayout(preset_row)

		self.tank_container = QVBoxLayout()
		layout.addLayout(self.tank_container)

		buttons_add = QHBoxLayout()
		btn_add = QPushButton(lang.tr("add_tank"))
		btn_add.clicked.connect(self.addTankRequested)
		buttons_add.addWidget(btn_add)
		buttons_add.addStretch()

		buttons_save = QHBoxLayout()
		btn_save = QPushButton(lang.tr("Save"))
		btn_save.clicked.connect(self.saveRequested)
		buttons_save.addWidget(btn_save)

		layout.addLayout(buttons_add)
		layout.addLayout(buttons_save)

	def set_speed_presets(self, presets):
		for spin in self.speed_presets_edits:
			spin.setValue(0)

		for spin, value in zip(self.speed_presets_edits, presets):
			spin.setValue(value)

	def speed_presets(self):
		return [
			spin.value()
			for spin in self.speed_presets_edits
			if spin.value() > 0
		]

	def set_tanks(self, tanks):
		clear_layout(self.tank_container)
		self.tank_rows = []

		for index, tank in enumerate(tanks):
			row_widget = QWidget()
			row = QHBoxLayout(row_widget)

			name = QLineEdit(tank.name)
			name.textChanged.connect(
				lambda text, i=index: self.tankNameChanged.emit(i, text)
			)

			length = QDoubleSpinBox()
			length.setMaximum(1000)
			length.setValue(tank.length)
			length.valueChanged.connect(
				lambda value, i=index: self.tankLengthChanged.emit(i, value)
			)

			color_btn = QPushButton()
			color_btn.setFixedWidth(50)
			color_btn.setStyleSheet(f"background:{tank.color};")
			color_btn.clicked.connect(
				lambda _, i=index: self.tankColorRequested.emit(i)
			)

			btn_up = QPushButton("▲")
			btn_up.clicked.connect(
				lambda _, i=index: self.tankMoveRequested.emit(i, -1)
			)

			btn_down = QPushButton("▼")
			btn_down.clicked.connect(
				lambda _, i=index: self.tankMoveRequested.emit(i, 1)
			)

			btn_delete = QPushButton("✖")
			btn_delete.clicked.connect(
				lambda _, i=index: self.tankRemoveRequested.emit(i)
			)

			row.addWidget(name, 3)
			row.addWidget(length, 1)
			row.addWidget(color_btn)
			row.addWidget(btn_up)
			row.addWidget(btn_down)
			row.addWidget(btn_delete)

			self.tank_rows.append(row_widget)
			self.tank_container.addWidget(row_widget)
