# utils/constants.py


import sys
from typing import Final
from pathlib import Path


def get_base_path() -> Path:
    if getattr(sys, 'frozen', False):
        # Exécutable compilé (PyInstaller)
        return Path(sys.executable).parent
    else:
        # Script lancé en mode normal
        return Path(__file__).resolve().parent


BASE_PATH: Final[Path] = get_base_path()

ICON_PATH: Final[str] = str(BASE_PATH / "ressources" / "filmtracker.png")
SETTINGS_FILE = "film_tracker_settings.json"
