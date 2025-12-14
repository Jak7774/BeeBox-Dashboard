# ===== display_hive_data.py =====
from lcd_display import lcd, colour

def display_on_lcd(hive_id, temperatures, humidities, weight):
    """Display hive data (temperatures, humidities, weight) on LCD."""
    lcd.fill(colour(0, 0, 0))
    lcd.show()

    y = 5
    # Display Hive ID
    lcd.text(f"Hive {hive_id}", 5, y, colour(255, 255, 0))
    y += 15

    # Display Temperatures
    lcd.text("Temperatures:", 5, y, colour(255, 255, 255))
    y += 10
    for label, value in temperatures:
        lcd.text(f"{label}: {value}C", 5, y, colour(0, 255, 255))
        y += 10

    y += 5
    lcd.text("Humidities:", 5, y, colour(255, 255, 255))
    y += 10
    for label, value in humidities:
        lcd.text(f"{label}: {value}%", 5, y, colour(0, 255, 0))
        y += 10

    y += 5
    lcd.text("Weight:", 5, y, colour(255, 255, 255))
    y += 10
    lcd.text(f"{weight} kg", 5, y, colour(255, 255, 0))

    lcd.show()
