# Coachella Desktop App

A high-performance desktop application for watching Coachella livestreams with a perfectly synced, interactive schedule. Built with Python, PySide6, and mpv.

<img width="1379" height="900" alt="image" src="https://github.com/user-attachments/assets/f6eb2b1b-d9ce-4179-9dfb-024465b1b7d8" />

## Features

- **Interactive Schedule**: A programmatically rendered, scrollable grid showing the full lineup across all 7 stages.
- **Multi-Day Support**: Switch between Friday, Saturday, and Sunday schedules using tabs.
- **Live Time Tracking**: A precise red timeline that indicates exactly who is playing right now in Pacific Daylight Time (PDT).
- **Column-Based Navigation**: Click anywhere on a stage's column to instantly switch the video player to that stream.
- **Automated Sync**: One-command synchronization that fetches the latest artist schedule directly from official YouTube descriptions.
- **Stream Recording**: Press the `R` key while the video window is focused to start or stop recording the current stream to a local file. HLS playback records to `.ts`; 1440p and 4K SABR playback records to `.mkv`. A blinking "🔴 RECORDING" indicator will appear on the schedule timeline.
- **Native Performance**: Uses `mpv` as the video backend for low-latency, high-quality streaming.

## Prerequisites

- **Python 3.9+**
- **mpv player**: The application requires `libmpv` to be installed on your system.
  - **Arch Linux**: `sudo pacman -S mpv`
  - **Ubuntu/Debian**: `sudo apt install mpv libmpv-dev`
  - **macOS**: `brew install mpv`
- **FFmpeg**: Required for 1440p and 4K YouTube SABR livestream playback. The app uses the bundled `yt-dlp_sabr` downloader to fetch SABR fragments, then uses `ffmpeg` to mux the separate live video and audio fragments into a stream that `mpv` can play.
  - **Arch Linux**: `sudo pacman -S ffmpeg`
  - **Ubuntu/Debian**: `sudo apt install ffmpeg`
  - **macOS**: `brew install ffmpeg`

## Installation

1. **Clone and Setup Environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use: venv\Scripts\activate
   pip install -r requirements.txt
   ```

## Usage

To automatically download the latest descriptions, sync the schedule, and launch the app in one command:

```bash
python main.py
```

- **Quality Selection**: `Auto`, `1080p`, and `720p` use the standard HLS playback path. `1440p` and `4K` use the bundled SABR-enabled `yt-dlp` fork plus FFmpeg.
- **Switch Stages**: Click on any column in the schedule grid.
- **Switch Days**: Click the tabs at the top (aligned with the stage columns).
- **Fullscreen**: Toggle fullscreen in the video player using the `F` key or double-click.
- **Recording**: Press `R` in the video window to start/stop saving the stream to a local file.

## Configuration

The application is entirely data-driven. To update stream URLs or stage colors for future years, simply edit `config.json`.

## Troubleshooting

- **Library Errors on Linux**: The app includes a bootstrap loader that handles Qt library version conflicts common on rolling-release distros (like Arch).
- **Timezone**: The app uses `America/Los_Angeles` (PDT) for the timeline regardless of your local system time, matching the official festival schedule.
