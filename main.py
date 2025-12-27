# ===== main.py =====
import os
import utime
import json
import machine
import socket
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
import ota # To Update Scripts

STATE_FILE = "config.json"
IMAGE_FILE = "Images/BeeBox.rgb"

SETTINGS_CACHE = {}
settings_lock = _thread.allocate_lock()

# ===== BUTTONS =====
BTN_UP = machine.Pin(2, machine.Pin.IN, machine.Pin.PULL_UP)
BTN_DOWN = machine.Pin(17, machine.Pin.IN, machine.Pin.PULL_UP)
BTN_SELECT = machine.Pin(15, machine.Pin.IN, machine.Pin.PULL_UP)
BTN_BACK = machine.Pin(3, machine.Pin.IN, machine.Pin.PULL_UP)

debounce_ms = 50
last_press = 0

# ===== GLOBALS =====
initial_fetch_complete = False
menu_active = False
background_thread_started = False
updating_data = False
wifi_error = False
stop_threads = False
lcd = lcd_display.lcd
data_lock = _thread.allocate_lock()
current_data = []
data_fresh = False

# ===== Background fetch =====
HIVE_FETCH_INTERVAL_SEC = 30 * 60  # 30 minutes
SAFE_FETCH_RETRIES = 10
SAFE_FETCH_DELAY = 5  # seconds between retries

# ==== OTA timing ====
last_ota_check = 0

# ==== Screen Globals ===
CONTENT_X = 8
CONTENT_W = 96   # leaves space for button hints

# ==== Screen power ====
last_activity = utime.time()
screen_state = "ON"   # ON | DIM | OFF

# ==== Setup / state ====
def record_activity():
    global last_activity
    last_activity = utime.time()

def is_first_time():
    try:
        with open(STATE_FILE, "r") as f:
            state = json.load(f)
        return not state.get("setup_complete", False)
    except OSError:
        return True
    except ValueError:
        return True

def mark_setup_complete():
    state = load_state()
    state["setup_complete"] = True
    save_state(state)

def load_state():
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

# ==== Splash screen ====
def show_splash(image_path):
    check_screen_power() # To Dim Screen
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
    
def draw_text_clipped(text, x, y, width, colour, scroll_offset=0):
    char_w = 8
    max_chars = width // char_w
    visible = text[scroll_offset:scroll_offset + max_chars]
    lcd.text(visible, x, y, colour)
    return max_chars

def check_screen_power():
    global screen_state

    with settings_lock:
        timeout_hours = SETTINGS_CACHE.get("screen_timeout_hours", 2)

    if timeout_hours == 0: # 0 = Never Timeout (always-on)
        return
    
    dim_after = timeout_hours * 3600
    off_after = dim_after + 30 * 60

    elapsed = utime.time() - last_activity
    bl = machine.PWM(machine.Pin(lcd_display.BL))

    if screen_state == "ON" and elapsed > dim_after:
        dim_pct = state.get("screen_dim_percent", 20)
        bl.duty_u16(int(dim_pct / 100 * 65535))
        screen_state = "DIM"

    elif screen_state == "DIM" and elapsed > off_after:
        bl.duty_u16(0)
        lcd.fill(0)
        lcd.show()
        screen_state = "OFF"

    elif screen_state != "ON" and elapsed < 2:
        with settings_lock:
            brightness = SETTINGS_CACHE.get("brightness", 100)
        bl.duty_u16(int(brightness / 100 * 65535))
        screen_state = "ON"

# ==== First-time setup message ====
def show_first_time_message():
    lcd.fill(lcd_display.colour(0, 0, 0))
    blue = lcd_display.colour(0, 120, 255)
    white = lcd_display.colour(255, 255, 255)

    lcd.text("BeeBox Display", 10, 28, blue)
    lcd.text("Welcome!", 30, 54, white)
    lcd.text("Launching wifi", 6, 86, white)
    lcd.text("setup...", 42, 98, white)
    lcd.show()
    utime.sleep(4)

# ==== Button helpers ====
def wait_release(pin):
    record_activity() # For Screen Timeout
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
    """
    Background thread: periodically fetch hive data.
    OTA checks are performed only after hive data fetch succeeds.
    Safe for MicroPython threading and Wi-Fi instability.
    """
    global current_data, data_fresh, menu_active, stop_threads, initial_fetch_complete, last_ota_check

    utime.sleep(5)
    print("[BG] Background updater started")

    while not stop_threads:
        try:
            if menu_active:
                utime.sleep(1)
                continue  # Skip fetch if menu is active

            print("[BG] Checking Wi-Fi connection...")
            if not wifi_utils.is_connected():
                print("[BG] Wi-Fi not connected, attempting reconnect...")
                draw_error(lcd, "Wi-Fi reconnect")
                if not wifi_utils.connect_to_wifi(timeout=10):
                    print("[BG] Wi-Fi reconnect failed")
                    draw_error(lcd, "Wi-Fi Error")
                    utime.sleep(5)
                    continue
                print("[BG] Reconnected to Wi-Fi")

            # --- Fetch hive data safely ---
            data = None
            for attempt in range(SAFE_FETCH_RETRIES):
                try:
                    data = get_hive_data()
                    if data:
                        break
                except Exception as e:
                    print(f"[BG] Fetch attempt {attempt+1} failed:", e)
                    utime.sleep(SAFE_FETCH_DELAY)

            if data:
                with data_lock:
                    current_data = data
                    data_fresh = True
                    print("[BG] Fetched hive data:", data)
                initial_fetch_complete = True
            else:
                print("[BG] Failed to fetch hive data after retries")
                draw_error(lcd, "Fetch Failed")
                utime.sleep(5)
                continue

            # --- OTA check AFTER successful data fetch ---
            try:
                state = load_state()
                interval_hours = state.get("check_interval_hours", 24)
                interval_sec = max(3600, interval_hours * 3600)
                now = utime.time()

                if now - last_ota_check > interval_sec:
                    print("[BG] OTA check triggered")
                    ota.safe_ota()
                    last_ota_check = now
            except Exception as e:
                print("[BG] OTA error:", e)

        except Exception as e:
            print("[BG] Unexpected background error:", e)
            draw_error(lcd, "BG Error")

        # Wait for the global fetch interval before next iteration
        for _ in range(HIVE_FETCH_INTERVAL_SEC):
            if stop_threads or menu_active:
                break
            utime.sleep(1)

def reboot_if_pending():
    try:
        state = load_state()
        if state.get("pending_reboot", False):
            print("[MAIN] OTA update complete — rebooting")
            state["pending_reboot"] = False
            save_state(state)
            utime.sleep(1)
            machine.reset()
    except Exception as e:
        print("[MAIN] Reboot check failed:", e)

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
    with settings_lock:
        settings = SETTINGS_CACHE.copy()

    options = [
        "Autoscroll",
        "Update Period",
        "Brightness Level",
        "Screen Timeout",
        "Units (C/F)",
        "Wifi Reconnect"
    ]
    idx = 0

    while True:
        result = scroll_menu("Settings", options, start_idx=idx)

        if isinstance(result, tuple) and result[0] == "BACK":
            return

        if result == "Back":
            return

        elif result == "Autoscroll":
            settings["autoscroll"] = not settings.get("autoscroll", True)
            with settings_lock:
                SETTINGS_CACHE.update(settings)
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
                    with settings_lock:
                        SETTINGS_CACHE.update(settings)
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
                    with settings_lock:
                        SETTINGS_CACHE.update(settings)
                    break
                bl.duty_u16(int(settings["brightness"] / 100 * 65535))
                lcd.text(f"{settings['brightness']:3d}% ", 40, 60, lcd_display.colour(255,255,255))
                lcd.show()

        elif result == "Screen Timeout":
            lcd.fill(lcd_display.colour(0,0,0))
            lcd.text("Screen timeout:", 5, 20, lcd_display.colour(255,255,0))

            def draw_value(val):
                label = "Never" if val == 0 else f"{val} hrs"
                lcd.text(label + "   ", 30, 60, lcd_display.colour(255,255,255))
                lcd.show()

            draw_value(settings.get("screen_timeout_hours", 2))

            lcd.text("UP/DN change", 20, 90, lcd_display.colour(150,150,150))
            lcd.text("BACK:Save", 30, 110, lcd_display.colour(150,150,150))

            while True:
                if BTN_UP.value() == 0:
                    wait_release(BTN_UP)
                    cur = settings.get("screen_timeout_hours", 2)
                    if cur == 0:
                        settings["screen_timeout_hours"] = 1
                    else:
                        settings["screen_timeout_hours"] = min(24, cur + 1)

                elif BTN_DOWN.value() == 0:
                    wait_release(BTN_DOWN)
                    cur = settings.get("screen_timeout_hours", 2)
                    if cur <= 1:
                        settings["screen_timeout_hours"] = 0  # Never
                    else:
                        settings["screen_timeout_hours"] = cur - 1

                elif BTN_BACK.value() == 0:
                    wait_release(BTN_BACK)
                    with settings_lock:
                        SETTINGS_CACHE.update(settings)
                    break

                draw_value(settings["screen_timeout_hours"])


        elif result == "Units (C/F)":
            current = settings.get("units", "C")
            settings["units"] = "F" if current == "C" else "C"
            with settings_lock:
                SETTINGS_CACHE.update(settings)
            lcd.fill(lcd_display.colour(0,0,0))
            lcd.text(f"Units: {settings['units']}", 10, 60, lcd_display.colour(255,255,0))
            lcd.show()
            utime.sleep(1)

        elif result == "Wifi Reconnect":
            settings["wifi_auto_reconnect"] = not settings.get("wifi_auto_reconnect", True)
            with settings_lock:
                SETTINGS_CACHE.update(settings)
            lcd.fill(lcd_display.colour(0,0,0))
            status = "Enabled" if settings["wifi_auto_reconnect"] else "Disabled"
            lcd.text(f"Auto-Reconnect {status}", 5, 60, lcd_display.colour(255,255,0))
            lcd.show()
            utime.sleep(1)

# ==== Menu ====
def scroll_menu(title, options, start_idx=0):
    global last_press
    check_screen_power() # Check to Dim Screen
    lcd.fill(lcd_display.colour(0, 0, 0))
    idx = start_idx
    top = 0
    items_per_page = 5
    scroll_offset = 0
    scroll_pause_until = 0
    last_scroll = utime.ticks_ms()

    while True:
        lcd.fill(lcd_display.colour(0, 0, 0))
        lcd.text(title, 10, 8, lcd_display.colour(255, 255, 0))
        for i in range(items_per_page):
            j = top + i
            if j >= len(options):
                break
            y = 28 + i * 18
            if j == idx:
                max_chars = CONTENT_W // 8
                text_len = len(options[j])
                max_scroll = max(0, text_len - max_chars)

                now = utime.ticks_ms()

                if max_scroll > 0:
                    if scroll_pause_until:
                        # Currently pausing
                        if utime.ticks_diff(now, scroll_pause_until) <= 0:
                            # Pause finished → jump back to start
                            scroll_offset = 0
                            scroll_pause_until = 0
                    elif utime.ticks_diff(now, last_scroll) > 250:
                        last_scroll = now
                        scroll_offset += 1

                        if scroll_offset >= max_scroll:
                            scroll_offset = max_scroll
                            scroll_pause_until = utime.ticks_add(now, 6000)  # pause at end
                else:
                    scroll_offset = 0
                
                lcd.fill_rect(CONTENT_X - 2, y - 2, CONTENT_W + 4, 14, lcd_display.colour(0, 100, 200))
                draw_text_clipped(
                    options[j],
                    CONTENT_X,
                    y,
                    CONTENT_W,
                    lcd_display.colour(255, 255, 255),
                    scroll_offset
                )


            else:
                # 🔧 DRAW NON-HIGHLIGHTED ITEMS
                lcd.text(
                    options[j],
                    CONTENT_X,
                    y,
                    lcd_display.colour(200, 200, 200)
                )

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
            scroll_offset = 0
            scroll_pause_until = 0
            if idx < top:
                top = idx
        elif BTN_DOWN.value() == 0:
            wait_release(BTN_DOWN)
            last_press = utime.ticks_ms()
            idx = (idx + 1) % len(options)
            scroll_offset = 0
            scroll_pause_until = 0
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

    check_screen_power() # Check to Dim Screen

    menu_active = False
    print(f"Displaying {mode} data...")
    
    # --- Startup wait: do NOT timeout ---
    while not initial_fetch_complete:
        lcd.fill(lcd_display.colour(0, 0, 0))
        lcd.text("Connecting...", 20, 50, lcd_display.colour(200, 200, 200))
        lcd.show()
        utime.sleep(1)

    # --- Continuous display loop ---
    while True:
        try:
            with data_lock:
                hives_copy = current_data.copy()
        except:
            hives_copy = []
        
        with settings_lock:
            settings = SETTINGS_CACHE.copy()
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
            menu_active = False
            return   

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
            try:
                os.remove(STATE_FILE)
            except OSError:
                pass
            lcd.fill(lcd_display.colour(0, 0, 0))
            lcd.text("Device Reset!", 20, 60, lcd_display.colour(255, 0, 0))
            lcd.show()
            utime.sleep(2)
            machine.reset()
        elif result == "Exit":
            # --- Uncomment below if exit should "shut down display"
#             lcd.fill(lcd_display.colour(0, 0, 0))
#             lcd.text("Goodbye!", 40, 60, lcd_display.colour(255, 255, 0))
#             lcd.show()
#             utime.sleep(1)
#             bl = machine.PWM(machine.Pin(lcd_display.BL))
#             bl.duty_u16(0)
#             stop_all_threads()
#             print("Interrupted safely.")
            
            menu_active = False
            return

# ==== Main ====
def main():
    global background_thread_started, stop_threads

    print("[MAIN] Starting main()")
    show_splash(IMAGE_FILE)

    try:
        # First-time setup (optional for testing, can skip)
        if is_first_time():
            print("[MAIN] First time setup detected")
            show_first_time_message()
            wifi_setup.main_menu()
            mark_setup_complete()

        global SETTINGS_CACHE
        SETTINGS_CACHE = settings_config.load_settings()
        print("[MAIN] Settings loaded:", SETTINGS_CACHE)
        
        # Start background updater once
        if not background_thread_started:
            try:
                _thread.start_new_thread(background_updater, ())
                print("[MAIN] Background updater thread started")
                background_thread_started = True
            except Exception as e:
                print("[MAIN] Failed to start background thread:", e)

        # Resume last viewed dashboard
        while True:
            reboot_if_pending()
            state = load_state()
            last_mode = state.get("last_sensor_mode", "sensor_all")
            print("[MAIN] Resuming dashboard mode:", last_mode)
            display_sensor_loop(last_mode)
            print("[MAIN] Returning to main menu")
            main_menu()

    except KeyboardInterrupt:
        print("[MAIN] Keyboard interrupt detected — stopping threads")
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
