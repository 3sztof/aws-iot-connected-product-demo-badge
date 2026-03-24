# Conference Badge — Requirements

## Overview

A standalone offline slideshow program for the AWS IoT Demo Badge 2023, designed for use at conferences. Runs on CircuitPython — no cloud connectivity needed.

## Hardware

- AWS IoT Demo Badge 2023 (nRF52840 + ST7789V 240×240 display + 3× WS2812 LEDs + 4 buttons + SHT31 temp/humidity + LSM6DSL accelerometer + ambient light sensor)
- Display: ST7789V, 240×240px, RGB565
- LEDs: 3× WS2812 (NeoPixel) on pin P0.12
- Buttons: B1 (P1.08), B2 (P0.07), B3 (P0.05), B4 (P0.04) — active low, pull-up
- Sensors: SHT31 (I2C 0x44), LSM6DSL (I2C 0x6A), ambient light (ADC P0.03)

## Slideshow Screens

The program cycles through these screens automatically:

1. **Photo** — personal headshot (BMP, 240×240)
2. **Company logo** — company badge/logo (BMP, 240×240)
3. **QR code** — generated on-device, links to LinkedIn profile URL
4. **Sensor readings** — live display of all badge sensor data (temperature, humidity, accelerometer, ambient light)

Each screen displays for ~4 seconds before advancing.

## Button Controls

| Button | Position | Action |
|--------|----------|--------|
| B1 | Left | Previous slide |
| B3 | Right | Next slide |
| B2 | Up | Play / Pause slideshow auto-advance |
| B4 | Down | Start / Stop LED light show |

## LED Light Show

- Triggered by B4 (toggle on/off)
- Runs a colorful animated sequence on the 3 WS2812 LEDs in a loop
- Should be eye-catching (rainbow cycle, chase, or similar)
- Runs concurrently with the slideshow (non-blocking)

## Sensor Readings Screen

Displays live data from all onboard sensors:
- Temperature (°C) from SHT31
- Humidity (%) from SHT31
- Accelerometer X/Y/Z from LSM6DSL
- Ambient light level from ADC

Updated in real-time while the screen is active.

## Image Requirements

- Format: BMP, 240×240 pixels
- Place in the badge's CIRCUITPY drive under `/images/`
- Files: `photo.bmp`, `logo.bmp`

## QR Code

- Generated on-device using `adafruit_miniqr`
- URL is configurable in `code.py` (default: LinkedIn profile URL)
- Rendered as black-on-white, centered on display

## Runtime

- Runs on CircuitPython 8.2.7 (badge-specific build)
- Fully offline — no WiFi, no cloud, no ExpressLink
- Program lives in `code.py` on the CIRCUITPY USB drive
- To update: edit files on the USB drive, badge auto-reloads

## Deployment

1. Flash CircuitPython UF2 to the badge (enter bootloader → copy UF2)
2. Copy `code.py` and `images/` to the CIRCUITPY drive
3. Badge auto-runs the slideshow on boot

## Reverting to Original Firmware

- Enter bootloader (double-tap reset)
- Flash the original Zephyr firmware UF2
- Original firmware and USB mass storage content are preserved on the external flash
