import re

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
        for j in range(len(matches)):
            time_str, artist_line = matches[j]
            artist = artist_line.split('\n')[0].strip()
            
            # Filter meta-lines
            artist_upper = artist.upper()
            if any(x in artist_upper for x in ["[REBROADCAST]", "LIVESTREAM BEGINS", "MUSIC RETURNS"]):
                continue
            if len(artist) < 2:
                continue

            try:
                # Normalize time to HH:MM (24h)
                time_str = time_str.replace(" ", "").lower()
                h_m = re.match(r"(\d{1,2}):(\d{2})(am|pm)", time_str)
                if not h_m: continue
                
                h = int(h_m.group(1))
                m = h_m.group(2)
                period = h_m.group(3)
                
                if period == "pm" and h != 12: h += 12
                if period == "am" and h == 12: h = 24
                if period == "am" and h < 4: h += 24 # Handle 1 AM as 25:00
                
                start_time = f"{h:02d}:{m}"
                
                # Estimate end time based on next slot
                if j + 1 < len(matches):
                    nt_str = matches[j+1][0].replace(" ", "").lower()
                    nh_m = re.match(r"(\d{1,2}):(\d{2})(am|pm)", nt_str)
                    if nh_m:
                        nh = int(nh_m.group(1))
                        nm = nh_m.group(2)
                        np = nh_m.group(3)
                        if np == "pm" and nh != 12: nh += 12
                        if np == "am" and nh == 12: nh = 24
                        if np == "am" and nh < 4: nh += 24
                        end_time = f"{nh:02d}:{nm}"
                    else:
                        end_time = f"{h+1:02d}:{m}"
                else:
                    end_time = f"{h+1:02d}:{m}" # Default 1 hour
                
                parsed_artists.append({
                    "artist": artist,
                    "start": start_time,
                    "end": end_time
                })
            except Exception:
                continue
        
        if parsed_artists:
            results[day_name] = parsed_artists
            
    return results
