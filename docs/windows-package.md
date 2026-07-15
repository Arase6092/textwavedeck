# Windows Package

WaveDeck publishes a Windows `onedir` package for the public release line.

## Why `onedir`

- PySide6, OpenCV, MediaPipe, and pywin32 are easier to validate in `onedir`
- startup is more predictable than a large `onefile` bundle
- runtime debugging is simpler if a contributor reports missing files

## Package Contents

- `WaveDeck.exe`
- required runtime DLLs and Python modules
- `Launch-WaveDeck.cmd`
- `README-QuickStart.txt`

## Runtime Requirements

- Windows 10 / 11
- Microsoft PowerPoint 2016 or later

Python is bundled. PowerPoint is not.
