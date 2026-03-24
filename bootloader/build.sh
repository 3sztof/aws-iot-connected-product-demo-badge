#!/usr/bin/env bash

# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

# Builds the Adafruit nRF52 Bootloader 0.8.0 for the AWS IoT Demo Badge 2023
# and produces a DFU zip package containing the bootloader + SoftDevice S140 v7.0.1.
#
# The DFU zip is flashed via adafruit-nrfutil over the badge's CDC serial port
# (BADGE_BOOT mode) to restore a missing or incorrect SoftDevice. This is the
# recovery step required when CircuitPython shows red NeoPixels and no USB.
#
# Why S140 v7.0.1 (not v7.3.0)?
#   CircuitPython 8.2.7 was compiled against S140 v7.0.1 headers. Using v7.3.0
#   causes USB enumeration to fail. The correct SoftDevice hex is bundled with
#   CircuitPython in: ../circuitpython/circuitpython/ports/nrf/bluetooth/s140_nrf52_7.0.1/
#   Run circuitpython/build_internal.sh first to clone that repo.
#
# Output:
#   build/demo_badge_2023_s140_7.0.1.zip  — flash this to recover a bricked badge
#   build/update-bootloader.uf2           — bootloader-only self-update (no SoftDevice)
#
# Flash the DFU zip:
#   adafruit-nrfutil dfu serial \
#     --package build/demo_badge_2023_s140_7.0.1.zip \
#     -p /dev/ttyACM0 -b 115200 --singlebank --touch 1200

set -o nounset
set -o pipefail
set -o xtrace
set -o errexit

cd "$(dirname "${BASH_SOURCE[0]}")"

# intelhex is required by the Makefile's hexmerge.py step
# Use uv tool if available, otherwise pip
if command -v uv &>/dev/null; then
    uv tool install intelhex 2>/dev/null || true
    INTELHEX_PATH="$(python3 -c "import pathlib; paths=[p for p in __import__('site').getsitepackages() if 'intelhex' in str(p)]; print(paths[0] if paths else '')" 2>/dev/null || true)"
    export PYTHONPATH="${HOME}/.local/share/uv/tools/intelhex/lib/python3.13/site-packages:${PYTHONPATH:-}"
else
    pip3 install -q intelhex
fi

rm -rf Adafruit_nRF52_Bootloader
git clone --depth 1 --branch 0.8.0 https://github.com/adafruit/Adafruit_nRF52_Bootloader.git

(cd Adafruit_nRF52_Bootloader && git am --keep-cr < ../0001-add-demo-badge-2023.patch)

(cd Adafruit_nRF52_Bootloader && git submodule update --init)

mkdir -p build/

(cd Adafruit_nRF52_Bootloader && PYTHONPATH="${PYTHONPATH:-}" make BOARD=demo_badge_2023 all)

# Copy build artifacts
BL_HEX="$(ls Adafruit_nRF52_Bootloader/_build/build-demo_badge_2023/demo_badge_2023_bootloader-*.hex \
    | grep -v nosd | grep -v update | head -1)"

cp "$BL_HEX" build/bootloader_nosd.hex
cp Adafruit_nRF52_Bootloader/_build/build-demo_badge_2023/demo_badge_2023_bootloader-*.out build/bootloader.elf
cp Adafruit_nRF52_Bootloader/_build/build-demo_badge_2023/update-demo_badge_2023_bootloader-*_nosd.uf2 build/update-bootloader.uf2

# Build the DFU zip with S140 v7.0.1 (the version CircuitPython 8.2.7 expects)
# This requires circuitpython/build_internal.sh to have been run first to clone the repo
SD_HEX="../circuitpython/circuitpython/ports/nrf/bluetooth/s140_nrf52_7.0.1/s140_nrf52_7.0.1_softdevice.hex"

if [ ! -f "$SD_HEX" ]; then
    echo "ERROR: SoftDevice hex not found at $SD_HEX"
    echo "Run circuitpython/build_internal.sh first to clone CircuitPython and get the SoftDevice."
    exit 1
fi

adafruit-nrfutil dfu genpkg \
    --dev-type 0x0052 \
    --dev-revision 52840 \
    --bootloader "$BL_HEX" \
    --softdevice "$SD_HEX" \
    build/demo_badge_2023_s140_7.0.1.zip

echo ""
echo "==> Build complete. Output files:"
ls -lh build/demo_badge_2023_s140_7.0.1.zip build/update-bootloader.uf2 build/bootloader_nosd.hex
echo ""
echo "==> To flash (badge must be in BADGE_BOOT mode):"
echo "    adafruit-nrfutil dfu serial \\"
echo "      --package build/demo_badge_2023_s140_7.0.1.zip \\"
echo "      -p /dev/ttyACM0 -b 115200 --singlebank --touch 1200"
