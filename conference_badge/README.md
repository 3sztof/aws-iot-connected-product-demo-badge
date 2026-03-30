# Conference Badge — Setup Guide

Turn your AWS IoT Demo Badge into a conference badge with an offline slideshow, QR code, sensor display, and LED light show.

## What You Get

- Auto-cycling slideshow: your photo → company logo → LinkedIn QR code → live sensor readings
- Name labels on your photo slide (first name top, last name bottom)
- Button controls: previous / next / play-pause / LED brightness cycling
- Rainbow LED animation on the 3 NeoPixels with 3 brightness levels
- Fully offline — no WiFi or cloud needed

## Prerequisites

- AWS IoT Demo Badge 2023
- USB cable
- Python 3 with Pillow (`pip install Pillow`) for image conversion
- Your images (JPEG/PNG, any size — the conversion script handles resizing)

## Step 1 — Prepare Your Images

### Directory structure

```
conference_badge/images/
├── raw/              ← your original high-res images (any format)
│   ├── me.jpeg
│   └── aws_logo.png
├── photo.bmp         ← converted, ready for the badge
└── logo.bmp          ← converted, ready for the badge
```

### Converting images

The badge display is 240×280 pixels (1.69" ST7789V). Images must be uncompressed indexed-color BMP files.

**Use the Python conversion script** (recommended over ImageMagick — ensures correct BMP format for CircuitPython's `OnDiskBitmap`):

```python
import struct
from PIL import Image, ImageEnhance

def write_bmp3_8bit(img_rgb, path, colors=256):
    """Write uncompressed 8-bit indexed BMP3 with BGRA palette."""
    if img_rgb.mode != "RGB":
        img_rgb = img_rgb.convert("RGB")
    indexed = img_rgb.quantize(colors=colors, method=Image.Quantize.MEDIANCUT,
                                dither=Image.Dither.FLOYDSTEINBERG)
    width, height = indexed.size
    pil_pal = indexed.getpalette()
    pixels = indexed.tobytes()
    row_stride = (width + 3) & ~3
    pal_size = colors * 4
    data_offset = 14 + 40 + pal_size
    pix_size = row_stride * height
    with open(path, 'wb') as f:
        f.write(b'BM')
        f.write(struct.pack('<I', data_offset + pix_size))
        f.write(b'\x00\x00\x00\x00')
        f.write(struct.pack('<I', data_offset))
        f.write(struct.pack('<I', 40))
        f.write(struct.pack('<ii', width, height))
        f.write(struct.pack('<HH', 1, 8))
        f.write(struct.pack('<I', 0))
        f.write(struct.pack('<I', pix_size))
        f.write(struct.pack('<iiii', 0, 0, colors, 0))
        for i in range(colors):
            r, g, b = pil_pal[i*3], pil_pal[i*3+1], pil_pal[i*3+2]
            f.write(struct.pack('BBBB', b, g, r, 0))
        for y in range(height - 1, -1, -1):
            f.write(pixels[y * width:(y + 1) * width])
            if row_stride - width:
                f.write(b'\x00' * (row_stride - width))

# --- Photo: 200×200 at 256 colors ---
photo = Image.open("images/raw/me.jpeg").convert("RGB")
w, h = photo.size
side = min(w, h)
left, top = (w - side) // 2, (h - side) // 2
photo = photo.crop((left, top, left + side, top + side)).resize((200, 200), Image.LANCZOS)
photo = ImageEnhance.Brightness(photo).enhance(0.95)
photo = ImageEnhance.Color(photo).enhance(0.70)
# Push dark background pixels to pure black
px = photo.load()
for y in range(200):
    for x in range(200):
        r, g, b = px[x, y]
        if r * 0.299 + g * 0.587 + b * 0.114 < 35:
            px[x, y] = (0, 0, 0)
write_bmp3_8bit(photo, "images/photo.bmp")

# --- Logo: 240×280 at 16 colors (fills entire display) ---
AWS_BG = (4, 39, 58)  # AWS Squid Ink — sampled from the official logo PNG
logo_rgba = Image.open("images/raw/aws_logo.png").convert("RGBA")
logo_rgba.thumbnail((220, 250), Image.LANCZOS)
bg = Image.new("RGB", (240, 280), AWS_BG)
bg.paste(logo_rgba, ((240 - logo_rgba.width) // 2, (280 - logo_rgba.height) // 2), logo_rgba)
# 4-bit BMP for logo (only ~3 distinct colors, saves RAM)
indexed = bg.convert("RGB").quantize(colors=16, method=Image.Quantize.MEDIANCUT,
                                      dither=Image.Dither.FLOYDSTEINBERG)
# Use write_bmp3_4bit or convert with the same pattern at bpp=4
```

> **Important**: Do NOT use RLE-compressed BMPs (ImageMagick may produce these). CircuitPython's `OnDiskBitmap` requires uncompressed BMP files.

## Step 2 — Configure

Edit `code.py`:

```python
LINKEDIN_URL = "https://linkedin.com/in/your-profile"
```

To change your name on the photo slide, find the `_name_first` and `_name_last` labels.

## Step 3 — Flash CircuitPython Firmware

The badge needs a custom CircuitPython build with `displayio` enabled.

1. Enter bootloader: single-tap the reset button → badge mounts as `BADGE_BOOT`
2. Copy the firmware:
   ```bash
   cp firmware/circuitpython_internal.uf2 /Volumes/BADGE_BOOT/
   ```
3. Badge reboots and mounts as `CIRCUITPY` (~238KB filesystem)

> **Always use `circuitpython_internal.uf2`** — it uses internal flash. The QSPI build enters safe mode due to Zephyr's leftover filesystem.

### Display init notes

The ST7789V display (1.69", 240×280, ER-TFT1.69-2) requires manual initialization in CircuitPython because `board.DISPLAY` is not configured in the board definition. The init sequence in `code.py` uses:
- **MADCTL 0x00** (RGB color order)
- **INVON** for correct color polarity on this panel
- **No RAMCTRL** — the Zephyr firmware's RAMCTRL sets little-endian pixel byte order which is incompatible with CircuitPython's big-endian displayio

## Step 4 — Deploy

```bash
cp code.py /Volumes/CIRCUITPY/
mkdir -p /Volumes/CIRCUITPY/images/
cp images/photo.bmp /Volumes/CIRCUITPY/images/
cp images/logo.bmp /Volumes/CIRCUITPY/images/
```

The badge auto-reloads and starts the slideshow immediately.

## Usage

### Slideshow

The display cycles through 4 screens every 6 seconds:

1. Your photo (with name labels)
2. Company logo (full-screen)
3. QR code (LinkedIn)
4. Live sensor readings (temperature, humidity, accelerometer, light)

### Button Layout

| Button | Physical Position | Action |
|--------|-------------------|--------|
| B4 | Left | Previous slide |
| B2 | Right | Next slide |
| B1 | Top | Play / Pause auto-advance |
| B3 | Bottom | LED brightness: dim → medium → bright → off |

> Note: The physical button positions differ from the silkscreen labels on the PCB.

### LED Light Show

Press bottom button (B3) to start a rainbow chase animation. Each press cycles through 3 brightness levels (10%, 30%, 60%), then turns off.

## Memory Architecture

The nRF52840 has 256KB RAM. After CircuitPython runtime and displayio buffers, ~107KB is free.

Images use `displayio.OnDiskBitmap` which reads pixels directly from the CIRCUITPY flash filesystem — **zero RAM allocation** for pixel data. This avoids heap fragmentation that would otherwise cause `MemoryError` after several slideshow cycles.

Sensor text updates are throttled to 1Hz to prevent string allocation from fragmenting the heap.

## Customization

### Slide duration

```python
SLIDE_DURATION = 6.0  # seconds per slide
```

### LED brightness levels

```python
LED_BRIGHTNESS_LEVELS = (0.1, 0.3, 0.6)
```

## Reverting to Original Firmware

1. Enter bootloader: single-tap reset button
2. Copy the original Zephyr UF2: `cp firmware/original_zephyr.uf2 /Volumes/BADGE_BOOT/`

The original Zephyr firmware and QSPI flash data are on separate flash partitions and are preserved.

## Troubleshooting

- **Display is blank** — check that `code.py` is on the root of CIRCUITPY. Connect serial console (`screen /dev/cu.usbmodem* 115200`) to see errors. Most likely: missing firmware with `displayio` enabled.
- **Colors wrong on images** — ensure RAMCTRL (0xB0) is NOT in the display init sequence. The Zephyr firmware's RAMCTRL uses little-endian byte order incompatible with CircuitPython.
- **"memory allocation failed"** — images must use `OnDiskBitmap` (not `adafruit_imageload`). Check sensor update throttling is in place (1Hz, not every loop).
- **Sensors show "not found"** — the sensor libraries (`adafruit_sht31d`, `adafruit_lsm6ds`) must be frozen in the CircuitPython build.
- **QR code hard to scan** — use a shorter URL (drop `www.`, trailing slashes). The QR auto-scales to fill the display.
- **Safe mode / CIRCUITPY not found** — filesystem corrupted. Connect serial, enter REPL, run `import storage; storage.erase_filesystem()` to recreate it.
- **Badge completely unresponsive** — see the Recovery section below.

---

## Firmware Files

```
firmware/
├── circuitpython_internal.uf2   # CircuitPython 8.2.7, INTERNAL_FLASH ← USE THIS
├── circuitpython.uf2            # CircuitPython 8.2.7, QSPI_FLASH (broken — see Recovery)
├── original_zephyr.uf2          # Original Zephyr firmware (cannot flash via UF2 — targets 0x1000)
├── zephyr_fixed.uf2             # Zephyr with patched family ID (still targets 0x1000)
└── zephyr_nrf_family.uf2        # Another Zephyr variant (still targets 0x1000)
```

### Flashing on Linux / WSL2

Standard `cp` to a mounted drive does not reliably trigger the UF2 bootloader.
Write directly to the raw block device:

```bash
# Find the device (badge must be in BADGE_BOOT mode — single-tap reset)
lsblk -o NAME,SIZE,LABEL | grep BADGE_BOOT   # e.g. sde

sudo dd if=firmware/circuitpython_internal.uf2 of=/dev/sde bs=512
```

On **WSL2**, attach the badge via `usbipd` first:

```powershell
# PowerShell (Admin) — once per session
usbipd attach --wsl --busid <X-X>   # find busid with: usbipd list
```

---

## Badge Recovery (Bricked / No USB)

### Symptoms

- 3× red NeoPixels + pulsing green user LED + no `CIRCUITPY` drive
- `BADGE_BOOT` appears on single-tap reset (bootloader is alive)
- No USB enumeration from CircuitPython at all

### Root Cause

The badge was originally set up with the Adafruit nRF52 Bootloader installed **without**
the Nordic SoftDevice S140. The SoftDevice (`0x1000–0x26FFF`) is a separate binary that
CircuitPython relies on for USB enumeration via SVC calls. Without it, the first SVC
instruction in `port_init()` causes a HardFault before USB ever initialises.

The badge sits at `0xF4000` (bootloader) which is why `BADGE_BOOT` works fine —
the bootloader doesn't use the SoftDevice for UF2 mode.

A secondary issue: `circuitpython.uf2` was built with `QSPI_FLASH_FILESYSTEM=1`. Even
with a working SoftDevice, it enters safe mode because the W25Q128BV QSPI chip still
has Zephyr's FAT filesystem on it. `circuitpython_internal.uf2` avoids this by using
the nRF52840's internal flash instead.

### nRF52840 Flash Layout (correct state)

```
0x00000000  MBR (4KB)               Nordic Master Boot Record
0x00001000  SoftDevice S140 v7.0.1  Nordic USB/BLE stack (~152KB)
0x00027000  CircuitPython 8.2.7     Application (~823KB)
0x000F4000  Adafruit Bootloader     UF2 / DFU
0x000FF000  Bootloader settings
```

### Recovery Steps

**Requirements:** Linux or WSL2, `adafruit-nrfutil`, `usbipd-win` (WSL2 only)

```bash
# Install adafruit-nrfutil (use uv — do not use pip directly)
uv tool install adafruit-nrfutil
```

**Step 1: Single-tap reset → BADGE_BOOT, attach via usbipd**

```powershell
usbipd attach --wsl --busid <X-X>
```

**Step 2: Flash bootloader + SoftDevice S140 v7.0.1**

The DFU zip is pre-built at `../bootloader/build/demo_badge_2023_s140_7.0.1.zip`.
To rebuild it from source: `cd ../bootloader && bash build.sh`

```bash
adafruit-nrfutil dfu serial \
  --package ../bootloader/build/demo_badge_2023_s140_7.0.1.zip \
  -p /dev/ttyACM0 -b 115200 --singlebank --touch 1200
```

**Step 3: Single-tap reset → BADGE_BOOT re-appears, re-attach, then flash CircuitPython**

```bash
sudo dd if=firmware/circuitpython_internal.uf2 of=/dev/sde bs=512
```

**Step 4: CIRCUITPY appears** — copy `code.py` and you're done.

### Why S140 v7.0.1 (not v7.3.0)?

CircuitPython 8.2.7 was compiled against S140 v7.0.1 headers. Using v7.3.0 also
causes USB to fail to enumerate due to API differences. The bootloader repo ships
v7.3.0 by default — `bootloader/build.sh` explicitly uses v7.0.1 from CircuitPython's
own bundled SoftDevice.

### Diagnostic Tool

`../qspi_eraser/` contains bare-metal probe programs that run via `BADGE_BOOT`:

- `sd_probe.uf2` — reads `0x1000` and blinks the user LED:
  - **Fast blink ×20** (100ms) = SoftDevice missing (`0xFFFFFFFF`)
  - **Slow blink ×5** (500ms) = SoftDevice present and valid
  - **Medium blink ×10** (200ms) = Unknown content

- `qspi_eraser.uf2` — erases first 256KB of QSPI flash (removes Zephyr FAT),
  then resets to `BADGE_BOOT`. Only needed if switching to the QSPI build.
