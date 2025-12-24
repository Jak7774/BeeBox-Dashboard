# wifi_setup.py
from machine import Pin
import network, utime, os
from wifi_encryption import encrypt, decrypt
from wifi_storage import save_wifi_credentials, load_wifi_credentials
import struct

# === LCD and colour helpers ===
try:
    from lcd_display import lcd, colour
except ImportError:
    from lcd import LCD_1inch44
    lcd = LCD_1inch44()
    def colour(r,g,b):
        return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)

# === Buttons ===
key0 = Pin(15, Pin.IN, Pin.PULL_UP)  # SELECT / OK
key1 = Pin(2, Pin.IN, Pin.PULL_UP)   # UP
key2 = Pin(17, Pin.IN, Pin.PULL_UP)  # DOWN
key3 = Pin(3, Pin.IN, Pin.PULL_UP)   # BACK

debounce_ms = 200
last_press = 0

CHARSET = " ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$_-."

# === Utilities ===
def wait_release(pin):
    while pin.value() == 0:
        utime.sleep_ms(10)

def button_hint():
    """White button labels only (right-hand edge)."""
    # keep these x positions consistent with your menu layout
    lcd.text("BK", 113, 10, colour(255, 255, 255))
    lcd.text("UP", 113, 45, colour(255, 255, 255))
    lcd.text("DN", 113, 76, colour(255, 255, 255))
    lcd.text("OK", 113, 110, colour(255, 255, 255))
    # do not call show() here if the caller will draw other things immediately;
    # but leaving it is harmless
    lcd.show()
   
def text_input(prompt, max_len=32):
    """
    Text entry:
      • UP/DN: cycle current character
      • OK: append char
      • BK: short press deletes, hold >=3s saves with live countdown
      • Right margin reserved for button labels
    """
    global last_press
    CHARSET = " ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$_-.:,/"
    CHAR_WIDTH = 8
    SCREEN_WIDTH = 128
    BUTTON_MARGIN = 20            # reserve 20px on the right
    LEFT_X = 5
    MAX_PER_LINE = (SCREEN_WIDTH - BUTTON_MARGIN - LEFT_X) // CHAR_WIDTH
    LINE_HEIGHT = 12
    TOP_Y = 30
    PREVIEW_Y = TOP_Y + LINE_HEIGHT * 3 + 2
    caret_y_offset = 9
    fast_debounce = 50            # faster response

    text = []
    sel_idx = 0

    lcd.fill(colour(0, 0, 0))
    lcd.text(prompt, LEFT_X, 8, colour(255, 255, 0))
    button_hint()
    lcd.show()

    def render():
        """Draw entered text + preview + caret."""
        preview = CHARSET[sel_idx]
        render_list = text[:] + [preview]
        total = len(render_list)
        lcd.fill_rect(0, TOP_Y - 2, SCREEN_WIDTH - BUTTON_MARGIN, LINE_HEIGHT * 4 + 8, colour(0, 0, 0))
        y = TOP_Y
        for i in range(0, total, MAX_PER_LINE):
            line = "".join(render_list[i:i + MAX_PER_LINE])
            lcd.text(line, LEFT_X, y, colour(255, 255, 255))
            y += LINE_HEIGHT

        caret_index = len(text)
        caret_line = caret_index // MAX_PER_LINE
        caret_col = caret_index % MAX_PER_LINE
        caret_x = LEFT_X + caret_col * CHAR_WIDTH + 1
        caret_y = TOP_Y + caret_line * LINE_HEIGHT + caret_y_offset
        lcd.text("^", caret_x, caret_y, colour(255, 255, 255))

        lcd.fill_rect(LEFT_X, PREVIEW_Y, 100, 20, colour(0, 0, 0))
        lcd.text("Hold BK for", LEFT_X, PREVIEW_Y + 14, colour(160, 160, 160))
        lcd.text("3s to Save", LEFT_X, PREVIEW_Y + 28, colour(160, 160, 160))
        button_hint()
        lcd.show()

    render()

    while True:
        # fast debounce
        if utime.ticks_diff(utime.ticks_ms(), last_press) < fast_debounce:
            utime.sleep_ms(10)
            continue

        # === UP ===
        if key1.value() == 0:
            wait_release(key1)
            last_press = utime.ticks_ms()
            sel_idx = (sel_idx + 1) % len(CHARSET)
            render()

        # === DOWN ===
        elif key2.value() == 0:
            wait_release(key2)
            last_press = utime.ticks_ms()
            sel_idx = (sel_idx - 1) % len(CHARSET)
            render()

        # === OK ===
        elif key0.value() == 0:
            wait_release(key0)
            last_press = utime.ticks_ms()
            if len(text) < max_len:
                text.append(CHARSET[sel_idx])
            render()

        # === BK ===
        elif key3.value() == 0:
            press_time = utime.ticks_ms()
            saved = False
            while key3.value() == 0:
                elapsed = utime.ticks_diff(utime.ticks_ms(), press_time)
                if elapsed >= 500 and not saved:
                    # live countdown during hold
                    for i in range(3, 0, -1):
                        if key3.value():  # released early
                            break
                        lcd.fill_rect(LEFT_X, PREVIEW_Y, 100, 80, colour(0,0,0))
                        lcd.text("Saving in", LEFT_X, PREVIEW_Y, colour(255,255,255))
                        lcd.text(f"{i}...", LEFT_X, PREVIEW_Y + 10, colour(255,255,255))
                        lcd.show()
                        utime.sleep_ms(500)
                    if not key3.value():  # still held
                        lcd.fill(colour(0,0,0))
                        lcd.text("Saved!", 40, 50, colour(0,255,0))
                        lcd.text("Returning to", 10, 70, colour(255,255,255))
                        lcd.text("Main Menu...", 25, 90, colour(255,255,255))
                        lcd.show()
                        utime.sleep_ms(1200)
                        return "".join(text)
                    saved = True
                utime.sleep_ms(20)

            # released early -> delete last char
            wait_release(key3)
            last_press = utime.ticks_ms()
            if text:
                text.pop()
                render()

        utime.sleep_ms(10) 
 
def wifi_scan():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    nets = wlan.scan()
    ssids = sorted({net[0].decode() for net in nets})
    return list(ssids)

def select_network(networks):
    """
    Scrollable list of SSIDs with 'Manual Entry' at the top.
    UP/DN to navigate, OK to select, BACK to cancel.
    'Manual Entry' is dark blue.
    """
    global last_press
    idx = 0
    top = 0
    items_per_page = 4
    debounce_ms_fast = 100  # faster response
    
    scroll_offset = 0
    scroll_pause_until = 0
    last_scroll = utime.ticks_ms()
    CHAR_W = 8
    CONTENT_W = 96   # leaves space for button labels

    while True:
        lcd.fill(colour(0, 0, 0))
        lcd.text("Select Wifi:", 10, 10, colour(255, 255, 0))

        for i in range(items_per_page):
            j = top + i
            if j >= len(networks):
                break
            y = 30 + i * 18
            s = networks[j]

            # determine background color
            if j == idx:
                if j == 0:  # Manual Entry highlighted
                    lcd.fill_rect(6, y - 2, 108, 14, colour(0, 0, 150))  # dark blue
                else:
                    lcd.fill_rect(6, y - 2, 108, 14, colour(0, 100, 200))  # normal highlight
                lmax_chars = CONTENT_W // CHAR_W
                text_len = len(s)
                max_scroll = max(0, text_len - max_chars)

                now = utime.ticks_ms()

                if max_scroll > 0:
                    if scroll_pause_until:
                        if utime.ticks_diff(now, scroll_pause_until) <= 0:
                            scroll_offset = 0
                            scroll_pause_until = 0
                    elif utime.ticks_diff(now, last_scroll) > 250:
                        last_scroll = now
                        scroll_offset += 1
                        if scroll_offset >= max_scroll:
                            scroll_offset = max_scroll
                            scroll_pause_until = utime.ticks_add(now, 5000)
                else:
                    scroll_offset = 0

                visible = s[scroll_offset:scroll_offset + max_chars]
                lcd.text(visible, 10, y, colour(255, 255, 255))

            else:
                max_chars = CONTENT_W // CHAR_W
                static_text = s[:max_chars]  # clip, but don't hard-code length

                if j == 0:  # Manual Entry unselected
                    lcd.text(static_text, 10, y, colour(100, 100, 255))
                else:
                    lcd.text(static_text, 10, y, colour(200, 200, 200))


        button_hint()
        lcd.show()

        now = utime.ticks_ms()
        if utime.ticks_diff(now, last_press) < debounce_ms_fast:
            utime.sleep_ms(5)
            continue

        # UP
        if key1.value() == 0:
            scroll_offset = 0
            scroll_pause_until = 0
            last_press = utime.ticks_ms()
            idx = (idx - 1) % len(networks)
            if idx < top:
                top = idx

        # DOWN
        elif key2.value() == 0:
            scroll_offset = 0
            scroll_pause_until = 0
            last_press = utime.ticks_ms()
            idx = (idx + 1) % len(networks)
            if idx >= top + items_per_page:
                top = idx - items_per_page + 1

        # OK
        elif key0.value() == 0:
            last_press = utime.ticks_ms()
            return networks[idx]  # returns "Manual Entry" or SSID

        # BACK
        elif key3.value() == 0:
            last_press = utime.ticks_ms()
            return None

def show_config():
    lcd.fill(colour(0,0,0))
    ssid, _ = load_wifi_credentials()

    if ssid:
        lcd.text("Saved Config:", 10, 20, colour(255,255,0))
        lcd.text(f"SSID: {ssid}", 10, 50, colour(200,255,200))
        lcd.text("PWD: ********", 10, 70, colour(200,200,200))
    else:
        lcd.text("No config found.", 10, 50, colour(255,100,100))

    lcd.show()
    utime.sleep(2)

def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    
    ssid, password = load_wifi_credentials()
    if not ssid:
        lcd.text("No Wi-Fi config", 10, 60, colour(255,0,0))
        lcd.show()
        utime.sleep(2)
        return
    
    lcd.fill(colour(0,0,0))
    lcd.text("Connecting...", 10, 60, colour(255,255,0))
    lcd.show()
    
    wlan.connect(ssid, password)
    for _ in range(20):
        if wlan.isconnected():
            lcd.fill(colour(0,0,0))
            lcd.text("Connected!", 20, 60, colour(0,255,0))
            lcd.show()
            utime.sleep(2)
            return
        utime.sleep(0.5)
        
    lcd.fill(colour(0,0,0))
    lcd.text("Failed to connect", 10, 60, colour(255,100,100))
    lcd.show()
    utime.sleep(2)

def main_menu():
    menu_items = ["Setup Wifi", "Connect Wifi", "Show Config", "Launch Dashboard"]
    global last_press
    idx = 0
    while True:
        lcd.fill(colour(0,0,0))
        lcd.text("Wifi Menu", 20, 10, colour(255,255,0))
        for i, item in enumerate(menu_items):
            y = 30 + i*20
            if i == idx:
                lcd.fill_rect(6, y-2, 108, 14, colour(0,100,200))
                lcd.text(item, 10, y, colour(255,255,255))
            else:
                lcd.text(item, 10, y, colour(200,200,200))
        button_hint()
        lcd.show()

        now = utime.ticks_ms()
        if utime.ticks_diff(now, last_press) < debounce_ms:
            utime.sleep_ms(30)
            continue

        if key1.value() == 0:  # UP
            wait_release(key1)
            last_press = utime.ticks_ms()
            idx = (idx - 1) % len(menu_items)
        elif key2.value() == 0:  # DOWN
            wait_release(key2)
            last_press = utime.ticks_ms()
            idx = (idx + 1) % len(menu_items)
        elif key0.value() == 0:  # OK
            wait_release(key0)
            last_press = utime.ticks_ms()
            choice = menu_items[idx]
            if choice == "Setup Wifi":
                lcd.fill(colour(0,0,0))
                lcd.text("Scanning...", 10, 60, colour(255,255,0))
                lcd.show()
                nets = wifi_scan()
                nets = ["Manual entry"] + nets
                if not nets:
                    nets = ["Manual entry"]
                ssid = select_network(nets)
                if ssid:
                    if ssid == "Manual entry":
                        ssid = text_input("SSID:")
                    password = text_input("Password:")
                    save_wifi_credentials(ssid, password)
                    lcd.fill(colour(0,0,0))
                    lcd.text("Saved!", 40, 60, colour(0,255,0))
                    lcd.show()
                    utime.sleep(1.5)
            elif choice == "Connect Wifi":
                connect_wifi()
            elif choice == "Show Config":
                show_config()
            elif choice == "Launch Dashboard":
                lcd.fill(colour(0,0,0))
                lcd.text("Welcome!", 40, 60, colour(255,255,0))
                lcd.show()
                utime.sleep(1)
                break
        elif key3.value() == 0:  # BACK
            wait_release(key3)
            last_press = utime.ticks_ms()
            lcd.fill(colour(0,0,0))
            lcd.text("Exiting...", 30, 60, colour(255,100,100))
            lcd.show()
            utime.sleep(1)
            break

# === Run ===
#main_menu()
