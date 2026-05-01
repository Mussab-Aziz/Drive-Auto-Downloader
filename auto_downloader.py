import io
import os
import time
from pathlib import Path
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

# Configure these with environment variables for safer open-source usage.
FOLDER_ID = os.getenv('GOOGLE_DRIVE_FOLDER_ID', '')
DOWNLOAD_DIR = os.getenv('DOWNLOAD_DIR', 'downloads')

def file_already_exists(download_dir: Path, file_name: str) -> bool:
    target_path = download_dir / file_name
    if target_path.exists():
        return True

    target_stem = target_path.stem.lower()
    for existing_file in download_dir.iterdir():
        if existing_file.is_file() and existing_file.stem.lower() == target_stem:
            return True

    return False

def get_credentials_file():
    candidates = [
        Path('credentials.json'),
        Path('client_secret_file.json'),
    ]

    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    matches = sorted(Path('.').glob('client_secret*.json'))
    if matches:
        return str(matches[0])

    raise FileNotFoundError(
        'No OAuth client secret file found. Expected credentials.json or client_secret*.json.'
    )

def authenticate():
    creds = None
    if os.path.exists('token.json'):
        try:
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        except Exception:
            # Placeholder/invalid token files should trigger a fresh OAuth flow.
            creds = None
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(get_credentials_file(), SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return creds

def download_sequential_files():
    if not FOLDER_ID:
        raise ValueError(
            'GOOGLE_DRIVE_FOLDER_ID is not set. Set it as an environment variable before running.'
        )

    creds = authenticate()
    service = build('drive', 'v3', credentials=creds)

    query = f"'{FOLDER_ID}' in parents and trashed=false"
    items = []
    page_token = None

    print("Scanning Google Drive folder for files... (This might take a moment)")
    
    # NEW: Pagination Loop to get ALL files, no matter how many
    while True:
        results = service.files().list(
            q=query, 
            fields="nextPageToken, files(id, name, mimeType)",
            pageToken=page_token,
            pageSize=1000 # Ask for up to 1000 per page to speed up the scan
        ).execute()
        
        items.extend(results.get('files', []))
        page_token = results.get('nextPageToken', None)
        
        if page_token is None:
            break # Exit the loop when there are no more pages

    if not items:
        print('No files found in the specified folder.')
        return

    download_dir = Path(DOWNLOAD_DIR)
    download_dir.mkdir(parents=True, exist_ok=True)
    print(f"Found {len(items)} total items. Starting sequential download...")

    for item in items:
        file_id = item['id']
        file_name = item['name']
        mime_type = item.get('mimeType', '')
        
        # SKIP LOGIC 1: Skip Google Docs/Folders
        if 'vnd.google-apps' in mime_type:
            continue

        # SKIP LOGIC 2: Skip files that already exist
        if file_already_exists(download_dir, file_name):
            print(f"Skipping: '{file_name}' (Already exists in destination folder)")
            continue

        file_path = download_dir / file_name

        print(f"\nDownloading: {file_name}")
        
        request = service.files().get_media(fileId=file_id)
        fh = io.FileIO(file_path, 'wb')
        downloader = MediaIoBaseDownload(fh, request)
        
        done = False
        retries = 0
        max_retries = 5 
        
        while not done:
            try:
                status, done = downloader.next_chunk(num_retries=3)
                if status:
                    print(f"Download Progress: {int(status.progress() * 100)}%", end='\r')
                retries = 0 
                
            except Exception as e:
                retries += 1
                if retries > max_retries:
                    print(f"\n[!] Failed to download '{file_name}' after {max_retries} attempts. Skipping to next file.")
                    break 
                
                print(f"\n[!] Error encountered: {e}")
                print(f"[!] Connection lost or unstable. Waiting 10 seconds before retry {retries}/{max_retries}...")
                time.sleep(10)
        
        if done:
            print(f"\nSuccessfully downloaded: {file_name}")

if __name__ == '__main__':
    download_sequential_files()