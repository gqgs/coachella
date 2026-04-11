import PIL.Image
import PIL.ImageOps
import numpy as np

img = PIL.Image.open('schedule.jpg').convert('L')
arr = np.array(img)
w = arr.shape[1]
# Check middle 100 pixels for horizontal lines
mid = arr[:, w//2 - 50:w//2 + 50]
diff = np.abs(mid[1:, :] - mid[:-1, :])
line_intensity = np.mean(diff, axis=1)

for y, val in enumerate(line_intensity):
    if val > 60: # High threshold for strong lines
        print(f"Strong line at Y={y}, intensity={val}")
