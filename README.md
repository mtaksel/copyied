# Copyied

A compact text clipboard history widget for Windows and macOS.

## Features

- Watches the clipboard automatically.
- Stores the 10 most recent items.
- Supports text and URLs.
- Keeps up to 10 text/link favorites.
- Includes dark mode and always-on-top settings.
- Saves app data in the platform's application-data folder.

## Platform versions

- Windows: see [`windows/README.md`](windows/README.md)
- macOS: see [`macos/README.md`](macos/README.md)

## Windows

For a standalone one-click app, download the `Copyied-Windows` artifact from GitHub Actions and run `Copyied.exe`. It does not open a Python or terminal window.

Double-click the `Copyied` desktop shortcut or run `dist/Copyied.exe` directly.

## macOS

Download the `Copyied-macOS` artifact from GitHub Actions, unzip it, and double-click `Copyied.app`.

For a local development run, double-click `launch.command`. macOS may ask for permission the first time; allow it in Privacy & Security.

To build a standalone application:

```bash
chmod +x launch.command build-mac.sh
./build-mac.sh
open dist/Copyied.app
```

The macOS app stores its data in `~/Library/Application Support/Copyied/store.json`.
