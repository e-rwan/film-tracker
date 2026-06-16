# utils/lang.py

from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent
LANG_DIR = PROJECT_DIR / "lang"

class Lang:

	def __init__(self):
		self._translations = {}

	def load(self, language="fr"):

		lang_file = LANG_DIR / f"{language}.lang"

		global translations

		self._translations = {}

		with open(lang_file, encoding="utf-8") as f:

			for line in f:

				line = line.strip()

				if (
					not line
					or line.startswith("#")
				):
					continue

				key, value = line.split(
					"=",
					1
				)

				self._translations[key.strip()] = (
					value.strip()
				)


	def tr(self, key, **kwargs):

		text = self._translations.get(
			key,
			key
		)

		try:
			return text.format(
				**kwargs
			)

		except KeyError:
			return text

# singleton
lang = Lang()