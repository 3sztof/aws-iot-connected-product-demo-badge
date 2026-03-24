BUILD   = build

CC      = arm-none-eabi-gcc
AS      = arm-none-eabi-gcc
OBJCOPY = arm-none-eabi-objcopy

CFLAGS  = -mcpu=cortex-m4 -mthumb -mfloat-abi=soft \
          -Os -g0 \
          -ffunction-sections -fdata-sections \
          -Wall -Wno-unused-function \
          -Isrc

LDFLAGS = -mcpu=cortex-m4 -mthumb -mfloat-abi=soft \
          -T nrf52840.ld \
          -Wl,--gc-sections \
          -nostdlib \
          --specs=nosys.specs

.PHONY: all clean qspi_eraser sd_probe

all: qspi_eraser sd_probe

$(BUILD):
	mkdir -p $(BUILD)

# ── QSPI eraser ──────────────────────────────────────────────────────────────

$(BUILD)/qspi_eraser.o: src/main.c | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD)/startup_qspi.o: startup.s | $(BUILD)
	$(AS) $(CFLAGS) -c $< -o $@

$(BUILD)/qspi_eraser.elf: $(BUILD)/qspi_eraser.o $(BUILD)/startup_qspi.o
	$(CC) $(LDFLAGS) -Wl,-Map=$(BUILD)/qspi_eraser.map $^ -o $@

$(BUILD)/qspi_eraser.bin: $(BUILD)/qspi_eraser.elf
	$(OBJCOPY) -O binary $< $@

$(BUILD)/qspi_eraser.uf2: $(BUILD)/qspi_eraser.bin
	python3 uf2conv.py $< -b 0x27000 -f 0xADA52840 -c -o $@
	@echo "==> $@ ready"; ls -lh $@

qspi_eraser: $(BUILD)/qspi_eraser.uf2

# ── SoftDevice probe ─────────────────────────────────────────────────────────

$(BUILD)/sd_probe.o: src/sd_probe.c | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD)/startup_sd.o: startup.s | $(BUILD)
	$(AS) $(CFLAGS) -c $< -o $@

$(BUILD)/sd_probe.elf: $(BUILD)/sd_probe.o $(BUILD)/startup_sd.o
	$(CC) $(LDFLAGS) -Wl,-Map=$(BUILD)/sd_probe.map $^ -o $@

$(BUILD)/sd_probe.bin: $(BUILD)/sd_probe.elf
	$(OBJCOPY) -O binary $< $@

$(BUILD)/sd_probe.uf2: $(BUILD)/sd_probe.bin
	python3 uf2conv.py $< -b 0x27000 -f 0xADA52840 -c -o $@
	@echo "==> $@ ready"; ls -lh $@

sd_probe: $(BUILD)/sd_probe.uf2

# ─────────────────────────────────────────────────────────────────────────────

clean:
	rm -rf $(BUILD)
