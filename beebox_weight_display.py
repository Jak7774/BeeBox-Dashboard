from lcd_display import lcd, colour, display_rgb_image, draw_number
from beebox_fetch import get_hive_data
import utime

# ================= Display Functions =================
def display_weight_single(hive_id, weight_value, image_path="Images/weight.rgb"):
    lcd.fill(colour(0, 0, 0))

    # ================= Layout Constants =================
    screen_width = 128
    screen_height = 128
    title_height = 14
    grid_top = title_height + 2
    grid_bottom = screen_height - 2
    grid_height = grid_bottom - grid_top

    # ================= Hive ID (Title Bar) =================
    title_bg = colour(40, 40, 40)
    text_colour = colour(255, 255, 255)

    lcd.fill_rect(0, 0, screen_width, title_height, title_bg)
    title = f"Hive {hive_id}"
    text_x = (screen_width - len(title) * 8) // 2
    lcd.text(title, text_x, 4, text_colour)

    # ================= Draw Weight =================
    num_str = str(weight_value)
    digit_width = 8
    digit_height = 16

    # Compute total width of the number string
    total_width = len(num_str) * digit_width

    # Icon parameters
    icon_width = 32
    icon_height = 32
    icon_x = 8
    icon_y = grid_top + (grid_height - icon_height) // 2

    # Number position (to the right of icon)
    draw_x = icon_x + icon_width + 8
    draw_y = grid_top + (grid_height - digit_height) // 2

    # Draw icon
    try:
        display_rgb_image(lcd, image_path, icon_x, icon_y, icon_width, icon_height)
    except Exception as e:
        print("Could not load image:", e)

    # Draw number
    draw_number(lcd, num_str, draw_x, draw_y, digit_width, digit_height)

    lcd.show()
    
# ================= Main =================
 
# hives = get_hive_data()
# while True:
#     for hive in hives:
#         display_weight_single(hive["id"], hive["weight"])
#         utime.sleep(5)
