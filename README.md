Drive Auto Downloader

Drive Auto Downloader is a Python tool that downloads all files from a specific Google Drive folder to your local machine. It supports large folders with pagination, skips Google Docs-like file types, avoids duplicate downloads, and retries when network issues occur.

## 🎯 Features

### Google Drive Authentication

- OAuth 2.0 login flow using Google APIs
- Automatic token reuse via local token file
- Automatic token refresh when expired
- Safe open-source setup using local credentials files and token caching

### Folder Download Automation

- Downloads all files from a target Google Drive folder
- Uses pagination to fetch every item (handles folders with many files)
- Ignores trashed files
- Skips Google-native file types (Docs/Sheets/Slides/Folders)

### Smart Download Behavior

- Duplicate prevention by filename and case-insensitive stem matching
- Sequential downloading for stability
- Retry logic on transient failures (up to 5 retries per file)
- Progress output while each file is downloading

## 🚀 Getting Started

### Prerequisites

- Python 3.7 or higher
- Git (optional, for cloning the repository)

### Installation

1. Download the code

```bash
git clone <your-github-repository-url>
cd <name-of-your-repository-folder>
```

2. Install dependencies

```bash
pip install --upgrade google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

3. Google Cloud authentication setup

- Go to Google Cloud Console.
- Create a new project (or select an existing one), then open **APIs & Services > Library**.
- Search for **Google Drive API** and click **Enable**.
- Go to **APIs & Services > OAuth consent screen**.
- Select **External** and click **Create**.
- Fill in required fields (App name, User support email, Developer contact info).
- Under **Test users**, click **+ Add Users** and add your Google email address.
- Go to **APIs & Services > Credentials**.
- Click **+ Create Credentials > OAuth client ID**.
- Select **Desktop app** as the application type.
- Click **Download JSON**.
- Rename the downloaded file to `credentials.json`.
- Move `credentials.json` into the project root (next to `auto_downloader.py`).

4. Configure the script

Open `auto_downloader.py` and update these variables at the top:

```python
# The ID from the end of your Google Drive folder URL
FOLDER_ID = 'your_target_folder_id_here'

# The local folder where you want the files saved
DOWNLOAD_DIR = r'E:\Your Target Folder Name'
```

5. Run the tool

```bash
python auto_downloader.py
```

On first run, a browser window opens for Google sign-in and consent.

If your app is still in testing mode, Google may show a warning page:

- Click **Advanced**.
- Click **Go to [App Name] (unsafe)**.
- Click **Continue** to grant read permissions.

After successful login, a local `token.json` file is created automatically.

## 📱 How It Works

1. Authenticates with Google Drive API using OAuth.
2. Fetches all files from the configured folder using paginated API calls.
3. Filters out Google-native file types.
4. Skips files that already exist in destination.
5. Downloads each remaining file with retry and progress tracking.

## 🛠️ Tech Stack

- Python
- Google Drive API (v3)
- google-auth / google-auth-oauthlib
- google-api-python-client

## 📂 Project Structure

```
Download Automation/
├── auto_downloader.py        # Main downloader logic
├── credentials.json          # OAuth credentials (local only, ignored by git)
├── client_secret_file.json   # Optional alternate OAuth credentials file
├── token.json                # OAuth token cache (ignored by git)
├── .gitignore                # Secret and local file ignore rules
└── README.md                 # Project documentation
```

## 🔐 Security for Open Source

This project is prepared for public repositories:

- Secrets are not hardcoded in source code.
- Sensitive files are ignored by git:
  - `token.json`
  - `credentials.json`
  - `client_secret_file.json`
  - `client_secret*.json`
  - `.env*`

Important:
- Never commit real OAuth credentials or token files.
- If credentials/tokens were previously exposed, rotate/revoke them in Google Cloud Console.

## ✅ Troubleshooting

### `No OAuth client secret file found`

Place `credentials.json` in the project root (next to `auto_downloader.py`).

### Browser login keeps asking every run

Ensure `token.json` is being created and writable in the project directory.

### `GOOGLE_DRIVE_FOLDER_ID is not set`

Set your target folder correctly before running (either in script variables or environment variables, depending on your version).

Built with ❤️ by Mussab