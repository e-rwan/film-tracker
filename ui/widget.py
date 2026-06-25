# ui/wiget.py

from PySide6.QtWidgets import (
	QFrame,
	QVBoxLayout,
	QWidget
)

def create_vline(line = True, Vmargin = 30, Hmargin = 0):

	container = QWidget()

	layout = QVBoxLayout(container)
	layout.setContentsMargins(
		Vmargin, Hmargin, Vmargin, Hmargin
	)

	if(line):
		line = QFrame()

		line.setFrameShape(
			QFrame.Shape.VLine
		)

		line.setFrameShadow(
			QFrame.Shadow.Sunken
		)

		layout.addWidget(line)

	return container