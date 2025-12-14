# ===== main.py =====
import os
import utime
import json
import machine
import _thread
import lcd_display
import settings_config
import wifi_setup
import wifi_utils
from Sensors_TextSummary import display_on_lcd
from beebox_fetch import get_hive_data
from beebox_temp_display import display_temp_quadrants
from beebox_humid_display import display_humidity_halves
from beebox_weight_display import display_weight_single

STATE_FILE = "config.json"
IMAGE_FILE = "Images/BeeBox.rgb"

# ===== BUTTONS =====
BTN_UP = machine.Pin(2, machine.Pin.IN, machine.Pin.PULL_UP)
BTN_DOWN = machine.Pin(17, machine.Pin.IN, machine.Pin.PULL_UP)
BTN_SELECT = machine.Pin(15, machine.Pin.IN, machine.Pin.PULL_UP)
BTN_BACK = machine.Pin(3, machine.Pin.IN, machine.Pin.PULL_UP)

debounce_ms = 200
last_press = 0

# ===== GLOBALS =====
menu_active = False
background_thread_started = False
updating_data = False
wifi_error = False
stop_threads = False
lcd = lcd_display.lcd
data_lock = _thread.allocate_lock()
current_data = []
data_fresh = False

# ==== Setup / state ====
def is_first_time():
    if not STATE_FILE in os.listdir():
        return True
    try:
        with open(STATE_FILE, "r") as f:
            state = json.load(f)
        return not state.get("setup_complete", False)
    except:
        return True


def mark_setup_complete():
    state = load_state()
    state["setup_complete"] = True
    save_state(state)


def load_state():
    if STATE_FILE in os.listdir():
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return {}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


# ==== Splash screen ====
def show_splash(image_path):
    lcd.fill(0xFFFF)
    lcd_display.display_rgb_image(
        lcd, image_path,
        x=(lcd.width - 96) // 2,
        y=(lcd.height - 64) // 2,
        width=96, height=64
    )
    lcd.show()
    utime.sleep(2)
        
def draw_error(lcd, message):
    """Show a small red error icon briefly (top-right corner)."""
    x, y = 110, 0
    size = 18

    lcd.fill_rect(x, y, size, size, lcd_display.colour(255, 0, 0))
    lcd.text("!", x + 6, y + 4, lcd_display.colour(255, 255, 255))
    lcd.show()
    utime.sleep(1)
    lcd.fill_rect(x, y, size, size, lcd_display.colour(0, 0, 0))  # clear after display
    lcd.show()

# ==== First-time setup message ====
def show_first_time_message():
    lcd.fill(lcd_display.colour(0, 0, 0))
    blue = lcd_display.colour(0, 120, 255)
    white = lcd_display.colour(255, 255, 255)

    lcd.text("BeeBox Display", 16, 28, blue)
    lcd.text("Welcome!", 10, 54, white)
    lcd.text("Launching Wi-Fi", 6, 86, white)
    lcd.text("setup...", 42, 98, white)
    lcd.show()
    utime.sleep(4)

# ==== Button helpers ====
def wait_release(pin):
    while pin.value() == 0:
        utime.sleep_ms(10)

def button_hint():
    lcd.text("BK", 113, 10, lcd_display.colour(255, 255, 255))
    lcd.text("UP", 113, 45, lcd_display.colour(255, 255, 255))
    lcd.text("DN", 113, 76, lcd_display.colour(255, 255, 255))
    lcd.text("OK", 113, 110, lcd_display.colour(255, 255, 255))
    lcd.show()

# ==== Wi-Fi helper ====
def wifi_connected():
    try:
        wlan = wifi_utils.network.WLAN(wifi_utils.network.STA_IF)
        return wlan.isconnected()
    except:
        return False

# ==== Background updater (safe + interruptible) ====
def background_updater():
    global current_data, menu_active, stop_threads

    utime.sleep(5)

    while not stop_threads:  # exit cleanly when stop_threads = True
        try:
            if not menu_active:
                if wifi_utils.is_connected():
                    draw_hourglass(lcd, True)
                    data = get_hive_data()
                    if data:
                        with data_lock:
                            global current_data, data_fresh
                            current_data = data
                            data_fresh = True
                    draw_hourglass(lcd, False)
                else:
                    draw_hourglass(lcd, False)
                    draw_error(lcd, "Wi-Fi Error")
            # else → paused for menus
        except Exception as e:
            print("Error during background update:", e)
            draw_hourglass(lcd, False)
            draw_error(lcd, "Update Error")

        update_period = settings_config.get_setting("update_period")
        for i in range(update_period):
            utime.sleep(1)
            if stop_threads or menu_active:
                break

# ==== Loading screen (hourglass) ====
def show_loading_screen():
    lcd = lcd_display.lcd
    lcd.fill(lcd_display.colour(0, 0, 0))
    img_path = "Images/hourglass.rgb"
    lcd_display.display_rgb_image(
        lcd,
        img_path,
        x=(lcd.width - 32) // 2,
        y=(lcd.height - 32) // 2,
        width=32,
        height=32
    )
    lcd.text(
        "Loading...",
        (lcd.width // 2) - 30,
        (lcd.height // 2) + 24,
        lcd_display.colour(200, 200, 200)
    )
    lcd.show()

# ==== Settings ====
def settings_menu():
    global menu_active
    menu_active = True
    settings = settings_config.load_settings()

    options = [
        "Autoscroll",
        "Update Period",
        "Brightness Level",
        "Units (C/F)",
        "Wifi Reconnect",
        "Back"
    ]
    idx = 0

    while True:
        result = scroll_menu("Settings", options, start_idx=idx)

        if isinstance(result, tuple) and result[0] == "BACK":
            idx = len(options) - 1
            continue

        if result == "Back":
            return

        elif result == "Autoscroll":
            settings["autoscroll"] = not settings.get("autoscroll", True)
            settings_config.save_settings(settings)
            lcd.fill(lcd_display.colour(0,0,0))
            status = "Enabled" if settings["autoscroll"] else "Disabled"
            lcd.text(f"{status}", 10, 60, lcd_display.colour(255,255,0))
            lcd.show()
            utime.sleep(1)

        elif result == "Update Period":
            lcd.fill(lcd_display.colour(0,0,0))
            lcd.text("Update (mins):", 6, 20, lcd_display.colour(255,255,0))
            lcd.text(f"{settings['update_period']//60:3d}", 40, 60, lcd_display.colour(255,255,255))
            lcd.text("UP:+5  DN:-5", 20, 90, lcd_display.colour(150,150,150))
            lcd.text("BACK:Save", 25, 110, lcd_display.colour(150,150,150))
            lcd.show()
            while True:
                if BTN_UP.value() == 0:
                    wait_release(BTN_UP)
                    settings["update_period"] += 300
                    lcd.text(f"{settings['update_period']//60:3d} ", 40, 60, lcd_display.colour(255,255,255))
                    lcd.show()
                elif BTN_DOWN.value() == 0:
                    wait_release(BTN_DOWN)
                    settings["update_period"] = max(300, settings["update_period"] - 300)
                    lcd.text(f"{settings['update_period']//60:3d} ", 40, 60, lcd_display.colour(255,255,255))
                    lcd.show()
                elif BTN_BACK.value() == 0:
                    wait_release(BTN_BACK)
                    settings_config.save_settings(settings)
                    break

        elif result == "Brightness Level":
            lcd.fill(lcd_display.colour(0,0,0))
            lcd.text("Brightness:", 10, 20, lcd_display.colour(255,255,0))
            lcd.text(f"{settings.get('brightness', 100)}%", 40, 60, lcd_display.colour(255,255,255))
            lcd.text("UP:+10 DN:-10", 15, 90, lcd_display.colour(150,150,150))
            lcd.text("BACK:Save", 25, 110, lcd_display.colour(150,150,150))
            lcd.show()
            bl = machine.PWM(machine.Pin(lcd_display.BL))
            while True:
                if BTN_UP.value() == 0:
                    wait_release(BTN_UP)
                    settings["brightness"] = min(100, settings.get("brightness", 100) + 10)
                elif BTN_DOWN.value() == 0:
                    wait_release(BTN_DOWN)
                    settings["brightness"] = max(10, settings.get("brightness", 100) - 10)
                elif BTN_BACK.value() == 0:
                    wait_release(BTN_BACK)
                    settings_config.save_settings(settings)
                    break
                bl.duty_u16(int(settings["brightness"] / 100 * 65535))
                lcd.text(f"{settings['brightness']:3d}% ", 40, 60, lcd_display.colour(255,255,255))
                lcd.show()

        elif result == "Units (C/F)":
            current = settings.get("units", "C")
            settings["units"] = "F" if current == "C" else "C"
            settings_config.save_settings(settings)
            lcd.fill(lcd_display.colour(0,0,0))
            lcd.text(f"Units: {settings['units']}", 10, 60, lcd_display.colour(255,255,0))
            lcd.show()
            utime.sleep(1)

        elif result == "Wifi Reconnect":
            settings["wifi_auto_reconnect"] = not settings.get("wifi_auto_reconnect", True)
            settings_config.save_settings(settings)
            lcd.fill(lcd_display.colour(0,0,0))
            status = "Enabled" if settings["wifi_auto_reconnect"] else "Disabled"
            lcd.text(f"Auto-Reconnect {status}", 5, 60, lcd_display.colour(255,255,0))
            lcd.show()
            utime.sleep(1)

# ==== Menu ====
def scroll_menu(title, options, start_idx=0):
    global last_press
    lcd.fill(lcd_display.colour(0, 0, 0))
    idx = start_idx
    top = 0
    items_per_page = 5

    while True:
        lcd.fill(lcd_display.colour(0, 0, 0))
        lcd.text(title, 10, 8, lcd_display.colour(255, 255, 0))
        for i in range(items_per_page):
            j = top + i
            if j >= len(options):
                break
            y = 28 + i * 18
            if j == idx:
                lcd.fill_rect(6, y - 2, 108, 14, lcd_display.colour(0, 100, 200))
                lcd.text(options[j], 10, y, lcd_display.colour(255, 255, 255))
            else:
                lcd.text(options[j], 10, y, lcd_display.colour(200, 200, 200))
        button_hint()
        lcd.show()

        now = utime.ticks_ms()
        if utime.ticks_diff(now, last_press) < debounce_ms:
            utime.sleep_ms(30)
            continue

        if BTN_UP.value() == 0:
            wait_release(BTN_UP)
            last_press = utime.ticks_ms()
            idx = (idx - 1) % len(options)
            if idx < top:
                top = idx
        elif BTN_DOWN.value() == 0:
            wait_release(BTN_DOWN)
            last_press = utime.ticks_ms()
            idx = (idx + 1) % len(options)
            if idx >= top + items_per_page:
                top = idx - items_per_page + 1
        elif BTN_SELECT.value() == 0:
            wait_release(BTN_SELECT)
            last_press = utime.ticks_ms()
            return options[idx]
        elif BTN_BACK.value() == 0:
            wait_release(BTN_BACK)
            last_press = utime.ticks_ms()
            return ("BACK", idx)


# ==== Sensor display ====
def display_sensor_loop(mode):
    global menu_active, current_data, data_fresh, wifi_error

    menu_active = False
    print(f"Displaying {mode} data...")

    # --- Initial load if no data yet ---
    if not current_data:
        show_loading_screen()
        utime.sleep(0.5)
        try:
            with data_lock:
                current_data = get_hive_data()
            data_fresh = True
            wifi_error = False
        except Exception as e:
            print("Error loading data:", e)
            wifi_error = True
            current_data = []

    # --- Continuous display loop ---
    while True:
        try:
            with data_lock:
                hives_copy = current_data.copy()
        except:
            hives_copy = []
        
        settings = settings_config.load_settings()
        autoscroll = settings.get("autoscroll", True)

        if not hives_copy:
            # No data? show small retry message
            lcd.fill(lcd_display.colour(0, 0, 0))
            lcd.text("No data", 30, 60, lcd_display.colour(255, 0, 0))
            lcd.show()
            utime.sleep(3)
            continue

        for hive in hives_copy:
            # Display the relevant sensor mode for each hive
            if mode == "sensor_all":
                display_on_lcd(hive["id"], hive["temperature"], hive["humidity"], hive["weight"])
            elif mode == "sensor_temp":
                display_temp_quadrants(hive["id"], hive["temperature"])
            elif mode == "sensor_humidity":
                display_humidity_halves(hive["id"], hive["humidity"])
            elif mode == "sensor_weight":
                display_weight_single(hive["id"], hive["weight"])

            # Wait a few seconds, check for BACK
            for _ in range(50):
                if BTN_BACK.value() == 0:
                    wait_release(BTN_BACK)
                    menu_active = True
                    return
                if not autoscroll:
                    if BTN_DOWN.value() == 0:
                        wait_release(BTN_DOWN)
                        break  # next hive
                    elif BTN_UP.value() == 0:
                        wait_release(BTN_UP)
                        break  # or wrap-around manually
                utime.sleep_ms(100)

        # After showing all hives, check if data refreshed
        if data_fresh:
            data_fresh = False
            # Reload silently (no loading screen)
            continue

# ==== View Sensors Menu ====
def view_sensors_menu():
    global menu_active
    menu_active = True
    options = ["All", "Temperature", "Humidity", "Weight"]

    while True:
        choice = scroll_menu("View Sensors", options)
        if not choice or isinstance(choice, tuple):
            return "back"

        mode_map = {
            "All": "sensor_all",
            "Temperature": "sensor_temp",
            "Humidity": "sensor_humidity",
            "Weight": "sensor_weight"
        }
        mode = mode_map.get(choice)
        if not mode:
            return None

        # Save the selected mode to state file for next boot
        state = load_state()
        state["last_sensor_mode"] = mode
        save_state(state)

        display_sensor_loop(mode)


# ==== Main Menu ====
def main_menu():
    global menu_active
    menu_active = True
    options = ["View Sensors", "Settings", "Wifi Settings", "Reset Device", "Exit"]
    idx = 0

    while True:
        result = scroll_menu("Main Menu", options, start_idx=idx)

        if isinstance(result, tuple) and result[0] == "BACK":
            idx = len(options) - 1
            continue

        if result == "View Sensors":
            result2 = view_sensors_menu()
            if result2 == "back":
                idx = 0
                continue
        elif result == "Settings":
            settings_menu()
            idx = 0  # reset highlight to top
            continue  # redraw main menu
        elif result == "Wifi Settings":
            wifi_setup.main_menu()
        elif result == "Reset Device":
            if STATE_FILE in os.listdir():
                os.remove(STATE_FILE)
            lcd.fill(lcd_display.colour(0, 0, 0))
            lcd.text("Device Reset!", 20, 60, lcd_display.colour(255, 0, 0))
            lcd.show()
            utime.sleep(2)
            machine.reset()
        elif result == "Exit":
            lcd.fill(lcd_display.colour(0, 0, 0))
            lcd.text("Goodbye!", 40, 60, lcd_display.colour(255, 255, 0))
            lcd.show()
            utime.sleep(1)
            bl = machine.PWM(machine.Pin(lcd_display.BL))
            bl.duty_u16(0)
            stop_all_threads()
            print("Interrupted safely.")
            return

# ==== Main ====
def main():
    global background_thread_started, stop_threads

    show_splash(IMAGE_FILE)

    try:
        if is_first_time():
            show_first_time_message()
            wifi_setup.main_menu()
            mark_setup_complete()

        # Try to resume last viewed screen
        state = load_state()
        last_mode = state.get("last_sensor_mode")

        if last_mode:
            print(f"Resuming last mode: {last_mode}")
            display_sensor_loop(last_mode)
            
         # Start background updater if not already running
        if not background_thread_started:
            _thread.start_new_thread(background_updater, ())
            background_thread_started = True

        # If BACK pressed from that mode → show menu
        main_menu()

    except KeyboardInterrupt:
        print("\nKeyboard interrupt detected — stopping threads.")
        stop_threads = True
        utime.sleep(0.5)
        raise
    
def stop_all_threads():
    global stop_threads
    stop_threads = True
    print("Stop signal sent — waiting for threads to close...")
    utime.sleep(2)
    print("All background threads stopped.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nKeyboardInterrupt detected. Stopping background threads...")
        stop_all_threads()
        utime.sleep(1)
        print("Stopped safely. You can now edit files again.")
