# main.py

from PySide6.QtWidgets import QApplication

from ui.main_window import MainWindow

from utils.lang import lang

def main():

	lang.load("fr")

	app = QApplication([])

	app.setStyle("Fusion")

	window = MainWindow()
	window.showMaximized()

	app.exec()


if __name__ == "__main__":
	main()