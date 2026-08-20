# GhostMail

GhostMail is a self-hosted email delivery application for Windows. It provides a browser-based interface for composing individual messages, sending spreadsheet-driven campaigns, scheduling delivery, and monitoring results through Resend or ZeptoMail.

The Windows installer includes Python and all application dependencies. End users do not need a development environment.

## Features

- Send individual HTML emails with CC, BCC, and attachments
- Import campaign recipients from CSV, XLS, or XLSX files
- Personalize and preview bulk messages for up to 1,000 recipients
- Generate a personalized PDF attachment for every campaign recipient
- Pause, resume, cancel, and inspect campaign jobs
- Schedule messages and campaigns for later delivery
- Store and test Resend and ZeptoMail API keys from the interface
- Check verified sender domains when supported by the provider
- Keep job history and delivery failures in a local SQLite database
- Run locally on `127.0.0.1`; the application is not exposed to the network

## Install on Windows

1. Sign in to GitHub with access to this repository, then download **[GhostMail-Setup.exe for Windows](https://github.com/sisbarro/ghost/releases/download/v1.2.1/GhostMail-Setup.exe)**.
2. Double-click the installer.
3. Keep **Create a desktop shortcut** selected and choose **Install**.
4. Leave **Launch GhostMail** selected and choose **Finish**.
5. Sign in with the initial password `ghost2026`.
6. Open **API Keys**, add a Resend or ZeptoMail key, and test it before sending.

The installer does not require administrator privileges. GhostMail opens in your default browser and stores its data in `%LOCALAPPDATA%\GhostMail`.

This is a Windows `.exe`, not an Android app. If the link opens an Android download or app store, discard that file and use the exact GitHub release link above. Because this repository is private, GitHub returns a 404 unless the browser is signed in to an authorized account.

> [!IMPORTANT]
> Change the initial password before normal use. Create `%LOCALAPPDATA%\GhostMail\.env`, set `APP_PASSWORD` and `FLASK_SECRET_KEY`, then restart GhostMail. See [`.env.example`](.env.example) for the available settings.

> [!NOTE]
> Locally built installers are unsigned. Windows SmartScreen may display **Windows protected your PC** until release builds are signed with a trusted code-signing certificate.

## Install on macOS

1. Download `GhostMail-macOS-Source.zip` from the GitHub release, unzip it on a Mac, and run `./build-macos.sh` to produce `installer/output/GhostMail.dmg` (or build from a clone — see below).
2. Open the DMG and drag **GhostMail.app** to **Applications**.
3. First launch: right-click **GhostMail.app** and choose **Open** (unsigned builds require this once), or approve it under **System Settings → Privacy & Security**.
4. Sign in with the initial password `ghost2026`, then add a provider API key.

GhostMail opens in the default browser and stores its data in `~/Library/Application Support/GhostMail`. To change the password, create `.env` in that folder and set `APP_PASSWORD`, then relaunch.

### Build the macOS app

On a Mac with Python 3.10+, run from this directory:

```bash
chmod +x build-macos.sh
./build-macos.sh
```

This produces `installer/output/GhostMail.dmg` containing `GhostMail.app`. macOS apps must be built on macOS; the Windows machine cannot cross-build them. For public distribution without Gatekeeper warnings, sign with a Developer ID certificate and notarize.

## Provider setup

GhostMail sends through an account you control:

1. Create an account with [Resend](https://resend.com/) or [ZeptoMail](https://www.zoho.com/zeptomail/).
2. Verify the sending domain in the provider dashboard.
3. Generate an API key with permission to send email.
4. In GhostMail, choose **API Keys**, paste the key for that provider, and choose **Save & Test**.
5. Use a From address on the verified domain.

API keys and job data remain on the local computer. The application contacts only the selected email provider and the external asset CDNs referenced by the interface.

## Personalized PDF mail merge

Campaigns can generate a different PDF attachment for every recipient:

1. Upload a recipient spreadsheet and compose the campaign.
2. Enable **Personalized PDF attachment**.
3. Enter a merged filename such as `Invoice-{{Account_Number}}.pdf`.
4. Enter the PDF document content using the same spreadsheet placeholders, such as `{{First_Name}}` or `{{Balance}}`.
5. Start or schedule the campaign.

GhostMail merges the current recipient's values, creates the PDF in memory, and attaches it only to that recipient's email. Common uploaded attachments can be used alongside the generated PDF. Basic HTML formatting including headings, paragraphs, bold, italics, underline, lists, line breaks, and text alignment is supported in PDF content.

## Run from source

Requirements:

- Windows 10 or later, or macOS 12 or later
- Python 3.10 or later

```powershell
git clone https://github.com/sisbarro/ghost.git
cd ghost
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
Copy-Item .env.example .env
py launcher.py
```

Edit `.env` before normal use. The source version stores its SQLite database in the project directory; packaged builds use `%LOCALAPPDATA%\GhostMail`.

## Build the Windows installer

Run the packaging script from PowerShell:

```powershell
.\build-installer.ps1
```

The script installs Python build dependencies, builds `GhostMail.exe` with PyInstaller, installs Inno Setup through `winget` when needed, and creates:

```text
installer\output\GhostMail-Setup.exe
```

The build machine needs Python 3, `winget` or Inno Setup 6, and internet access. See [INSTALL.md](INSTALL.md) for additional packaging notes.

## Project structure

```text
app.py                  Flask application and API routes
database.py             SQLite persistence layer
providers.py            Resend and ZeptoMail integrations
launcher.py             Local server and browser launcher
runtime_paths.py        Source and packaged data locations
templates/index.html    Application interface
static/                 Browser JavaScript and styles
GhostMail.spec          PyInstaller configuration
installer/GhostMail.iss Inno Setup configuration
build-installer.ps1     Reproducible Windows packaging script
```

## Security and privacy

- Never commit `.env`, API keys, or `ghostmail.db`; these paths are excluded by [`.gitignore`](.gitignore).
- GhostMail binds only to `127.0.0.1`, so other devices cannot access it directly.
- Provider credentials are stored locally. Protect the Windows account and use restricted API keys where available.
- Email recipient data and campaign history may contain personal information. Back up and handle `%LOCALAPPDATA%\GhostMail` accordingly.
- Use GhostMail only for recipients who have consented to receive your messages and follow applicable anti-spam laws and provider policies.

## License

No open-source license has been granted yet. Unless a license file is added, the source remains all rights reserved by its copyright holder.