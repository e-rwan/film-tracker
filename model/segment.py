# segment.py

from dataclasses import dataclass


@dataclass(eq=False)
class Segment:
	"""
	Represents a continuous section of ribbon.

	A segment can be either a film or a leader.
	Segments are stored in RibbonModel in their physical order
	along the ribbon.
	"""

	type: str
	length: float
	id: int
	name: str | None = None

	@classmethod
	def film(cls, length, segment_id, film_name):
		return cls(
			"film",
			length,
			segment_id,
			film_name
		)

	@classmethod
	def leader(cls, length, segment_id):
		return cls(
			"leader",
			length,
			segment_id
		)

	@property
	def is_film(self):
		return self.type == "film"

	@property
	def is_lead(self):
		return self.type == "leader"