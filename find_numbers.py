import PIL.Image
import numpy as np

img = PIL.Image.open('debug_left.jpg').convert('L')
# Threshold to find dark text (lower is darker)
arr = np.array(img) < 80 
# Project to y-axis (sum of dark pixels in each row)
y_density = np.sum(arr, axis=1)

# Find clusters of non-zero density
in_cluster = False
clusters = []
for y, d in enumerate(y_density):
    if d > 2: # At least 2 dark pixels in row
        if not in_cluster:
            in_cluster = True
            start = y
    else:
        if in_cluster:
            in_cluster = False
            clusters.append((start, y-1))

for start, end in clusters:
    mid = (start + end) // 2
    height = end - start + 1
    if height > 5: # Filter noise
        print(f"Number blob at Y={mid}, height={height}")
