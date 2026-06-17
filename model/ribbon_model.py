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

	def add_film(self, film_length, leader_length, film_name=None):
		"""Add a new film and its leader to the ribbon."""
		last_film_end = None

		for seg, seg_start, seg_end in self.iter_segments():
			if seg.is_film:
				last_film_end = seg_end

		if last_film_end is not None:
			free_leader = self.processed_length - last_film_end

			if free_leader > 0:
				self.segments.append(Segment.leader(free_leader, self.next_segment_id()))

		if not film_name:
			film_name = f"film {self.next_film_id()}"

		if film_length > 0:
			self.segments.append(Segment.film(film_length, self.next_segment_id(), film_name))
		if leader_length > 0:
			self.segments.append(Segment.leader(leader_length, self.next_segment_id()))

	def attach_film(self, film_length, leader_length, film_name=None):
		"""
		Add a film immediately after the last existing segment.
		"""

		queue_length = max(
			0,
			self.ribbon_length() - self.processed_length
		)

		# Something already waiting in queue or No ribbon yet
		if queue_length > 0 or not self.segments:
			self.add_film(
				film_length,
				leader_length,
				film_name
			)
			return

		if not film_name:
			film_name = f"film {self.next_film_id()}"

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

	def build_segment_list(self, zone_start, zone_end, title, total_length:float = 600.0, speed_ft_min: float | None = None):
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
				f"{seg.name} : "
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

