import io
import json
import os
import re
import time
from pathlib import Path
from typing import Callable, Optional
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request, AuthorizedSession
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

# MIME type categories to filter
FILE_TYPE_FILTERS = {
    'photos': [
        'image/jpeg',
        'image/png',
        'image/gif',
        'image/webp',
        'image/bmp',
        'image/tiff',
        'image/svg+xml',
    ],
    'videos': [
        'video/mp4',
        'video/mpeg',
        'video/quicktime',
        'video/x-msvideo',
        'video/x-matroska',
        'video/webm',
        'video/3gpp',
        'video/3gpp2',
        'video/x-flv',
        'video/x-ms-wmv',
    ],
    'audio': [
        'audio/mpeg',
        'audio/wav',
        'audio/ogg',
        'audio/flac',
        'audio/aac',
        'audio/x-m4a',
        'audio/webm',
        'audio/aiff',
        'audio/x-wav',
        'audio/mp4',
    ],
}


def format_network_error(e: Exception) -> str:
    """Convert raw urllib3 / socket / OS exceptions into clean, human-readable messages."""
    err_str = str(e)
    if "getaddrinfo failed" in err_str or "NameResolutionError" in err_str:
        return "No internet connection (DNS lookup failed)"
    if "Read timed out" in err_str or "WinError 10060" in err_str or "timed out" in err_str.lower():
        return "Connection timed out"
    if "ConnectionResetError" in err_str or "10054" in err_str or "10053" in err_str:
        return "Connection reset by host or network"
    if "Connection refused" in err_str or "10061" in err_str:
        return "Connection refused"
    if "Max retries exceeded" in err_str:
        return "Network connection unavailable"
    return err_str


def sanitize_filename(name: str) -> str:
    """
    Replace characters that are illegal in Windows file names so that the tool
    uses the same name the browser uses when a user downloads files manually
    from the Google Drive web interface.

    Illegal on Windows: \ / : * ? " < > |
    Also strip trailing dots/spaces which Windows silently removes.
    """
    # Replace every illegal character with an underscore
    sanitized = re.sub(r'[\\/:*?"<>|]', '_', name)
    # Windows silently strips trailing dots and spaces from file/dir names
    sanitized = sanitized.rstrip('. ')
    return sanitized or '_'  # never return an empty string




class GoogleDriveDownloader:
    def __init__(
        self,
        credentials_file: str,
        token_file: str = 'token.json',
        log_callback: Optional[Callable[[str], None]] = None,
        cancel_event: Optional[object] = None,
    ):
        """
        Initialize the Google Drive downloader.

        Args:
            credentials_file: Path to the OAuth client secret file
            token_file: Path to store/load the token
            log_callback: Optional callback function for logging messages
            cancel_event: Optional threading.Event to signal cancellation
        """
        self.credentials_file = credentials_file
        self.token_file = token_file
        self.log_callback = log_callback
        self.cancel_event = cancel_event
        self.service = None
        self.creds = None
        self.session = None
        self.downloaded_count = 0
        self.skipped_count = 0

    def log(self, message: str):
        """Log a message using the callback or print."""
        if self.log_callback:
            self.log_callback(message)
        else:
            print(message)

    def authenticate(self) -> Credentials:
        """Authenticate with Google Drive API with retry on token refresh network errors."""
        creds = None
        if os.path.exists(self.token_file):
            creds = Credentials.from_authorized_user_file(self.token_file, SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                attempt = 0
                while True:
                    if self.cancel_event and self.cancel_event.is_set():
                        raise Exception("Operation cancelled by user.")
                    try:
                        creds.refresh(Request())
                        break
                    except Exception as e:
                        attempt += 1
                        wait_sec = 10
                        clean_err = format_network_error(e)
                        self.log(f"[!] Network error refreshing credentials ({clean_err}).")
                        self.log(f"[!] Retrying token refresh in 10s… (press Stop to cancel)")
                        for _ in range(wait_sec):
                            if self.cancel_event and self.cancel_event.is_set():
                                raise Exception("Operation cancelled by user.")
                            time.sleep(1)
            else:
                self.log("\n" + "=" * 70)
                self.log("AUTHENTICATION REQUIRED")
                self.log("=" * 70)
                self.log("")
                self.log("Please sign in with your Google account in the browser window")
                self.log("that will open momentarily...")
                self.log("")
                self.log("If a browser window doesn't open automatically, check your")
                self.log("system taskbar — it may be opening in the background.")
                self.log("")

                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_file, SCOPES
                )
                creds = flow.run_local_server(port=0, open_browser=True)

                self.log("")
                self.log("✓ Authentication successful!")
                self.log("")

            with open(self.token_file, 'w') as token:
                token.write(creds.to_json())
        self.creds = creds
        self.session = AuthorizedSession(creds)
        return creds

    def get_session(self) -> AuthorizedSession:
        """Get or initialize an AuthorizedSession for direct unbuffered HTTP streaming."""
        if self.creds is None or not self.creds.valid:
            self.creds = self.authenticate()
            self.session = AuthorizedSession(self.creds)
        elif self.session is None:
            self.session = AuthorizedSession(self.creds)
        return self.session

    def re_authenticate(self):
        """
        Re-authenticate with Google Drive using a different account.
        Removes the existing token to force a fresh login.
        """
        if os.path.exists(self.token_file):
            os.remove(self.token_file)
            self.log("Token file removed. Please proceed with authentication for a different account.")

        # Reset service so it will authenticate on next use
        self.service = None
        self.creds = None
        self.session = None
        return True

    def build_service(self):
        """Build the Google Drive service with network retry resilience."""
        if self.service is None:
            attempt = 0
            while True:
                if self.cancel_event and self.cancel_event.is_set():
                    raise Exception("Operation cancelled by user.")
                try:
                    creds = self.authenticate()
                    self.service = build('drive', 'v3', credentials=creds)
                    break
                except Exception as e:
                    attempt += 1
                    wait_sec = 10
                    clean_err = format_network_error(e)
                    self.log(f"[!] Network error building Google Drive service ({clean_err}).")
                    self.log(f"[!] Retrying in 10s… (press Stop to cancel)")
                    for _ in range(wait_sec):
                        if self.cancel_event and self.cancel_event.is_set():
                            raise Exception("Operation cancelled by user.")
                        time.sleep(1)
        return self.service

    def verify_folder_access(self, folder_id: str):
        """
        Verify that the folder exists and we have access to it.
        Kept for backward compatibility; download_folder now uses get_item_info().
        """
        info = self.get_item_info(folder_id)
        if info.get('mimeType') != 'application/vnd.google-apps.folder':
            raise Exception(
                f"❌ The provided ID '{folder_id}' is not a folder. It appears to be a file."
            )

    def get_item_info(self, item_id: str) -> dict:
        """
        Fetch metadata for any Drive item (file or folder) with infinite retry resilience.
        """
        attempt = 0
        while True:
            if self.cancel_event and self.cancel_event.is_set():
                raise Exception("Operation cancelled by user.")
            try:
                return self.service.files().get(
                    fileId=item_id,
                    fields="id, name, mimeType, size"
                ).execute()
            except HttpError as e:
                error_code = e.resp.status if e.resp else 500
                if error_code == 404:
                    raise Exception(
                        f"❌ Item not found (HTTP 404). The ID '{item_id}' does not exist, "
                        "may have been deleted, or you have no access to it."
                    )
                elif error_code == 403:
                    raise Exception(
                        "❌ Access denied (HTTP 403). You don't have permission to access this item. "
                        "Please verify it is shared with your Google account."
                    )
                elif error_code == 401:
                    self.log("[!] Access token expired while fetching item info. Refreshing...")
                    self.creds.refresh(Request())
                    self.session = AuthorizedSession(self.creds)
                    continue
                else:
                    attempt += 1
                    wait_sec = 10
                    self.log(f"[!] Google Drive API error (HTTP {error_code}): {e}")
                    self.log(f"[!] Retrying in 10s… (press Stop to cancel)")
            except Exception as e:
                # Catch WinError 10060, ConnectionError, timeout, etc.
                attempt += 1
                wait_sec = 10
                clean_err = format_network_error(e)
                self.log(f"[!] Connection error fetching item info ({clean_err}).")
                self.log(f"[!] Retrying in 10s… (press Stop to cancel)")

            for _ in range(wait_sec):
                if self.cancel_event and self.cancel_event.is_set():
                    raise Exception("Operation cancelled by user.")
                time.sleep(1)

    def should_filter_file(self, mime_type: str, file_filters: dict) -> bool:
        """
        Check if a file should be filtered based on file type preferences.

        Args:
            mime_type: The MIME type of the file
            file_filters: Dictionary with keys 'photos', 'videos', 'audio' with True/False values

        Returns:
            True if the file should be filtered (skipped), False otherwise
        """
        if file_filters.get('photos') and mime_type in FILE_TYPE_FILTERS['photos']:
            return True
        if file_filters.get('videos') and mime_type in FILE_TYPE_FILTERS['videos']:
            return True
        if file_filters.get('audio') and mime_type in FILE_TYPE_FILTERS['audio']:
            return True
        return False

    def get_all_files_recursive(self, folder_id: str, prefix: str = '') -> list:
        """
        Recursively get all files from a folder and its subfolders with full network outage resilience.
        """
        items = []
        page_token = None
        query = f"'{folder_id}' in parents and trashed=false"

        while True:
            # ── API call with infinite network retry loop ─────────────────
            api_attempt = 0
            while True:
                if self.cancel_event and self.cancel_event.is_set():
                    return items
                try:
                    results = self.service.files().list(
                        q=query,
                        fields="nextPageToken, files(id, name, mimeType, size)",
                        pageToken=page_token,
                        pageSize=1000,
                    ).execute()
                    break  # success — leave retry loop

                except HttpError as e:
                    error_code = e.resp.status if e.resp else 500
                    if error_code == 403:
                        raise Exception(
                            "❌ Access denied while accessing folder. "
                            "You may not have permission to this subfolder."
                        )
                    elif error_code == 404:
                        raise Exception("❌ A folder in the path was not found or deleted.")
                    elif error_code == 401:
                        self.log("[!] Access token expired during folder scan. Refreshing...")
                        self.creds.refresh(Request())
                        self.session = AuthorizedSession(self.creds)
                        continue
                    elif error_code == 429:
                        api_attempt += 1
                        wait_sec = 10
                        self.log(
                            f"[!] Rate limit hit (HTTP 429) during folder scan (attempt {api_attempt}). "
                            f"Waiting 10s… (press Stop to cancel)"
                        )
                    else:
                        api_attempt += 1
                        wait_sec = 10
                        self.log(
                            f"[!] Google Drive API error (HTTP {error_code}) during scan: {e}. "
                            f"Retrying in 10s… (press Stop to cancel)"
                        )

                except Exception as e:
                    # Catch WinError 10060, ConnectionResetError, TimeoutError, etc.
                    api_attempt += 1
                    wait_sec = 10
                    clean_err = format_network_error(e)
                    self.log(
                        f"[!] Network error during folder scan (attempt {api_attempt}): {clean_err}. "
                        f"Retrying in 10s… (press Stop to cancel)"
                    )

                for _ in range(wait_sec):
                    if self.cancel_event and self.cancel_event.is_set():
                        return items
                    time.sleep(1)

            # ── Process page results ──────────────────────────────────────
            files = results.get('files', [])
            for file_info in files:
                file_name = sanitize_filename(file_info['name'].strip())
                relative_path = f"{prefix}/{file_name}" if prefix else file_name
                file_size = int(file_info.get('size', 0) or 0)

                if file_info['mimeType'] == 'application/vnd.google-apps.folder':
                    self.log(f"  📁 Scanning: {relative_path}/")
                    sub_items = self.get_all_files_recursive(file_info['id'], relative_path)
                    if self.cancel_event and self.cancel_event.is_set():
                        return items
                    items.extend(sub_items)
                else:
                    items.append(
                        (
                            file_info['id'],
                            file_name,
                            file_info.get('mimeType', ''),
                            relative_path,
                            file_size,
                        )
                    )

            page_token = results.get('nextPageToken', None)
            if page_token is None:
                break

        return items

    # ── Shared download retry engine ──────────────────────────────────────────

    def _download_with_retry(
        self, file_id: str, file_path: Path, label: str, known_size: int = 0
    ) -> bool:
        """
        Stream file download directly over HTTP with real-time unbuffered chunks and 80ms UI progress updates.

        Features:
        - Direct HTTP streaming via AuthorizedSession (bypasses MediaIoBaseDownload 100MB buffering).
        - 64 KB streaming chunks written continuously straight to disk.
        - Real-time live speed and ETA updates emitted every 80ms (~12 updates per second).
        - Immediate 0% progress tick with known file size upfront (0ms delay).
        - Retries indefinitely every 10 seconds on network failures.
        - HTTP 429 rate limits logged with clean 10s wait message.
        - Instant cancellation response.

        Args:
            file_id:     The Google Drive file ID
            file_path:   Local path where the file will be saved
            label:       Short name used in log messages
            known_size:  Known file size in bytes from metadata

        Returns:
            True on success, False if cancelled.
        """
        attempt = 0
        initial_size_mb = round(known_size / (1024 * 1024), 1) if known_size else None
        url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"

        # Use a .part sidecar file so partial data is never mixed with complete files.
        # On each retry the offset is read from the part file's current size so we
        # resume exactly where the connection dropped — no re-downloading from byte 0.
        part_path = file_path.with_suffix(file_path.suffix + '.part')
        total_bytes = known_size or 0  # updated on first successful response
        size_mb = initial_size_mb

        while True:
            if self.cancel_event and self.cancel_event.is_set():
                return False

            # How many bytes we already have on disk from a previous attempt
            bytes_done = part_path.stat().st_size if part_path.exists() else 0

            success = False
            start_time = time.time()
            last_emit_time = 0
            samples = []  # [(timestamp, cumulative_bytes_done)]

            try:
                session = self.get_session()

                # Always emit current progress so the bar shows immediately
                progress_percent = int((bytes_done / total_bytes) * 100) if total_bytes > 0 else 0
                self.log(json.dumps({
                    "type": "progress",
                    "percent": progress_percent,
                    "speed_mbps": 0,
                    "eta_sec": None,
                    "size_mb": size_mb,
                }))

                # Send Range header if we already have some bytes
                headers = {}
                if bytes_done > 0:
                    headers["Range"] = f"bytes={bytes_done}-"
                    self.log(f"[~] Resuming '{label}' from {round(bytes_done / (1024 * 1024), 1)} MB…")

                with session.get(url, stream=True, timeout=45, headers=headers) as response:
                    if response.status_code == 429:
                        attempt += 1
                        wait_sec = 10
                        self.log(
                            f"[!] Rate limit hit (HTTP 429) on attempt {attempt}. "
                            f"Waiting 10s… (press Stop to cancel)"
                        )
                        for _ in range(wait_sec):
                            if self.cancel_event and self.cancel_event.is_set():
                                return False
                            time.sleep(1)
                        continue

                    if response.status_code == 401:
                        self.log("[!] Access token expired during download. Refreshing credentials...")
                        self.creds.refresh(Request())
                        self.session = AuthorizedSession(self.creds)
                        continue

                    if response.status_code == 404:
                        self.log(f"[!] ❌ File '{label}' not found or deleted on Google Drive (HTTP 404). Skipping.")
                        part_path.unlink(missing_ok=True)
                        return False
                    if response.status_code == 403:
                        self.log(f"[!] ❌ Access denied for file '{label}' (HTTP 403). Check sharing permissions. Skipping.")
                        part_path.unlink(missing_ok=True)
                        return False

                    # 206 = partial content (Range accepted), 200 = full response
                    if response.status_code == 416:
                        # 416 Range Not Satisfiable — server says offset is past EOF,
                        # meaning we already have the complete file. Rename and finish.
                        self.log(f"[~] '{label}' appears already complete (HTTP 416). Finalising…")
                        part_path.rename(file_path)
                        return True

                    if response.status_code not in (200, 206):
                        response.raise_for_status()

                    # If the server returned 200 (doesn't support Range), restart from 0
                    if response.status_code == 200 and bytes_done > 0:
                        self.log(f"[~] Server doesn't support resume for '{label}'. Restarting from 0…")
                        bytes_done = 0
                        part_path.unlink(missing_ok=True)

                    # Update total size from Content-Length / Content-Range header
                    content_length = int(response.headers.get('Content-Length', 0) or 0)
                    if response.status_code == 206:
                        # Content-Range: bytes start-end/total
                        cr = response.headers.get('Content-Range', '')
                        try:
                            total_bytes = int(cr.split('/')[-1])
                        except (ValueError, IndexError):
                            total_bytes = bytes_done + content_length
                    elif content_length:
                        total_bytes = content_length
                    elif known_size:
                        total_bytes = known_size

                    size_mb = round(total_bytes / (1024 * 1024), 1) if total_bytes else initial_size_mb

                    # Open in append mode so we add bytes to what's already on disk
                    write_mode = 'ab' if bytes_done > 0 else 'wb'
                    with open(part_path, write_mode) as fh:
                        for chunk in response.iter_content(chunk_size=64 * 1024):
                            if self.cancel_event and self.cancel_event.is_set():
                                self.log(f"[INFO] {label} cancelled.")
                                fh.flush()
                                # Keep the .part file so the next run can resume
                                return False

                            if chunk:
                                fh.write(chunk)
                                bytes_done += len(chunk)
                                now = time.time()

                                # Emit progress updates every 80ms (~12 FPS)
                                if now - last_emit_time >= 0.08 or (total_bytes > 0 and bytes_done >= total_bytes):
                                    last_emit_time = now
                                    samples.append((now, bytes_done))
                                    if len(samples) > 8:
                                        samples = samples[-8:]

                                    if len(samples) >= 2 and (samples[-1][0] - samples[0][0]) > 0.001:
                                        delta_bytes = samples[-1][1] - samples[0][1]
                                        delta_time = samples[-1][0] - samples[0][0]
                                        speed_bps = delta_bytes / delta_time
                                    else:
                                        elapsed = now - start_time
                                        speed_bps = bytes_done / elapsed if elapsed > 0.001 else 0

                                    speed_mbps = round(speed_bps / (1024 * 1024), 2)
                                    progress_percent = int((bytes_done / total_bytes) * 100) if total_bytes > 0 else 0
                                    remaining = max(total_bytes - bytes_done, 0)
                                    eta_sec = int(remaining / speed_bps) if speed_bps > 1024 else None

                                    self.log(json.dumps({
                                        "type": "progress",
                                        "percent": progress_percent,
                                        "speed_mbps": speed_mbps,
                                        "eta_sec": eta_sec,
                                        "size_mb": size_mb,
                                    }))

                # Rename .part → final filename only on full success
                part_path.rename(file_path)
                success = True
                return True

            except Exception as e:
                attempt += 1
                wait_sec = 10
                clean_err = format_network_error(e)
                # Tell the user exactly how many MB were saved so they know work isn't lost
                saved_mb = round(part_path.stat().st_size / (1024 * 1024), 1) if part_path.exists() else 0
                self.log(
                    f"[!] Connection dropped downloading '{label}' (attempt {attempt}): {clean_err}. "
                    f"{saved_mb} MB saved — will resume in 10s. (press Stop to cancel)"
                )

            # Sleep in 1-second ticks so Cancel is always responsive
            for _ in range(wait_sec):
                if self.cancel_event and self.cancel_event.is_set():
                    return False
                time.sleep(1)

    # ── Public download methods ───────────────────────────────────────────────

    def download_file(self, file_id: str, file_path: Path, file_size: int = 0) -> bool:
        """
        Download a single regular file from Google Drive.

        Delegates all streaming, retry, and progress logic to
        _download_with_retry().

        Args:
            file_id:    The Google Drive file ID
            file_path:  Local path where the file will be saved
            file_size:  Known file size in bytes

        Returns:
            True if the file was downloaded successfully, False if cancelled.
        """
        if self.cancel_event and self.cancel_event.is_set():
            return False
        file_path.parent.mkdir(parents=True, exist_ok=True)
        return self._download_with_retry(file_id, file_path, file_path.name, file_size)

    def download_folder(
        self,
        folder_id: str,
        download_dir: str,
        file_filters: Optional[dict] = None,
        skip_google_files: bool = False,
    ):
        """
        Download an entire Google Drive folder while preserving structure.

        Args:
            folder_id:          The Google Drive folder ID (or file ID) to download
            download_dir:       Local directory where to save files
            file_filters:       Dict with keys 'photos', 'videos', 'audio'
                                set to True to skip those file types
            skip_google_files:  When True, Google Workspace files (Docs, Sheets,
                                Slides, Drawings) are logged and counted as skipped.
                                When False they are silently passed over.
        """
        if file_filters is None:
            file_filters = {}

        try:
            self.log("Building Google Drive service...")
            self.build_service()

            self.log("Verifying access…")
            item_info = self.get_item_info(folder_id)
            is_folder = item_info.get('mimeType') == 'application/vnd.google-apps.folder'

            if is_folder:
                self.log("Scanning Google Drive folder for files… (This might take a moment)")
                items = self.get_all_files_recursive(folder_id)
            else:
                # Single file link — build a synthetic one-item list so the
                # download loop below runs without any special-casing.
                file_name = sanitize_filename(item_info['name'].strip())
                mime_type = item_info.get('mimeType', '')
                file_size = int(item_info.get('size', 0) or 0)
                self.log(f"Single file detected: '{file_name}'")
                items = [(folder_id, file_name, mime_type, file_name, file_size)]

            if not items:
                self.log("No files found in the specified folder.")
                return

            download_path = Path(download_dir)
            download_path.mkdir(parents=True, exist_ok=True)

            total = len(items)
            self.log(f"Found {total} total items. Starting download…")
            self.downloaded_count = 0
            self.skipped_count = 0
            # Counts files/exports actually attempted — drives the overall progress bar
            file_index = 0

            for file_id, file_name, mime_type, relative_path, file_size in items:
                # Check for cancellation at the top of every iteration
                if self.cancel_event and self.cancel_event.is_set():
                    self.log("[INFO] Download cancelled by user.")
                    break

                # ── Google Workspace native files ─────────────────────────
                if 'vnd.google-apps' in mime_type:
                    if skip_google_files:
                        self.log(f"Skipping: '{relative_path}' (Google Workspace file)")
                        self.skipped_count += 1
                    continue

                # ── File type filters ────────────────────────────────────
                if self.should_filter_file(mime_type, file_filters):
                    self.log(f"Skipping: '{relative_path}' (Filtered by type)")
                    self.skipped_count += 1
                    continue

                file_path = download_path / relative_path
                part_path = file_path.with_suffix(file_path.suffix + '.part')

                # ── Already downloaded (complete file) ───────────────────
                if file_path.exists():
                    self.log(f"Skipping: '{relative_path}' (Already exists)")
                    self.skipped_count += 1
                    continue

                file_index += 1
                # Overall progress event (improvement B)
                self.log(json.dumps({
                    "type": "overall_progress",
                    "current": file_index,
                    "total": total,
                }))

                # Show resume message if we have a partial download already
                if part_path.exists():
                    saved_mb = round(part_path.stat().st_size / (1024 * 1024), 1)
                    self.log(f"\nResuming: {relative_path} ({saved_mb} MB already downloaded)")
                else:
                    self.log(f"\nDownloading: {relative_path}")

                if self.download_file(file_id, file_path, file_size):
                    self.log(f"✓ Successfully downloaded: {relative_path}")
                    self.downloaded_count += 1
                else:
                    self.skipped_count += 1

            self.log(f"\n{'=' * 60}")
            self.log("✓ Download completed!")
            self.log(f"Downloaded: {self.downloaded_count} files")
            self.log(f"Skipped:    {self.skipped_count} items")
            self.log(f"{'=' * 60}")

        except HttpError as e:
            if not (self.cancel_event and self.cancel_event.is_set()):
                error_code = e.resp.status if e.resp else 500
                self.log(f"\n[ERROR] Google Drive API Error (HTTP {error_code})")
            raise

        except Exception as e:
            if not (self.cancel_event and self.cancel_event.is_set()):
                self.log(f"\n{str(e)}")
            raise
