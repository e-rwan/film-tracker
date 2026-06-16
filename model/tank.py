# model/tank.py

from dataclasses import dataclass, asdict


@dataclass
class Tank:
	"""
	Represents a machine section.

	The order of Tank objects inside the list
	defines the physical order of the machine.
	"""

	name: str
	length: float
	color: str = "#808080"

	def to_dict(self):
		return asdict(self)

	@classmethod
	def from_dict(cls, data):
		return cls(
			name=data.get("name", ""),
			length=float(data.get("length", 0)),
			color=data.get("color", "#808080")
		)