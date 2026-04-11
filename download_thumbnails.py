import os
import requests

streams = [
    "2NA7XUw51oo",
    "MdUBm8G41ZU",
    "NlrpPqb0vwo",
    "HJVG2Ck3uuk",
    "4C5p1tdRv6c",
    "OGNPnQViI3g",
    "1KANGsDaRvw"
]

os.makedirs("assets", exist_ok=True)

for i, video_id in enumerate(streams):
    url = f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg"
    response = requests.get(url)
    if response.status_code == 200:
        with open(f"assets/thumb_{i}.jpg", "wb") as f:
            f.write(response.content)
        print(f"Downloaded thumbnail for {video_id}")
    else:
        print(f"Failed to download thumbnail for {video_id}")
