import json
import os
import math

from PySide6.QtCore import QRectF, QTimer, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
	QApplication,
	QDoubleSpinBox,
	QFormLayout,
	QHBoxLayout,
	QLabel,
	QPushButton,
	QSizePolicy,
	QTabWidget,
	QTextEdit,
	QGroupBox,
	QVBoxLayout,
	QWidget,
)

# ============================================================
# ARCHITECTURE OVERVIEW
# ============================================================
#
# Segment
# -------
# Represents a physical ribbon segment.
#
# Attributes:
#     type      : "film" or "leader"
#     length    : segment length in meters
#     id        : film identifier (film segments only)
#
# Main members:
#     film()    : create a film segment
#     leader()  : create a leader segment
#     is_film   : convenience property
#
#
# RibbonModel
# -----------
# Business logic and ribbon state.
#
# Responsibilities:
#     - store ribbon segments
#     - track ribbon progression
#     - detect completed films
#     - calculate Queue / Processing / Receiving zones
#     - calculate receiving reel contents
#
# Methods:
#     ribbon_length()
#         Return total ribbon length.
#
#     iter_segments()
#         Iterate through segments and yield:
#         (segment, start_position, end_position)
#
#     add_film(film_length, leader_length)
#         Append a new film and leader to the ribbon.
#
#     get_received_lengths(machine_length)
#         Calculate visible film/leader lengths on the
#         receiving reel.
#
#     build_segment_list(...)
#         Build textual information for Queue,
#         Processing or Receiving views.
#
#
# ProcessWidget
# -------------
# Rendering widget.
#
# Responsibilities:
#     - draw machine tanks
#     - draw supply reel
#     - draw receiving reel
#     - draw ribbon position
#
# Methods:
#     _draw_reels()
#         Draw reel labels and reels.
#
#     paintEvent()
#         Main rendering routine.
#
#     draw_reel()
#         Draw a single reel.
#
#     update_data()
#         Receive new visualization data and repaint.
#
#
# Main
# ----
# Main application window.
#
# Responsibilities:
#     - user interface
#     - application workflow
#     - synchronization between UI and RibbonModel
#
# Methods:
#     build()
#         Create the user interface.
#
#     elements()
#         Return machine element lengths.
#
#     add_film()
#         Add a film to the ribbon.
#
#     ribbon_length()
#         Return total ribbon length.
#
#     tick()
#         Timer callback advancing ribbon position.
#
#     machine_length()
#         Return total machine path length.
#
#     start()
#         Start processing simulation.
#
#     pause()
#         Pause processing simulation.
#
#     reset()
#         Reset ribbon state.
#
#     clear_receiving_reel()
#         Clear received ribbon history.
#
#     refresh()
#         Update all displays and calculations.
#
#     save()
#         Save application settings.
#
#     load()
#         Load application settings.
#
# ============================================================

SETTINGS="film_tracker_settings.json"


from dataclasses import dataclass

@dataclass
class Segment:
	"""
	Represents a continuous section of ribbon.

	A segment can be either a film or a leader.
	Segments are stored in RibbonModel in their physical order
	along the ribbon.
	"""

	type: str
	length: float
	id: int | None = None

	@classmethod
	def film(cls, length, film_id):
		return cls("film", length, film_id)

	@classmethod
	def leader(cls, length):
		return cls("leader", length)

	@property
	def is_film(self):
		return self.type == "film"


# ============================================================
# Ribbon model (business logic)
# ============================================================

class RibbonModel:
	"""
	Business model representing the ribbon state.

	Responsible for:
	- storing film and leader segments,
	- tracking ribbon progression through the machine,
	- detecting completed films,
	- calculating Queue, Processing and Receiving zones.

	This class contains no Qt-specific code.
	"""

	def __init__(self):
		self.segments = []
		self.processed_length = 0.0
		self.receiving_offset = 0.0
		self.next_film_id = 1

	def ribbon_length(self):
		"""Return total ribbon length in meters."""
		return sum(seg.length for seg in self.segments)

	def iter_segments(self):
		"""Iterate over segments and yield (segment, start, end) positions."""
		cursor = 0.0

		for seg in self.segments:
			start = cursor
			end = start + seg.length
			yield seg, start, end
			cursor = end

	def add_film(self, film_length, leader_length):
		"""Add a new film and its leader to the ribbon."""
		last_film_end = None

		for seg, seg_start, seg_end in self.iter_segments():
			if seg.is_film:
				last_film_end = seg_end

		if last_film_end is not None:
			free_leader = self.processed_length - last_film_end

			if free_leader > 0:
				self.segments.append(Segment.leader(free_leader))

		self.segments.append(Segment.film(film_length, self.next_film_id))

		self.segments.append(Segment.leader(leader_length))

		self.next_film_id += 1

	def get_received_lengths(self, machine_length):
		"""
		Calculate the visible film and leader lengths
		currently present on the receiving reel.
		"""
		film = 0.0
		leader = 0.0
		received_position = self.processed_length - machine_length

		for seg, seg_start, seg_end in self.iter_segments():

			received = min(
				seg.length,
				max(0, received_position - seg_start)
			)


			if seg.is_film:
				film += received
			else:
				leader += received

		total_received = film + leader
		visible_received = max(
			0,
			total_received - self.receiving_offset
		)

		if total_received <= 0:
			return 0.0, 0.0

		ratio = visible_received / total_received
		return film * ratio, leader * ratio


	def get_remaining_time(self, seg_end, machine_length, speed_ft_min, extra_length=0):
		"""
		Return remaining time before the end of a segment
		(or segment + leader) exits the machine.
		"""
		speed_m_min = speed_ft_min * 0.3048

		if speed_m_min <= 0:
			return "--:--"

		receiving_position = (
			self.processed_length
			- machine_length
		)

		remaining_length = (
			seg_end
			+ extra_length
			- receiving_position
		)

		if remaining_length <= 0:
			return "00:00"

		remaining_seconds = (
			remaining_length
			/ speed_m_min
			* 60
		)

		minutes = int(remaining_seconds // 60)
		seconds = int(remaining_seconds % 60)

		return f"{minutes:02d}:{seconds:02d}"


	def build_segment_list(self, zone_start, zone_end, title, total_length=600, speed_ft_min=None):
		"""
		Build a textual representation of the films
		visible within a ribbon zone.
		"""

		occupied_length = 0
		film_lines = []
		for i, (seg, seg_start, seg_end) in enumerate(self.iter_segments()):

			visible = max(
				0,
				min(seg_end, zone_end) - max(seg_start, zone_start)
			)


			if visible <= 0 or not seg.is_film:
				continue

			leader_visible = 0
			leader_total = 0

			if (
				i + 1 < len(self.segments)
				and self.segments[i + 1].type == "leader"
			):
				next_seg = self.segments[i + 1]

				next_start = seg_end
				next_end = next_start + next_seg.length

				leader_visible = max(
					0,
					min(next_end, zone_end) - max(next_start, zone_start)
				)

			remaining_text = ""
			if (
				title == "Processing"
				and speed_ft_min is not None
			):
				remaining_text = (
					f"  -  Remaining : "
					f"{self.get_remaining_time(
						seg_end,
						total_length,
						speed_ft_min,
						leader_total
					)}"
				)
			
			film_lines.append(
				f"Film {seg.id} : "
				f"{visible :.1f} / "
				f"{seg.length:.1f} m"
				f"{f' (+{leader_visible:.1f}m)' if leader_visible > 0 else ''}"
				f"{remaining_text}"
			)

			occupied_length += visible + leader_visible

		lines = [f"{title} : {occupied_length:.1f} / {total_length:.1f} m", ""]

		lines.extend(film_lines)

		return "\n".join(lines)




ELEMENTS=[
	"Loading Elevator","Prebath","Buffer Wash","Developer","Stop",
	"Wash 1","Bleach","Wash 2","Fixer","Wash 3","Wash 4",
	"Final Rinse","Dryer","Take-up Elevator"
]

def color_for(name):
	"""Return display color associated with a machine element."""

	n = name.lower()

	if "wash" in n:
		return QColor(135, 165, 220)

	if "bath" in n or "rinse" in n:
		return QColor(110, 140, 190)

	if "developer" in n:
		return QColor(145, 135, 200)   # violet

	if "bleach" in n:
		return QColor(190, 120, 120)

	if "fix" in n:
		return QColor(110, 170, 110)   # vert

	if "stop" in n:
		return QColor(210, 195, 105)

	if "elevator" in n:
		return QColor(45, 45, 45)

	if "dry" in n:
		return QColor(180, 145, 95)

	return QColor(120, 120, 120)



# ============================================================
# Process visualization widget
# ============================================================

class ProcessWidget(QWidget):
	"""
	Graphical visualization of the processing machine.

	Displays:
	- machine tanks,
	- supply and receiving reels,
	- ribbon position within the process path.

	This widget is responsible only for rendering.
	Business logic is handled by RibbonModel.
	"""

	def __init__(self):
		super().__init__()
		self.elements={}
		self.ribbon=[]
		self.position=0.0

		self.supply_length=0.0
		self.received_length=0.0

		self.setMinimumHeight(550)

		self.supply_angle = 0.0


	def _draw_reels(self, p):
		"""Draw reel labels and reels."""
		p.drawText(20,40,"Supply Reel")
		self.draw_reel(p, 20, 55, 70, self.supply_angle)

		p.drawText(self.width()-90,40,"Receiving Reel")
		self.draw_reel(p, self.width()-90, 55, 70, self.supply_angle)

	def _compute_layout(self, process_len):
		"""
		Compute machine drawing geometry.
		"""

		waiting_zone = process_len * 0.1
		receiving_zone = process_len * 0.1

		axis_start = -waiting_zone
		axis_end = process_len + receiving_zone

		margin = 10
		width = self.width() - margin * 2

		process_x = (
			margin
			+ width * waiting_zone
			/ (axis_end - axis_start)
		)

		process_w = (
			width * process_len
			/ (axis_end - axis_start)
		)

		return {
			"process_len": process_len,
			"process_x": process_x,
			"process_w": process_w,
			"tank_y": 80,
			"tank_h": 250,
		}

	def _draw_headers(self, p):
		"""
		Draw reel labels and reel lengths.
		"""

		self._draw_reels(p)

		p.drawText(
			QRectF(0, 130, 120, 30),
			Qt.AlignmentFlag.AlignCenter,
			f"{self.supply_length:.0f} m"
		)

		p.drawText(
			QRectF(
				self.width() - 120,
				130,
				120,
				30
			),
			Qt.AlignmentFlag.AlignCenter,
			f"{self.received_length:.0f} m"
		)

	def _draw_tanks(self, p, layout):
		"""
		Draw machine tanks and labels.
		"""

		process_len = layout["process_len"]
		process_x = layout["process_x"]
		process_w = layout["process_w"]

		y = layout["tank_y"]
		h = layout["tank_h"]

		curx = process_x

		for name, length in self.elements.items():

			sw = process_w * length / process_len

			rect = QRectF(
				curx,
				y,
				sw,
				h
			)

			p.fillRect(
				rect,
				color_for(name)
			)

			pen = QPen(Qt.GlobalColor.black)
			pen.setWidth(2)

			p.setPen(pen)
			p.drawRect(rect)

			xx = curx

			while xx < curx + sw - 4:
				p.drawLine(
					int(xx),
					y + 16,
					int(xx + 4),
					y + 12
				)

				p.drawLine(
					int(xx + 4),
					y + 12,
					int(xx + 8),
					y + 16
				)

				xx += 8

			p.setPen(Qt.GlobalColor.white)

			text_width = (
				p.fontMetrics()
				.horizontalAdvance(name)
			)

			p.save()

			anchor_x = curx + sw / 2
			anchor_y = y - 5

			p.translate(
				anchor_x,
				anchor_y
			)

			p.rotate(35)

			p.drawText(
				-text_width,
				0,
				name
			)

			p.restore()

			curx += sw

	def _draw_ribbon(self, p, layout):
		"""
		Draw ribbon segments visible in the machine.
		"""

		process_len = layout["process_len"]
		process_x = layout["process_x"]
		process_w = layout["process_w"]

		y = layout["tank_y"]

		machine_start = 0
		machine_end = process_len

		total_ribbon_length = sum(
			seg.length
			for seg in self.ribbon
		)

		cursor = -total_ribbon_length

		for seg in reversed(self.ribbon):

			cursor += seg.length

			seg_start = (
				cursor
				- seg.length
				+ self.position
			)

			seg_end = (
				cursor
				+ self.position
			)

			visible_start = max(
				seg_start,
				machine_start
			)

			visible_end = min(
				seg_end,
				machine_end
			)

			if visible_end <= visible_start:
				continue

			local_start = (
				visible_start
				- machine_start
			)

			local_end = (
				visible_end
				- machine_start
			)

			x1 = (
				process_x
				+ process_w
				* local_start
				/ (machine_end - machine_start)
			)

			x2 = (
				process_x
				+ process_w
				* local_end
				/ (machine_end - machine_start)
			)

			if seg.is_film:
				p.setBrush(
					QColor(
						40,
						40,
						40,
						180
					)
				)
			else:
				p.setBrush(
					QColor(
						255,
						255,
						255,
						120
					)
				)

			pen = QPen(
				QColor(
					255,
					255,
					255
				)
			)

			pen.setWidth(1)
			pen.setStyle(
				Qt.PenStyle.DashLine
			)

			p.setPen(pen)

			p.drawRect(
				QRectF(
					x1,
					y + 120,
					x2 - x1,
					40
				)
			)

	def paintEvent(self, e):
		"""
		Render the machine, reels and ribbon position.
		"""

		if not self.elements:
			return

		p = QPainter(self)

		p.setRenderHint(
			QPainter.RenderHint.Antialiasing
		)

		process_len = max(
			sum(self.elements.values()),
			1
		)

		layout = self._compute_layout(
			process_len
		)

		self._draw_headers(p)

		self._draw_tanks(
			p,
			layout
		)

		self._draw_ribbon(
			p,
			layout
		)

	def draw_reel(self, p, x, y, diameter, angle=0.0):
		"""Draw a film reel with rotating holes."""

		center_x = x + diameter / 2
		center_y = y + diameter / 2

		# Cercle extérieur
		p.drawEllipse(
			QRectF(
				x,
				y,
				diameter,
				diameter
			)
		)

		# Moyeu central
		hub_diameter = diameter * 0.05

		p.drawEllipse(
			QRectF(
				center_x - hub_diameter / 2,
				center_y - hub_diameter / 2,
				hub_diameter,
				hub_diameter
			)
		)

		hole_radius = diameter * 0.1
		hole_distance = diameter * 0.28

		for i in range(5):

			a = math.radians(
				i * 72
				- 90
				+ angle
			)

			hx = (
				center_x
				+ math.cos(a) * hole_distance
			)

			hy = (
				center_y
				+ math.sin(a) * hole_distance
			)

			# Trou
			p.drawEllipse(
				QRectF(
					hx - hole_radius,
					hy - hole_radius,
					hole_radius * 2,
					hole_radius * 2
				)
			)

	def update_data(
		self,
		elements,
		ribbon,
		position,
		supply_length,
		received_length
	):
		self.elements = elements
		self.ribbon = ribbon
		self.position = position

		self.supply_length = supply_length
		self.received_length = received_length

		self.update()



# ============================================================
# Main application window
# ============================================================

class Main(QWidget):
	"""
	Main application window.

	Coordinates user interactions, RibbonModel updates
	and ProcessWidget rendering.
	"""

	def __init__(self):
		super().__init__()

		self.model = RibbonModel()

		self.received_film=0.0
		self.received_leader=0.0

		self.timer=QTimer()
		self.timer.timeout.connect(self.tick)

		self.build()
		self.load()

	def build(self):
		self.setWindowTitle("Film Tracker V5")

		root=QVBoxLayout(self)

		tabs=QTabWidget()
		root.addWidget(tabs)

		process_tab=QWidget()
		settings_tab=QWidget()

		tabs.addTab(process_tab,"Process")
		tabs.addTab(settings_tab,"Settings")

		process=QVBoxLayout(process_tab)

		# PARAMS
		params = QHBoxLayout()

		self.speed = QDoubleSpinBox()
		self.speed.setMaximum(10000)
		self.speed.setSuffix(" ft/min")
		self.speed.setMaximumWidth(120)

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

		params.addSpacing(20)

		params.addWidget(QLabel("Film"))
		params.addWidget(self.film_length)

		params.addSpacing(20)

		params.addWidget(QLabel("Leader"))
		params.addWidget(self.leader_length)

		params.addStretch()

		process.addLayout(params)

		btns=QHBoxLayout()
		for txt,fn in [
			("Add Film",self.add_film),
			("Start",self.start),
			("Pause",self.pause),
			("Reset",self.reset),
			("Clear Reel",self.clear_receiving_reel)
		]:
			b=QPushButton(txt)
			b.clicked.connect(fn)
			btns.addWidget(b)

		process.addLayout(btns)

		# INFO
		info_group = QGroupBox()
		info_group.setContentsMargins(0, 20, 0, 20)
		info_layout = QHBoxLayout(info_group)

		# Queue
		queue_layout = QVBoxLayout()
		self.queue_label = QTextEdit()
		self.queue_label.setReadOnly(True)
		queue_layout.addWidget(self.queue_label)
		info_layout.addLayout(queue_layout, 1)

		# Processing
		processing_layout = QVBoxLayout()
		self.processing_label = QTextEdit()
		self.processing_label.setReadOnly(True)
		processing_layout.addWidget(self.processing_label)
		info_layout.addLayout(processing_layout, 1)

		# Receiving
		receiving_layout = QVBoxLayout()
		self.receiving_label = QTextEdit()
		self.receiving_label.setReadOnly(True)
		receiving_layout.addWidget(self.receiving_label)
		info_layout.addLayout(receiving_layout, 1)

		info_group.setFixedHeight(220)
		process.addWidget(info_group)

		self.view=ProcessWidget()
		self.view.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Expanding)
		process.addWidget(self.view,1)

		# Tanks settings
		settings=QFormLayout(settings_tab)
		self.inputs={}

		for e in ELEMENTS:
			sp=QDoubleSpinBox()
			sp.setMaximum(1000)
			sp.setSuffix(" m")
			self.inputs[e]=sp
			settings.addRow(e,sp)

	def elements(self):
		return {k:v.value() for k,v in self.inputs.items()}

	def add_film(self):
		"""
		Add a new film and its leader to the ribbon.
		"""

		self.model.add_film(
			self.film_length.value(),
			self.leader_length.value()
		)

		self.refresh()

	def ribbon_length(self):
		return self.model.ribbon_length()
	
	def tick(self):
		step = (
			self.speed.value()
			* 0.3048
			/ 60.0
			/ 20.0
		)

		self.model.processed_length += step

		self.view.supply_angle += step * 300

		self.refresh()

	def machine_length(self):
		return sum(self.elements().values())

	## Buttons

	def start(self):
		self.timer.start(50)

	def pause(self):
		self.timer.stop()

	def reset(self):
		self.timer.stop()
		self.model.segments.clear()
		self.received_film=0.0
		self.received_leader=0.0
		self.model.next_film_id = 1
		self.model.processed_length=0.0
		self.model.receiving_offset=0.0

		self.refresh()

	def clear_receiving_reel(self):

		self.model.receiving_offset = max(
			0,
			self.model.processed_length - self.machine_length()
		)

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

		# Queue
		self.queue_label.setPlainText(
			self.model.build_segment_list(
				queue_start,
				queue_end,
				"Queue",
				600
			)
		)

		# Processing
		self.processing_label.setPlainText(
			self.model.build_segment_list(
				machine_start,
				machine_end,
				"Processing",
				self.machine_length(),
				self.speed.value()
			)
		)

		# Receiving
		self.receiving_label.setPlainText(
			self.model.build_segment_list(
				receiving_start,
				receiving_end,
				"Receiving",
				600
			)
		)

		total_queue = max(
			0,
			self.ribbon_length() - self.model.processed_length
		)

		self.view.update_data(
			self.elements(),
			self.model.segments,
			self.model.processed_length,
			total_queue,
			self.received_film + self.received_leader
		)

		self.save()

	def save(self):
		data={
			"speed":self.speed.value(),
			"film_length":self.film_length.value(),
			"leader_length":self.leader_length.value(),
			"elements":self.elements()
		}
		with open(SETTINGS,"w") as fp:
			json.dump(data,fp,indent=2)

	def load(self):
		if not os.path.exists(SETTINGS):
			return

		with open(SETTINGS) as fp:
			data=json.load(fp)

		self.speed.setValue(data.get("speed",25))
		self.film_length.setValue(data.get("film_length",300))
		self.leader_length.setValue(data.get("leader_length",3))

		for k,v in data.get("elements",{}).items():
			if k in self.inputs:
				self.inputs[k].setValue(v)

		self.model.processed_length = 0
		self.refresh()

app=QApplication([])
app.setStyle("Fusion")
w=Main()
w.showMaximized()
app.exec()
