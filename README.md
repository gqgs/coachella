# Coachella 2026 Desktop App

A desktop application reproducing the Coachella live stream interface.

## Prerequisites

- Python 3.x
- `mpv` and `libmpv` installed on your system.
  - On Arch Linux: `sudo pacman -S mpv`
  - On Ubuntu/Debian: `sudo apt install mpv libmpv-dev`
  - On macOS: `brew install mpv`
- `yt-dlp` should be available (installed via pip in requirements).

## Setup

1. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Download thumbnails:
   ```bash
   python download_thumbnails.py
   ```

## Running the App

```bash
source venv/bin/activate
python main.py
```

## Features

- **Stream Switching**: Click on any of the 7 stage thumbnails at the bottom left to switch the live stream.
- **Embedded Player**: Uses `mpv` for high-performance video playback.
- **Fullscreen**: 
  - Double-click the video area to toggle fullscreen.
  - Press `F` to toggle fullscreen.
  - Press `Esc` to exit fullscreen.
