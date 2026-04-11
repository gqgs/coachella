import subprocess
import json
import os
import sys

def main():
    if not os.path.exists("config.json"):
        print("Error: config.json not found.")
        sys.exit(1)

    with open("config.json", "r") as f:
        config = json.load(f)

    os.makedirs("descriptions", exist_ok=True)

    for stage in config.get("STAGES", []):
        name = stage["name"]
        url = stage["url"]
        safe_name = name.replace(" ", "_")
        target_path = os.path.join("descriptions", f"{safe_name}.txt")

        print(f"Downloading description for {name}...")
        try:
            result = subprocess.run(
                ["yt-dlp", "--get-description", "--no-warnings", "--ignore-errors", url],
                capture_output=True, text=True, check=True, timeout=60
            )
            with open(target_path, "w") as f:
                f.write(result.stdout)
            print(f"  Saved to {target_path}")
        except Exception as e:
            print(f"  Error downloading {name}: {e}")

if __name__ == "__main__":
    main()
