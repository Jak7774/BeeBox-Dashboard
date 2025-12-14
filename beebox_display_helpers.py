from lcd_display import lcd, colour, display_rgb_image, draw_number

import framebuf

# ================= TEMPERATURE QUADRANTS =================
def display_temp_quadrants(hive_id, temps, image_path="Images/temperature.rgb"):
    lcd.fill(colour(0, 0, 0))

    screen_width = 128
    screen_height = 128
    title_height = 14
    bottom_margin = 2
    grid_top = title_height + 2
    grid_bottom = screen_height - bottom_margin
    grid_height = grid_bottom - grid_top

    title_bg = colour(40, 40, 40)
    text_colour = colour(255, 255, 255)

    lcd.fill_rect(0, 0, screen_width, title_height, title_bg)
    title = f"Hive {hive_id}"
    text_x = (screen_width - len(title) * 8) // 2
    lcd.text(title, text_x, 4, text_colour)

    quadrant_height = grid_height // 2
    centers = [
        (screen_width // 4, grid_top + quadrant_height // 2),
        (3 * screen_width // 4, grid_top + quadrant_height // 2),
        (screen_width // 4, grid_top + quadrant_height + quadrant_height // 2),
        (3 * screen_width // 4, grid_top + quadrant_height + quadrant_height // 2)
    ]

    lcd.hline(0, grid_top + quadrant_height, screen_width, colour(60, 60, 60))
    lcd.vline(screen_width // 2, grid_top, grid_height, colour(60, 60, 60))

    labels = ["Brood", "Super", "Roof", "Outside"]
    labels_coords = [
        (centers[0][0], grid_top + 2),
        (centers[1][0], grid_top + 2),
        (centers[2][0], grid_bottom - 10),
        (centers[3][0], grid_bottom - 10)
    ]

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

        lx, ly = labels_coords[i]
        label_width = len(temp_label) * 8
        lcd.text(temp_label, lx - label_width // 2, ly, text_colour)

    try:
        display_rgb_image(lcd, image_path, 50, grid_top + (quadrant_height//2) + 8, 32, 32)
    except Exception as e:
        print("Could not load image:", e)

    lcd.show()


# ================= HUMIDITY HALVES =================
def display_humidity_halves(hive_id, humidities, image_path="Images/humidity.rgb"):
    lcd.fill(colour(0, 0, 0))

    screen_width = 128
    screen_height = 128
    title_height = 14
    bottom_margin = 2
    grid_top = title_height + 2
    grid_bottom = screen_height - bottom_margin
    grid_height = grid_bottom - grid_top

    title_bg = colour(40, 40, 40)
    text_colour = colour(255, 255, 255)

    lcd.fill_rect(0, 0, screen_width, title_height, title_bg)
    title = f"Hive {hive_id}"
    text_x = (screen_width - len(title) * 8) // 2
    lcd.text(title, text_x, 4, text_colour)

    half_width = screen_width // 2
    centers = [
        (half_width // 2, grid_top + grid_height // 2),
        (half_width + half_width // 2, grid_top + grid_height // 2)
    ]

    lcd.vline(half_width, grid_top, grid_height, colour(60, 60, 60))

    labels = ["Inside", "Outside"]
    labels_coords = [
        (centers[0][0], grid_bottom - 10),
        (centers[1][0], grid_bottom - 10)
    ]

    for i, hum_label in enumerate(labels):
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

        lx, ly = labels_coords[i]
        label_width = len(hum_label) * 8
        lcd.text(hum_label, lx - label_width // 2, ly, text_colour)

    try:
        icon_x = (screen_width - 32) // 2
        icon_y = grid_top + 8
        display_rgb_image(lcd, image_path, icon_x, icon_y, 32, 32)
    except Exception as e:
        print("Could not load image:", e)

    lcd.show()


# ================= WEIGHT SINGLE =================
def display_weight_single(hive_id, weight_value, image_path="Images/weight.rgb"):
    lcd.fill(colour(0, 0, 0))

    screen_width = 128
    screen_height = 128
    title_height = 14
    grid_top = title_height + 2
    grid_bottom = screen_height - 2
    grid_height = grid_bottom - grid_top

    title_bg = colour(40, 40, 40)
    text_colour = colour(255, 255, 255)

    lcd.fill_rect(0, 0, screen_width, title_height, title_bg)
    title = f"Hive {hive_id}"
    text_x = (screen_width - len(title) * 8) // 2
    lcd.text(title, text_x, 4, text_colour)

    num_str = str(round(float(weight_value), 1))
    digit_width = 8
    digit_height = 16
    total_width = len(num_str) * digit_width

    icon_width = 32
    icon_height = 32
    icon_x = 8
    icon_y = grid_top + (grid_height - icon_height) // 2

    draw_x = icon_x + icon_width + 8
    draw_y = grid_top + (grid_height - digit_height) // 2

    try:
        display_rgb_image(lcd, image_path, icon_x, icon_y, icon_width, icon_height)
    except Exception as e:
        print("Could not load image:", e)

    draw_number(lcd, num_str, draw_x, draw_y, digit_width, digit_height)
    lcd.show()

