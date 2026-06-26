"""
FastAPI backend server for Google Drive Download Automation.
Wraps the existing GoogleDriveDownloader and exposes REST + SSE endpoints
for the React frontend UI.
"""

import asyncio
import json
import queue
import threading
import subprocess
import sys
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from enhanced_downloader import GoogleDriveDownloader

# ─── App Setup ──────────────────────────────────────────────────────────────

app = FastAPI(title="Drive Download Automation API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CONFIG_PATH = Path(".") / "ui_config.json"

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

# ─── Pydantic Models ──────────────────────────────────────────────────────────

class Config(BaseModel):
    source_folder_id: str = ""
    destination_folder: str = ""
    token_file: str = ""
    secret_file: str = ""
    skip_photos: bool = False
    skip_videos: bool = False
    skip_audio: bool = False

class DownloadRequest(BaseModel):
    source_folder_id: str
    destination_folder: str
    secret_file: str
    skip_photos: bool = False
    skip_videos: bool = False
    skip_audio: bool = False

class BrowseRequest(BaseModel):
    title: str = "Select"
    initial_dir: str = ""

class SwitchAccountRequest(BaseModel):
    pass

# ─── Utilities ────────────────────────────────────────────────────────────────

def extract_folder_id(folder_input: str) -> str:
    """Extract folder ID from a Google Drive link or raw ID."""
    folder_input = folder_input.strip()
    if "drive.google.com" in folder_input:
        try:
            if "/folders/" in folder_input:
                folder_id = folder_input.split("/folders/")[1].split("?")[0].split("&")[0]
                return folder_id.strip()
            else:
                raise ValueError("Could not find 'folders/' in the link")
        except (IndexError, AttributeError):
            raise ValueError("Invalid Google Drive folder link format")
    else:
        if len(folder_input) > 10:
            return folder_input
        else:
            raise ValueError("Invalid folder ID format")

def open_folder_dialog(title: str, initial_dir: str) -> Optional[str]:
    """Open a native folder picker dialog using a subprocess to avoid tkinter thread issues."""
    try:
        result = subprocess.check_output(
            [sys.executable, "dialog_helper.py", "folder", title, initial_dir],
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        ).strip()
        return result if result else None
    except Exception as e:
        print(f"Dialog error: {e}")
        return None

def open_file_dialog(title: str, initial_dir: str) -> Optional[str]:
    """Open a native file picker dialog using a subprocess to avoid tkinter thread issues."""
    try:
        result = subprocess.check_output(
            [sys.executable, "dialog_helper.py", "file", title, initial_dir],
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        ).strip()
        return result if result else None
    except Exception as e:
        print(f"Dialog error: {e}")
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
    loop = asyncio.get_event_loop()
    path = await loop.run_in_executor(
        None, open_folder_dialog, req.title, req.initial_dir
    )
    return {"path": path}

@app.post("/api/browse/file")
async def browse_file(req: BrowseRequest):
    """Open a native file picker and return the selected path."""
    loop = asyncio.get_event_loop()
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
        token_path = Path("token.json")
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
    if state.is_downloading:
        return {"ok": False, "error": "Download already in progress"}

    # Validate & extract folder ID
    try:
        if not req.source_folder_id.strip():
            return {"ok": False, "error": "Source Folder Link/ID is required"}
        folder_id = extract_folder_id(req.source_folder_id)
    except ValueError as e:
        return {"ok": False, "error": str(e)}

    dest_dir = req.destination_folder.strip()
    if not dest_dir:
        return {"ok": False, "error": "Destination Folder is required"}

    secret_file = req.secret_file.strip()
    if not secret_file:
        return {"ok": False, "error": "Client Secret File is required"}
    if not Path(secret_file).exists():
        return {"ok": False, "error": f"Client Secret File not found at: {secret_file}"}

    token_file = "token.json"

    state.reset()
    state.is_downloading = True

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
    )
    try:
        with open(CONFIG_PATH, "w") as f:
            json.dump(config.model_dump(), f, indent=2)
    except Exception:
        pass

    # Start thread
    thread = threading.Thread(
        target=run_download_thread,
        args=(folder_id, dest_dir, secret_file, token_file, file_filters),
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
                msg = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: state.log_queue.get(timeout=30)
                )
                if msg is None:
                    # Download finished – send a close signal and stop
                    yield "data: __DONE__\n\n"
                    break
                # Escape for SSE
                escaped = msg.replace("\n", "\\n")
                yield f"data: {escaped}\n\n"
            except Exception:
                # Timeout or cancelled
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
