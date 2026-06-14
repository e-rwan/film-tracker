# main_window.py

import json
import os
import math

from datetime import datetime
from pathlib import Path
from PySide6.QtCore import QTimer, Qt, QEvent, QElapsedTimer, QUrl
from PySide6.QtGui import QGuiApplication, QColor, QFont, QTextDocument, QDesktopServices
from PySide6.QtWidgets import (
	QApplication,
	QDoubleSpinBox,
	QFormLayout,
	QFrame,
	QGroupBox,
	QHBoxLayout,
	QLabel,
	QLineEdit,
	QPushButton,
	QToolButton,
	QSizePolicy,
	QTabWidget,
	QTextEdit,
	QVBoxLayout,
	QWidget,
	QColorDialog,
	QSplitter,
	QDialog,
	QFileDialog
)
from PySide6.QtPrintSupport import (
    QPrintDialog,
    QPrinter,
)

from utils.constants import SETTINGS_FILE
from model.ribbon_model import RibbonModel
from model.tank import Tank
from ui.process_widget import ProcessWidget
from ui.segment_editor import SegmentEditor


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

		self.speed_presets = []

		self.received_film=0.0
		self.received_leader=0.0 

		self.timer=QTimer()
		self.timer.timeout.connect(self.tick)

		self.elapsed_timer = QElapsedTimer()
		self.elapsed_timer.start()

		self.last_time = self.elapsed_timer.elapsed()

		app = QApplication.instance()
		if app: app.installEventFilter(self)

		self.build_ui()
		self.load_settings()

## BUILD
	def build_ui(self):

		self.setWindowTitle("Film Tracker V5")

		root = QVBoxLayout(self)

		tabs = QTabWidget()
		root.addWidget(tabs)

		process_tab = QWidget()
		settings_tab = QWidget()

		tabs.addTab(process_tab, "Process")
		tabs.addTab(settings_tab, "Settings")

		self.build_process_tab(process_tab)
		self.build_settings_tab(settings_tab)
		
	def build_process_tab(self, tab):

		process = QVBoxLayout(tab)

		self.build_params_bar(process)
		self.build_transport_bar(process)
		self.build_reset_bar(process)

		splitter = QSplitter(
			Qt.Orientation.Vertical
		)

		self.segment_editor = SegmentEditor()
		self.view = ProcessWidget()
		self.connect_segment_editor()

		splitter.addWidget(
			self.segment_editor
		)

		splitter.addWidget(
			self.view
		)

		splitter.setStretchFactor(0, 2)
		splitter.setStretchFactor(1, 1)

		process.addWidget(
			splitter,
			1
		)

## SETTINGS TAB 
	def build_settings_tab(self, tab):	

		layout = QVBoxLayout(tab)

		# speed preset
		layout.addWidget(
			QLabel("Speed presets")
		)
		self.speed_presets_edit = QLineEdit()
		layout.addWidget(
			self.speed_presets_edit
		)

		# tank list
		self.tank_container = QVBoxLayout()
		layout.addLayout(
			self.tank_container
		)
		self.speed_presets_edit.setText(
			", ".join(
				str(v)
				for v in self.speed_presets
			)
		)

		# add tank button
		buttons = QHBoxLayout()
		btn_add = QPushButton("Add tank")
		btn_add.clicked.connect(
			self.add_tank
		)
		buttons.addWidget(
			btn_add
		)
		buttons.addStretch()

		layout.addLayout(
			buttons
		)

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

		# Tank lenght
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
				name="New Tank",
				length=1.0,
				color="#808080"
			)
		)

		self.rebuild_tank_editor()

		self.save_settings()

	def remove_tank(self, index):

		if len(self.model.tanks) <= 1:
			return

		self.model.tanks.pop(index)

		self.rebuild_tank_editor()

		self.save_settings()

	def move_tank_up(self, index):

		if index <= 0:
			return

		self.model.tanks[index - 1], self.model.tanks[index] = (
			self.model.tanks[index],
			self.model.tanks[index - 1]
		)

		self.rebuild_tank_editor()
		self.save_settings()
		self.refresh()

	def move_tank_down(self, index):

		if index >= len(self.model.tanks) - 1:
			return

		self.model.tanks[index + 1], self.model.tanks[index] = (
			self.model.tanks[index],
			self.model.tanks[index + 1]
		)

		self.rebuild_tank_editor()
		self.save_settings()
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
		self.save_settings()
		self.refresh()

## MAIN TAB
	def build_params_bar(self, process):

		params = QHBoxLayout()

		self.speed = QDoubleSpinBox()
		self.speed.setMaximum(10000)
		self.speed.setSuffix(" ft/min")
		self.speed.setMaximumWidth(120)

		self.film_name = QLineEdit()

		self.film_length = QDoubleSpinBox()
		self.film_length.setMaximum(10000)
		self.film_length.setSuffix(" m")
		self.film_length.setMaximumWidth(120)

		self.leader_length = QDoubleSpinBox()
		self.leader_length.setMaximum(100)
		self.leader_length.setSuffix(" m")
		self.leader_length.setValue(3)
		self.leader_length.setMaximumWidth(120)

		params.addWidget(QLabel("Speed"))
		params.addWidget(self.speed)

		self.speed_preset_layout = QHBoxLayout()
		params.addLayout(
			self.speed_preset_layout
		)

		params.addSpacing(20)

		line = QFrame()
		line.setFrameShape(QFrame.Shape.VLine)
		line.setFrameShadow(QFrame.Shadow.Sunken)

		params.addWidget(line)

		params.addSpacing(20)

		params.addWidget(QLabel("Name"))
		params.addWidget(self.film_name)

		params.addSpacing(20)

		params.addWidget(QLabel("Film"))
		params.addWidget(self.film_length)

		params.addSpacing(20)

		params.addWidget(QLabel("Leader"))
		params.addWidget(self.leader_length)

		params.addSpacing(20)

		button_font = self.font()
		button_font.setBold(True)
		button_font.setPointSize(12)

		b = QPushButton("➠ Add to queue")
		b.clicked.connect(self.add_film)
		b.setFont(button_font)
		params.addWidget(b)

		b = QPushButton("➥ Attach to film")
		b.clicked.connect(self.attach_to_film)
		b.setFont(button_font)
		params.addWidget(b)

		b = QPushButton("🖶 Print queue")
		b.clicked.connect(self.print_queue)
		# b.setFont(button_font)
		params.addWidget(b)


		params.addStretch()

		process.addLayout(params)

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
			"Move ribbon -1 m (Ctrl = -10 m)"
		)

		self.start_pause_btn = QPushButton("▶ Start")

		self.start_pause_btn.clicked.connect(
			self.toggle_simulation
		)

		btnsPlay.addWidget(self.start_pause_btn)

		self.start_pause_btn.setToolTip(
			"Start|Pause simulation"
		)

		self.move_right_btn = QPushButton("+1m >>")

		self.move_right_btn.clicked.connect(
			lambda: self.move_ribbon(1)
		)

		btnsPlay.addWidget(self.move_right_btn)

		self.move_right_btn.setToolTip(
			"Move ribbon +1 m (Ctrl = +10 m)"
		)

		font = self.start_pause_btn.font()
		font.setBold(True)

		self.move_left_btn.setFont(font)
		self.start_pause_btn.setFont(font)
		self.move_right_btn.setFont(font)

		process.addLayout(btnsPlay)

	def build_reset_bar(self, process):

		btnsClear = QHBoxLayout()

		b = QPushButton("Reset")
		b.clicked.connect(self.reset)
		btnsClear.addWidget(b)

		b.setToolTip(
			"Reset whole simulation"
		)

		b = QPushButton("Clear supply reel")
		b.clicked.connect(self.clear_supply_reel)
		btnsClear.addWidget(b)

		b.setToolTip(
			"Empty suplly queue list"
		)

		b = QPushButton("Clear receiving reel")
		b.clicked.connect(
			self.clear_receiving_reel
		)

		btnsClear.addWidget(b)

		b.setToolTip(
			"Empty receiving queue list"
		)

		process.addLayout(btnsClear)

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
			if event.key() == Qt.Key.Key_Control:
				self.move_left_btn.setText("<< -10m")
				self.move_right_btn.setText("+10m >>")

		elif event.type() == QEvent.Type.KeyRelease:
			if event.key() == Qt.Key.Key_Control:
				self.move_left_btn.setText("<< -1m")
				self.move_right_btn.setText("+1m >>")

		return False

## SEGMENTS
	def on_segment_selected(self, segment):

		self.selected_segment = segment

		self.view.set_selected_segment(
			segment
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

			if visible <= 0:
				continue

			eta = ""

			if (
				speed_ft_min
				and seg.is_film
			):
				eta = self.model.get_remaining_time(
					seg_end,
					self.machine_length(),
					speed_ft_min
				)

			rows.append(
				{
					"zone": zone_name,
					"segment": seg,
					"visible": visible,
					"eta": eta
				}
			)

		return rows

	def delete_selected_segment(self):

		segment = self.selected_segment

		if segment is None:
			return

		if segment not in self.model.segments:
			return

		self.model.segments.remove(segment)

		self.selected_segment = None

		self.refresh()

	def move_selected_segment(self, offset):

		segment = self.selected_segment

		if segment is None:
			return

		index = self.model.segments.index(segment)

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

	def apply_selected_segment(
		self,
		name,
		length
	):

		segment = self.selected_segment

		if segment is None:
			return

		segment.length = length

		if segment.is_film:
			segment.name = name

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

## SIMULATION
	def add_film(self):
		"""
		Add a new film and its leader to the ribbon.
		"""

		self.model.add_film(
			self.film_length.value(),
			self.leader_length.value(),
			self.film_name.text()
		)

		self.refresh()

	def attach_to_film(self):
		"""
		Attach a film directly behind the last film already
		in the machine.

		If queue already contains ribbon, fallback to the
		normal queue insertion.
		"""

		self.model.attach_film(
			self.film_length.value(),
			self.leader_length.value(),
			self.film_name.text()
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
				& Qt.KeyboardModifier.ControlModifier
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

	def toggle_simulation(self):

		if self.timer.isActive():
			self.timer.stop()
			self.start_pause_btn.setText(
				"▶ Start"
			)

		else:
			self.last_time = (
				self.elapsed_timer.elapsed()
			)
			self.timer.start(50)
			self.start_pause_btn.setText(
				"❚❚ Pause"
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
		self.speed_presets_edit.setText(
			", ".join(
				str(v)
				for v in self.speed_presets
			)
		)
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
				"Queue",
				self.speed.value()
			)
		)

		rows.extend(
			self.build_segment_rows(
				machine_start,
				machine_end,
				"Processing",
				self.speed.value()
			)
		)

		rows.extend(
			self.build_segment_rows(
				receiving_start,
				receiving_end,
				"Receiving"
			)
		)

		self.segment_editor.populate(
			rows
		)

		self.segment_editor.populate(rows)

		if self.selected_segment is not None:
			self.segment_editor.select_segment(
				self.selected_segment
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
		self.start_pause_btn.setText("Start")
		self.timer.stop()
		self.model.segments.clear()
		self.received_film=0.0
		self.received_leader=0.0
		self.model.next_film_id = 1
		self.model.processed_length=0.0
		self.model.receiving_offset=0.0

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
				float(v.strip())
				for v in self.speed_presets_edit.text().split(",")
				if v.strip()
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

		for seg in self.model.segments:

			if seg.is_film:
				name = seg.name
				text_align = "left"
			else:
				name = "Leader"
				text_align = "right"

			rows.append(
				f"""
				<tr>
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
			</style>
		</head>

		<body>

		<h1>Queue List</h1>

		<p>
			Date: {date}
		</p>

		<table
			border="1"
			cellspacing="0"
			cellpadding="6"
			width="100%"
		>

		<tr>
			<th width="35%">Name</th>
			<th width="15%">Length</th>
			<th width="50%">Notes</th>
		</tr>

		{''.join(rows)}

		</table>

		</body>
		</html>
		"""