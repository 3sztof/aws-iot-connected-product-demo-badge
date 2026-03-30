#!/usr/bin/env bash

# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

# Builds CircuitPython 8.2.7 for the AWS IoT Demo Badge 2023 with
# INTERNAL_FLASH_FILESYSTEM=1 (uses nRF52840 built-in 1MB flash).
#
# Why not the default QSPI build (build.sh)?
#   The QSPI build (QSPI_FLASH_FILESYSTEM=1) enters safe mode without USB when
#   the W25Q128BV QSPI chip has a foreign filesystem on it (e.g. from Zephyr).
#   This build avoids that entirely. Tradeoff: ~48KB CIRCUITPY vs 16MB.
#
# Why CIRCUITPY_FULL_BUILD=0?
#   FULL_BUILD=1 overflows nRF52840's 1MB internal flash by ~144KB.
#
# Known build issues fixed here:
#   1. Shallow clone (--depth 1) has no tags → git describe fails in
#      preprocess_frozen_modules.py and gen_display_resources.py.
#      Fix: fetch tags for frozen submodules + patch preprocess_frozen_modules.py.
#   2. gen_display_resources.py BitmapStub missing __setitem__ (Python 3.10
#      incompatibility with newer adafruit_bitmap_font).
#      Fix: patch BitmapStub in gen_display_resources.py.
#   3. tools/bitmap_font submodule not fetched by fetch-port-submodules.
#      Fix: explicitly init tools/bitmap_font.
#   4. Missing pip packages: huffman, semver.
#      Fix: install before build.
#   5. CIRCUITPY_FULL_BUILD=0 + displayio pulls in EPaperDisplay which
#      references missing QSTRs. Fix: explicitly disable EPaperDisplay,
#      FramebufferIO, SharpDisplay, RGBMatrix, GifIO.

set -o nounset
set -o pipefail
set -o xtrace
set -o errexit

cd "$(dirname "${BASH_SOURCE[0]}")"

rm -rf circuitpython
git clone --depth 1 --branch 8.2.7 https://github.com/adafruit/circuitpython.git

(cd circuitpython && git am ../0001-add-demo-badge-2023.patch)

# Switch from QSPI to internal flash filesystem, disable full build to fit in 1MB
BOARD_MK="circuitpython/ports/nrf/boards/demo_badge_2023/mpconfigboard.mk"
sed -i 's/^QSPI_FLASH_FILESYSTEM = 1/INTERNAL_FLASH_FILESYSTEM = 1/' "$BOARD_MK"
sed -i '/^EXTERNAL_FLASH_DEVICES/d' "$BOARD_MK"
sed -i 's/^CIRCUITPY_FULL_BUILD = 1/CIRCUITPY_FULL_BUILD = 0/' "$BOARD_MK"

# Disable modules that cause build/link errors with FULL_BUILD=0 + displayio
cat >> "$BOARD_MK" << 'EOF'

# Disabled: cause linker errors or QSTR failures with FULL_BUILD=0
CIRCUITPY_FRAMEBUFFERIO = 0
CIRCUITPY_SHARPDISPLAY = 0
CIRCUITPY_RGBMATRIX = 0
CIRCUITPY_GIFIO = 0
CIRCUITPY_EPAPERDISPLAY = 0

# Explicitly enable modules that code.py needs (disabled by FULL_BUILD=0)
CIRCUITPY_DISPLAYIO = 1
CIRCUITPY_BUSIO = 1
CIRCUITPY_ANALOGIO = 1
CIRCUITPY_DIGITALIO = 1
CIRCUITPY_NEOPIXEL_WRITE = 1
CIRCUITPY_TERMINALIO = 1
EOF

# Fix 1: patch preprocess_frozen_modules.py to handle shallow clones with no tags
python3 - << 'PYEOF'
import re, pathlib
p = pathlib.Path("circuitpython/tools/preprocess_frozen_modules.py")
src = p.read_text()
old = '''\
    except subprocess.CalledProcessError:
        describe = subprocess.check_output("git describe --tags", shell=True, cwd=path)
        tag, additional_commits, commit_ish = (
            describe.strip().decode("utf-8", "strict").rsplit("-", maxsplit=2)
        )
        commit_ish = commit_ish[1:]'''
new = '''\
    except subprocess.CalledProcessError:
        try:
            describe = subprocess.check_output("git describe --tags", shell=True, cwd=path)
            tag, additional_commits, commit_ish = (
                describe.strip().decode("utf-8", "strict").rsplit("-", maxsplit=2)
            )
            commit_ish = commit_ish[1:]
        except subprocess.CalledProcessError:
            return "0.0.0+unknown"'''
if old in src:
    p.write_text(src.replace(old, new))
    print("patched preprocess_frozen_modules.py")
else:
    print("preprocess_frozen_modules.py already patched or changed upstream")
PYEOF

# Fix 2: patch gen_display_resources.py BitmapStub to support __setitem__
python3 - << 'PYEOF'
import pathlib
p = pathlib.Path("circuitpython/tools/gen_display_resources.py")
src = p.read_text()
old = '''\
class BitmapStub:
    def __init__(self, width, height, color_depth):
        self.width = width
        self.rows = [b""] * height

    def _load_row(self, y, row):
        self.rows[y] = bytes(row)'''
new = '''\
class BitmapStub:
    def __init__(self, width, height, color_depth):
        self.width = width
        self.rows = [b""] * height
        self._data = bytearray(width * height)

    def __setitem__(self, index, value):
        self._data[index] = value

    def _load_row(self, y, row):
        self.rows[y] = bytes(row)'''
if old in src:
    p.write_text(src.replace(old, new))
    print("patched gen_display_resources.py")
else:
    print("gen_display_resources.py already patched or changed upstream")
PYEOF

# Fetch nRF port submodules (nrfx, tinyusb, protomatter, etc.)
(cd circuitpython/ports/nrf/ && make fetch-port-submodules) || true

# Fix 3: init tools/bitmap_font (needed by gen_display_resources.py)
(cd circuitpython && git submodule update --init tools/bitmap_font tools/uf2)

# Fix 4: install missing pip packages
pip3 install -r circuitpython/requirements-dev.txt -q
pip3 install -q huffman semver

# Fetch tags for frozen submodules so preprocess_frozen_modules.py can version them
(cd circuitpython && git submodule foreach --quiet \
    'case "$name" in frozen/*) git fetch --tags --depth=1 2>/dev/null || true; esac')

# Build mpy-cross
(cd circuitpython && make -C mpy-cross -j"$(nproc)")

mkdir -p builds/

# Build CircuitPython for the badge
(cd circuitpython/ports/nrf/ && make BOARD=demo_badge_2023 -j"$(nproc)")

cp circuitpython/ports/nrf/build-demo_badge_2023/firmware.uf2 builds/circuitpython_internal.uf2

echo ""
echo "==> Built: builds/circuitpython_internal.uf2"
ls -lh builds/circuitpython_internal.uf2
