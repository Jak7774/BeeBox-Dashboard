from lcd_display import lcd, colour, display_rgb_image, draw_number
from beebox_fetch import get_hive_data
import utime

# ================= Display Functions =================
def display_humidity_halves(hive_id, humidities, image_path="Images/humidity.rgb"):
    lcd.fill(colour(0, 0, 0))

    # ================= Layout Constants =================
    screen_width = 128
    screen_height = 128
    title_height = 14
    bottom_margin = 2
    grid_top = title_height + 2
    grid_bottom = screen_height - bottom_margin
    grid_height = grid_bottom - grid_top

    # ================= Hive ID (Title Bar) =================
    title_bg = colour(40, 40, 40)
    text_colour = colour(255, 255, 255)

    lcd.fill_rect(0, 0, screen_width, title_height, title_bg)
    title = f"Hive {hive_id}"
    text_x = (screen_width - len(title) * 8) // 2
    lcd.text(title, text_x, 4, text_colour)

    # ================= Split Screen (Left / Right) =================
    half_width = screen_width // 2
    centers = [
        (half_width // 2, grid_top + grid_height // 2),       # Left center
        (half_width + half_width // 2, grid_top + grid_height // 2)  # Right center
    ]

    # Vertical divider line
    lcd.vline(half_width, grid_top, grid_height, colour(60, 60, 60))

    # ================= Labels =================
    labels = ["Inside", "Outside"]  # adjust to match your actual humidity sources
    labels_coords = [
        (centers[0][0], grid_bottom - 10),   # Left label
        (centers[1][0], grid_bottom - 10)    # Right label
    ]

    # ================= Draw Data =================
    for i, hum_label in enumerate(labels):
        # Find matching humidity
        value = "--"
        for k, v in humidities:
            if k.lower() == hum_label.lower():
                value = v
                break

        num_str = str(value)
        digit_width = 8
        digit_height = 16

        total_width = len(num_str) * digit_width
        draw_x = centers[i][0] - total_width // 2
        draw_y = centers[i][1] - digit_height // 2
        draw_number(lcd, num_str, draw_x, draw_y, digit_width, digit_height)

        # Draw label
        lx, ly = labels_coords[i]
        label_width = len(hum_label) * 8
        lcd.text(hum_label, lx - label_width // 2, ly, colour(255, 255, 255))

    # ================= Center Image =================
    try:
        # smaller icon in top-middle between the halves
        icon_x = (screen_width - 32) // 2
        icon_y = grid_top + 8
        display_rgb_image(lcd, image_path, icon_x, icon_y, 32, 32)
    except Exception as e:
        print("Could not load image:", e)

    lcd.show()
    
# ================= Main =================
 
# hives = get_hive_data()
# while True:
#     for hive in hives:
#         display_humidity_halves(hive["id"], hive["humidity"])
#         utime.sleep(5)

