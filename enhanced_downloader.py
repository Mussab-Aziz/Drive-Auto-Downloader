import io
import os
import sys
import time
from pathlib import Path
from typing import Callable, Optional
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
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
        self.downloaded_count = 0
        self.skipped_count = 0

    def log(self, message: str):
        """Log a message using the callback or print."""
        if self.log_callback:
            self.log_callback(message)
        else:
            print(message)

    def file_already_exists(self, download_dir: Path, file_name: str) -> bool:
        """Check if a file already exists in the download directory."""
        target_path = download_dir / file_name
        if target_path.exists():
            return True

        target_stem = target_path.stem.lower()
        for existing_file in download_dir.iterdir():
            if existing_file.is_file() and existing_file.stem.lower() == target_stem:
                return True

        return False

    def authenticate(self) -> Credentials:
        """Authenticate with Google Drive API."""
        creds = None
        if os.path.exists(self.token_file):
            creds = Credentials.from_authorized_user_file(self.token_file, SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                self.log("\n" + "="*70)
                self.log("AUTHENTICATION REQUIRED")
                self.log("="*70)
                self.log("")
                self.log("Please sign in with your Google account in the browser window")
                self.log("that will open momentarily...")
                self.log("")
                self.log("If a browser window doesn't open automatically:")
                self.log("Copy the authorization link below and paste it in your browser:")
                self.log("")
                
                # Capture stdout to intercept the authorization URL
                old_stdout = sys.stdout
                sys.stdout = io.StringIO()
                
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_file, SCOPES
                    )
                    creds = flow.run_local_server(port=0, open_browser=True)
                    
                finally:
                    # Restore stdout and extract the authorization URL
                    captured_output = sys.stdout.getvalue()
                    sys.stdout = old_stdout
                    
                    # Parse and log the URL
                    for line in captured_output.split('\n'):
                        if 'https://' in line and 'accounts.google.com' in line:
                            self.log(f"► {line.strip()}")
                            break
                
                self.log("")
                self.log("Waiting for authorization...")
                self.log("")
                self.log("✓ Authentication successful!")
                self.log("")
            
            with open(self.token_file, 'w') as token:
                token.write(creds.to_json())
        return creds

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
        return True

    def build_service(self):
        """Build the Google Drive service."""
        if self.service is None:
            creds = self.authenticate()
            self.service = build('drive', 'v3', credentials=creds)
        return self.service

    def verify_folder_access(self, folder_id: str):
        """
        Verify that the folder exists and we have access to it.
        
        Args:
            folder_id: The Google Drive folder ID to verify
            
        Raises:
            Exception: If folder doesn't exist or we don't have access
        """
        try:
            result = self.service.files().get(
                fileId=folder_id,
                fields="id, name, mimeType"
            ).execute()
            
            if result.get('mimeType') != 'application/vnd.google-apps.folder':
                raise Exception(f"❌ The provided ID '{folder_id}' is not a folder. It appears to be a file.")
            
        except HttpError as e:
            error_code = e.resp.status if e.resp else 500
            if error_code == 404:
                raise Exception(f"❌ Folder not found (HTTP 404). The folder ID '{folder_id}' does not exist, may have been deleted, or you have no access to it.")
            elif error_code == 403:
                raise Exception(f"❌ Access denied (HTTP 403). You don't have permission to access this folder. Please verify the folder is shared with your Google account.")
            elif error_code == 401:
                raise Exception(f"❌ Authentication failed (HTTP 401). Your credentials may have expired. Please delete token.json and try again.")
            else:
                raise Exception(f"❌ Google Drive API error (HTTP {error_code}): {str(e)}")

    def should_filter_file(self, mime_type: str, file_filters: dict) -> bool:
        """
        Check if a file should be filtered based on file type preferences.
        
        Args:
            mime_type: The MIME type of the file
            file_filters: Dictionary with keys 'photos', 'videos', 'audio' with True/False values
        
        Returns:
            True if the file should be filtered (skipped), False otherwise
        """
        if file_filters.get('photos'):
            if mime_type in FILE_TYPE_FILTERS['photos']:
                return True

        if file_filters.get('videos'):
            if mime_type in FILE_TYPE_FILTERS['videos']:
                return True

        if file_filters.get('audio'):
            if mime_type in FILE_TYPE_FILTERS['audio']:
                return True

        return False

    def get_all_files_recursive(self, folder_id: str, prefix: str = '') -> list:
        """
        Recursively get all files from a folder and its subfolders.
        
        Args:
            folder_id: The Google Drive folder ID
            prefix: Path prefix for building the relative path
        
        Returns:
            List of tuples: (file_id, file_name, mime_type, relative_path)
        """
        items = []
        page_token = None
        query = f"'{folder_id}' in parents and trashed=false"

        while True:
            try:
                results = self.service.files().list(
                    q=query,
                    fields="nextPageToken, files(id, name, mimeType)",
                    pageToken=page_token,
                    pageSize=1000,
                ).execute()

            except HttpError as e:
                error_code = e.resp.status if e.resp else 500
                if error_code == 403:
                    raise Exception(f"❌ Access denied while accessing folder. You may not have permission to this subfolder.")
                elif error_code == 404:
                    raise Exception(f"❌ A folder in the path was not found or deleted.")
                else:
                    raise Exception(f"❌ Google Drive API error: {str(e)}")

            files = results.get('files', [])
            for file_info in files:
                # Strip whitespace from names to avoid invalid paths
                file_name = file_info['name'].strip()
                relative_path = f"{prefix}/{file_name}" if prefix else file_name
                
                # If it's a folder, recurse into it
                if file_info['mimeType'] == 'application/vnd.google-apps.folder':
                    items.extend(
                        self.get_all_files_recursive(file_info['id'], relative_path)
                    )
                else:
                    # It's a file, add it to the list
                    items.append(
                        (
                            file_info['id'],
                            file_name,
                            file_info.get('mimeType', ''),
                            relative_path,
                        )
                    )

            page_token = results.get('nextPageToken', None)
            if page_token is None:
                break

        return items

    def download_file(
        self, file_id: str, file_path: Path, max_retries: int = 5
    ) -> bool:
        """
        Download a single file from Google Drive.
        
        Args:
            file_id: The Google Drive file ID
            file_path: Path where to save the file
            max_retries: Maximum number of retries
        
        Returns:
            True if successful, False otherwise
        """
        # Check for cancellation before starting
        if self.cancel_event and self.cancel_event.is_set():
            return False
            
        file_path.parent.mkdir(parents=True, exist_ok=True)

        request = self.service.files().get_media(fileId=file_id)
        fh = io.FileIO(file_path, 'wb')
        downloader = MediaIoBaseDownload(fh, request)

        done = False
        retries = 0

        while not done:
            try:
                status, done = downloader.next_chunk(num_retries=3)
                if status:
                    progress_percent = int(status.progress() * 100)
                    self.log(f"Download Progress: {progress_percent}%")
                retries = 0
                
                # Check for cancellation during download
                if self.cancel_event and self.cancel_event.is_set():
                    self.log(f"[INFO] Download of {file_path.name} cancelled.")
                    fh.close()
                    file_path.unlink(missing_ok=True)  # Remove incomplete file
                    return False

            except Exception as e:
                retries += 1
                if retries > max_retries:
                    self.log(
                        f"[!] Failed to download after {max_retries} attempts. Skipping."
                    )
                    return False

                self.log(f"[!] Error: {e}")
                self.log(f"[!] Waiting 10 seconds before retry {retries}/{max_retries}...")
                time.sleep(10)

        return True

    def download_folder(
        self,
        folder_id: str,
        download_dir: str,
        file_filters: Optional[dict] = None,
    ):
        """
        Download an entire Google Drive folder while preserving structure.
        
        Args:
            folder_id: The Google Drive folder ID to download
            download_dir: Local directory where to save files
            file_filters: Dictionary with keys 'photos', 'videos', 'audio' with True/False values
                         to filter out those file types
        """
        if file_filters is None:
            file_filters = {}

        try:
            self.log("Building Google Drive service...")
            self.build_service()

            self.log("Verifying folder access...")
            self.verify_folder_access(folder_id)

            self.log("Scanning Google Drive folder for files... (This might take a moment)")
            items = self.get_all_files_recursive(folder_id)

            if not items:
                self.log("No files found in the specified folder.")
                return

            download_path = Path(download_dir)
            download_path.mkdir(parents=True, exist_ok=True)

            self.log(f"Found {len(items)} total items. Starting download...")
            self.downloaded_count = 0
            self.skipped_count = 0

            for file_id, file_name, mime_type, relative_path in items:
                # Check for cancellation
                if self.cancel_event and self.cancel_event.is_set():
                    self.log("[INFO] Download cancelled by user.")
                    break
                # Skip Google Docs/native Google apps
                if 'vnd.google-apps' in mime_type:
                    self.log(f"Skipping: '{relative_path}' (Google native file)")
                    self.skipped_count += 1
                    continue

                # Check if file should be filtered
                if self.should_filter_file(mime_type, file_filters):
                    self.log(f"Skipping: '{relative_path}' (Filtered by type)")
                    self.skipped_count += 1
                    continue

                file_path = download_path / relative_path

                # Check if file already exists
                if file_path.exists():
                    self.log(f"Skipping: '{relative_path}' (Already exists)")
                    self.skipped_count += 1
                    continue

                self.log(f"\nDownloading: {relative_path}")

                if self.download_file(file_id, file_path):
                    self.log(f"Successfully downloaded: {relative_path}")
                    self.downloaded_count += 1
                else:
                    self.skipped_count += 1

            self.log(
                f"\n{'='*60}"
            )
            self.log(f"Download completed!")
            self.log(f"Downloaded: {self.downloaded_count} files")
            self.log(f"Skipped: {self.skipped_count} items")
            self.log(f"{'='*60}")
            
        except HttpError as e:
            error_code = e.resp.status if e.resp else 500
            self.log(f"\n[ERROR] Google Drive API Error (HTTP {error_code})")
            raise
            
        except Exception as e:
            self.log(f"\n{str(e)}")
            raise
