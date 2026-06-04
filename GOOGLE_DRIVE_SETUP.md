# Getting Google Drive API Credentials

This guide walks you through setting up Google Drive API credentials for the downloader.

## Step-by-Step Setup

### 1. Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click on the project dropdown at the top
3. Click **"NEW PROJECT"**
4. Enter a name (e.g., "Drive Downloader")
5. Click **"CREATE"**
6. Wait for the project to be created (may take a minute)

### 2. Enable Google Drive API

1. In the Cloud Console, make sure your new project is selected
2. Click the **menu icon** (☰) on the top left
3. Navigate to **APIs & Services** → **Library**
4. Search for **"Google Drive API"**
5. Click on it
6. Click the **ENABLE** button
7. Wait for it to enable

### 3. Create OAuth Credentials

1. Go to **APIs & Services** → **Credentials** (in the left menu)
2. Click **+ CREATE CREDENTIALS** button
3. Select **OAuth client ID**
4. You'll be prompted to create a consent screen first:
   - Click **CREATE CONSENT SCREEN**
   - Select **External** for User Type
   - Click **CREATE**

### 4. Configure the Consent Screen

Fill in the required information:
- **App name**: "Drive Downloader"
- **User support email**: Your Google email
- **Developer contact email**: Your Google email
- Click **SAVE AND CONTINUE**

Skip the scopes screen (or add `https://www.googleapis.com/auth/drive.readonly`).

Skip the test users screen.

Go back to creating credentials by clicking **Credentials** in the left menu.

### 5. Create Desktop Application Credentials

1. Click **+ CREATE CREDENTIALS** again
2. Select **OAuth client ID**
3. Choose **Desktop application** as the Application type
4. Name it (e.g., "Drive Downloader Desktop")
5. Click **CREATE**
6. You'll see a popup with your credentials
7. Click **DOWNLOAD JSON**

### 6. Place the Credentials File

1. Save the downloaded JSON file
2. Rename it to **`client_secret_file.json`**
3. Place it in the same folder as the downloader app:
   ```
   e:\Download Automation\
   ├── app_ui.py
   ├── enhanced_downloader.py
   ├── client_secret_file.json  ← Here
   └── ...
   ```

## Verification

After placing the file, you should see it listed when you:
1. Run `python app_ui.py`
2. Click the "Browse" button next to "Client Secret File"

## First Run

When you start a download for the first time:
1. A browser window will open
2. Google will ask you to authenticate
3. Click **Allow** to grant the app permission
4. You'll be redirected to `localhost`
5. Close the browser window
6. The app saves your token and continues

Your token is saved in `token.json` for future use.

## What Permissions Are Granted?

The app only requests **read-only access** to your Google Drive:
- Can view and download files
- Cannot modify, delete, or upload files
- Cannot share files

## Troubleshooting

### "Invalid Credentials" Error
- Double-check the file is named `client_secret_file.json`
- Verify you downloaded it from the correct Google Cloud project
- Try downloading it again

### OAuth Window Doesn't Open
- Check if a popup blocker is preventing it
- Disable popup blocker for localhost temporarily
- Check your firewall settings

### Permission Denied After Authentication
- Make sure the folder you're downloading from is accessible with your Google account
- Verify you have read permission on that folder
- Try re-authenticating by deleting `token.json`

### "Quota Exceeded"
- Google Drive API has rate limits
- Wait a few hours before downloading again
- Consider downloading smaller folders first

## Security Notes

✅ **Safe:**
- Your credentials are stored locally
- No credentials are sent to third parties
- The app only accesses Google Drive
- You can revoke access anytime

🔐 **To revoke access:**
1. Go to [Google Account Security](https://myaccount.google.com/security)
2. Find "Third-party apps & services"
3. Remove "Drive Downloader" access

## Additional Resources

- [Google Cloud Console](https://console.cloud.google.com/)
- [Google Drive API Documentation](https://developers.google.com/drive)
- [OAuth 2.0 Guide](https://developers.google.com/identity/protocols/oauth2)
