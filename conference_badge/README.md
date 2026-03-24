# Conference Badge — Setup Guide

Turn your AWS IoT Demo Badge into a conference badge with an offline slideshow, QR code, sensor display, and LED light show.

## What You Get

- Auto-cycling slideshow: your photo → company logo → LinkedIn QR code → live sensor readings
- Button controls: previous / next / play-pause / LED toggle
- Rainbow LED animation on the 3 NeoPixels
- Fully offline — no WiFi or cloud needed

## Prerequisites

- AWS IoT Demo Badge 2023
- USB cable
- Your images (240×240 BMP format)

## Step 1 — Prepare Your Images

### Image requirements

The badge display is 240×240 pixels. CircuitPython needs indexed-color BMP files (256 colors max, BMP3 format).

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

Requires ImageMagick (`brew install imagemagick`).

**Headshot / square photo** — crops and fills the full 240×240 area:

```bash
convert images/raw/me.jpeg \
    -resize 240x240^ -gravity center -extent 240x240 \
    -colors 256 -type palette BMP3:images/photo.bmp
```

**Logo / non-square image** — scales to fit inside 240×240 with a white background, centered:

```bash
convert images/raw/aws_logo.png \
    -resize 200x200 -background white -gravity center -extent 240x240 \
    -colors 256 -type palette BMP3:images/logo.bmp
```

> Adjust `-resize 200x200` to control how much padding surrounds the logo. Use `240x240` for edge-to-edge, or smaller values for more whitespace.

**Dark background variant** — use `-background black` if your logo is light-colored.

### Verify the output

```bash
identify images/photo.bmp images/logo.bmp
# Should show: BMP3 240x240 ... 8-bit sRGB 256c
```

## Step 2 — Configure Your LinkedIn URL

Edit `code.py` and change the URL at the top:

```python
LINKEDIN_URL = "https://linkedin.com/in/your-profile"
```

## Step 3 — Flash CircuitPython to the Badge

The badge needs CircuitPython firmware instead of the default Zephyr firmware.

### Option A: Use a pre-built CircuitPython UF2

If you have a pre-built `circuitpython.uf2` for the Demo Badge:

1. Enter bootloader mode: double-tap the reset button (or run `enter_bootloader` from the Zephyr serial shell)
2. The badge appears as a USB drive (e.g. `DEMOBADGE` or `BOOT`)
3. Copy the UF2 file to the drive:
   ```bash
   cp circuitpython.uf2 /Volumes/DEMOBADGE/
   ```
4. Badge reboots and mounts as `CIRCUITPY`

### Option B: Build CircuitPython from source

```bash
cd circuitpython/
./build.sh
# Output: builds/circuitpython.uf2
```

Then flash as in Option A.

## Step 4 — Deploy the Badge Program

Once the badge is running CircuitPython and mounted as `CIRCUITPY`:

```bash
# Copy the main program
cp code.py /Volumes/CIRCUITPY/

# Copy your images
mkdir -p /Volumes/CIRCUITPY/images/
cp images/photo.bmp /Volumes/CIRCUITPY/images/
cp images/logo.bmp /Volumes/CIRCUITPY/images/
```

The badge auto-reloads and starts the slideshow immediately.

## Usage

### Slideshow

The display cycles through 4 screens every 4 seconds:

1. Your photo
2. Company logo
3. QR code (LinkedIn)
4. Live sensor readings (temperature, humidity, accelerometer, light)

### Button Controls

| Button | Position | Action |
|--------|----------|--------|
| B1 | Left | Previous slide |
| B3 | Right | Next slide |
| B2 | Top | Play / Pause auto-advance |
| B4 | Bottom | Toggle LED light show |

### LED Light Show

Press B4 to start a rainbow chase animation on the 3 NeoPixels. Press again to stop.

## Customization

### Slide duration

In `code.py`:
```python
SLIDE_DURATION = 4.0  # seconds
```

### LED brightness

```python
NEOPIXEL_BRIGHTNESS = 0.3  # 0.0 to 1.0
```

## Reverting to Original Firmware

1. Enter bootloader: double-tap reset button
2. Copy the original Zephyr UF2: `cp firmware/build/zephyr.uf2 /Volumes/BOOT/`
3. Or flash `firmware/adafruit_bootloader_demo_badge_2023/update-bootloader.uf2` first if needed

The original Zephyr firmware and USB mass storage data are on separate flash partitions and are preserved.

## Troubleshooting

- **"Missing: /images/photo.bmp"** — image file not found on CIRCUITPY drive. Check the path.
- **Display is blank** — check that `code.py` is on the root of CIRCUITPY. Open the serial console (`screen /dev/cu.usbmodem* 115200`) to see Python errors.
- **Sensors show "not found"** — the CircuitPython build may not include the sensor library. Check that `adafruit_sht31d` and `adafruit_lsm6ds` are in the frozen modules.
- **QR code too small** — the QR scales automatically. Shorter URLs produce larger QR modules.

---

## Firmware Files

```
firmware/
├── circuitpython_internal.uf2   # CircuitPython 8.2.7, INTERNAL_FLASH_FILESYSTEM=1 ← USE THIS
├── circuitpython.uf2            # CircuitPython 8.2.7, QSPI_FLASH_FILESYSTEM=1 (broken — see Recovery)
├── original_zephyr.uf2          # Original Zephyr firmware (cannot flash via UF2 — targets 0x1000)
├── zephyr_fixed.uf2             # Zephyr with patched family ID (still targets 0x1000)
└── zephyr_nrf_family.uf2        # Another Zephyr variant (still targets 0x1000)
```

Always use `circuitpython_internal.uf2`. See the Recovery section for why.

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
