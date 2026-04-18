import re


DAY_END_LIMITS = {
    "Friday": 25 * 60,
    "Saturday": 25 * 60,
    "Sunday": 24 * 60,
}


def parse_schedule_time(time_str):
    time_str = time_str.replace(" ", "").lower()
    h_m = re.match(r"(\d{1,2}):(\d{2})(am|pm)", time_str)
    if not h_m:
        return None

    hour = int(h_m.group(1))
    minute = int(h_m.group(2))
    period = h_m.group(3)

    if period == "pm" and hour != 12:
        hour += 12
    if period == "am" and hour == 12:
        hour = 24
    if period == "am" and hour < 4:
        hour += 24

    return (hour * 60) + minute


def format_schedule_time(total_minutes):
    hour = total_minutes // 60
    minute = total_minutes % 60
    return f"{hour:02d}:{minute:02d}"


def parse_multi_day_schedule(text):
    """
    Parses a Coachella description text into a dictionary of days.
    Returns: { "Friday": [ artists ], "Saturday": [...], ... }
    """
    # Look for headers like "Friday, April 10:", "Saturday, April 11:", etc.
    # We'll extract everything between these headers.
    day_headers = ["Friday", "Saturday", "Sunday"]
    
    # Pre-process text to find all header positions
    positions = []
    for day in day_headers:
        pattern = rf"({day},?\s+April\s+\d{{1,2}}:?)"
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            positions.append((match.start(), day))
    
    # Sort positions by start index
    positions.sort()
    
    results = {}
    
    for i in range(len(positions)):
        start_idx, day_name = positions[i]
        end_idx = positions[i+1][0] if i+1 < len(positions) else len(text)
        
        # Heuristic: if there's a "Catch the rest" footer, stop there
        footer_match = re.search(r"Catch the rest", text[start_idx:end_idx], re.IGNORECASE)
        if footer_match:
            end_idx = start_idx + footer_match.start()
            
        section = text[start_idx:end_idx]
        
        # Regex for "4:00pm - Artist Name" or "4:00pm Artist"
        pattern = r"(\d{1,2}:\d{2}\s*(?:am|pm))\s*[-–—\s]\s*(.+)"
        matches = re.findall(pattern, section)
        
        parsed_artists = []
        for time_str, artist_line in matches:
            artist = artist_line.split('\n')[0].strip()
            
            # Filter meta-lines
            artist_upper = artist.upper()
            if any(x in artist_upper for x in ["[REBROADCAST]", "LIVESTREAM BEGINS", "MUSIC RETURNS"]):
                continue
            if len(artist) < 2:
                continue

            start_minutes = parse_schedule_time(time_str)
            if start_minutes is None:
                continue

            parsed_artists.append({
                "artist": artist,
                "start": format_schedule_time(start_minutes),
                "_start_minutes": start_minutes
            })

        if parsed_artists:
            day_end_limit = DAY_END_LIMITS.get(day_name)
            durations = []
            schedule_artists = []
            for j, artist in enumerate(parsed_artists):
                start_minutes = artist["_start_minutes"]
                if j + 1 < len(parsed_artists):
                    end_minutes = parsed_artists[j + 1]["_start_minutes"]
                    duration = end_minutes - start_minutes
                    if duration > 0:
                        durations.append(duration)
                else:
                    duration = max(durations) if durations else 60
                    end_minutes = start_minutes + duration
                if day_end_limit is not None:
                    end_minutes = min(end_minutes, day_end_limit)

                schedule_artists.append({
                    "artist": artist["artist"],
                    "start": artist["start"],
                    "end": format_schedule_time(end_minutes)
                })

            results[day_name] = schedule_artists
            
    return results
