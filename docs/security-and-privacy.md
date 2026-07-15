# Security And Privacy Notes

WaveDeck is designed to keep presentation material on the local machine.

## What The App Does

- Opens local `.ppt` and `.pptx` files
- Uses Microsoft PowerPoint COM to export slide images
- Stores validated cache files under `%LOCALAPPDATA%\GesturePPT\projects\`
- Stores runtime logs under `%LOCALAPPDATA%\GesturePPT\logs\gesture-ppt.log`

## What The App Does Not Do

- Upload slide contents to a remote service
- Write PPT text content into logs
- Auto-install PowerPoint, Python, or third-party packages

## Publishing Guidance

Before sharing screenshots, logs, or issue reports:

- remove private slide content
- remove filesystem paths if they reveal sensitive names
- never paste access tokens or cookies
- avoid showing camera footage in public showcase assets

## Cache Safety

WaveDeck exports into a temporary directory first. The cache is only promoted after the slide count and image readability checks pass, so a failed or canceled export does not replace a healthy cache.
