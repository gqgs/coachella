import json
import os
import sys
from extractor import parse_multi_day_schedule

def main():
    if not os.path.exists("config.json"):
        print("Error: config.json not found.")
        sys.exit(1)

    with open("config.json", "r") as f:
        config = json.load(f)

    full_schedule = {} # Format: { "Friday": { "STAGE": [...] }, "Saturday": ... }

    desc_dir = "descriptions"
    if not os.path.exists(desc_dir):
        print(f"Error: {desc_dir}/ directory not found. Please run download_descriptions.py first.")
        sys.exit(1)

    for stage in config.get("STAGES", []):
        name = stage["name"]
        safe_name = name.replace(" ", "_")
        desc_path = os.path.join(desc_dir, f"{safe_name}.txt")

        if not os.path.exists(desc_path):
            print(f"  Warning: No description file for {name} found at {desc_path}")
            continue

        print(f"Parsing schedule for {name}...")
        with open(desc_path, "r") as f:
            text = f.read()
        
        stage_days = parse_multi_day_schedule(text)
        
        for day, artists in stage_days.items():
            if day not in full_schedule:
                full_schedule[day] = {}
            full_schedule[day][name] = artists
            print(f"  - Found {len(artists)} artists for {day}")

    if full_schedule:
        with open("schedule.json", "w") as f:
            json.dump(full_schedule, f, indent=2)
        print("\nSuccess! schedule.json updated with multi-day data.")
    else:
        print("\nError: No schedule data was extracted.")

if __name__ == "__main__":
    main()
