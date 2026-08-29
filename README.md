# Copyied

A compact text clipboard history widget for Windows and macOS.

## Features

- Watches the clipboard automatically.
- Stores the 10 most recent items.
- Supports text and URLs.
- Keeps up to 10 text/link favorites.
- Includes dark mode and always-on-top settings.
- Saves app data in the platform's application-data folder.

## Windows

Double-click the `Copyied` desktop shortcut.

To recreate the shortcut:

```powershell
cd C:\Users\mehme\clipboard-history-tool
.\create-shortcut.ps1
```

To run from the terminal:

```powershell
cd C:\Users\mehme\clipboard-history-tool
.\run.ps1
```

## macOS

For a local development run, double-click `launch.command`. macOS may ask for permission the first time; allow it in Privacy & Security.

To build a standalone application:

```bash
chmod +x launch.command build-mac.sh
./build-mac.sh
open dist/Copyied.app
```

The macOS app stores its data in `~/Library/Application Support/Copyied/store.json`.
