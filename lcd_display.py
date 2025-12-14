from machine import Pin, SPI, PWM
import framebuf

# ========== LCD SETUP ==========
BL = 13
DC = 8
RST = 12
MOSI = 11
SCK = 10
CS = 9

def colour(R, G, B):
    return (((G & 0b00011100) << 3) + ((R & 0b11111000) >> 3) << 8) + \
           (B & 0b11111000) + ((G & 0b11100000) >> 5)

class lcd_1inch44(framebuf.FrameBuffer):
    def __init__(self):
        self.width = 128
        self.height = 128
        self.cs = Pin(CS, Pin.OUT)
        self.rst = Pin(RST, Pin.OUT)
        self.spi = SPI(1, baudrate=10000_000, polarity=0, phase=0,
                       sck=Pin(SCK), mosi=Pin(MOSI))
        self.dc = Pin(DC, Pin.OUT)
        self.buffer = bytearray(self.height * self.width * 2)
        super().__init__(self.buffer, self.width, self.height, framebuf.RGB565)
        self.init_display()

    def write_cmd(self, cmd):
        self.cs(1); self.dc(0); self.cs(0)
        self.spi.write(bytearray([cmd]))
        self.cs(1)

    def write_data(self, buf):
        self.cs(1); self.dc(1); self.cs(0)
        self.spi.write(bytearray([buf]))
        self.cs(1)

    def init_display(self):
        self.rst(1); self.rst(0); self.rst(1)
        self.write_cmd(0x36); self.write_data(0x70)
        self.write_cmd(0x3A); self.write_data(0x05)
        self.write_cmd(0x11); self.write_cmd(0x29)

    def show(self):
        self.write_cmd(0x2A); self.write_data(0x00); self.write_data(0x01)
        self.write_data(0x00); self.write_data(0x80)
        self.write_cmd(0x2B); self.write_data(0x00); self.write_data(0x02)
        self.write_data(0x00); self.write_data(0x82)
        self.write_cmd(0x2C)
        self.cs(1); self.dc(1); self.cs(0)
        self.spi.write(self.buffer)
        self.cs(1)

# Initialize LCD
pwm = PWM(Pin(BL))
pwm.freq(1000)
pwm.duty_u16(65535)
lcd = lcd_1inch44()


# ========== Helper functions ==========
def display_rgb_image(lcd, image_path, x=0, y=0, width=128, height=128):
    try:
        with open(image_path, "rb") as f:
            data = f.read()
        buf = bytearray(width * height * 2)
        for i in range(width * height):
            r = data[i * 3]
            g = data[i * 3 + 1]
            b = data[i * 3 + 2]
            rgb565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
            buf[i * 2] = rgb565 >> 8
            buf[i * 2 + 1] = rgb565 & 0xFF
        img = framebuf.FrameBuffer(buf, width, height, framebuf.RGB565)
        lcd.blit(img, x, y)
    except Exception as e:
        print("Could not load image:", e)

def draw_number(lcd, number_str, x, y, digit_width=16, digit_height=16, spacing=0):
    cursor_x = x
    for ch in str(number_str):
        img_file = f"Images/numbers/{ch}.rgb"
        display_rgb_image(lcd, img_file, cursor_x, y, digit_width, digit_height)
        cursor_x += digit_width + spacing

