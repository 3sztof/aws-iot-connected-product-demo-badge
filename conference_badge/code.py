# Conference Badge Slideshow for AWS IoT Demo Badge 2023
# Runs on CircuitPython 8.2.7
# Copy this file + images/ folder to the CIRCUITPY drive

import time
import board
import digitalio
import displayio
import neopixel
import busio
import analogio
import adafruit_imageload
import adafruit_miniqr
from adafruit_display_text import label
from adafruit_bitmap_font import bitmap_font

# ─── CONFIG ───────────────────────────────────────────────────────────
LINKEDIN_URL = "https://www.linkedin.com/in/3sztof/"
SLIDE_DURATION = 4.0  # seconds per slide
NEOPIXEL_BRIGHTNESS = 0.3
# ──────────────────────────────────────────────────────────────────────

# ─── DISPLAY SETUP ───────────────────────────────────────────────────
display = board.DISPLAY
display.brightness = 1.0

# ─── NEOPIXELS ───────────────────────────────────────────────────────
pixels = neopixel.NeoPixel(board.NEOPIXEL, 3, brightness=NEOPIXEL_BRIGHTNESS, auto_write=True)
pixels.fill((0, 0, 0))

# ─── BUTTONS (active low, internal pull-up) ──────────────────────────
def make_button(pin):
    b = digitalio.DigitalInOut(pin)
    b.direction = digitalio.Direction.INPUT
    b.pull = digitalio.Pull.UP
    return b

btn_left = make_button(board.BUTTON_1)   # B1 = previous
btn_up = make_button(board.BUTTON_2)     # B2 = play/pause
btn_right = make_button(board.BUTTON_3)  # B3 = next
btn_down = make_button(board.BUTTON_4)   # B4 = LED toggle

# ─── SENSORS ─────────────────────────────────────────────────────────
i2c = board.I2C()

# SHT31 (temp/humidity)
try:
    import adafruit_sht31d
    sht31 = adafruit_sht31d.SHT31D(i2c)
except Exception:
    sht31 = None

# LSM6DSL (accelerometer)
try:
    from adafruit_lsm6ds.lsm6ds3 import LSM6DS3 as LSM6DSL
    lsm = LSM6DSL(i2c, address=0x6A)
except Exception:
    try:
        from adafruit_lsm6ds.lsm6dsl import LSM6DSL
        lsm = LSM6DSL(i2c, address=0x6A)
    except Exception:
        lsm = None

# Ambient light (ADC)
try:
    light_sensor = analogio.AnalogIn(board.AMBIENT_LIGHT)
except Exception:
    light_sensor = None

# ─── QR CODE GENERATOR ───────────────────────────────────────────────
def make_qr_group(url):
    qr = adafruit_miniqr.QRCode(qr_type=3, error_correct=adafruit_miniqr.L)
    qr.add_data(bytearray(url.encode("utf-8")))
    qr.make()

    bmp = displayio.Bitmap(qr.matrix.width, qr.matrix.height, 2)
    palette = displayio.Palette(2)
    palette[0] = 0xFFFFFF  # white
    palette[1] = 0x000000  # black

    for y in range(qr.matrix.height):
        for x in range(qr.matrix.width):
            bmp[x, y] = 1 if qr.matrix[x, y] else 0

    # scale to fill display
    scale = min(240 // qr.matrix.width, 240 // qr.matrix.height)
    tg = displayio.TileGrid(bmp, pixel_shader=palette)
    group = displayio.Group(scale=scale)
    group.append(tg)

    # center it
    outer = displayio.Group()
    offset_x = (240 - qr.matrix.width * scale) // 2
    offset_y = (240 - qr.matrix.height * scale) // 2
    group.x = offset_x
    group.y = offset_y
    outer.append(group)

    # add label below/above
    lbl = label.Label(terminalio.FONT, text="Scan me!", color=0x000000)
    lbl.anchor_point = (0.5, 1.0)
    lbl.anchored_position = (120, 238)
    outer.append(lbl)
    return outer

# ─── IMAGE LOADER ────────────────────────────────────────────────────
def load_image_group(path):
    try:
        bmp, pal = adafruit_imageload.load(path, bitmap=displayio.Bitmap, palette=displayio.Palette)
        tg = displayio.TileGrid(bmp, pixel_shader=pal)
        group = displayio.Group()
        group.append(tg)
        return group
    except Exception as e:
        # show error text if image missing
        group = displayio.Group()
        lbl = label.Label(terminalio.FONT, text=f"Missing:\n{path}", color=0xFF0000)
        lbl.anchor_point = (0.5, 0.5)
        lbl.anchored_position = (120, 120)
        group.append(lbl)
        return group

# ─── SENSOR SCREEN ───────────────────────────────────────────────────
import terminalio

def make_sensor_group():
    group = displayio.Group()

    title = label.Label(terminalio.FONT, text="Sensor Readings", color=0x00AAFF, scale=2)
    title.anchor_point = (0.5, 0.0)
    title.anchored_position = (120, 10)
    group.append(title)

    readings = label.Label(terminalio.FONT, text="Loading...", color=0xFFFFFF, scale=1)
    readings.anchor_point = (0.0, 0.0)
    readings.anchored_position = (10, 50)
    group.append(readings)

    return group, readings

def update_sensor_text(readings_label):
    lines = []

    if sht31:
        try:
            lines.append(f"Temp:     {sht31.temperature:.1f} C")
            lines.append(f"Humidity: {sht31.relative_humidity:.1f} %")
        except Exception:
            lines.append("Temp/Humidity: error")
    else:
        lines.append("SHT31: not found")

    lines.append("")

    if lsm:
        try:
            ax, ay, az = lsm.acceleration
            lines.append(f"Accel X: {ax:+.2f} m/s2")
            lines.append(f"Accel Y: {ay:+.2f} m/s2")
            lines.append(f"Accel Z: {az:+.2f} m/s2")
            gx, gy, gz = lsm.gyro
            lines.append(f"Gyro  X: {gx:+.2f} rad/s")
            lines.append(f"Gyro  Y: {gy:+.2f} rad/s")
            lines.append(f"Gyro  Z: {gz:+.2f} rad/s")
        except Exception:
            lines.append("Accel/Gyro: error")
    else:
        lines.append("LSM6DSL: not found")

    lines.append("")

    if light_sensor:
        try:
            raw = light_sensor.value
            lines.append(f"Light:    {raw}")
        except Exception:
            lines.append("Light: error")
    else:
        lines.append("Light: not found")

    readings_label.text = "\n".join(lines)

# ─── LED LIGHT SHOW ──────────────────────────────────────────────────
def wheel(pos):
    """Color wheel: 0-255 input → (r, g, b) rainbow."""
    if pos < 85:
        return (255 - pos * 3, pos * 3, 0)
    elif pos < 170:
        pos -= 85
        return (0, 255 - pos * 3, pos * 3)
    else:
        pos -= 170
        return (pos * 3, 0, 255 - pos * 3)

led_show_active = False
led_hue = 0

def led_step():
    """Advance one frame of the LED animation. Call frequently."""
    global led_hue
    if not led_show_active:
        return
    for i in range(3):
        pixels[i] = wheel((led_hue + i * 85) % 256)
    led_hue = (led_hue + 3) % 256

# ─── BUILD SLIDES ────────────────────────────────────────────────────
SLIDE_PHOTO = 0
SLIDE_LOGO = 1
SLIDE_QR = 2
SLIDE_SENSORS = 3
NUM_SLIDES = 4

photo_group = load_image_group("/images/photo.bmp")
logo_group = load_image_group("/images/logo.bmp")
qr_group = make_qr_group(LINKEDIN_URL)
sensor_group, sensor_readings_label = make_sensor_group()

slides = [photo_group, logo_group, qr_group, sensor_group]

# ─── STATE ───────────────────────────────────────────────────────────
current_slide = 0
auto_play = True
last_advance = time.monotonic()
last_btn_time = 0
DEBOUNCE = 0.25

def show_slide(index):
    global current_slide, last_advance
    current_slide = index % NUM_SLIDES
    display.root_group = slides[current_slide]
    last_advance = time.monotonic()

def btn_pressed(btn):
    """Check if button is pressed (active low) with debounce."""
    global last_btn_time
    if not btn.value:  # active low
        now = time.monotonic()
        if now - last_btn_time > DEBOUNCE:
            last_btn_time = now
            return True
    return False

# ─── MAIN LOOP ───────────────────────────────────────────────────────
show_slide(0)

while True:
    now = time.monotonic()

    # Button: left = previous
    if btn_pressed(btn_left):
        show_slide(current_slide - 1)

    # Button: right = next
    if btn_pressed(btn_right):
        show_slide(current_slide + 1)

    # Button: up = play/pause
    if btn_pressed(btn_up):
        auto_play = not auto_play

    # Button: down = toggle LED show
    if btn_pressed(btn_down):
        led_show_active = not led_show_active
        if not led_show_active:
            pixels.fill((0, 0, 0))

    # Auto-advance slideshow
    if auto_play and (now - last_advance >= SLIDE_DURATION):
        show_slide(current_slide + 1)

    # Update sensor readings if on that slide
    if current_slide == SLIDE_SENSORS:
        update_sensor_text(sensor_readings_label)

    # LED animation step
    led_step()

    time.sleep(0.02)  # ~50fps loop
