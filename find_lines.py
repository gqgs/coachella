import PIL.Image
import PIL.ImageOps
import numpy as np

img = PIL.Image.open('schedule.jpg').convert('L')
arr = np.array(img)
# Calculate horizontal gradients to find horizontal lines
diff = np.abs(arr[1:, :] - arr[:-1, :])
line_intensity = np.mean(diff, axis=1)

# Find peaks in line_intensity
for y, val in enumerate(line_intensity):
    if val > 30: # Threshold for a horizontal line
        print(f"Potential line at Y={y}, intensity={val}")
