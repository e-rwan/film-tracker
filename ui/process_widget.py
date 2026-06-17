# process_widget.py

import math

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from model.tank import Tank
from utils.lang import lang

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
		self.tanks: list[Tank] = []
		self.ribbon=[]
		self.position=0.0
		self.speed_ft_min = 0

		self.supply_length=0.0
		self.received_length=0.0

		self.selected_segment = None

		self.setMinimumHeight(300)

		self.reel_angle = 0.0

	def _draw_reels(self, p):
		"""Draw reel labels and reels."""
		p.drawText(20,40, lang.tr("supply_reel"))
		self.draw_reel(p, 20, 55, 70, self.reel_angle)

		p.drawText(self.width()-90,40, lang.tr("receiving_reel"))
		self.draw_reel(p, self.width()-90, 55, 70, self.reel_angle)

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
			"tank_h": 100,
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

		for tank in self.tanks:

			name = tank.name
			length = tank.length

			sw = process_w * length / process_len

			rect = QRectF(
				curx,
				y,
				sw,
				h
			)

			p.fillRect(
				rect,
				tank.color
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
		h = layout["tank_h"]

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

			# SEPARATOR
			if seg.is_separator:
				x = x1
				pen = QPen(
					QColor(200, 200, 200)
				)
				if seg is self.selected_segment:
					pen = QPen(
						QColor(0, 255, 0)
					)
				pen.setWidth(2)
				p.setPen(pen)
				p.drawLine(
					int(x),
					y + h / 2 - 15,
					int(x),
					y + h / 2 + 55
				)
				font = p.font()
				p.setFont(font)
				text_width = (
					p.fontMetrics()
					.horizontalAdvance(seg.name)
				)
				p.drawText(
					int(x - text_width / 2),
					int(y + h / 2 - 20),
					seg.name
				)
				continue

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

			if seg is self.selected_segment:
				pen = QPen(
					QColor(
						255,
						0,
						0
					)
				)
				p.setBrush(
					QColor(
						200,
						60,
						20,
						120
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
					y + h/2,
					x2 - x1,
					40
				)
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

		if not self.tanks:
			return

		process_x = layout["process_x"]
		process_w = layout["process_w"]

		y = layout["tank_y"] + layout["tank_h"] + 20

		table_h = 70

		count = len(self.tanks)

		if count <= 0:
			return

		cell_w = process_w / count

		speed_m_min = self.speed_ft_min * 0.3048

		for index, tank in enumerate(self.tanks):

			name = tank.name
			length = tank.length

			x = process_x + index * cell_w

			rect = QRectF(
				x,
				y,
				cell_w,
				table_h
			)

			# background
			base_color = QColor(tank.color)
			table_color = self._darken_color(
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

	def paintEvent(self, e):
		"""
		Render the machine, reels and ribbon position.
		"""

		if not self.tanks:
			return

		p = QPainter(self)

		p.setRenderHint(
			QPainter.RenderHint.Antialiasing
		)

		process_len = max(
			sum(
				tank.length
				for tank in self.tanks
			),
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

	def draw_reel(self, p, x, y, diameter, angle=0.0):
		"""Draw a film reel with rotating holes."""

		center_x = x + diameter / 2
		center_y = y + diameter / 2

		# external circle
		p.drawEllipse(
			QRectF(
				x,
				y,
				diameter,
				diameter
			)
		)

		# side holes
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
			# central hole
			p.drawEllipse(
				QRectF(
					hx - hole_radius,
					hy - hole_radius,
					hole_radius * 2,
					hole_radius * 2
				)
			)

	def set_selected_segment(self, segment):

		self.selected_segment = segment
		self.update()

	def _darken_color(self, color, factor=0.45):
		"""
		Return a darker version of a color while
		preserving its hue and saturation.
		"""

		h, s, v, a = color.getHsv()

		if v > 100:
			v = int(v * factor)

		return QColor.fromHsv(
			h,
			s,
			v,
			a
		)

	def update_data(
		self,
		tanks: list[Tank],
		ribbon,
		position,
		supply_length,
		received_length,
		speed_ft_min
	):
		self.tanks = tanks
		self.ribbon = ribbon
		self.position = position
		self.speed_ft_min = speed_ft_min

		self.supply_length = supply_length
		self.received_length = received_length

		self.update()