import subprocess
import sys
import os
import requests
import stat

def run_command(command, description):
    print(f"\n>>> {description}...")
    try:
        # Use sys.executable to ensure we use the venv's python
        cmd = [sys.executable] + command
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error during {description}: {e}")
        return False
    return True

def download_sabr_executable():
    print("\n>>> Downloading specialized yt-dlp executable (SABR) for 4K support...")
    
    # Map platforms to SABR release assets
    if sys.platform.startswith("win"):
        asset = "yt-dlp.exe"
        target = "yt-dlp_sabr.exe"
    elif sys.platform.startswith("darwin"):
        asset = "yt-dlp_macos"
        target = "yt-dlp_sabr"
    else:
        asset = "yt-dlp_linux"
        target = "yt-dlp_sabr"

    url = f"https://github.com/bashonly/yt-dlp/releases/download/sabr/{asset}"
    
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        with open(target, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        # Make executable (not needed on Windows but safe to call)
        if not sys.platform.startswith("win"):
            st = os.stat(target)
            os.chmod(target, st.st_mode | stat.S_IEXEC)
            
        print(f"  Successfully downloaded and prepared {target}")
        return True
    except Exception as e:
        print(f"  Error downloading SABR executable: {e}")
        return False

def main():
    # 0. Ensure SABR executable is present
    target = "yt-dlp_sabr.exe" if sys.platform.startswith("win") else "yt-dlp_sabr"
    if not os.path.exists(target):
        if not download_sabr_executable():
            sys.exit(1)

    # 1. Download descriptions
    if not run_command(["download_descriptions.py"], "Downloading YouTube descriptions"):
        print("Continuing anyway (using existing cache if available)...")

    # 2. Sync schedule
    if not run_command(["sync_schedule.py"], "Extracting schedule data"):
        sys.exit(1)

    # 3. Run the main app
    print("\n>>> Launching Coachella Desktop App...")
    try:
        subprocess.run([sys.executable, "main.py"])
    except KeyboardInterrupt:
        print("\nShutting down...")

if __name__ == "__main__":
    main()
