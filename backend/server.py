"""
FastAPI backend server for Google Drive Download Automation.
Wraps the existing GoogleDriveDownloader and exposes REST + SSE endpoints
for the React frontend UI.
"""

import asyncio
import json
import queue
import threading
import sys
import webbrowser
from pathlib import Path
from typing import Optional
from contextlib import asynccontextmanager
import tkinter as tk
from tkinter import filedialog

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel


def get_base_path() -> Path:
    """Return the base directory for data files.

    When running as a PyInstaller bundle, sys._MEIPASS points to the
    temporary directory where assets are unpacked.  During normal
    development the base path is simply the directory that contains
    this file.
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent

from enhanced_downloader import GoogleDriveDownloader

# ─── App Setup ──────────────────────────────────────────────────────────────

async def _open_browser_async():
    """Wait briefly for uvicorn to be ready then open the browser."""
    await asyncio.sleep(1)
    webbrowser.open("http://127.0.0.1:8000")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan – opens the browser when running as a frozen app."""
    if getattr(sys, "frozen", False):
        asyncio.create_task(_open_browser_async())
    yield


app = FastAPI(title="Drive Download Automation API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_PATH = get_base_path()
CONFIG_PATH = BASE_PATH / "ui_config.json"



# ─── Global Download State ────────────────────────────────────────────────────

class DownloadState:
    def __init__(self):
        self.is_downloading = False
        self.cancel_event = threading.Event()
        self.log_queue: queue.Queue = queue.Queue()
        self.downloader: Optional[GoogleDriveDownloader] = None

    def reset(self):
        self.cancel_event.clear()
        # Drain the queue
        while not self.log_queue.empty():
            try:
                self.log_queue.get_nowait()
            except queue.Empty:
                break

state = DownloadState()
# Lock that makes the is_downloading check-and-set in start_download atomic
# so simultaneous API calls cannot both pass the guard and spawn two threads.
_download_lock = threading.Lock()

# ─── Pydantic Models ──────────────────────────────────────────────────────────

class Config(BaseModel):
    source_folder_id: str = ""
    destination_folder: str = ""
    secret_file: str = ""
    skip_photos: bool = False
    skip_videos: bool = False
    skip_audio: bool = False
    skip_google_files: bool = False

class DownloadRequest(BaseModel):
    source_folder_id: str
    destination_folder: str
    secret_file: str
    skip_photos: bool = False
    skip_videos: bool = False
    skip_audio: bool = False
    skip_google_files: bool = False
    max_workers: int = 4  # 1–8 parallel download connections

class BrowseRequest(BaseModel):
    title: str = "Select"
    initial_dir: str = ""

class SwitchAccountRequest(BaseModel):
    pass

# ─── Utilities ────────────────────────────────────────────────────────────────

def extract_folder_id(folder_input: str) -> str:
    """
    Extract the Drive item ID from a Google Drive link or raw ID.

    Supported formats:
      - Folder link:  https://drive.google.com/drive/folders/FOLDER_ID[?...]
      - File link:    https://drive.google.com/file/d/FILE_ID/view[?...]
      - Raw ID:       any alphanumeric string longer than 10 characters
    """
    folder_input = folder_input.strip()
    if "drive.google.com" in folder_input:
        try:
            if "/folders/" in folder_input:
                # Standard folder share link
                drive_id = folder_input.split("/folders/")[1].split("?")[0].split("&")[0]
                return drive_id.strip()
            elif "/file/d/" in folder_input:
                # Single-file share link — the downloader will handle the single-file case
                drive_id = folder_input.split("/file/d/")[1].split("/")[0].split("?")[0]
                return drive_id.strip()
            else:
                raise ValueError(
                    "Unrecognised Google Drive link. "
                    "Please use a folder link (…/folders/ID) or a file link (…/file/d/ID)."
                )
        except (IndexError, AttributeError):
            raise ValueError("Invalid Google Drive link format")
    else:
        if len(folder_input) > 10:
            return folder_input
        else:
            raise ValueError("Invalid ID — must be longer than 10 characters")


# ─── Tkinter Dialog Manager ───────────────────────────────────────────────────
# Tkinter MUST have its event loop on a single dedicated thread.
# We spin up one daemon thread that owns tk.mainloop() and dispatches
# all dialog calls through it via a queue + root.after().

class _TkDialogManager:
    """Singleton that owns the Tk event loop thread and services dialog requests."""

    def __init__(self):
        self._req_queue: queue.Queue = queue.Queue()
        self._root: Optional[tk.Tk] = None
        self._thread = threading.Thread(target=self._thread_main, daemon=True, name="TkDialogThread")
        self._thread.start()
        # Wait until Tk is ready
        self._ready = threading.Event()
        self._ready.wait(timeout=10)

    def _thread_main(self):
        self._root = tk.Tk()
        self._root.withdraw()          # keep root window hidden
        self._root.wm_attributes("-topmost", True)
        self._ready.set()
        self._root.after(50, self._poll)
        self._root.mainloop()

    def _poll(self):
        """Called by Tk's event loop every 50 ms to process queued dialog calls."""
        try:
            while True:
                fn, result_box = self._req_queue.get_nowait()
                try:
                    result_box["result"] = fn(self._root)
                except Exception as exc:
                    result_box["error"] = exc
                finally:
                    result_box["event"].set()
        except queue.Empty:
            pass
        self._root.after(50, self._poll)

    def _dispatch(self, fn) -> Optional[str]:
        box = {"result": None, "error": None, "event": threading.Event()}
        self._req_queue.put((fn, box))
        box["event"].wait(timeout=300)          # 5-minute user timeout
        if box["error"]:
            raise box["error"]
        return box["result"]

    def ask_directory(self, title: str, initialdir: str) -> Optional[str]:
        def _run(root):
            root.wm_attributes("-topmost", True)
            path = filedialog.askdirectory(
                title=title, initialdir=initialdir, parent=root
            )
            root.wm_attributes("-topmost", False)
            return path or None
        return self._dispatch(_run)

    def ask_open_filename(self, title: str, initialdir: str) -> Optional[str]:
        def _run(root):
            root.wm_attributes("-topmost", True)
            path = filedialog.askopenfilename(
                title=title,
                initialdir=initialdir,
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
                parent=root,
            )
            root.wm_attributes("-topmost", False)
            return path or None
        return self._dispatch(_run)


_tk_manager: Optional["_TkDialogManager"] = None
_tk_manager_lock = threading.Lock()


def _get_tk_manager() -> "_TkDialogManager":
    global _tk_manager
    if _tk_manager is None:
        with _tk_manager_lock:
            if _tk_manager is None:
                _tk_manager = _TkDialogManager()
    return _tk_manager


def open_folder_dialog(title: str, initial_dir: str) -> Optional[str]:
    """Show a native folder-picker dialog on the dedicated Tk thread."""
    if not initial_dir or not Path(initial_dir).exists():
        initial_dir = str(Path.home())
    try:
        return _get_tk_manager().ask_directory(title, initial_dir)
    except Exception as exc:
        print(f"Folder dialog error: {exc}")
        return None


def open_file_dialog(title: str, initial_dir: str) -> Optional[str]:
    """Show a native file-picker dialog on the dedicated Tk thread."""
    if not initial_dir or not Path(initial_dir).exists():
        initial_dir = str(Path.home())
    try:
        return _get_tk_manager().ask_open_filename(title, initial_dir)
    except Exception as exc:
        print(f"File dialog error: {exc}")
        return None


# ─── Config Endpoints ──────────────────────────────────────────────────────────

@app.get("/api/config")
async def get_config():
    """Load saved configuration from disk."""
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return Config().model_dump()

@app.post("/api/config")
async def save_config(config: Config):
    """Save configuration to disk."""
    try:
        with open(CONFIG_PATH, "w") as f:
            json.dump(config.model_dump(), f, indent=2)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}

# ─── Browse Endpoints ──────────────────────────────────────────────────────────

@app.post("/api/browse/folder")
async def browse_folder(req: BrowseRequest):
    """Open a native folder picker and return the selected path."""
    loop = asyncio.get_running_loop()
    path = await loop.run_in_executor(
        None, open_folder_dialog, req.title, req.initial_dir
    )
    return {"path": path}

@app.post("/api/browse/file")
async def browse_file(req: BrowseRequest):
    """Open a native file picker and return the selected path."""
    loop = asyncio.get_running_loop()
    path = await loop.run_in_executor(
        None, open_file_dialog, req.title, req.initial_dir
    )
    return {"path": path}

# ─── Account Endpoints ──────────────────────────────────────────────────────────

@app.post("/api/account/switch")
async def switch_account():
    """Delete the token file to force re-authentication on next download."""
    if state.is_downloading:
        return {"ok": False, "error": "Cannot switch account while downloading"}
    try:
        token_path = BASE_PATH / "token.json"
        if token_path.exists():
            token_path.unlink()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}

# ─── Download Endpoints ────────────────────────────────────────────────────────

def run_download_thread(
    folder_id: str,
    dest_dir: str,
    secret_file: str,
    token_file: str,
    file_filters: dict,
    skip_google_files: bool,
    max_workers: int = 4,
):
    """Runs the download in a background thread and feeds logs to the queue."""
    def log_cb(msg: str):
        state.log_queue.put(msg)

    try:
        state.log_queue.put("Starting download process...")
        state.log_queue.put(f"Destination: {dest_dir}\n")

        state.downloader = GoogleDriveDownloader(
            credentials_file=secret_file,
            token_file=token_file,
            log_callback=log_cb,
            cancel_event=state.cancel_event,
        )

        state.downloader.download_folder(
            folder_id=folder_id,
            download_dir=dest_dir,
            file_filters=file_filters,
            skip_google_files=skip_google_files,
            max_workers=max_workers,
        )

        if state.cancel_event.is_set():
            state.log_queue.put("\n[INFO] Download was cancelled by the user.")
        else:
            state.log_queue.put("\n[SUCCESS] Download completed!")

    except Exception as e:
        state.log_queue.put(f"\n[ERROR] {str(e)}")
    finally:
        state.is_downloading = False
        # Sentinel to signal SSE stream to close
        state.log_queue.put(None)


@app.post("/api/download/start")
async def start_download(req: DownloadRequest):
    """Start the download process in a background thread."""
    with _download_lock:
        if state.is_downloading:
            return {"ok": False, "error": "Download already in progress"}
        # Reserve the slot immediately — prevents concurrent requests from
        # both passing the guard before either thread has started.
        state.is_downloading = True

    # Validate inputs – reset the flag if any check fails
    try:
        if not req.source_folder_id.strip():
            state.is_downloading = False
            return {"ok": False, "error": "Source Folder Link/ID is required"}
        folder_id = extract_folder_id(req.source_folder_id)
    except ValueError as e:
        state.is_downloading = False
        return {"ok": False, "error": str(e)}

    dest_dir = req.destination_folder.strip()
    if not dest_dir:
        state.is_downloading = False
        return {"ok": False, "error": "Destination Folder is required"}

    # Verify the destination is writable before touching the Drive API (improvement E)
    try:
        _dest_path = Path(dest_dir)
        _dest_path.mkdir(parents=True, exist_ok=True)
        _probe = _dest_path / ".drive_write_test"
        _probe.write_text("ok")
        _probe.unlink()
    except Exception as _exc:
        state.is_downloading = False
        return {"ok": False, "error": f"Destination folder is not writable: {_exc}"}

    secret_file = req.secret_file.strip()
    if not secret_file:
        state.is_downloading = False
        return {"ok": False, "error": "Client Secret File is required"}
    if not Path(secret_file).exists():
        state.is_downloading = False
        return {"ok": False, "error": f"Client Secret File not found at: {secret_file}"}

    token_file = str(BASE_PATH / "token.json")

    state.reset()
    # is_downloading is already True from the lock block above

    file_filters = {
        "photos": req.skip_photos,
        "videos": req.skip_videos,
        "audio": req.skip_audio,
    }

    # Save config
    config = Config(
        source_folder_id=req.source_folder_id,
        destination_folder=dest_dir,
        secret_file=secret_file,
        skip_photos=req.skip_photos,
        skip_videos=req.skip_videos,
        skip_audio=req.skip_audio,
        skip_google_files=req.skip_google_files,
    )
    try:
        with open(CONFIG_PATH, "w") as f:
            json.dump(config.model_dump(), f, indent=2)
    except Exception:
        pass

    # Start thread
    thread = threading.Thread(
        target=run_download_thread,
        args=(folder_id, dest_dir, secret_file, token_file, file_filters, req.skip_google_files, req.max_workers),
        daemon=True,
    )
    thread.start()

    return {"ok": True}


@app.post("/api/download/cancel")
async def cancel_download():
    """Signal the download thread to stop."""
    if not state.is_downloading:
        return {"ok": False, "error": "No download in progress"}
    state.cancel_event.set()
    return {"ok": True}


@app.get("/api/download/logs")
async def stream_logs():
    """Stream download log messages via Server-Sent Events."""
    async def event_generator():
        while True:
            try:
                msg = await asyncio.get_running_loop().run_in_executor(
                    None, lambda: state.log_queue.get(timeout=60)  # 60 s keeps pings rare (improvement F)
                )
                if msg is None:
                    # Download finished – send a close signal and stop
                    yield "data: __DONE__\n\n"
                    break
                # Escape for SSE
                escaped = msg.replace("\n", "\\n")
                yield f"data: {escaped}\n\n"
            except Exception:
                # Timeout heartbeat — keeps the connection alive
                yield "data: __PING__\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/status")
async def get_status():
    """Return current download status."""
    return {
        "is_downloading": state.is_downloading,
        "cancelled": state.cancel_event.is_set(),
    }


# ─── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=False)


# ─── Serve built React frontend (MUST be last so API routes take priority) ─────
# Starlette checks routes in registration order. Mounting StaticFiles at "/"
# before API routes would cause it to intercept all POST requests with 405.
# By mounting here, all API routes registered above are checked first.
_frontend_dist = BASE_PATH / "frontend_dist"
if _frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="static")
