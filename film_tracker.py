import json
import os
import math

from PySide6.QtCore import QRectF, QTimer, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QGuiApplication, QFont
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
	QFrame
)

# ============================================================
# ARCHITECTURE OVERVIEW
# ============================================================
#
# Segment
# -------
# Represents a physical ribbon segment.
#
# Types:
#     - film
#     - leader
#
# Attributes:
#     type      : segment type
#     length    : segment length in meters
#     id        : film identifier (film only)
#
# Helpers:
#     film()    : create a film segment
#     leader()  : create a leader segment
#     is_film   : convenience property
#
#
# RibbonModel
# -----------
# Pure business logic.
#
# Responsibilities:
#     - store ribbon segments
#     - manage ribbon progression
#     - calculate Queue / Processing / Receiving zones
#     - calculate receiving reel contents
#     - calculate remaining processing times
#
# State:
#     segments
#     processed_length
#     receiving_offset
#     next_film_id
#
# Methods:
#     ribbon_length()
#         Return total ribbon length.
#
#     iter_segments()
#         Iterate over ribbon segments and return:
#         (segment, start_position, end_position)
#
#     add_film()
#         Append a film and its leader.
#
#     get_received_lengths()
#         Calculate visible film and leader lengths
#         on the receiving reel.
#
#     get_remaining_time()
#         Calculate remaining processing time before
#         a film exits the machine.
#
#     build_segment_list()
#         Generate textual information for Queue,
#         Processing and Receiving panels.
#
#
# ProcessWidget
# -------------
# Machine visualization widget.
#
# Responsibilities:
#     - draw reels
#     - draw machine tanks
#     - draw ribbon position
#     - display supply and receiving reel lengths
#
# Rendering helpers:
#     _compute_layout()
#         Calculate drawing geometry.
#
#     _draw_headers()
#         Draw reels and reel lengths.
#
#     _draw_tanks()
#         Draw machine tanks and labels.
#
#     _draw_ribbon()
#         Draw visible ribbon segments.
#
#     _draw_reels()
#         Draw supply and receiving reels.
#
# Public methods:
#     paintEvent()
#         Main rendering entry point.
#
#     draw_reel()
#         Draw a single reel.
#
#     update_data()
#         Update displayed data and trigger repaint.
#
#
# Main
# ----
# Main application window and controller.
#
# Responsibilities:
#     - create user interface
#     - manage user actions
#     - drive simulation
#     - synchronize UI and RibbonModel
#     - save/load settings
#
# Methods:
#     build()
#         Create the user interface.
#
#     elements()
#         Return machine element lengths.
#
#     machine_length()
#         Return total machine length.
#
#     ribbon_length()
#         Return total ribbon length.
#
#     add_film()
#         Add a film to the ribbon.
#
#     tick()
#         Advance ribbon position.
#
#     start()
#         Start simulation.
#
#     pause()
#         Pause simulation.
#
#     reset()
#         Reset application state.
#
#     clear_receiving_reel()
#         Clear received ribbon history.
#
#     refresh()
#         Refresh calculations and displays.
#
#     save()
#         Save settings to disk.
#
#     load()
#         Load settings from disk.
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

	@property
	def is_lead(self):
		return self.type == "leader"


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

	def attach_film(self, film_length, leader_length):
		"""
		Add a film immediately after the last existing segment.

		Unlike add_film(), no extra free leader is inserted
		between the previous film and the new one.

		If queue already contains ribbon, fallback to add_film().
		"""

		queue_length = max(
			0,
			self.ribbon_length() - self.processed_length
		)

		# Something already waiting in queue
		if queue_length > 0:
			self.add_film(
				film_length,
				leader_length
			)
			return

		# No ribbon yet
		if not self.segments:
			self.add_film(
				film_length,
				leader_length
			)
			return

		self.segments.append(
			Segment.film(
				film_length,
				self.next_film_id
			)
		)

		self.segments.append(
			Segment.leader(
				leader_length
			)
		)

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


			if visible <= 0:
				continue

			if seg.is_lead:
				film_lines.append(
					f"Leader : "
					f"{visible:.1f} / "
					f"{seg.length:.1f} m"
				)
				occupied_length += visible
				continue

			remaining_text = ""
			if (
				(title == "Processing" or title == "Queue")
				and speed_ft_min is not None
			):
				remaining_text = (
					f"  -  Remaining : "
					f"{self.get_remaining_time(
						seg_end,
						total_length,
						speed_ft_min
					)}"
				)
			
			film_lines.append(
				f"{f' Film {seg.id} : '}"
				f"{visible :.1f} / "
				f"{seg.length:.1f} m"
				f"{remaining_text}"
			)

			occupied_length += visible

		if(title == "Processing" ):
			lines = [f"{title} : {occupied_length:.1f} / {total_length:.1f} m", ""]
		else:
			lines = [f"{title} : {occupied_length:.1f}"]

		lines.extend(film_lines)

		return "\n".join(lines)


	def clear_supply_reel(self):
		"""
		Remove everything still waiting in queue.

		Keep only the portion already engaged
		in the machine or already received.
		"""

		new_segments = []

		for seg, seg_start, seg_end in self.iter_segments():

			remaining = min(
				seg.length,
				max(
					0,
					self.processed_length - seg_start
				)
			)

			if remaining <= 0:
				continue

			if remaining >= seg.length:
				new_segments.append(seg)
				continue

			if seg.is_film:
				new_segments.append(
					Segment.film(
						remaining,
						seg.id
					)
				)
			else:
				new_segments.append(
					Segment.leader(
						remaining
					)
				)

		self.segments = new_segments



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

def darken_color(color, factor=0.45):
	"""
	Return a darker version of a color while
	preserving its hue and saturation.
	"""

	h, s, v, a = color.getHsv()

	v = int(v * factor) if v > 100 else v

	return QColor.fromHsv(
		h,
		s,
		v,
		a
	)


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
		self.speed_ft_min = 0

		self.supply_length=0.0
		self.received_length=0.0

		self.setMinimumHeight(650)

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
				darken_color(color_for(name), 0.8)
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
			anchor_y = y - 10

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

		self._draw_tank_table(
			p,
			layout
		)

		self._draw_ribbon(
			p,
			layout
		)

	def _draw_tank_table(self, p, layout):
		"""
		Draw process information table.

		Each tank gets the same width.
		Displays:
			- tank name
			- length
			- processing time
		"""

		if not self.elements:
			return

		process_x = layout["process_x"]
		process_w = layout["process_w"]

		y = layout["tank_y"] + layout["tank_h"] + 20

		table_h = 70

		count = len(self.elements)

		if count <= 0:
			return

		cell_w = process_w / count

		speed_m_min = self.speed_ft_min * 0.3048

		for index, (name, length) in enumerate(self.elements.items()):

			x = process_x + index * cell_w

			rect = QRectF(
				x,
				y,
				cell_w,
				table_h
			)

			# background
			base_color = color_for(name)
			table_color = darken_color(
				base_color,
				0.45
			)

			p.fillRect(
				rect,
				table_color
			)

			# contour
			p.setPen(QColor(120, 120, 120))
			p.drawRect(rect)

			# duration
			if speed_m_min > 0:
				duration_sec = length / speed_m_min * 60

				minutes = int(duration_sec // 60)
				seconds = int(duration_sec % 60)

				duration_text = f"{minutes:02d}:{seconds:02d}"
			else:
				duration_text = "--:--"

			p.setPen(Qt.GlobalColor.white)

			# nom
			p.drawText(
				QRectF(x, y + 4, cell_w, 20),
				Qt.AlignmentFlag.AlignCenter,
				name
			)

			# longueur
			p.drawText(
				QRectF(x, y + 24, cell_w, 20),
				Qt.AlignmentFlag.AlignCenter,
				f"{length:.2f} m"
			)

			# durée
			p.drawText(
				QRectF(x, y + 44, cell_w, 20),
				Qt.AlignmentFlag.AlignCenter,
				duration_text
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
		received_length,
		speed_ft_min
	):
		self.elements = elements
		self.ribbon = ribbon
		self.position = position
		self.speed_ft_min = speed_ft_min

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

		params.addSpacing(20)
		
		b=QPushButton("Add to queue")
		b.clicked.connect(self.add_film)
		params.addWidget(b)

		b=QPushButton("Attach to film")
		b.clicked.connect(self.attach_to_film)
		params.addWidget(b)

		params.addStretch()

		process.addLayout(params)

		# Play/pause, forward/backward button
		btnsPlay=QHBoxLayout()

		self.move_left_btn = QPushButton("Step backward")
		self.move_left_btn.clicked.connect(
			lambda: self.move_ribbon(-1)
		)
		btnsPlay.addWidget(self.move_left_btn)
		self.move_left_btn.setToolTip(
			"Move ribbon -1 m (Ctrl = -10 m)"
		)

		self.start_pause_btn = QPushButton("Start")
		self.start_pause_btn.clicked.connect(
			self.toggle_simulation
		)
		btnsPlay.addWidget(self.start_pause_btn)
		self.start_pause_btn.setToolTip(
			"Start|Pause simulation"
		)

		self.move_right_btn = QPushButton("Step forward")
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

		# Clear/reset buttons
		btnsClear=QHBoxLayout()

		line = QFrame()
		line.setFrameShape(QFrame.Shape.VLine)
		line.setFrameShadow(QFrame.Shadow.Sunken)
		btnsClear.addWidget(line)

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
		b.clicked.connect(self.clear_receiving_reel)
		btnsClear.addWidget(b)
		b.setToolTip(
			"Empty receiving queue list"
		)

		process.addLayout(btnsClear)

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

	def attach_to_film(self):
		"""
		Attach a film directly behind the last film already
		in the machine.

		If queue already contains ribbon, fallback to the
		normal queue insertion.
		"""

		self.model.attach_film(
			self.film_length.value(),
			self.leader_length.value()
		)

		self.refresh()

	def ribbon_length(self):
		return self.model.ribbon_length()

	def toggle_simulation(self):

		if self.timer.isActive():

			self.timer.stop()

			self.start_pause_btn.setText(
				"Start"
			)

		else:

			self.timer.start(50)

			self.start_pause_btn.setText(
				"Pause"
			)

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
			min(
				self.model.processed_length,
				self.ribbon_length()
			)
		)

		self.refresh()

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
	def reset(self):
		self.start_pause_btn.setText("Start")
		self.model.segments.clear()
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

		# QUEUE
		self.update_text_edit(
			self.queue_label,
			self.model.build_segment_list(
				queue_start,
				queue_end,
				"Queue",
				self.machine_length(),
				self.speed.value()
			)
		)

		# PROCESSING
		self.update_text_edit(
			self.processing_label,
			self.model.build_segment_list(
				machine_start,
				machine_end,
				"Processing",
				self.machine_length(),
				self.speed.value()
			)
		)

		# RECEIVING
		self.update_text_edit(
			self.receiving_label,
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
			self.received_film + self.received_leader,
			self.speed.value()
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
