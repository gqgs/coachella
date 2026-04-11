import subprocess
import json
import re
import sys

STAGES = {
    "COACHELLA STAGE": "https://www.youtube.com/watch?v=2NA7XUw51oo",
    "OUTDOOR THEATRE": "https://www.youtube.com/watch?v=MdUBm8G41ZU",
    "SAHARA": "https://www.youtube.com/watch?v=NlrpPqb0vwo",
    "MOJAVE": "https://www.youtube.com/watch?v=HJVG2Ck3uuk",
    "GOBI": "https://www.youtube.com/watch?v=4C5p1tdRv6c",
    "SONORA": "https://www.youtube.com/watch?v=OGNPnQViI3g",
    "QUASAR": "https://www.youtube.com/watch?v=1KANGsDaRvw"
}

def get_description(url):
    try:
        result = subprocess.run(
            ["yt-dlp", "--get-description", url],
            capture_output=True, text=True, check=True
        )
        return result.stdout
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return ""

def parse_schedule(description, stage_name):
    # Find the section for the stage (descriptions often list all stages)
    # Look for "STAGE NAME SCHEDULE"
    marker = f"{stage_name} SCHEDULE"
    start_idx = description.upper().find(marker)
    if start_idx == -1:
        # Fallback to just looking for time patterns if the header isn't specific
        section = description
    else:
        section = description[start_idx:start_idx+2000] # Take a chunk

    # Regex for "4:00pm - Artist Name" or "12:00am - Artist"
    pattern = r"(\d{1,2}:\d{2}(?:am|pm))\s*-\s*(.+)"
    matches = re.findall(pattern, section)
    
    parsed = []
    for i in range(len(matches)):
        time_str, artist = matches[i]
        
        # Convert 12-hour to 24-hour for internal logic
        # Note: 12:00am is 24:00 in our app's logic for "next day early morning"
        h_m = re.match(r"(\d{1,2}):(\d{2})(am|pm)", time_str)
        h = int(h_m.group(1))
        m = h_m.group(2)
        period = h_m.group(3)
        
        if period == "pm" and h != 12: h += 12
        if period == "am" and h == 12: h = 24
        if period == "am" and h < 4: h += 24 # 1am -> 25
        
        start_time = f"{h:02d}:{m}"
        
        # Estimate end time based on next artist or +50 mins
        if i + 1 < len(matches):
            next_time_str = matches[i+1][0]
            nh_m = re.match(r"(\d{1,2}):(\d{2})(am|pm)", next_time_str)
            nh = int(nh_m.group(1))
            nm = nh_m.group(2)
            nperiod = nh_m.group(3)
            if nperiod == "pm" and nh != 12: nh += 12
            if nperiod == "am" and nh == 12: nh = 24
            if nperiod == "am" and nh < 4: nh += 24
            end_time = f"{nh:02d}:{nm}"
        else:
            end_time = f"{h:02d}:{int(m)+50:02d}" # Default 50 min set
            if int(m)+50 >= 60:
                end_time = f"{h+1:02d}:{int(m)+50-60:02d}"

        parsed.append({
            "artist": artist.strip(),
            "start": start_time,
            "end": end_time
        })
    return parsed

def main():
    full_schedule = {}
    for name, url in STAGES.items():
        print(f"Syncing {name}...")
        desc = get_description(url)
        if desc:
            items = parse_schedule(desc, name)
            if items:
                full_schedule[name] = items
                print(f"  Found {len(items)} artists.")
            else:
                print(f"  No schedule items found in description.")
        else:
            print(f"  Failed to get description.")

    if full_schedule:
        with open("schedule.json", "w") as f:
            json.dump(full_schedule, f, indent=2)
        print("\nSuccess! schedule.json updated.")
    else:
        print("\nFailed to find any schedule data. YouTube might be throttling requests.")

if __name__ == "__main__":
    main()
