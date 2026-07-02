# model/ribbon_model.py

from model.segment import Segment
from model.tank import Tank

class RibbonModel:
	"""
	Business model representing the ribbon state.

	Responsible for:
	- storing film and leader segments,
	- tracking ribbon progression through the machine,
	- detecting completed films,
	- calculating Queue, Processing and Receiving zones.
	"""

	def __init__(self):
		self.tanks: list[Tank] = []

		self.segments = []

		self._next_segment_id = 1
		self._next_film_id = 1

		self.processed_length = 0.0
		self.receiving_offset = 0.0

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

	def add_film(
		self,
		film_length,
		leader_length,
		film_name=None,
		attach=False
	):
		"""Add a new film and its leader."""

		if attach:
			queue_length = max(
				0,
				self.ribbon_length() - self.processed_length
			)

			# Queue already contains ribbon
			if queue_length > 0 or not self.segments:
				attach = False

		if not attach:
			last_film_end = None

			for seg, seg_start, seg_end in self.iter_segments():
				if seg.is_film:
					last_film_end = seg_end

			if last_film_end is not None:

				free_leader = (
					self.processed_length
					- last_film_end
				)

				if free_leader > 0:
					self.segments.append(
						Segment.leader(
							free_leader,
							self.next_segment_id()
						)
					)

		if not film_name:
			film_name = (
				f"film {self.next_film_id()}"
			)

		if film_length > 0:
			self.segments.append(
				Segment.film(
					film_length,
					self.next_segment_id(),
					film_name
				)
			)

		if leader_length > 0:
			self.segments.append(
				Segment.leader(
					leader_length,
					self.next_segment_id()
				)
			)

	def add_separator(self, name):
		self.segments.append(
			Segment.separator(
				name,
				self.next_segment_id()
			)
		)

	def get_received_lengths(self, machine_length):
		"""
		Calculate the visible film and leader lengths
		currently present on the receiving reel.
		"""
		film = 0.0
		leader = 0.0
		received_position = self.processed_length - machine_length

		for seg, seg_start, seg_end in self.iter_segments():
			received = min(seg.length, max(0, received_position - seg_start))

			if seg.is_film:
				film += received
			else:
				leader += received

		total_received = film + leader

		if total_received <= 0:
			return 0.0, 0.0

		# Retirer receiving_offset proportionnellement à film/leader réels
		offset = min(self.receiving_offset, total_received)

		ratio = 1.0 - (offset / total_received)

		return film * ratio, leader * ratio

	def machine_length(self):
		return sum(tank.length for tank in self.tanks)


	def add_tank(self, name, length=1.0, color="#808080"):

		self.tanks.append(
			Tank(
				name=name,
				length=length,
				color=color,
			)
		)

	def update_tank_name(self, index, name):
		if 0 <= index < len(self.tanks):
			self.tanks[index].name = name

	def update_tank_length(self, index, length):
		if 0 <= index < len(self.tanks):
			self.tanks[index].length = length

	def set_tank_color(self, index, color):
		if 0 <= index < len(self.tanks):
			self.tanks[index].color = color

	def remove_tank(self, index):
		if len(self.tanks) <= 1:
			return False

		if 0 <= index < len(self.tanks):
			self.tanks.pop(index)
			return True

		return False

	def move_tank(self, index, offset):
		new_index = index + offset

		if (
			index < 0
			or new_index < 0
			or index >= len(self.tanks)
			or new_index >= len(self.tanks)
		):
			return False

		self.tanks[index], self.tanks[new_index] = (
			self.tanks[new_index],
			self.tanks[index],
		)
		return True

	def get_segment_by_id(self, segment_id):
		for segment in self.segments:
			if segment.id == segment_id:
				return segment
		return None

	def delete_segment_by_id(self, segment_id):
		segment = self.get_segment_by_id(segment_id)
		if segment is None:
			return None

		index = next(
			i
			for i, current in enumerate(self.segments)
			if current is segment
		)
		del self.segments[index]

		if not self.segments:
			return None

		index = min(index, len(self.segments) - 1)
		return self.segments[index]

	def move_segment_by_id(self, segment_id, offset):
		segment = self.get_segment_by_id(segment_id)
		if segment is None:
			return False

		index = next(
			i
			for i, current in enumerate(self.segments)
			if current is segment
		)
		new_index = index + offset

		if new_index < 0 or new_index >= len(self.segments):
			return False

		self.segments[index], self.segments[new_index] = (
			self.segments[new_index],
			self.segments[index],
		)
		return True

	def update_segment_by_id(self, segment_id, name, length):
		segment = self.get_segment_by_id(segment_id)
		if segment is None:
			return None

		segment.length = length

		if segment.is_film:
			segment.name = name
		elif segment.is_separator:
			segment.name = name

		return segment

	def build_zone_rows(
		self,
		zone_start,
		zone_end,
		zone_name,
		speed_ft_min=None,
		queue_entry_position=None,
		queue_exit_position=None,
	):
		rows = []

		for seg, seg_start, seg_end in self.iter_segments():
			visible = max(0, min(seg_end, zone_end) - max(seg_start, zone_start))
			if visible <= 0:
				continue

			eta = ""
			eta_in = ""

			if speed_ft_min and seg.is_film and queue_exit_position is not None:
				eta = self.get_remaining_time(
					seg_end,
					queue_exit_position,
					speed_ft_min,
				)

				if queue_entry_position is not None:
					eta_in = self.get_remaining_time(
						seg_end,
						queue_entry_position,
						speed_ft_min,
					)

			row = {
				"zone": zone_name,
				"segment": seg,
				"visible": visible,
			}

			if zone_name == "queue" and eta_in:
				row["OUT"] = f"{eta_in} ({eta})"
			else:
				row["OUT"] = eta

			rows.append(row)

		return rows

	def reset_runtime(self):
		self.segments.clear()
		self._next_film_id = 1
		self.processed_length = 0.0
		self.receiving_offset = 0.0

	def get_remaining_time(
		self,
		position,
		target_position,
		speed_ft_min
	):

		"""
		Return remaining time before 'position'
		reaches 'target_position'.
		"""

		speed_m_min = speed_ft_min * 0.3048

		if speed_m_min <= 0:
			return "--:--"

		remaining_length = (
			position
			- target_position
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
						seg.id,
						seg.name
					)
				)
			else:
				new_segments.append(
					Segment.leader(
						remaining,
						self.next_segment_id()
					)
				)

		self.segments = new_segments

	def next_segment_id(self):

		segment_id = self._next_segment_id

		self._next_segment_id += 1

		return segment_id

	def next_film_id(self):

		film_id = self._next_film_id

		self._next_film_id += 1

		return film_id

	def time_until_position(self, position, speed_m_s):
		"""
		Return the remaining time (in seconds) before processed_length
		reaches the given ribbon position.
		"""

		if speed_m_s <= 0:
			return None

		remaining = max(
			0,
			position - self.processed_length
		)

		return remaining / speed_m_s

