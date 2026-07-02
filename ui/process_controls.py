from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QGuiApplication, QFont
from PySide6.QtWidgets import (
	QButtonGroup,
	QDoubleSpinBox,
	QHBoxLayout,
	QLabel,
	QLineEdit,
	QPushButton,
	QRadioButton,
	QToolButton,
	QVBoxLayout,
	QWidget,
)

from ui.widget import clear_layout, create_vline
from utils.lang import lang

FT_TO_M = 0.3048


class ProcessControls(QWidget):
	resetRequested = Signal()
	printQueueRequested = Signal()
	addFilmRequested = Signal(bool)
	addFilmPresetRequested = Signal(float)
	addSeparatorRequested = Signal()
	moveRibbonRequested = Signal(int)
	startPauseRequested = Signal()

	def __init__(self):
		super().__init__()
		self.display_feet = False
		self._build_ui()

	def _build_ui(self):
		layout = QVBoxLayout(self)
		layout.setContentsMargins(0, 0, 0, 0)

		layout.addLayout(self._build_speed_toolbar())
		layout.addLayout(self._build_film_toolbar())
		layout.addLayout(self._build_transport_bar())

	def _build_speed_toolbar(self):
		params = QHBoxLayout()

		speedparams = QHBoxLayout()
		speedparams.setAlignment(Qt.AlignmentFlag.AlignLeft)

		self.speed = QDoubleSpinBox()
		self.speed.setMaximum(10000)
		self.speed.setSuffix(" ft/min")
		self.speed.setMaximumWidth(120)

		speedparams.addWidget(QLabel(lang.tr("Speed")))
		speedparams.addWidget(self.speed)
		speedparams.addWidget(create_vline(False, 10))

		self.speed_preset_layout = QHBoxLayout()
		speedparams.addLayout(self.speed_preset_layout)

		resetparams = QHBoxLayout()
		resetparams.setAlignment(Qt.AlignmentFlag.AlignRight)

		reset_button = QPushButton(lang.tr("reset"))
		reset_button.clicked.connect(self.resetRequested)
		reset_button.setToolTip(lang.tr("tooltip_reset"))
		resetparams.addWidget(reset_button)
		resetparams.addWidget(create_vline(False, 10))

		print_button = QPushButton(lang.tr("print_queue"))
		print_button.clicked.connect(self.printQueueRequested)
		print_button.setToolTip(lang.tr("tooltip_print"))
		resetparams.addWidget(print_button)

		params.addLayout(speedparams)
		params.addLayout(resetparams)
		return params

	def _build_film_toolbar(self):
		filmparams = QHBoxLayout()

		self.film_name = QLineEdit()
		filmparams.addWidget(QLabel(lang.tr("name")))
		filmparams.addWidget(self.film_name)

		filmparams.addWidget(create_vline())

		self.add100ft_button = QPushButton("30m")
		self.add100ft_button.clicked.connect(
			lambda: self.addFilmPresetRequested.emit(30.48)
		)
		self.add100ft_button.setToolTip(lang.tr("tooltip_add100ft"))
		filmparams.addWidget(self.add100ft_button)

		self.add400ft_button = QPushButton("122m")
		self.add400ft_button.clicked.connect(
			lambda: self.addFilmPresetRequested.emit(121.92)
		)
		self.add400ft_button.setToolTip(lang.tr("tooltip_add400ft"))
		filmparams.addWidget(self.add400ft_button)

		filmparams.addWidget(create_vline(False, 10))

		self.film_length = QDoubleSpinBox()
		self.film_length.setMaximum(10000)
		self.film_length.setSuffix(" m")
		filmparams.addWidget(QLabel(lang.tr("film")))
		filmparams.addWidget(self.film_length)

		self.leader_length = QDoubleSpinBox()
		self.leader_length.setMaximum(1000)
		self.leader_length.setSuffix(" m")
		self.leader_length.setValue(3)
		filmparams.addWidget(QLabel(lang.tr("leader")))
		filmparams.addWidget(self.leader_length)

		filmparams.addWidget(create_vline(False, 10))

		self.unit_group = QButtonGroup(self)
		self.radio_m = QRadioButton("m")
		self.radio_ft = QRadioButton("ft")
		self.radio_m.setChecked(True)
		self.unit_group.addButton(self.radio_m)
		self.unit_group.addButton(self.radio_ft)
		filmparams.addWidget(self.radio_m)
		filmparams.addWidget(self.radio_ft)
		self.radio_m.toggled.connect(self.update_units)

		filmparams.addWidget(create_vline())

		button_font = self.font()
		button_font.setBold(True)

		add_button = QPushButton(lang.tr("add_to_queue"))
		add_button.clicked.connect(lambda: self.addFilmRequested.emit(False))
		add_button.setFont(button_font)
		add_button.setToolTip(lang.tr("tooltip_addfilm"))
		filmparams.addWidget(add_button)

		attach_button = QPushButton(lang.tr("attach_to_film"))
		attach_button.clicked.connect(lambda: self.addFilmRequested.emit(True))
		attach_button.setFont(button_font)
		attach_button.setToolTip(lang.tr("tooltip_attachtofilm"))
		filmparams.addWidget(attach_button)

		filmparams.addWidget(create_vline())

		separator_button = QPushButton(lang.tr("add_separator"))
		separator_button.clicked.connect(self.addSeparatorRequested)
		separator_button.setFont(button_font)
		separator_button.setToolTip(lang.tr("tooltip_addmarker"))
		filmparams.addWidget(separator_button)

		return filmparams

	def _build_transport_bar(self):
		btnsPlay = QHBoxLayout()
		arialfont = QFont("Segoe UI Symbol")

		self.move_left_btn = QPushButton("<< -1m")
		self.move_left_btn.clicked.connect(
			lambda: self.moveRibbonRequested.emit(-1)
		)
		self.move_left_btn.setFont(arialfont)
		self.move_left_btn.setToolTip(lang.tr("tooltip_move_left"))
		btnsPlay.addWidget(self.move_left_btn)

		self.start_pause_btn = QPushButton(lang.tr("start"))
		self.start_pause_btn.clicked.connect(self.startPauseRequested)
		self.start_pause_btn.setToolTip(lang.tr("tooltip_start_pause"))
		btnsPlay.addWidget(self.start_pause_btn)

		self.move_right_btn = QPushButton("+1m >>")
		self.move_right_btn.clicked.connect(
			lambda: self.moveRibbonRequested.emit(1)
		)
		self.move_right_btn.setToolTip(lang.tr("tooltip_move_right"))
		btnsPlay.addWidget(self.move_right_btn)

		font = self.start_pause_btn.font()
		font.setBold(True)
		self.start_pause_btn.setStyleSheet("background-color: #344B34;")
		self.move_left_btn.setFont(font)
		self.start_pause_btn.setFont(font)
		self.move_right_btn.setFont(font)
		return btnsPlay

	def set_speed_presets(self, presets):
		clear_layout(self.speed_preset_layout)

		for speed in presets:
			btn = QToolButton(self)
			btn.setText(f"{speed:g}")
			btn.setMaximumWidth(60)
			btn.clicked.connect(lambda _, s=speed: self.speed.setValue(s))
			self.speed_preset_layout.addWidget(btn)

	def set_runtime_values(self, speed, film_length, leader_length):
		self.speed.setValue(speed)
		self.film_length.setValue(film_length)
		self.leader_length.setValue(leader_length)

	def set_simulation_running(self, running):
		if running:
			self.start_pause_btn.setStyleSheet("background-color: #661D1D;")
			self.start_pause_btn.setText(lang.tr("pause"))
		else:
			self.start_pause_btn.setStyleSheet("background-color: #344B34;")
			self.start_pause_btn.setText(lang.tr("start"))

	def update_shift_step_labels(self, shift_pressed):
		step = 10 if shift_pressed else 1
		self.move_left_btn.setText(f"<< -{step}m")
		self.move_right_btn.setText(f"+{step}m >>")

	def is_film_input(self, widget):
		return widget in (
			self.film_name,
			self.film_length,
			self.leader_length,
		)

	def speed_value(self):
		return self.speed.value()

	def film_name_value(self):
		return self.film_name.text()

	def film_length_value(self):
		return self.film_length.value()

	def leader_length_value(self):
		return self.leader_length.value()

	def film_length_meters(self):
		return self.ui_to_meters(self.film_length.value())

	def leader_length_meters(self):
		return self.ui_to_meters(self.leader_length.value())

	def ui_to_meters(self, value):
		return value * FT_TO_M if self.display_feet else value

	def update_units(self):
		old_film = self.film_length.value()
		old_leader = self.leader_length.value()

		self.display_feet = self.radio_ft.isChecked()
		if self.display_feet:
			self.film_length.setValue(old_film / FT_TO_M)
			self.leader_length.setValue(old_leader / FT_TO_M)
			self.add100ft_button.setText("100ft")
			self.add400ft_button.setText("400ft")
		else:
			self.film_length.setValue(old_film * FT_TO_M)
			self.leader_length.setValue(old_leader * FT_TO_M)
			self.add100ft_button.setText("30,5m")
			self.add400ft_button.setText("122m")

		self.refresh_unit_display()

	def refresh_unit_display(self):
		if self.display_feet:
			self.film_length.setSuffix(" ft")
			self.leader_length.setSuffix(" ft")
		else:
			self.film_length.setSuffix(" m")
			self.leader_length.setSuffix(" m")

	def current_move_step(self):
		return 10.0 if (
			QGuiApplication.keyboardModifiers() & Qt.KeyboardModifier.ShiftModifier
		) else 1.0
