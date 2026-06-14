# main.py

from PySide6.QtWidgets import QApplication

from ui.main_window import MainWindow


def main():

	app = QApplication([])

	app.setStyle("Fusion")

	window = MainWindow()
	window.showMaximized()

	app.exec()


if __name__ == "__main__":
	main()