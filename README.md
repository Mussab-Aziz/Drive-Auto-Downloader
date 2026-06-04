# Google Drive Folder Downloader - Complete Setup Guide

## Overview

This is a complete automation tool for downloading entire Google Drive folders while preserving folder structures. It features a professional UI built with tkinter.

## Features

✨ **Main Features:**
- Download entire Google Drive folders with all subfolders intact
- Preserve folder structure on local disk
- Filter out unwanted file types (photos, videos, audio)
- User-friendly GUI interface
- Auto-save configuration between sessions
- Progress tracking and detailed logging
- Retry logic for failed downloads
- Support for large folders with pagination

## Files Included

1. **app_ui.py** - The main GUI application (start here!)
2. **enhanced_downloader.py** - Core download engine with recursive folder support
3. **auto_downloader.py** - Command-line version (original)

## Setup Instructions

### Step 1: Install Required Dependencies

```bash
pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client
```

### Step 2: Get Google Drive API Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project
3. Enable the Google Drive API
4. Create an OAuth 2.0 Desktop Application credential
5. Download the credentials JSON file
6. Rename it to `client_secret_file.json` and place it in this folder

**Or** keep your existing naming - the app will let you browse and select any credentials file.

### Step 3: Run the Application

```bash
python app_ui.py
```

This opens the GUI where you can:
- Browse for your credentials files
- Enter the Google Drive folder ID
- Select download destination
- Choose file types to skip
- Start the download

## How to Use the GUI

### Getting Your Google Drive Folder ID

1. Open your Google Drive folder
2. Look at the URL: `https://drive.google.com/drive/folders/YOUR_FOLDER_ID_HERE`
3. Copy the long string after `/folders/` - that's your Folder ID
4. Paste it in the "Source Folder ID" field

### Configuration Steps

1. **Source Folder ID**: Paste the Google Drive folder ID
2. **Destination Folder**: Click "Browse" and select where to save files on your computer
3. **Token File**: Select your `token.json` (will be auto-created on first run if doesn't exist)
4. **Client Secret File**: Select your `client_secret_file.json` downloaded from Google Cloud

### File Type Filters

Check any of these to **skip** downloading those file types:
- 📷 **Skip Photos** - Excludes JPEG, PNG, GIF, WebP, BMP, TIFF, SVG
- 🎥 **Skip Videos** - Excludes MP4, MOV, MKV, WebM, FLV, WMV, 3GP, and more
- 🔊 **Skip Audio** - Excludes MP3, WAV, FLAC, AAC, OGG, M4A, AIFF, and more

### Starting the Download

1. Fill in all required fields
2. Select any file types you want to skip
3. Click **"Start Download"**
4. Watch the progress in the log window
5. Automatic retry (up to 5 times) for any failed downloads

**The app will:**
- Create all necessary folders locally
- Preserve the exact folder structure from Google Drive
- Skip files that already exist
- Skip Google native files (Google Docs, Sheets, etc.)
- Show detailed progress for each file

## Command-Line Usage (Legacy)

If you prefer command-line, you can still use `auto_downloader.py`:

```bash
python auto_downloader.py
```

Edit the `FOLDER_ID` and `DOWNLOAD_DIR` variables in the script to customize.

## First-Time Authentication

When you click "Start Download" for the first time:
1. A browser window will open asking you to authenticate with Google
2. Grant permission to the app to access your Google Drive
3. You'll be redirected to localhost - close the browser
4. The app saves your authentication token for future use

## Troubleshooting

### "No files found in the specified folder"
- Double-check your Folder ID is correct
- Make sure the folder has files you can access
- Ensure your Google credentials have read access

### "Token file error"
- Delete `token.json` to force re-authentication
- Verify your client secret file is valid

### Download interrupted
- The app automatically retries up to 5 times
- Your partially downloaded files are preserved
- Run the download again - already downloaded files will be skipped

### Permission Denied
- Verify your credentials file is properly formatted
- Check that your Google account has access to the folder
- Re-authenticate by deleting `token.json`

## Advanced: Modifying Download Behavior

Edit `enhanced_downloader.py` to customize:

```python
# Add more MIME types to filter
FILE_TYPE_FILTERS = {
    'photos': [...],
    'videos': [...],
    'audio': [...],
}

# Change retry logic
max_retries = 5  # Modify this value

# Change page size for large folders
pageSize=1000  # Increase if experiencing timeout issues
```

## Configuration Auto-Save

The app automatically saves your settings to `ui_config.json`:
- Source Folder ID
- Destination path
- Selected credentials files
- Filter preferences

These are restored when you run the app again!

## Performance Tips

1. **Large Folders**: For folders with 1000+ files, the first scan might take a few minutes
2. **Network Issues**: Download at off-peak hours for faster transfers
3. **Cancel & Resume**: You can cancel anytime and resume later - already downloaded files are skipped

## File Structure Example

**Google Drive:**
```
My Project/
├── Documents/
│   ├── report.pdf
│   └── notes.txt
├── Images/
│   ├── photo1.jpg
│   └── photo2.jpg
└── Videos/
    └── tutorial.mp4
```

**Downloaded to (with your choices):**
```
E:\Downloads\
└── My Project/
    ├── Documents/
    │   ├── report.pdf
    │   └── notes.txt
    ├── Images/
    │   ├── photo1.jpg
    │   └── photo2.jpg
    └── Videos/
        └── tutorial.mp4
```

## Support

- Check the log window for detailed error messages
- Most issues are related to authentication - try re-authenticating
- Ensure your Google Drive folder is shared appropriately

## License

Use freely for personal and commercial projects.
