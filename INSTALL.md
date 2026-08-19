# GhostMail for Windows

## Install

1. Double-click `GhostMail-Setup.exe`.
2. Keep **Create a desktop shortcut** selected and choose **Install**.
3. Leave **Launch GhostMail** selected and choose **Finish**.
4. GhostMail opens in the default browser. The initial login password is `ghost2026`.
5. Open **API Keys** and add a Resend or ZeptoMail API key before sending email.

For campaign mail merge, enable **Personalized PDF attachment** and use spreadsheet placeholders in the PDF filename and content.

GhostMail includes its own Python runtime. End users do not need Python, Flask, or any other developer tools.

Application data is stored in `%LOCALAPPDATA%\GhostMail` and is preserved when GhostMail is upgraded or uninstalled.

## Build the installer

From PowerShell in this directory, run:

```powershell
.\build-installer.ps1
```

The script installs the required build tools when possible and creates:

```text
installer\output\GhostMail-Setup.exe
```

The build machine needs Python 3 and internet access. The finished installer can be installed offline; GhostMail needs internet access for email delivery and its externally hosted interface assets.

This local build is not code-signed. Windows SmartScreen may show **Windows protected your PC** on another computer; choose **More info**, verify the publisher/source, and choose **Run anyway**. Signing the installer with a trusted code-signing certificate removes this warning for production distribution.

## Optional configuration

To override the initial login password, create `%LOCALAPPDATA%\GhostMail\.env` containing:

```dotenv
APP_PASSWORD=choose-a-strong-password
```

Restart GhostMail after changing this file.