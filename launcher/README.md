# Open CopyCat with one click (Windows)

1. Set the project up once, as described in the main [README](../README.md) (Python 3.11+, `.venv`,
   `pip install -r requirements.txt`, and a `.env` copied from `.env.example`).
   For the real AI, put your own keys in `.env` and set `MOCK_MODE=0`; with `MOCK_MODE=1` it uses the example data.
2. Double-click `launcher/make-desktop-shortcut.bat`. A **CopyCat** shortcut with an orange "C" icon appears on your desktop.
3. From now on, double-click the shortcut. It starts the server (in a minimised window) if it is not running yet
   and opens http://localhost:8000 in your browser.

To stop CopyCat, close the minimised window called "CopyCat server".

The shortcut points at the files in this folder, so if you move the repo, run `make-desktop-shortcut.bat` again.
Your keys stay in your own `.env`, which is never committed.
