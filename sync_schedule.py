import subprocess
import json
import re
import sys
import os

def load_config():
    config_path = "config.json"
    if not os.path.exists(config_path):
        print(f"Error: {config_path} not found.")
        sys.exit(1)
    with open(config_path, "r") as f:
        return json.load(f)

def get_description(url):
    try:
        # Use a reasonable timeout and handle errors
        result = subprocess.run(
            ["yt-dlp", "--get-description", "--no-warnings", url],
            capture_output=True, text=True, check=True, timeout=30
        )
        return result.stdout
    except Exception as e:
        print(f"  Error fetching {url}: {e}")
        return ""

def parse_schedule(description, stage_name):
    # Normalize stage name for matching
    stage_name_clean = stage_name.upper().replace(" STAGE", "")
    
    # Try to find a specific section for this stage
    # Coachella descriptions often use "STAGE NAME SCHEDULE" headers
    patterns_to_try = [
        f"{stage_name.upper()} SCHEDULE",
        f"{stage_name_clean} SCHEDULE",
        f"{stage_name.upper()}"
    ]
    
    section = None
    desc_upper = description.upper()
    for p in patterns_to_try:
        start_idx = desc_upper.find(p)
        if start_idx != -1:
            # Found a header, take content until next major header or end
            # Major headers usually start with all caps or specific stage names
            next_header_idx = len(description)
            # Simple heuristic: look for next "SCHEDULE" or double newline followed by caps
            potential_next = re.search(r"\n\n[A-Z\s]+SCHEDULE", description[start_idx + len(p):])
            if potential_next:
                next_header_idx = start_idx + len(p) + potential_next.start()
            
            section = description[start_idx:next_header_idx]
            break
    
    if not section:
        section = description # Fallback

    # Regex for "4:00pm - Artist Name"
    # Coachella format is usually "Time - Artist"
    pattern = r"(\d{1,2}:\d{2}(?:am|pm))\s*-\s*(.+)"
    matches = re.findall(pattern, section)
    
    parsed = []
    for i in range(len(matches)):
        time_str, artist = matches[i]
        
        # Clean artist name (remove trailing lines/rebroadcast tags)
        artist = artist.split('\n')[0].strip()
        if "[REBROADCAST]" in artist.upper() or "LIVESTREAM BEGINS" in artist.upper() or "MUSIC RETURNS" in artist.upper():
            continue

        try:
            h_m = re.match(r"(\d{1,2}):(\d{2})(am|pm)", time_str)
            h = int(h_m.group(1))
            m = h_m.group(2)
            period = h_m.group(3)
            
            if period == "pm" and h != 12: h += 12
            if period == "am" and h == 12: h = 24
            if period == "am" and h < 4: h += 24
            
            start_time = f"{h:02d}:{m}"
            
            # Estimate end time
            if i + 1 < len(matches):
                nt_str = matches[i+1][0]
                nh_m = re.match(r"(\d{1,2}):(\d{2})(am|pm)", nt_str)
                nh = int(nh_m.group(1))
                nm = nh_m.group(2)
                np = nh_m.group(3)
                if np == "pm" and nh != 12: nh += 12
                if np == "am" and nh == 12: nh = 24
                if np == "am" and nh < 4: nh += 24
                end_time = f"{nh:02d}:{nm}"
            else:
                # Default duration for last set (usually longer)
                end_time = f"{h+1:02d}:{m}" 
            
            parsed.append({
                "artist": artist,
                "start": start_time,
                "end": end_time
            })
        except Exception: continue
        
    return parsed

def main():
    config = load_config()
    stages = config.get("STAGES", [])
    
    full_schedule = {}
    for stage in stages:
        name = stage["name"]
        url = stage["url"]
        print(f"Syncing {name}...")
        desc = get_description(url)
        if desc:
            items = parse_schedule(desc, name)
            if items:
                full_schedule[name] = items
                print(f"  Found {len(items)} artists.")
            else:
                print(f"  No schedule items found.")
        else:
            print(f"  Failed to get description.")

    if full_schedule:
        with open("schedule.json", "w") as f:
            json.dump(full_schedule, f, indent=2)
        print("\nSuccess! schedule.json updated.")
    else:
        print("\nNo data found. Check your internet or if YouTube is throttling.")

if __name__ == "__main__":
    main()
