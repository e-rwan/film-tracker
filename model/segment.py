# segment.py

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
	name: str | None = None

	@classmethod
	def film(cls, length, film_id, film_name):
		return cls(
			"film",
			length,
			film_id,
			film_name
		)

	@classmethod
	def leader(cls, length):
		return cls(
			"leader",
			length
		)

	@property
	def is_film(self):
		return self.type == "film"

	@property
	def is_lead(self):
		return self.type == "leader"