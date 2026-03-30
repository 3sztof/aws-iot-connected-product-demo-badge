import gc
import time
import board
import digitalio
import displayio
import neopixel
import busio
import analogio
import terminalio
import adafruit_miniqr
from adafruit_display_text import label

LINKEDIN_URL = "https://linkedin.com/in/3sztof"
SLIDE_DURATION = 6.0
LED_BRIGHTNESS_LEVELS = (0.1, 0.3, 0.6)

_event_pin = digitalio.DigitalInOut(board.EXPRESSLINK_EVENT)
_event_pin.direction = digitalio.Direction.OUTPUT
_event_pin.value = False

# ─── DISPLAY (ST7789V 240×280 1.69" ER-TFT1.69-2) ──────────────────
displayio.release_displays()
spi = busio.SPI(clock=board.SCK, MOSI=board.MOSI)
display_bus = displayio.FourWire(
    spi, command=board.DISPLAY_DC, chip_select=board.DISPLAY_CS
)

_ST7789_INIT = (
    b"\x01\x80\x96\x11\x80\xff\x3a\x01\x05\x36\x01\x00\x21\x00\x13\x80\x0a\x29\x80\xff"
)
display = displayio.Display(
    display_bus,
    _ST7789_INIT,
    width=240,
    height=280,
    colstart=0,
    rowstart=20,
    backlight_pin=board.DISPLAY_BACKLIGHT_PWM,
)
display.brightness = 1.0

pixels = neopixel.NeoPixel(board.NEOPIXEL, 3, brightness=0.1, auto_write=True)
pixels.fill((0, 0, 0))


def make_button(pin):
    b = digitalio.DigitalInOut(pin)
    b.direction = digitalio.Direction.INPUT
    b.pull = digitalio.Pull.UP
    return b


btn_left = make_button(board.BUTTON_4)
btn_right = make_button(board.BUTTON_2)
btn_up = make_button(board.BUTTON_1)
btn_down = make_button(board.BUTTON_3)

i2c = board.I2C()

try:
    import adafruit_sht31d

    sht31 = adafruit_sht31d.SHT31D(i2c)
except Exception:
    sht31 = None

try:
    from adafruit_lsm6ds.lsm6ds3 import LSM6DS3 as LSM6DSL

    lsm = LSM6DSL(i2c, address=0x6A)
except Exception:
    try:
        from adafruit_lsm6ds.lsm6dsl import LSM6DSL

        lsm = LSM6DSL(i2c, address=0x6A)
    except Exception:
        lsm = None

try:
    light_sensor = analogio.AnalogIn(board.AMBIENT_LIGHT)
except Exception:
    light_sensor = None


def make_qr_group(url):
    qr = adafruit_miniqr.QRCode(qr_type=3, error_correct=adafruit_miniqr.L)
    qr.add_data(bytearray(url, "utf-8"))
    qr.make()

    qr_size = qr.matrix.width
    scale = min(240 // qr_size, 240 // qr_size)
    pixel_size = qr_size * scale

    bmp = displayio.Bitmap(qr_size, qr_size, 2)
    pal = displayio.Palette(2)
    pal[0] = 0xFFFFFF
    pal[1] = 0x000000

    for y in range(qr_size):
        for x in range(qr_size):
            bmp[x, y] = 1 if qr.matrix[x, y] else 0

    tg = displayio.TileGrid(bmp, pixel_shader=pal)
    inner = displayio.Group(scale=scale)
    inner.append(tg)

    outer = displayio.Group()
    inner.x = (240 - pixel_size) // 2
    inner.y = (280 - pixel_size) // 2
    outer.append(inner)

    lbl = label.Label(terminalio.FONT, text="Scan me!", color=0x000000)
    lbl.anchor_point = (0.5, 1.0)
    lbl.anchored_position = (120, 276)
    outer.append(lbl)
    return outer


def load_image_into(group, path):
    display.auto_refresh = False
    while len(group):
        group.pop()
    gc.collect()
    try:
        bmp = displayio.OnDiskBitmap(path)
        group.y = (280 - bmp.height) // 2
        x_off = (240 - bmp.width) // 2
        group.append(displayio.TileGrid(bmp, pixel_shader=bmp.pixel_shader, x=x_off))
    except Exception as e:
        print("Image error", path, e)
        group.y = 0
        lbl = label.Label(terminalio.FONT, text=str(e), color=0xFF0000)
        lbl.anchor_point = (0.5, 0.5)
        lbl.anchored_position = (120, 140)
        group.append(lbl)
    display.auto_refresh = True


def make_sensor_group():
    group = displayio.Group()

    title = label.Label(
        terminalio.FONT, text="Sensor Readings", color=0x00AAFF, scale=2
    )
    title.anchor_point = (0.5, 0.0)
    title.anchored_position = (120, 20)
    group.append(title)

    readings = label.Label(terminalio.FONT, text="Loading...", color=0xFFFFFF, scale=1)
    readings.anchor_point = (0.5, 0.0)
    readings.anchored_position = (120, 55)
    group.append(readings)

    return group, readings


def update_sensor_text(readings_label):
    lines = []
    if sht31:
        try:
            lines.append("Temp:     %.1f C" % sht31.temperature)
            lines.append("Humidity: %.1f %%" % sht31.relative_humidity)
        except Exception:
            lines.append("Temp/Humidity: error")
    else:
        lines.append("SHT31: not found")
    lines.append("")
    if lsm:
        try:
            ax, ay, az = lsm.acceleration
            lines.append("Accel X: %+.2f m/s2" % ax)
            lines.append("Accel Y: %+.2f m/s2" % ay)
            lines.append("Accel Z: %+.2f m/s2" % az)
            gx, gy, gz = lsm.gyro
            lines.append("Gyro  X: %+.2f rad/s" % gx)
            lines.append("Gyro  Y: %+.2f rad/s" % gy)
            lines.append("Gyro  Z: %+.2f rad/s" % gz)
        except Exception:
            lines.append("Accel/Gyro: error")
    else:
        lines.append("LSM6DSL: not found")
    lines.append("")
    if light_sensor:
        try:
            lines.append("Light:    %d" % light_sensor.value)
        except Exception:
            lines.append("Light: error")
    else:
        lines.append("Light: not found")
    readings_label.text = "\n".join(lines)


def wheel(pos):
    if pos < 85:
        return (255 - pos * 3, pos * 3, 0)
    elif pos < 170:
        pos -= 85
        return (0, 255 - pos * 3, pos * 3)
    else:
        pos -= 170
        return (pos * 3, 0, 255 - pos * 3)


led_show_active = False
led_brightness_idx = 0
led_hue = 0


def led_step():
    global led_hue
    if not led_show_active:
        return
    for i in range(3):
        pixels[i] = wheel((led_hue + i * 85) % 256)
    led_hue = (led_hue + 3) % 256


SLIDE_PHOTO = 0
SLIDE_LOGO = 1
SLIDE_QR = 2
SLIDE_SENSORS = 3
NUM_SLIDES = 4

_IMAGE_PATHS = {
    SLIDE_PHOTO: "/images/photo.bmp",
    SLIDE_LOGO: "/images/logo.bmp",
}

sensor_group, sensor_readings_label = make_sensor_group()
qr_group = make_qr_group(LINKEDIN_URL)
_img_group = displayio.Group()

_name_first = label.Label(terminalio.FONT, text="Krzysztof", color=0xFFFFFF, scale=2)
_name_first.anchor_point = (0.5, 0.5)
_name_first.anchored_position = (120, -20)
_name_last = label.Label(terminalio.FONT, text="Wilczynski", color=0xFFFFFF, scale=2)
_name_last.anchor_point = (0.5, 0.5)
_name_last.anchored_position = (120, 220)

gc.collect()
print("Free RAM after init:", gc.mem_free())

current_slide = 0
auto_play = True
last_advance = time.monotonic()
last_btn_time = 0
last_sensor_update = 0
DEBOUNCE = 0.25


def show_slide(index):
    global current_slide, last_advance
    current_slide = index % NUM_SLIDES
    if current_slide in _IMAGE_PATHS:
        display.root_group = _img_group
        load_image_into(_img_group, _IMAGE_PATHS[current_slide])
        if current_slide == SLIDE_PHOTO:
            _img_group.append(_name_first)
            _img_group.append(_name_last)
    elif current_slide == SLIDE_QR:
        display.root_group = qr_group
    elif current_slide == SLIDE_SENSORS:
        display.root_group = sensor_group
    last_advance = time.monotonic()


def btn_pressed(btn):
    global last_btn_time
    if not btn.value:
        now = time.monotonic()
        if now - last_btn_time > DEBOUNCE:
            last_btn_time = now
            return True
    return False


show_slide(0)
last_advance = time.monotonic()

while True:
    now = time.monotonic()

    if btn_pressed(btn_left):
        show_slide(current_slide - 1)

    if btn_pressed(btn_right):
        show_slide(current_slide + 1)

    if btn_pressed(btn_up):
        auto_play = not auto_play

    if btn_pressed(btn_down):
        if not led_show_active:
            led_show_active = True
            led_brightness_idx = 0
            pixels.brightness = LED_BRIGHTNESS_LEVELS[0]
        else:
            led_brightness_idx += 1
            if led_brightness_idx >= len(LED_BRIGHTNESS_LEVELS):
                led_show_active = False
                pixels.fill((0, 0, 0))
            else:
                pixels.brightness = LED_BRIGHTNESS_LEVELS[led_brightness_idx]

    if auto_play and (now - last_advance >= SLIDE_DURATION):
        show_slide(current_slide + 1)

    if current_slide == SLIDE_SENSORS:
        if now - last_sensor_update >= 1.0:
            update_sensor_text(sensor_readings_label)
            last_sensor_update = now

    led_step()
    time.sleep(0.01)
