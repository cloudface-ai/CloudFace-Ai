# Service Account Setup Guide

This guide helps you set up Google Cloud service account to avoid expensive OAuth verification costs.

## Step 1: Create Service Account

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Select your project (or create one)
3. Go to "IAM & Admin" > "Service Accounts"
4. Click "Create Service Account"
5. Name: `cloudface-ai-bot`
6. Description: `Bot for processing shared Google Drive folders`
7. Click "Create and Continue"
8. Skip roles for now, click "Done"

## Step 2: Create and Download Key

1. Find your service account in the list
2. Click on the email address
3. Go to "Keys" tab
4. Click "Add Key" > "Create new key"
5. Choose "JSON" format
6. Click "Create"
7. Save the downloaded file as `service-account.json` in your project folder

## Step 3: Update Environment

1. Copy `example.env` to `.env`:
   ```bash
   cp example.env .env
   ```

2. Edit `.env` and update these lines:
   ```
   SERVICE_ACCOUNT_JSON_PATH=/Users/spvinod/Desktop/CloudFace-Ai/service-account.json
   BOT_SERVICE_ACCOUNT_EMAIL=your-bot@your-project-id.iam.gserviceaccount.com
   ```

3. Get the bot email from the JSON file:
   ```bash
   python3 -c "import json; print(json.load(open('service-account.json'))['client_email'])"
   ```

## Step 4: Test Setup

```bash
python test_service_account.py
```

## Step 5: Share Folder with Bot

1. Go to Google Drive
2. Right-click on a folder with photos
3. Click "Share"
4. Add the service account email (from step 3)
5. Set permission to "Viewer"
6. Copy the folder URL

## Step 6: Test the New Endpoint

Start your app:
```bash
python web_server.py
```

Test with curl:
```bash
curl -X POST http://localhost:8550/process_drive_shared \
  -H "Content-Type: application/json" \
  -d '{
    "drive_url": "https://drive.google.com/drive/folders/YOUR_FOLDER_ID",
    "force_reprocess": false,
    "max_depth": 10
  }'
```

## Benefits

- ✅ No OAuth verification costs
- ✅ No third-party security assessment needed
- ✅ Works with any Google account (consumer or Workspace)
- ✅ Same functionality as before
- ✅ Users just share folder with bot email

## Troubleshooting

- **"Service account JSON not found"**: Check the path in `.env`
- **"Access token failed"**: Verify the JSON file is valid
- **"Drive access failed"**: Check if service account has Drive API enabled
- **"Folder not accessible"**: Make sure folder is shared with bot email
