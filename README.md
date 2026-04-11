# Coachella Desktop App

A high-performance desktop application for watching Coachella livestreams with a perfectly synced, interactive schedule. Built with Python, PySide6, and mpv.

## Features

- **Interactive Schedule**: A programmatically rendered, scrollable grid showing the full lineup across all 7 stages.
- **Multi-Day Support**: Switch between Friday, Saturday, and Sunday schedules using tabs.
- **Live Time Tracking**: A precise red timeline that indicates exactly who is playing right now in Pacific Daylight Time (PDT).
- **Column-Based Navigation**: Click anywhere on a stage's column to instantly switch the video player to that stream.
- **Automated Sync**: One-command synchronization that fetches the latest artist schedule directly from official YouTube descriptions.
- **Stream Recording**: Press the `R` key while the video window is focused to start or stop recording the current stream to a local `.ts` file. A blinking "🔴 RECORDING" indicator will appear on the schedule timeline.
- **Native Performance**: Uses `mpv` as the video backend for low-latency, high-quality streaming.

## Prerequisites

- **Python 3.9+**
- **mpv player**: The application requires `libmpv` to be installed on your system.
  - **Arch Linux**: `sudo pacman -S mpv`
  - **Ubuntu/Debian**: `sudo apt install mpv libmpv-dev`
  - **macOS**: `brew install mpv`

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
python run.py
```

- **Switch Stages**: Click on any column in the schedule grid.
- **Switch Days**: Click the tabs at the top (aligned with the stage columns).
- **Fullscreen**: Toggle fullscreen in the video player using the `F` key or double-click.
- **Recording**: Press `R` in the video window to start/stop saving the stream to a local file.

## Configuration

The application is entirely data-driven. To update stream URLs or stage colors for future years, simply edit `config.json`.

## Troubleshooting

- **Library Errors on Linux**: The app includes a bootstrap loader that handles Qt library version conflicts common on rolling-release distros (like Arch).
- **Timezone**: The app uses `America/Los_Angeles` (PDT) for the timeline regardless of your local system time, matching the official festival schedule.
