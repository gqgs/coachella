import subprocess
import sys
import os

def run_command(command, description):
    print(f"\n>>> {description}...")
    try:
        # Use the same python interpreter as the current script
        cmd = [sys.executable] + command
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error during {description}: {e}")
        return False
    return True

def main():
    # 0. Update yt-dlp (frequently needed for live streams)
    run_command(["-m", "pip", "install", "-U", "yt-dlp"], "Updating yt-dlp to latest version")

    # 1. Download descriptions
    if not run_command(["download_descriptions.py"], "Downloading YouTube descriptions"):
        print("Continuing anyway (using existing cache if available)...")

    # 2. Sync schedule
    if not run_command(["sync_schedule.py"], "Extracting schedule data"):
        sys.exit(1)

    # 3. Run the main app
    print("\n>>> Launching Coachella Desktop App...")
    # Using Popen for the main app so we don't necessarily block if we wanted to do more, 
    # but run is fine here.
    try:
        subprocess.run([sys.executable, "main.py"])
    except KeyboardInterrupt:
        print("\nShutting down...")

if __name__ == "__main__":
    main()
