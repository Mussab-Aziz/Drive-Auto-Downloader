"""
Entry point for the packaged Google Drive Downloader application.

PyInstaller compiles this file as the executable's entry point.
It starts the FastAPI/uvicorn server which also serves the React
frontend as static files, then opens the default browser.
"""

import os
import sys
import webbrowser
import threading
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# When frozen by PyInstaller the backend directory is unpacked to _MEIPASS.
# We need to add it to sys.path so that `import server` (and its siblings)
# resolve correctly.
# ---------------------------------------------------------------------------
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    _base = Path(sys._MEIPASS)  # type: ignore[attr-defined]
else:
    _base = Path(__file__).resolve().parent / "backend"

if str(_base) not in sys.path:
    sys.path.insert(0, str(_base))

# ---------------------------------------------------------------------------
# When built with console=False, sys.stdout and sys.stderr are None.
# Uvicorn's DefaultFormatter calls stream.isatty() during log setup, which
# raises AttributeError -> ValueError.  Redirect to devnull to prevent this.
# ---------------------------------------------------------------------------
if getattr(sys, "frozen", False):
    _devnull = open(os.devnull, "w")
    if sys.stdout is None:
        sys.stdout = _devnull
    if sys.stderr is None:
        sys.stderr = _devnull

import uvicorn  # noqa: E402  (import after path manipulation)


def _open_browser():
    """Wait for the server to boot then open the browser."""
    time.sleep(2)
    webbrowser.open("http://127.0.0.1:8000")


if __name__ == "__main__":
    # Launch browser in a background thread so it doesn't block uvicorn
    threading.Thread(target=_open_browser, daemon=True).start()

    uvicorn.run(
        "server:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
        log_config=None,
        log_level="warning",
        access_log=False,
    )
