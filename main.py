# main.py

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon


from ui.main_window import MainWindow

from utils.lang import lang
from utils.constants import ICON_PATH

def main():

	lang.load("fr")

	app = QApplication([])

	app.setStyle("Fusion")
	app.setWindowIcon(QIcon(ICON_PATH))

	window = MainWindow()
	window.showMaximized()

	app.exec()


if __name__ == "__main__":
	main()