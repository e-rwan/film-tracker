# ui/wiget.py

from PySide6.QtWidgets import (
	QFrame,
	QLayout,
	QVBoxLayout,
	QWidget
)


def clear_layout(layout: QLayout):

	while layout.count():
		item = layout.takeAt(0)

		if item is None:
			continue

		widget = item.widget()
		child_layout = item.layout()

		if child_layout is not None:
			clear_layout(child_layout)
			continue

		if widget is not None:
			widget.deleteLater()




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