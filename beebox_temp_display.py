from lcd_display import lcd, colour, display_rgb_image, draw_number
from beebox_fetch import get_hive_data
import utime

# ================= Display Functions =================
def display_temp_quadrants(hive_id, temps, image_path="Images/temperature.rgb"):
    lcd.fill(colour(0, 0, 0))

    # ================= Layout Constants =================
    screen_width = 128
    screen_height = 128
    title_height = 14
    bottom_margin = 2
    grid_top = title_height + 2  # start just below title bar
    grid_bottom = screen_height - bottom_margin
    grid_height = grid_bottom - grid_top

    # ================= Hive ID (Title Bar) =================
    title_bg = colour(40, 40, 40)
    text_colour = colour(255, 255, 255)
    lcd.fill_rect(0, 0, screen_width, title_height, title_bg)
    title = f"Hive {hive_id}"
    text_x = (screen_width - len(title) * 8) // 2
    lcd.text(title, text_x, 4, text_colour)

    # ================= Quadrant Grid =================
    quadrant_height = grid_height // 2
    centers = [
        (screen_width // 4, grid_top + quadrant_height // 2),             # Top left
        (3 * screen_width // 4, grid_top + quadrant_height // 2),         # Top right
        (screen_width // 4, grid_top + quadrant_height + quadrant_height // 2),  # Bottom left
        (3 * screen_width // 4, grid_top + quadrant_height + quadrant_height // 2)  # Bottom right
    ]

    lcd.hline(0, grid_top + quadrant_height, screen_width, colour(60, 60, 60))
    lcd.vline(screen_width // 2, grid_top, grid_height, colour(60, 60, 60))

    # ================= Labels =================
    labels = ["Brood", "Super", "Roof", "Outside"]
    labels_coords = [
        (centers[0][0], grid_top + 2),
        (centers[1][0], grid_top + 2),
        (centers[2][0], grid_bottom - 10),
        (centers[3][0], grid_bottom - 10)
    ]

    # ================= Draw Data =================
    for i, temp_label in enumerate(labels):
        value = "--"
        for k, v in temps:
            if k.lower() == temp_label.lower():
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
        label_width = len(temp_label) * 8
        lcd.text(temp_label, lx - label_width // 2, ly, colour(255, 255, 255))

    # ================= Center Image =================
    display_rgb_image(lcd, image_path, 50, grid_top + (quadrant_height // 2) + 8, 32, 32)

    lcd.show()

# ================= Main =================

# hives = get_hive_data()
# while True:
#     for hive in hives:
#         display_temp_quadrants(hive["id"], hive["temperature"])
#         utime.sleep(5)

