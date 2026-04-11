import PIL.Image
import numpy as np

img = PIL.Image.open('schedule.jpg').convert('RGB')
arr = np.array(img)
# Boxes are light/white-ish. Background is teal/orange/etc.
# Let's find pixels where R, G, B are all > 200
mask = np.all(arr > 220, axis=2)

# Save mask for debug
debug_mask = PIL.Image.fromarray((mask * 255).astype(np.uint8))
debug_mask.save('debug_mask.png')

# Project to y-axis to find horizontal bands of boxes
y_density = np.mean(mask, axis=1)
for y, d in enumerate(y_density):
    if d > 0.1: # At least 10% of width is a box
        print(f"Box pixels at Y={y}, density={d}")
