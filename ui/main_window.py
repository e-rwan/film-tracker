# ui/main_window.py

import json
import os
import math

from datetime import datetime
from pathlib import Path
from PySide6.QtCore import QTimer, Qt, QEvent, QElapsedTimer, QUrl
from PySide6.QtGui import QGuiApplication, QColor, QFont, QTextDocument, QDesktopServices, QPen
from PySide6.QtWidgets import (
	QApplication,
	QDoubleSpinBox,
	QAbstractSpinBox,
	QHBoxLayout,
	QLabel,
	QLineEdit,
	QPushButton,
	QToolButton,
	QSizePolicy,
	QTabWidget,
	QVBoxLayout,
	QWidget,
	QColorDialog,
	QSplitter,
	QInputDialog,
    QRadioButton,
    QButtonGroup
)
from PySide6.QtPrintSupport import (
    QPrinter,
)

from utils.constants import SETTINGS_FILE
from model.ribbon_model import RibbonModel
from model.tank import Tank
from ui.process_widget import ProcessWidget
from ui.segment_editor import SegmentEditor
from ui.segment_editor import ZONE_QUEUE
from ui.widget import create_vline
from utils.lang import lang

FT_TO_M = 0.3048
M_TO_FT = 1 / FT_TO_M

class MainWindow(QWidget):
	"""
	Main application window.

	Coordinates user interactions, RibbonModel updates
	and ProcessWidget rendering.
	"""

	def __init__(self):
		super().__init__()

		self.model = RibbonModel()

		self.model.tanks = []

		self.selected_segment = None
		self.selected_segment_id = None

		self.speed_presets = []

		self.received_film=0.0
		self.received_leader=0.0 

		self.timer=QTimer()
		self.timer.timeout.connect(self.tick)

		self.elapsed_timer = QElapsedTimer()
		self.elapsed_timer.start()

		self.last_time = self.elapsed_timer.elapsed()

		self.display_feet = False

		app = QApplication.instance()
		if app: app.installEventFilter(self)

		self.build_ui()
		self.load_settings()

## BUILD
	def build_ui(self):

		self.setWindowTitle(lang.tr("window_title"))

		root = QVBoxLayout(self)

		tabs = QTabWidget()
		root.addWidget(tabs)

		process_tab = QWidget()
		settings_tab = QWidget()

		tabs.addTab(process_tab, lang.tr("process"))
		tabs.addTab(settings_tab, lang.tr("settings"))

		self.build_process_tab(process_tab)
		self.build_settings_tab(settings_tab)
		
	def build_process_tab(self, tab):

		process = QVBoxLayout(tab)

		self.build_toolbar01(process)
		self.build_toolbar02(process)
		self.build_transport_bar(process)

		splitter = QSplitter(
			Qt.Orientation.Vertical
		)

		self.segment_editor = SegmentEditor()
		self.view = ProcessWidget()
		self.view.segmentClicked.connect(
			self.on_process_segment_clicked
		)
		self.connect_segment_editor()

		splitter.addWidget(
			self.segment_editor
		)

		splitter.addWidget(
			self.view
		)

		splitter.setStretchFactor(0, 3)
		splitter.setStretchFactor(1, 2)

		process.addWidget(
			splitter,
			1
		)

	## SETTINGS TAB 
	def build_settings_tab(self, tab):	

		layout = QVBoxLayout(tab)

		# speed preset
		preset_row = QHBoxLayout()
		self.speed_presets_edits = []
		preset_row.addWidget(
			QLabel(lang.tr("speed_presets"))
		)
		preset_row.addWidget(create_vline(False, 10))
		for _ in range(4):
			spin = QDoubleSpinBox()
			spin.setMaximum(30)
			spin.setSuffix(" ft/min")
			spin.setMaximumWidth(120)
			self.speed_presets_edits.append(
				spin
			)
			preset_row.addWidget(spin)
		preset_row.addStretch()
		layout.addLayout(preset_row)

		# tank list
		self.tank_container = QVBoxLayout()
		layout.addLayout(self.tank_container)

		# add tank button
		buttonsAdd = QHBoxLayout()
		btn_add = QPushButton(lang.tr("add_tank"))
		btn_add.clicked.connect(self.add_tank)
		buttonsAdd.addWidget(btn_add)
		buttonsAdd.addStretch()

		# save settings button
		buttonsSave = QHBoxLayout()
		btn_save = QPushButton(lang.tr("Save"))
		btn_save.clicked.connect(self.save_settings)
		buttonsSave.addWidget(btn_save)

		layout.addLayout(buttonsAdd)
		layout.addLayout(buttonsSave)

	def rebuild_tank_editor(self):

		while self.tank_container.count():

			item = self.tank_container.takeAt(0)

			if item is None:
				continue

			widget = item.widget()

			if widget is not None:
				widget.deleteLater()

		for index, tank in enumerate(
			self.model.tanks
		):

			self.add_tank_row(
				index,
				tank
			)

	def add_tank_row(self, index, tank):
		row_widget = QWidget()

		row = QHBoxLayout(
			row_widget
		)

		# Tank name
		name = QLineEdit(
			tank.name
		)
		name.textChanged.connect(
			lambda text, t=tank:
			setattr(t, "name", text)
		)

		# Tank length
		length = QDoubleSpinBox()
		length.setMaximum(
			1000
		)
		length.setValue(
			tank.length
		)
		length.valueChanged.connect(
			lambda value, t=tank:
			setattr(t, "length", value)
		)

		# Tank color
		color_btn = QPushButton()
		color_btn.setFixedWidth(
			50
		)
		color_btn.setStyleSheet(
			f"background:{tank.color};"
		)
		color_btn.clicked.connect(
			lambda _, t=tank:
			self.choose_tank_color(t)
		)

		# Tank position
		btn_up = QPushButton("▲")
		btn_up.clicked.connect(
			lambda _, i=index:
			self.move_tank_up(i)
		)
		btn_down = QPushButton("▼")
		btn_down.clicked.connect(
			lambda _, i=index:
			self.move_tank_down(i)
		)

		# Tank delete
		btn_delete = QPushButton("✖")
		btn_delete.clicked.connect(
			lambda _, i=index:
			self.remove_tank(i)
		)

		row.addWidget(
			name,
			3
		)
		row.addWidget(
			length,
			1
		)
		row.addWidget(
			color_btn
		)
		row.addWidget(
			btn_up
		)
		row.addWidget(
			btn_down
		)
		row.addWidget(
			btn_delete
		)

		self.tank_container.addWidget(
			row_widget
		)

	def add_tank(self):

		self.model.tanks.append(
			Tank(
				name=lang.tr("new_tank"),
				length=1.0,
				color="#808080"
			)
		)

		self.rebuild_tank_editor()

		# self.save_settings()

	def remove_tank(self, index):

		if len(self.model.tanks) <= 1:
			return

		self.model.tanks.pop(index)

		self.rebuild_tank_editor()

		# self.save_settings()

	def move_tank_up(self, index):

		if index <= 0:
			return

		self.model.tanks[index - 1], self.model.tanks[index] = (
			self.model.tanks[index],
			self.model.tanks[index - 1]
		)

		self.rebuild_tank_editor()
		# self.save_settings()
		self.refresh()

	def move_tank_down(self, index):

		if index >= len(self.model.tanks) - 1:
			return

		self.model.tanks[index + 1], self.model.tanks[index] = (
			self.model.tanks[index],
			self.model.tanks[index + 1]
		)

		self.rebuild_tank_editor()
		# self.save_settings()
		self.refresh()

	def choose_tank_color(self, tank):

		color = QColorDialog.getColor(
			QColor(tank.color),
			self,
			f"Color - {tank.name}"
		)

		if not color.isValid():
			return

		tank.color = color.name()

		self.rebuild_tank_editor()
		# self.save_settings()
		self.refresh()

	## MAIN TAB
	def build_toolbar01(self, process):
		"""
		Speed, speed presets, reset and print
		"""

		speedparams = QHBoxLayout()
		speedparams.setAlignment(
			Qt.AlignmentFlag.AlignLeft
		)

		# speed and presets
		self.speed = QDoubleSpinBox()
		self.speed.setMaximum(10000)
		self.speed.setSuffix(" ft/min")
		self.speed.setMaximumWidth(120)
		speedparams.addWidget(QLabel(lang.tr("Speed")))
		speedparams.addWidget(self.speed)

		speedparams.addWidget(create_vline(False, 10))
		
		self.speed_preset_layout = QHBoxLayout()
		speedparams.addLayout(self.speed_preset_layout)

		#reset
		resetparams = QHBoxLayout()
		resetparams.setAlignment(
			Qt.AlignmentFlag.AlignRight
		)
		b = QPushButton(lang.tr("reset"))
		b.clicked.connect(self.reset)
		resetparams.addWidget(b)
		b.setToolTip(lang.tr("tooltip_reset"))
		
		resetparams.addWidget(create_vline(False, 10))

		# print queue
		b = QPushButton(lang.tr("print_queue"))
		b.clicked.connect(self.print_queue)
		resetparams.addWidget(b)
		b.setToolTip(lang.tr("tooltip_print"))

		params = QHBoxLayout()
		params.addLayout(speedparams)
		params.addLayout(resetparams)
		process.addLayout(params)

	def build_toolbar02(self, process):
		"""
		Film and leader creation
		"""

		filmparams = QHBoxLayout()

		# film name
		self.film_name = QLineEdit()
		# self.film_name.setMaximumWidth(300)
		filmparams.addWidget(QLabel(lang.tr("name")))
		filmparams.addWidget(self.film_name)

		filmparams.addWidget(create_vline())

		# preset 30m
		self.add100ft_button = QPushButton("30m")
		self.add100ft_button.clicked.connect(
			lambda: self.add_film_preset(30.48)
		)
		filmparams.addWidget(self.add100ft_button)
		self.add100ft_button.setToolTip(lang.tr("tooltip_add100ft"))

		# preset 122m
		self.add400ft_button = QPushButton("122m")
		self.add400ft_button.clicked.connect(
			lambda: self.add_film_preset(121.92)
		)
		filmparams.addWidget(self.add400ft_button)
		self.add400ft_button.setToolTip(lang.tr("tooltip_add400ft"))

		filmparams.addWidget(create_vline(False, 10))

		# film length
		self.film_length = QDoubleSpinBox()
		self.film_length.setMaximum(10000)
		self.film_length.setSuffix(" m")
		# self.film_length.setMaximumWidth(120)
		filmparams.addWidget(QLabel(lang.tr("film")))
		filmparams.addWidget(self.film_length)

		# leader length
		self.leader_length = QDoubleSpinBox()
		self.leader_length.setMaximum(1000)
		self.leader_length.setSuffix(" m")
		self.leader_length.setValue(3)
		# self.leader_length.setMaximumWidth(120)
		filmparams.addWidget(QLabel(lang.tr("leader")))
		filmparams.addWidget(self.leader_length)

		filmparams.addWidget(create_vline(False, 10))

		# unit selector
		self.unit_group = QButtonGroup(self)
		self.radio_m = QRadioButton("m")
		self.radio_ft = QRadioButton("ft")
		self.radio_m.setChecked(True)
		self.unit_group.addButton(self.radio_m)
		self.unit_group.addButton(self.radio_ft)
		filmparams.addWidget(self.radio_m)
		filmparams.addWidget(self.radio_ft)
		self.radio_m.toggled.connect(
			self.update_units
		)

		filmparams.addWidget(create_vline())

		## buttons
		button_font = self.font()
		button_font.setBold(True)

		# add to queue
		b = QPushButton(lang.tr("add_to_queue"))
		b.clicked.connect(self.add_film)
		b.setFont(button_font)
		filmparams.addWidget(b)
		b.setToolTip(lang.tr("tooltip_addfilm"))

		# attach to film
		b = QPushButton(lang.tr("attach_to_film"))
		b.clicked.connect(lambda: self.add_film(attach = True))
		b.setFont(button_font)
		filmparams.addWidget(b)
		b.setToolTip(lang.tr("tooltip_attachtofilm"))

		filmparams.addWidget(create_vline())

		# add separator
		b = QPushButton(lang.tr("add_separator"))
		b.clicked.connect(self.add_separator)
		b.setFont(button_font)
		filmparams.addWidget(b)
		b.setToolTip(lang.tr("tooltip_addmarker"))

		# filmparams.addStretch()
		process.addLayout(filmparams)

	def build_transport_bar(self, process):

		btnsPlay = QHBoxLayout()
		arialfont = QFont("Segoe UI Symbol")

		self.move_left_btn = QPushButton("<< -1m")
		self.move_left_btn.clicked.connect(
			lambda: self.move_ribbon(-1)
		)
		self.move_left_btn.setFont(arialfont)

		btnsPlay.addWidget(self.move_left_btn)

		self.move_left_btn.setToolTip(
			lang.tr("tooltip_move_left")
		)

		self.start_pause_btn = QPushButton(lang.tr("start"))

		self.start_pause_btn.clicked.connect(
			self.toggle_simulation
		)

		btnsPlay.addWidget(self.start_pause_btn)

		self.start_pause_btn.setToolTip(
			lang.tr("tooltip_start_pause")
		)

		self.move_right_btn = QPushButton("+1m >>")

		self.move_right_btn.clicked.connect(
			lambda: self.move_ribbon(1)
		)

		btnsPlay.addWidget(self.move_right_btn)

		self.move_right_btn.setToolTip(
			lang.tr("tooltip_move_right")
		)

		font = self.start_pause_btn.font()
		self.start_pause_btn.setStyleSheet(
			"background-color: #344B34;"
		)
		font.setBold(True)

		self.move_left_btn.setFont(font)
		self.start_pause_btn.setFont(font)
		self.move_right_btn.setFont(font)

		process.addLayout(btnsPlay)

	def build_info_panels(self, process):

		self.segment_editor = SegmentEditor()

		process.addWidget(
			self.segment_editor
		)

		self.segment_editor.segmentSelected.connect(
			self.on_segment_selected
		)

		self.segment_editor.deleteRequested.connect(
			self.delete_selected_segment
		)

		self.segment_editor.moveUpRequested.connect(
			lambda: self.move_selected_segment(+1)
		)

		self.segment_editor.moveDownRequested.connect(
			lambda: self.move_selected_segment(-1)
		)

		self.segment_editor.applyRequested.connect(
			self.apply_selected_segment
		)

	def build_process_view(self, process):

		self.view = ProcessWidget()

		self.view.setSizePolicy(
			QSizePolicy.Policy.Expanding,
			QSizePolicy.Policy.Expanding
		)

		process.addWidget(
			self.view,
			1
		)

	def rebuild_speed_presets(self):

		while self.speed_preset_layout.count():

			item = self.speed_preset_layout.takeAt(0)

			if item is None: continue
			widget = item.widget()
			if widget is None: continue
			widget.deleteLater()

		for speed in self.speed_presets:

			btn = QToolButton(self)
			btn.setText(
				f"{speed:g}"
			)

			btn.setMaximumWidth(60)

			btn.clicked.connect(
				lambda _, s=speed:
				self.speed.setValue(s)
			)

			self.speed_preset_layout.addWidget(
				btn
			)

	def eventFilter(self, obj, event):

		if event.type() == QEvent.Type.KeyPress:

			if self.handle_shortcuts(event):
				return True

			if event.key() == Qt.Key.Key_Shift:
				self.move_left_btn.setText("<< -10m")
				self.move_right_btn.setText("+10m >>")

		elif event.type() == QEvent.Type.KeyRelease:

			if event.key() == Qt.Key.Key_Shift:
				self.move_left_btn.setText("<< -1m")
				self.move_right_btn.setText("+1m >>")

		return False

	def handle_shortcuts(self, event):

		focus = QApplication.focusWidget()

		key = event.key()
		mod = event.modifiers()

		editing = isinstance(
			focus,
			(QLineEdit, QAbstractSpinBox)
		)

		in_tables = (
			focus is not None
			and self.segment_editor.tables_widget.isAncestorOf(focus)
		)

		# ------------------------------------------------------------------
		# Space = Start / Pause
		# ------------------------------------------------------------------

		if (
			key == Qt.Key.Key_Space
			and not editing
		):
			self.toggle_simulation()
			return True

		# ------------------------------------------------------------------
		# Ctrl + P
		# ------------------------------------------------------------------

		if (
			key == Qt.Key.Key_P
			and mod & Qt.KeyboardModifier.ControlModifier
		):
			self.print_queue()
			return True

		# ------------------------------------------------------------------
		# ← / →
		# ------------------------------------------------------------------

		if (
			mod & Qt.KeyboardModifier.ControlModifier
			and not editing
			):
			if key == Qt.Key.Key_Left:
				self.move_ribbon(-1)
				return True

			if key == Qt.Key.Key_Right:
				self.move_ribbon(+1)
				return True

		# ------------------------------------------------------------------
		# ↑ / ↓ = Move selected segment
		# ------------------------------------------------------------------

		if mod & Qt.KeyboardModifier.ControlModifier:
			if (
				key in (Qt.Key.Key_Up, Qt.Key.Key_Down)
				and self.selected_segment_id is not None
				and not editing
			):
				if key == Qt.Key.Key_Up:
					self.move_selected_segment(-1)
				else:
					self.move_selected_segment(+1)

				return True

		# ------------------------------------------------------------------
		# Enter = Add film
		# ------------------------------------------------------------------

		if key in (
			Qt.Key.Key_Return,
			Qt.Key.Key_Enter
		):

			if focus in (
				self.film_name,
				self.film_length,
				self.leader_length
			):
				self.add_film()
				return True

			if focus in (
				self.segment_editor.name_edit,
				self.segment_editor.length_spin
			):
				self.apply_selected_segment(
					self.segment_editor.name_edit.text(),
					self.segment_editor.length_spin.value()
				)
				return True

		# ------------------------------------------------------------------
		# Delete = Delete selected segment
		# ------------------------------------------------------------------

		if (
			key == Qt.Key.Key_Delete
			and self.selected_segment_id is not None
			and not editing
		):
			self.delete_selected_segment()
			return True

		return False

	def add_film_preset(self, length):

		if (length <= 0):
			return

		self.model.add_film(
			length,
			0,
			self.film_name.text()
		)

		self.refresh()

	def update_units(self):

		old_film = self.film_length.value()
		old_leader = self.leader_length.value()

		self.display_feet = (
			self.radio_ft.isChecked()
		)
		if self.display_feet:
			self.film_length.setValue(
				old_film / FT_TO_M
			)
			self.leader_length.setValue(
				old_leader / FT_TO_M
			)
			self.add100ft_button.setText("100ft")
			self.add400ft_button.setText("400ft")

		else:
			self.film_length.setValue(
				old_film * FT_TO_M
			)
			self.leader_length.setValue(
				old_leader * FT_TO_M
			)
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

	def ui_to_meters(self, value):
		return (
			value * FT_TO_M
			if self.display_feet
			else value
		)

	def meters_to_ui(self, value):
		return (
			value / FT_TO_M
			if self.display_feet
			else value
		)

## SEGMENTS
	def on_segment_selected(self, segment_id):

		self.selected_segment_id = segment_id

		self.view.set_selected_segment(
			segment_id
		)

	def build_segment_rows(
		self,
		zone_start,
		zone_end,
		zone_name,
		speed_ft_min=None
	):

		rows = []

		for seg, seg_start, seg_end in self.model.iter_segments():

			visible = max(
				0,
				min(seg_end, zone_end)
				- max(seg_start, zone_start)
			)

			if (visible <= 0):
				continue

			eta = ""
			eta_in = ""

			if (
				speed_ft_min
				and seg.is_film
			):
				eta = self.model.get_remaining_time(
					seg_end,
					self.model.processed_length - self.machine_length(),
					speed_ft_min
				)
				eta_in = self.model.get_remaining_time(
					seg_end,
					self.model.processed_length,
					speed_ft_min
				)

			row = {
				"zone": zone_name,
				"segment": seg,
				"visible": visible,
			}

			if zone_name == ZONE_QUEUE:
				row["OUT"] = f"{eta_in} ({eta})"
			else:
				row["OUT"] = eta

			rows.append(row)



		return rows

	def delete_selected_segment(self):

		segment = self.get_selected_segment()

		if self.selected_segment_id is None or segment is None:
			return

		if segment not in self.model.segments:
			return

		index = next(
			i
			for i, s in enumerate(self.model.segments)
			if s is segment
		)

		del self.model.segments[index]

		if self.model.segments:
			index = min(
				index,
				len(self.model.segments) - 1
			)
			self.selected_segment_id = (
				self.model.segments[index].id
			)

		else:
			self.selected_segment_id = None

		self.refresh()

		segment = self.get_selected_segment()

		if segment is not None:
			self.segment_editor.select_segment(segment.id)
			self.segment_editor.load_segment(segment)
			self.view.set_selected_segment(segment.id)
		else:
			self.segment_editor.set_segment_enabled(False)

	def move_selected_segment(self, offset):

		segment = self.get_selected_segment()

		if segment is None:
			return

		index = next(
			i
			for i, s in enumerate(self.model.segments)
			if s is segment
		)

		new_index = index + offset

		if (
			new_index < 0
			or new_index >= len(self.model.segments)
		):
			return

		self.model.segments[index], self.model.segments[new_index] = (
			self.model.segments[new_index],
			self.model.segments[index]
		)

		self.refresh()

		self.selected_segment_id = segment.id

		self.segment_editor.select_segment(
			segment.id
		)

		self.segment_editor.load_segment(
				segment
		)

		self.view.set_selected_segment(
			segment.id
		)

	def apply_selected_segment(
		self,
		name,
		length
	):

		segment = self.get_selected_segment()

		if segment is None:
			return

		segment.length = length

		if segment.is_film:
			segment.length = length
			segment.name = name

		elif segment.is_separator:
			segment.name = name

		else:
			segment.length = length

		self.refresh()

	def connect_segment_editor(self):

		self.segment_editor.segmentSelected.connect(
			self.on_segment_selected
		)

		self.segment_editor.deleteRequested.connect(
			self.delete_selected_segment
		)

		self.segment_editor.moveUpRequested.connect(
			lambda: self.move_selected_segment(-1)
		)

		self.segment_editor.moveDownRequested.connect(
			lambda: self.move_selected_segment(+1)
		)

		self.segment_editor.applyRequested.connect(
			self.apply_selected_segment
		)

	def get_selected_segment(self):

		if self.selected_segment_id is None:
			return None

		for seg in self.model.segments:

			if seg.id == self.selected_segment_id:
				return seg

		return None

## SIMULATION
	def add_film(self, attach = False):
		"""
		Add a new film and its leader to the ribbon.
		"""

		if (
			self.film_length.value() <= 0
			and self.leader_length.value() <= 0
		):
			return

		film_length = self.ui_to_meters(self.film_length.value())
		leader_length = self.ui_to_meters(self.leader_length.value())

		self.model.add_film(
			film_length,
			leader_length,
			self.film_name.text(),
			attach = attach
			)

		self.refresh()

	def add_separator(self):

		name, ok = QInputDialog.getText(
			self,
			lang.tr("add_separator"),
			lang.tr("separator_name")
		)

		if not ok:
			return

		if not name.strip():
			return

		self.model.add_separator(
			name.strip()
		)

		self.refresh()

	def move_ribbon(self, direction):
		"""
		Move ribbon manually left or right
		"""

		step = (
			10.0
			if (
				QGuiApplication.keyboardModifiers()
				& Qt.KeyboardModifier.ShiftModifier
			)
			else 1.0
		)

		self.model.processed_length += (
			direction * step
		)

		self.model.processed_length = max(
			0,
			self.model.processed_length
		)

		self.refresh()

	def toggle_simulation(self, state="auto"):

		if (
			self.timer.isActive()
			or state == "off"
			and state != "on"
		):
			self.timer.stop()
			self.start_pause_btn.setStyleSheet(
				"background-color: #344B34;"
			)
			self.start_pause_btn.setText(
				lang.tr("start")
			)

		else:
			self.last_time = (
				self.elapsed_timer.elapsed()
			)
			self.timer.start(65)
			self.start_pause_btn.setStyleSheet(
				"background-color: #661D1D;"
			)
			self.start_pause_btn.setText(
				lang.tr("pause")
			)

	def tick(self):

		current_time = self.elapsed_timer.elapsed()

		dt = (
			current_time
			- self.last_time
		) / 1000.0

		self.last_time = current_time

		speed_m_s = (
			self.speed.value()
			* 0.3048
			/ 60.0
		)

		self.model.processed_length += (
			speed_m_s * dt
		)
		angle_step = math.log(speed_m_s * 100) * 2
		self.view.reel_angle += angle_step
		self.refresh()

## VAR
	def ribbon_length(self):
		return self.model.ribbon_length()

	def machine_length(self):
		return sum(
			tank.length
			for tank in self.model.tanks
		)

## LOAD/REFRESH
	def load_settings(self):

		if not os.path.exists(SETTINGS_FILE):
			return

		with open(SETTINGS_FILE) as fp:
			data = json.load(fp)

		# speed
		self.speed.setValue(
			data.get("speed", 25)
		)

		# speed presets
		self.speed_presets = data.get(
			"speed_presets",
			[]
		)
		for spin, value in zip(
			self.speed_presets_edits,
			self.speed_presets
		):
			spin.setValue(value)
		self.rebuild_speed_presets()

		# film length
		self.film_length.setValue(
			data.get("film_length", 300)
		)

		# leader length
		self.leader_length.setValue(
			data.get("leader_length", 3)
		)

		# tank list
		self.model.tanks = [
			Tank.from_dict(t)
			for t in data.get("tanks", [])
		]
		self.rebuild_tank_editor()

		self.model.processed_length = 0

		self.refresh()

	def refresh(self):

		self.received_film, self.received_leader = self.model.get_received_lengths(self.machine_length())

		# Zones
		queue_start = self.model.processed_length
		queue_end = self.ribbon_length()

		machine_start = max(
			0,
			self.model.processed_length - self.machine_length()
		)
		machine_end = self.model.processed_length

		receiving_start = self.model.receiving_offset
		receiving_end = machine_start

		rows = []

		rows.extend(
			self.build_segment_rows(
				queue_start,
				queue_end,
				"queue",
				self.speed.value()
			)
		)

		rows.extend(
			self.build_segment_rows(
				machine_start,
				machine_end,
				"processing",
				self.speed.value()
			)
		)

		rows.extend(
			self.build_segment_rows(
				receiving_start,
				receiving_end,
				"receiving"
			)
		)

		self.segment_editor.populate(rows)

		segment = self.get_selected_segment()

		if self.selected_segment_id is not None and segment is not None:
			self.segment_editor.select_segment(
				segment.id
			)
			# self.segment_editor.load_segment(
			# 	segment
			# )
			self.view.set_selected_segment(
				segment.id
			)
		else:
			self.view.set_selected_segment(
				None
			)

		total_queue = max(
			0,
			self.ribbon_length() - self.model.processed_length
		)

		self.view.update_data(
			self.model.tanks,
			self.model.segments,
			self.model.processed_length,
			total_queue,
			self.received_film + self.received_leader,
			self.speed.value()
		)

		# self.save_settings()

	def update_text_edit(self, edit, text):

		if text == edit.toPlainText():
			return

		sb = edit.verticalScrollBar()

		ratio = (
			sb.value() / max(1, sb.maximum())
		)

		edit.setPlainText(text)

		sb = edit.verticalScrollBar()

		sb.setValue(
			int(sb.maximum() * ratio)
		)

## ACTIONS
	def reset(self):
		self.toggle_simulation("off")
		self.model.segments.clear()
		self.received_film=0.0
		self.received_leader=0.0
		self.model._next_film_id = 1
		self.model.processed_length=0.0
		self.model.receiving_offset=0.0
		self.segment_editor.set_segment_enabled(False)

		self.refresh()

	def clear_supply_reel(self):
		self.model.clear_supply_reel()
		self.refresh()

	def clear_receiving_reel(self):

		self.model.receiving_offset = max(
			0,
			self.model.processed_length - self.machine_length()
		)

		self.refresh()

	def save_settings(self):
		try:
			self.speed_presets = [
				spin.value()
				for spin in self.speed_presets_edits
				if spin.value() > 0
			]
			self.rebuild_speed_presets()
		except ValueError:
			pass

		data = {
			"speed": self.speed.value(),
			"speed_presets": self.speed_presets,
			"film_length": self.film_length.value(),
			"leader_length": self.leader_length.value(),

			"tanks": [
				tank.to_dict()
				for tank in self.model.tanks
			]
		}

		with open(
			SETTINGS_FILE,
			"w"
		) as fp:

			json.dump(
				data,
				fp,
				indent=2
			)

	def on_process_segment_clicked(
		self,
		segment
	):

		self.selected_segment_id = segment.id


		self.segment_editor.select_segment(
			segment.id
		)

		self.segment_editor.load_segment(
			segment
		)

		self.segment_editor.load_segment(
				segment
		)

		self.segment_editor.name_edit.setText(
			segment.name or ""
		)

		self.segment_editor.length_spin.setValue(
			segment.length
		)

		self.view.set_selected_segment(
			segment.id
		)

# PRINT
	def print_queue(self):

		today = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
		file_date = datetime.now().strftime(
			"%Y%m%d_%H%M%S"
		)

		pdf_path = (
			Path.home()
			/f"devlist/queue_list_{file_date}.pdf"
		)

		printer = QPrinter()

		printer.setOutputFormat(
			QPrinter.OutputFormat.PdfFormat
		)

		printer.setOutputFileName(
			str(pdf_path)
		)

		doc = QTextDocument()

		doc.setHtml(
			self.build_queue_html(today)
		)

		doc.print_(printer)

		QDesktopServices.openUrl(
			QUrl.fromLocalFile(
				str(pdf_path)
			)
		)

	def build_queue_html(self, date=""):

		rows = []

		total_film_lenght = 0
		total_leader_lenght = 0
		for seg in reversed(self.model.segments):

			if seg.is_film:
				total_film_lenght += seg.length
				name = seg.name
				cssclass = "film"
			elif seg.is_separator:
				name = seg.name
				cssclass = "separator"				
			else:
				total_leader_lenght += seg.length
				if seg.length <= 2: continue
				name = lang.tr("leader")
				cssclass = "leader"

			if seg.is_separator:
				rows.append(
					f"""
					<tr class="{cssclass}">
						<td colspan=3>{name}</td>
					</tr>
					"""
				)
			else:
				rows.append(
					f"""
					<tr class="{cssclass}">
						<td>{name}</td>
						<td>{seg.length:.1f} m</td>
						<td style="height:40px">&nbsp;</td>
					</tr>
					"""
				)

		return f"""
		<html>
		<head>
			<style>
				body {{
					font-family: Arial;
					font-size: 10pt;
				}}

				h1 {{
					text-align:center;
				}}

				table {{
					border-collapse:collapse;
				}}

				th, td {{
					border:1px solid black;
					padding:8px;
				}}

				th {{
					background:#dddddd;
				}}
				.leader td{{
					text-align: right;
				}}
				.film td{{
					font-weight: bold;
				}}
				.separator td{{
					text-align: center;
					font-weight: bold;
					font-size: 16px;
					border-top-width: 2px;
					border-bottom-width: 2px;
				}}
			</style>
		</head>

		<body>

		<h1>{lang.tr("queue_list")}</h1>

		<p>
			Date: {date}
		</p>
		<br>
		<table
			border="1"
			cellspacing="0"
			cellpadding="6"
			width="100%"
		>

		<tr>
			<th width="35%">{lang.tr("name")}</th>
			<th width="15%">{lang.tr("length")}</th>
			<th width="50%">{lang.tr("notes")}</th>
		</tr>

		{''.join(rows)}

		<tr>
			<td colspan=3>
				TOTAL film: {total_film_lenght}
				<br>
				TOTAL {lang.tr("leader")}: {total_leader_lenght}
			</td>
		</tr>
		</table>

		</body>
		</html>
		"""