import io
import json
import math
import os
import re
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable, Optional
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request, AuthorizedSession
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# ── IDM-style segmented download settings ─────────────────────────────────────
# Split files into this many parallel byte-range connections (like IDM does).
NUM_SEGMENTS   = 4
# Only segment files at least this large; smaller files use a single connection.
MIN_SEG_BYTES  = 5 * 1024 * 1024   # 5 MB

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
        # Lock for thread-safe credential refresh (used by segment workers)
        self._creds_lock = threading.Lock()

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

    def _new_session(self) -> AuthorizedSession:
        """
        Recreate self.session (singleton used outside segment workers).
        Closes old pool first so stale TCP sockets don't accumulate over long runs.
        """
        if self.session is not None:
            try:
                self.session.close()
            except Exception:
                pass
        self.session = AuthorizedSession(self.creds)
        return self.session

    def _make_thread_session(self) -> AuthorizedSession:
        """
        Create a brand-new AuthorizedSession that is NEVER stored in self.session.
        Each segment worker calls this so the 4 threads have fully independent
        HTTP connection pools — exactly what gives IDM-level throughput.
        """
        return AuthorizedSession(self.creds)

    def get_session(self) -> AuthorizedSession:
        """Get or initialize an AuthorizedSession for direct unbuffered HTTP streaming."""
        if self.creds is None or not self.creds.valid:
            self.creds = self.authenticate()
            return self._new_session()
        if self.session is None:
            return self._new_session()
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

    # ── Download engine ───────────────────────────────────────────────────────

    def _download_with_retry(
        self, file_id: str, file_path: Path, label: str, known_size: int = 0
    ) -> bool:
        """
        Dispatcher: routes to the fast IDM-style segmented path for files ≥ 5 MB
        (where splitting into 4 parallel Range connections gives full bandwidth),
        or to the single-connection path for small files.

        Returns True on success, False if cancelled.
        """
        if known_size >= MIN_SEG_BYTES:
            return self._download_segmented(file_id, file_path, label, known_size)
        return self._download_single(file_id, file_path, label, known_size)

    # ── IDM-style segmented download ──────────────────────────────────────────

    def _download_segmented(
        self, file_id: str, file_path: Path, label: str, total_size: int
    ) -> bool:
        """
        Split `file_path` into NUM_SEGMENTS equal byte-range slices, download
        all slices simultaneously with independent TCP connections, then merge
        them into the final file — exactly the technique IDM uses.

        Segment files:  file.mp4.seg.0, file.mp4.seg.1, …
        On resume, each .seg.N file's current size is the resume offset for that
        slice, so only the missing bytes are re-requested.
        """
        url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"
        size_mb = round(total_size / (1024 * 1024), 1)

        # Build segment boundaries  [start, end] inclusive
        seg_size = math.ceil(total_size / NUM_SEGMENTS)
        segments = []
        for i in range(NUM_SEGMENTS):
            start = i * seg_size
            end   = min(start + seg_size - 1, total_size - 1)
            seg_path = Path(str(file_path) + f'.seg.{i}')
            segments.append((i, start, end, seg_path))

        # Shared progress state (accessed from all NUM_SEGMENTS threads)
        shared = {
            'lock':       threading.Lock(),
            'bytes':      [0] * NUM_SEGMENTS,   # bytes received per segment
            'speeds':     [0.0] * NUM_SEGMENTS,  # rolling speed per segment (bps)
            'last_emit':  [0.0],                 # [timestamp] — mutable so closure can write
            'total_size': total_size,
        }

        # Seed bytes from existing .seg.N files so resume is reflected immediately
        for i, start, end, seg_path in segments:
            if seg_path.exists():
                shared['bytes'][i] = min(seg_path.stat().st_size, end - start + 1)

        # Emit immediate 0% (or resume %) progress tick before any network activity
        initial_done = sum(shared['bytes'])
        self.log(json.dumps({
            'type':      'progress',
            'percent':   int(initial_done / total_size * 100) if total_size else 0,
            'speed_mbps': 0,
            'eta_sec':   None,
            'size_mb':   size_mb,
        }))

        self.log(
            f'[~] Splitting into {NUM_SEGMENTS} parallel segments '
            f'({size_mb} MB) — combined speed will match full bandwidth…'
        )

        # ── Launch segment workers ────────────────────────────────────────────
        with ThreadPoolExecutor(max_workers=NUM_SEGMENTS) as pool:
            futures = {
                pool.submit(
                    self._download_segment,
                    url, i, start, end, seg_path, shared, label
                ): i
                for i, start, end, seg_path in segments
            }

            all_ok = True
            for fut in as_completed(futures):
                try:
                    if not fut.result():
                        all_ok = False
                except Exception as exc:
                    seg_i = futures[fut]
                    self.log(f'[ERROR] Segment {seg_i} raised an unexpected exception: {exc}')
                    all_ok = False

        if not all_ok or (self.cancel_event and self.cancel_event.is_set()):
            # Segments are preserved on disk; next run resumes each from its offset
            return False

        # ── Merge segments into final file ────────────────────────────────────
        self.log(f'[~] Merging {NUM_SEGMENTS} segments → {label}…')
        part_path = Path(str(file_path) + '.part')
        try:
            with open(part_path, 'wb') as out:
                for i, start, end, seg_path in segments:
                    with open(seg_path, 'rb') as inp:
                        while True:
                            buf = inp.read(4 * 1024 * 1024)  # 4 MB copy buffer
                            if not buf:
                                break
                            out.write(buf)
                    seg_path.unlink()  # delete segment as soon as it's merged
        except Exception as exc:
            self.log(f'[ERROR] Merge failed for "{label}": {exc}')
            part_path.unlink(missing_ok=True)
            return False

        part_path.rename(file_path)
        return True

    def _download_segment(
        self,
        url: str,
        seg_idx: int,
        byte_start: int,
        byte_end: int,
        seg_path: Path,
        shared: dict,
        label: str,
    ) -> bool:
        """
        Download one byte-range slice of a file to `seg_path`.

        - Has its own indefinite retry loop (retries only this slice on error).
        - Resumes from seg_path's current size — never re-downloads finished bytes.
        - Updates shared['bytes'][seg_idx] and shared['speeds'][seg_idx] after every
          chunk so the aggregated progress event stays accurate.
        - Emits a single aggregated `type: progress` event every 80 ms (rate-limited
          by shared['last_emit'] so only one thread emits at a time).
        """
        seg_size  = byte_end - byte_start + 1
        attempt   = 0
        CHUNK     = 512 * 1024     # 512 KB per read — 4 threads = 2 MB GIL burst
        FLUSH_AT  = 8 * 1024 * 1024  # flush each segment file every 8 MB

        local_session = self._make_thread_session()
        try:
            while True:
                if self.cancel_event and self.cancel_event.is_set():
                    return False

                # How many bytes of this slice are already on disk
                bytes_done = seg_path.stat().st_size if seg_path.exists() else 0

                # If we already have the full slice, we're done
                if bytes_done >= seg_size:
                    with shared['lock']:
                        shared['bytes'][seg_idx] = seg_size
                    return True

                actual_start = byte_start + bytes_done
                start_time   = time.time()
                samples      = []   # [(timestamp, bytes_done_this_attempt)]
                bytes_since_flush = 0

                try:
                    headers = {'Range': f'bytes={actual_start}-{byte_end}'}

                    with local_session.get(url, stream=True, timeout=45, headers=headers) as resp:
                        if resp.status_code == 401:
                            self.log('[!] Token expired (segment). Refreshing…')
                            with self._creds_lock:
                                self.creds.refresh(Request())
                            local_session.close()
                            local_session = self._make_thread_session()
                            continue

                        if resp.status_code == 429:
                            attempt += 1
                            self.log(
                                f'[!] Rate limit on segment {seg_idx} '
                                f'(attempt {attempt}) — waiting 10s…'
                            )
                            for _ in range(10):
                                if self.cancel_event and self.cancel_event.is_set():
                                    return False
                                time.sleep(1)
                            continue

                        if resp.status_code == 416:
                            # Already have this slice — treat as done
                            with shared['lock']:
                                shared['bytes'][seg_idx] = seg_size
                            return True

                        if resp.status_code not in (200, 206):
                            resp.raise_for_status()

                        write_mode = 'ab' if bytes_done > 0 else 'wb'
                        with open(seg_path, write_mode) as fh:
                            for chunk in resp.iter_content(chunk_size=CHUNK):
                                if self.cancel_event and self.cancel_event.is_set():
                                    fh.flush()
                                    return False

                                if not chunk:
                                    continue

                                fh.write(chunk)
                                bytes_done       += len(chunk)
                                bytes_since_flush += len(chunk)

                                if bytes_since_flush >= FLUSH_AT:
                                    fh.flush()
                                    bytes_since_flush = 0

                                now = time.time()
                                samples.append((now, bytes_done))
                                if len(samples) > 8:
                                    samples = samples[-8:]

                                # ── Update shared state ───────────────────────
                                payload_to_emit = None
                                with shared['lock']:
                                    shared['bytes'][seg_idx] = bytes_done

                                    # Rolling speed for this segment
                                    if len(samples) >= 2 and (samples[-1][0] - samples[0][0]) > 0.001:
                                        db = samples[-1][1] - samples[0][1]
                                        dt = samples[-1][0] - samples[0][0]
                                        shared['speeds'][seg_idx] = db / dt
                                    else:
                                        elapsed = now - start_time
                                        shared['speeds'][seg_idx] = (
                                            bytes_done / elapsed if elapsed > 0.001 else 0
                                        )

                                    # Build payload inside lock, emit outside
                                    if now - shared['last_emit'][0] >= 0.08:
                                        shared['last_emit'][0] = now
                                        total_done  = sum(shared['bytes'])
                                        total_speed = sum(shared['speeds'])
                                        total_size  = shared['total_size']
                                        pct = int(total_done / total_size * 100) if total_size else 0
                                        remaining   = max(total_size - total_done, 0)
                                        eta = int(remaining / total_speed) if total_speed > 1024 else None
                                        payload_to_emit = json.dumps({
                                            'type':       'progress',
                                            'percent':    pct,
                                            'speed_mbps': round(total_speed / (1024 * 1024), 2),
                                            'eta_sec':    eta,
                                            'size_mb':    round(total_size / (1024 * 1024), 1),
                                        })

                                # self.log is called outside the lock — no deadlock risk
                                if payload_to_emit:
                                    self.log(payload_to_emit)

                    return True  # slice fully downloaded

                except Exception as e:
                    attempt += 1
                    clean_err = format_network_error(e)
                    saved_mb  = round(seg_path.stat().st_size / (1024 * 1024), 1) if seg_path.exists() else 0
                    self.log(
                        f'[!] Segment {seg_idx} error (attempt {attempt}): {clean_err}. '
                        f'{saved_mb} MB saved — retrying in 10s… (press Stop to cancel)'
                    )
                    for _ in range(10):
                        if self.cancel_event and self.cancel_event.is_set():
                            return False
                        time.sleep(1)

        finally:
            try:
                local_session.close()
            except Exception:
                pass

    # ── Single-connection fallback (for files < 5 MB) ─────────────────────────

    def _download_single(
        self, file_id: str, file_path: Path, label: str, known_size: int = 0
    ) -> bool:
        """
        Single TCP connection download with resume support.
        Used for files smaller than MIN_SEG_BYTES where segmentation overhead
        outweighs any benefit, and as a fallback when file size is unknown.
        """
        attempt = 0
        initial_size_mb = round(known_size / (1024 * 1024), 1) if known_size else None
        url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"

        part_path  = file_path.with_suffix(file_path.suffix + '.part')
        total_bytes = known_size or 0
        size_mb     = initial_size_mb

        while True:
            if self.cancel_event and self.cancel_event.is_set():
                return False

            bytes_done    = part_path.stat().st_size if part_path.exists() else 0
            start_time    = time.time()
            last_emit_time = 0
            samples       = []

            try:
                session = self._new_session()

                progress_percent = int((bytes_done / total_bytes) * 100) if total_bytes > 0 else 0
                self.log(json.dumps({
                    'type':       'progress',
                    'percent':    progress_percent,
                    'speed_mbps': 0,
                    'eta_sec':    None,
                    'size_mb':    size_mb,
                }))

                headers = {}
                if bytes_done > 0:
                    headers['Range'] = f'bytes={bytes_done}-'
                    self.log(f"[~] Resuming '{label}' from {round(bytes_done / (1024*1024), 1)} MB…")

                with session.get(url, stream=True, timeout=45, headers=headers) as response:
                    if response.status_code == 429:
                        attempt += 1
                        self.log(
                            f'[!] Rate limit (HTTP 429) on attempt {attempt}. '
                            f'Waiting 10s… (press Stop to cancel)'
                        )
                        for _ in range(10):
                            if self.cancel_event and self.cancel_event.is_set():
                                return False
                            time.sleep(1)
                        continue

                    if response.status_code == 401:
                        self.log('[!] Access token expired. Refreshing credentials…')
                        self.creds.refresh(Request())
                        self.session = AuthorizedSession(self.creds)
                        continue

                    if response.status_code == 404:
                        self.log(f"[!] ❌ File '{label}' not found (HTTP 404). Skipping.")
                        part_path.unlink(missing_ok=True)
                        return False
                    if response.status_code == 403:
                        self.log(f"[!] ❌ Access denied for '{label}' (HTTP 403). Skipping.")
                        part_path.unlink(missing_ok=True)
                        return False

                    if response.status_code == 416:
                        self.log(f"[~] '{label}' already complete (HTTP 416). Finalising…")
                        part_path.rename(file_path)
                        return True

                    if response.status_code not in (200, 206):
                        response.raise_for_status()

                    if response.status_code == 200 and bytes_done > 0:
                        self.log(f"[~] Server doesn't support resume for '{label}'. Restarting…")
                        bytes_done = 0
                        part_path.unlink(missing_ok=True)

                    content_length = int(response.headers.get('Content-Length', 0) or 0)
                    if response.status_code == 206:
                        cr = response.headers.get('Content-Range', '')
                        try:
                            total_bytes = int(cr.split('/')[-1])
                        except (ValueError, IndexError):
                            total_bytes = bytes_done + content_length
                    elif content_length:
                        total_bytes = content_length
                    elif known_size:
                        total_bytes = known_size

                    size_mb = round(total_bytes / (1024*1024), 1) if total_bytes else initial_size_mb

                    write_mode    = 'ab' if bytes_done > 0 else 'wb'
                    CHUNK         = 1 * 1024 * 1024
                    FLUSH_EVERY   = 16 * 1024 * 1024
                    bytes_since_flush = 0

                    with open(part_path, write_mode) as fh:
                        for chunk in response.iter_content(chunk_size=CHUNK):
                            if self.cancel_event and self.cancel_event.is_set():
                                self.log(f'[INFO] {label} cancelled.')
                                fh.flush()
                                return False

                            if chunk:
                                fh.write(chunk)
                                bytes_done        += len(chunk)
                                bytes_since_flush += len(chunk)

                                if bytes_since_flush >= FLUSH_EVERY:
                                    fh.flush()
                                    bytes_since_flush = 0

                                now = time.time()
                                if now - last_emit_time >= 0.08 or (
                                    total_bytes > 0 and bytes_done >= total_bytes
                                ):
                                    last_emit_time = now
                                    samples.append((now, bytes_done))
                                    if len(samples) > 8:
                                        samples = samples[-8:]

                                    if len(samples) >= 2 and (samples[-1][0] - samples[0][0]) > 0.001:
                                        speed_bps = (samples[-1][1] - samples[0][1]) / (
                                            samples[-1][0] - samples[0][0]
                                        )
                                    else:
                                        elapsed   = now - start_time
                                        speed_bps = bytes_done / elapsed if elapsed > 0.001 else 0

                                    speed_mbps = round(speed_bps / (1024*1024), 2)
                                    progress_percent = int(bytes_done / total_bytes * 100) if total_bytes else 0
                                    remaining  = max(total_bytes - bytes_done, 0)
                                    eta_sec    = int(remaining / speed_bps) if speed_bps > 1024 else None

                                    self.log(json.dumps({
                                        'type':       'progress',
                                        'percent':    progress_percent,
                                        'speed_mbps': speed_mbps,
                                        'eta_sec':    eta_sec,
                                        'size_mb':    size_mb,
                                    }))

                part_path.rename(file_path)
                return True

            except Exception as e:
                attempt += 1
                clean_err = format_network_error(e)
                saved_mb  = round(part_path.stat().st_size / (1024*1024), 1) if part_path.exists() else 0
                self.log(
                    f"[!] Connection dropped downloading '{label}' (attempt {attempt}): {clean_err}. "
                    f"{saved_mb} MB saved — will resume in 10s. (press Stop to cancel)"
                )

            for _ in range(10):
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

            # ── Pre-scan: count already-finished files so the progress bar
            # shows "File 1 of 35" on a resume, not "File 1 of 135" ────────
            already_done = 0
            for _, _, _mime, _rel, _ in items:
                if 'vnd.google-apps' in _mime:
                    continue  # these are never downloaded as binary files
                _fp = download_path / _rel
                if _fp.exists():
                    already_done += 1

            remaining_count = total - already_done

            if already_done > 0:
                self.log(
                    f"Found {total} total items — "
                    f"{already_done} already downloaded, "
                    f"{remaining_count} remaining. Starting download…"
                )
            else:
                self.log(f"Found {total} total items. Starting download…")

            self.downloaded_count = 0
            self.skipped_count = 0
            # Counts only files actually attempted this session (not pre-existing ones)
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
                # Report progress against remaining_count (files still needed this session)
                # so on a resume the bar correctly shows "1 of 35" not "1 of 135".
                self.log(json.dumps({
                    "type": "overall_progress",
                    "current": file_index,
                    "total": remaining_count,
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
