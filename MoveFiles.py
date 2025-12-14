import os

# Make sure Images folder exists
if "Images" not in os.listdir():
    os.mkdir("Images")

# List of files in root
files = ["temperature.rgb", "humidity.rgb", "weight.rgb"]

for f in files:
    if f in os.listdir():
        os.rename(f, f"Images/{f}")
        print(f"Moved {f} to Images/")
