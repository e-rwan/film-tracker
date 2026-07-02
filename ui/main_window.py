# ui/main_window.py

import json
import math
import os

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QElapsedTimer, QEvent, QTimer, Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QTextDocument
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import (
	QAbstractSpinBox,
	QApplication,
	QColorDialog,
	QInputDialog,
	QSplitter,
	QTabWidget,
	QVBoxLayout,
	QWidget,
)

from model.ribbon_model import RibbonModel
from model.tank import Tank
from ui.info_panel import InfoPanel
from ui.process_controls import ProcessControls
from ui.process_widget import ProcessWidget
from ui.settings_panel import SettingsPanel
from utils.constants import SETTINGS_FILE
from utils.lang import lang


class MainWindow(QWidget):
	"""
	Main application window.

	Coordinates user interactions, RibbonModel updates
	and UI synchronization.
	"""

	def __init__(self):
		super().__init__()

		self.model = RibbonModel()
		self.selected_segment_id = None
		self.speed_presets = []
		self.received_film = 0.0
		self.received_leader = 0.0

		self.timer = QTimer()
		self.timer.timeout.connect(self.tick)

		self.elapsed_timer = QElapsedTimer()
		self.elapsed_timer.start()
		self.last_time = self.elapsed_timer.elapsed()

		app = QApplication.instance()
		if app:
			app.installEventFilter(self)

		self.build_ui()
		self.connect_signals()
		self.load_settings()

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
		layout = QVBoxLayout(tab)

		self.process_controls = ProcessControls()
		layout.addWidget(self.process_controls)

		splitter = QSplitter(Qt.Orientation.Vertical)
		self.info_panel = InfoPanel()
		self.view = ProcessWidget()

		splitter.addWidget(self.info_panel)
		splitter.addWidget(self.view)
		splitter.setStretchFactor(0, 3)
		splitter.setStretchFactor(1, 2)

		layout.addWidget(splitter, 1)

	def build_settings_tab(self, tab):
		layout = QVBoxLayout(tab)
		self.settings_panel = SettingsPanel()
		layout.addWidget(self.settings_panel)

	def connect_signals(self):
		self.process_controls.resetRequested.connect(self.reset)
		self.process_controls.printQueueRequested.connect(self.print_queue)
		self.process_controls.addFilmRequested.connect(self.add_film)
		self.process_controls.addFilmPresetRequested.connect(self.add_film_preset)
		self.process_controls.addSeparatorRequested.connect(self.add_separator)
		self.process_controls.moveRibbonRequested.connect(self.move_ribbon)
		self.process_controls.startPauseRequested.connect(self.toggle_simulation)

		self.settings_panel.addTankRequested.connect(self.add_tank)
		self.settings_panel.saveRequested.connect(self.save_settings)
		self.settings_panel.tankNameChanged.connect(self.on_tank_name_changed)
		self.settings_panel.tankLengthChanged.connect(self.on_tank_length_changed)
		self.settings_panel.tankColorRequested.connect(self.choose_tank_color)
		self.settings_panel.tankMoveRequested.connect(self.move_tank)
		self.settings_panel.tankRemoveRequested.connect(self.remove_tank)

		self.info_panel.segmentSelected.connect(self.on_segment_selected)
		self.info_panel.moveUpRequested.connect(
			lambda: self.move_selected_segment(-1)
		)
		self.info_panel.moveDownRequested.connect(
			lambda: self.move_selected_segment(1)
		)
		self.info_panel.deleteRequested.connect(self.delete_selected_segment)
		self.info_panel.applyRequested.connect(self.apply_selected_segment)

		self.view.segmentClicked.connect(self.on_process_segment_clicked)

	def eventFilter(self, obj, event):
		if event.type() == QEvent.Type.KeyPress:
			if self.handle_shortcuts(event):
				return True

			if event.key() == Qt.Key.Key_Shift:
				self.process_controls.update_shift_step_labels(True)

		elif event.type() == QEvent.Type.KeyRelease:
			if event.key() == Qt.Key.Key_Shift:
				self.process_controls.update_shift_step_labels(False)

		return False

	def handle_shortcuts(self, event):
		focus = QApplication.focusWidget()
		key = event.key()
		mod = event.modifiers()

		editing = isinstance(focus, QAbstractSpinBox) or self.process_controls.is_film_input(focus) or self.info_panel.is_editor_input(focus)

		if key == Qt.Key.Key_Space and not editing:
			self.toggle_simulation()
			return True

		if key == Qt.Key.Key_P and mod & Qt.KeyboardModifier.ControlModifier:
			self.print_queue()
			return True

		if mod & Qt.KeyboardModifier.ControlModifier and not editing:
			if key == Qt.Key.Key_Left:
				self.move_ribbon(-1)
				return True

			if key == Qt.Key.Key_Right:
				self.move_ribbon(1)
				return True

		if mod & Qt.KeyboardModifier.ControlModifier:
			if key in (Qt.Key.Key_Up, Qt.Key.Key_Down) and self.selected_segment_id is not None and not editing:
				if key == Qt.Key.Key_Up:
					self.move_selected_segment(-1)
				else:
					self.move_selected_segment(1)
				return True

		if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
			if self.process_controls.is_film_input(focus):
				self.add_film()
				return True

			if self.info_panel.is_editor_input(focus):
				self.apply_selected_segment(
					self.info_panel.name_edit.text(),
					self.info_panel.length_spin.value(),
				)
				return True

		if key == Qt.Key.Key_Delete and self.selected_segment_id is not None and not editing:
			self.delete_selected_segment()
			return True

		return False

	def add_film_preset(self, length):
		if length <= 0:
			return

		self.model.add_film(length, 0, self.process_controls.film_name_value())
		self.refresh()

	def add_film(self, attach=False):
		film_length = self.process_controls.film_length_meters()
		leader_length = self.process_controls.leader_length_meters()

		if film_length <= 0 and leader_length <= 0:
			return

		self.model.add_film(
			film_length,
			leader_length,
			self.process_controls.film_name_value(),
			attach=attach,
		)
		self.refresh()

	def add_separator(self):
		name, ok = QInputDialog.getText(
			self,
			lang.tr("add_separator"),
			lang.tr("separator_name"),
		)

		if ok and name.strip():
			self.model.add_separator(name.strip())
			self.refresh()

	def move_ribbon(self, direction):
		step = self.process_controls.current_move_step()
		self.model.processed_length = max(
			0,
			self.model.processed_length + direction * step,
		)
		self.refresh()

	def toggle_simulation(self, state="auto"):
		should_stop = self.timer.isActive() or (state == "off" and state != "on")

		if should_stop:
			self.timer.stop()
			self.process_controls.set_simulation_running(False)
			return

		self.last_time = self.elapsed_timer.elapsed()
		self.timer.start(65)
		self.process_controls.set_simulation_running(True)

	def tick(self):
		current_time = self.elapsed_timer.elapsed()
		dt = (current_time - self.last_time) / 1000.0
		self.last_time = current_time

		speed_m_s = self.process_controls.speed_value() * 0.3048 / 60.0
		self.model.processed_length += speed_m_s * dt

		if speed_m_s > 0:
			self.view.reel_angle += math.log(max(speed_m_s * 100, 1)) * 2

		self.refresh()

	def on_segment_selected(self, segment_id):
		self.selected_segment_id = segment_id
		self.sync_selected_segment()

	def on_process_segment_clicked(self, segment):
		self.selected_segment_id = segment.id
		self.sync_selected_segment(segment)

	def sync_selected_segment(self, segment=None):
		segment = segment or self.get_selected_segment()

		if segment is None:
			self.selected_segment_id = None
			self.info_panel.clear_selection()
			self.view.set_selected_segment(None)
			return

		self.info_panel.show_segment(segment)
		self.view.set_selected_segment(segment.id)

	def get_selected_segment(self):
		if self.selected_segment_id is None:
			return None
		return self.model.get_segment_by_id(self.selected_segment_id)

	def delete_selected_segment(self):
		if self.selected_segment_id is None:
			return

		next_segment = self.model.delete_segment_by_id(self.selected_segment_id)
		self.selected_segment_id = next_segment.id if next_segment else None
		self.refresh()

	def move_selected_segment(self, offset):
		if self.selected_segment_id is None:
			return

		if self.model.move_segment_by_id(self.selected_segment_id, offset):
			self.refresh()

	def apply_selected_segment(self, name, length):
		if self.selected_segment_id is None:
			return

		if self.model.update_segment_by_id(self.selected_segment_id, name, length):
			self.refresh()

	def add_tank(self):
		self.model.add_tank(lang.tr("new_tank"))
		self.settings_panel.set_tanks(self.model.tanks)
		self.refresh()

	def remove_tank(self, index):
		if self.model.remove_tank(index):
			self.settings_panel.set_tanks(self.model.tanks)
			self.refresh()

	def move_tank(self, index, offset):
		if self.model.move_tank(index, offset):
			self.settings_panel.set_tanks(self.model.tanks)
			self.refresh()

	def choose_tank_color(self, index):
		if not (0 <= index < len(self.model.tanks)):
			return

		tank = self.model.tanks[index]
		color = QColorDialog.getColor(QColor(tank.color), self, f"Color - {tank.name}")
		if not color.isValid():
			return

		self.model.set_tank_color(index, color.name())
		self.settings_panel.set_tanks(self.model.tanks)
		self.refresh()

	def on_tank_name_changed(self, index, name):
		self.model.update_tank_name(index, name)
		self.refresh()

	def on_tank_length_changed(self, index, length):
		self.model.update_tank_length(index, length)
		self.refresh()

	def load_settings(self):
		self.settings_panel.set_tanks(self.model.tanks)

		if not os.path.exists(SETTINGS_FILE):
			self.refresh()
			return

		with open(SETTINGS_FILE) as fp:
			data = json.load(fp)

		self.speed_presets = data.get("speed_presets", [])
		self.process_controls.set_runtime_values(
			data.get("speed", 25),
			data.get("film_length", 300),
			data.get("leader_length", 3),
		)
		self.process_controls.set_speed_presets(self.speed_presets)
		self.settings_panel.set_speed_presets(self.speed_presets)

		self.model.tanks = [
			Tank.from_dict(tank_data)
			for tank_data in data.get("tanks", [])
		]
		self.settings_panel.set_tanks(self.model.tanks)
		self.model.processed_length = 0
		self.refresh()

	def save_settings(self):
		self.speed_presets = self.settings_panel.speed_presets()
		self.process_controls.set_speed_presets(self.speed_presets)

		data = {
			"speed": self.process_controls.speed_value(),
			"speed_presets": self.speed_presets,
			"film_length": self.process_controls.film_length_value(),
			"leader_length": self.process_controls.leader_length_value(),
			"tanks": [tank.to_dict() for tank in self.model.tanks],
		}


		with open(SETTINGS_FILE, "w") as fp:
			json.dump(data, fp, indent=2)

	def refresh(self):

		machine_length = self.model.machine_length()
		self.received_film, self.received_leader = self.model.get_received_lengths(machine_length)

		queue_start = self.model.processed_length
		queue_end = self.model.ribbon_length()
		machine_start = max(0, self.model.processed_length - machine_length)
		machine_end = self.model.processed_length
		receiving_start = self.model.receiving_offset
		receiving_end = machine_start
		speed = self.process_controls.speed_value()

		rows = []
		rows.extend(
			self.model.build_zone_rows(
				queue_start,
				queue_end,
				"queue",
				speed_ft_min=speed,
				queue_entry_position=self.model.processed_length,
				queue_exit_position=self.model.processed_length - machine_length,
			)
		)
		rows.extend(
			self.model.build_zone_rows(
				machine_start,
				machine_end,
				"processing",
				speed_ft_min=speed,
				queue_exit_position=self.model.processed_length - machine_length,
			)
		)
		rows.extend(
			self.model.build_zone_rows(
				receiving_start,
				receiving_end,
				"receiving",
			)
		)

		self.info_panel.populate(rows)

		segment = self.get_selected_segment()
		if segment is None:
			self.selected_segment_id = None
			self.info_panel.clear_selection()
			self.view.set_selected_segment(None)
		else:
			self.info_panel.set_selected_segment(segment.id)
			self.view.set_selected_segment(segment.id)

		total_queue = max(0, self.model.ribbon_length() - self.model.processed_length)

		self.view.update_data(
			self.model.tanks,
			self.model.segments,
			self.model.processed_length,
			total_queue,
			self.received_film + self.received_leader,
			speed,
		)

	def reset(self):
		self.toggle_simulation("off")
		self.model.reset_runtime()
		self.received_film = 0.0
		self.received_leader = 0.0
		self.selected_segment_id = None
		self.info_panel.clear_selection()
		self.refresh()

	def clear_supply_reel(self):
		self.model.clear_supply_reel()
		self.refresh()

	def clear_receiving_reel(self):
		self.model.receiving_offset = max(
			0,
			self.model.processed_length - self.model.machine_length(),
		)
		self.refresh()

	def print_queue(self):
		today = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
		file_date = datetime.now().strftime("%Y%m%d_%H%M%S")
		pdf_path = Path.home() / f"devlist/queue_list_{file_date}.pdf"

		printer = QPrinter()
		printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
		printer.setOutputFileName(str(pdf_path))

		doc = QTextDocument()
		doc.setHtml(self.build_queue_html(today))
		doc.print_(printer)

		QDesktopServices.openUrl(QUrl.fromLocalFile(str(pdf_path)))

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
				if seg.length <= 2:
					continue
				name = lang.tr("leader")
				cssclass = "leader"

			if seg.is_separator:
				rows.append(
					f"""
					<tr class=\"{cssclass}\">
						<td colspan=3>{name}</td>
					</tr>
					"""
				)
			else:
				rows.append(
					f"""
					<tr class=\"{cssclass}\">
						<td>{name}</td>
						<td>{seg.length:.1f} m</td>
						<td style=\"height:40px\">&nbsp;</td>
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
		<p>Date: {date}</p>
		<br>
		<table border="1" cellspacing="0" cellpadding="6" width="100%">
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