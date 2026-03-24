/**
 * QSPI Flash Eraser for AWS IoT Demo Badge 2023 (nRF52840)
 *
 * Erases the first 256KB of the W25Q128 QSPI flash (covers the FAT filesystem
 * superblock and FAT tables that Zephyr left behind), then resets into the
 * Adafruit UF2 bootloader so CircuitPython can be reflashed cleanly.
 *
 * QSPI pins (from badge hardware):
 *   CS   = P0.17
 *   SCK  = P0.19
 *   D0   = P0.20
 *   D1   = P0.21
 *   D2   = P0.22
 *   D3   = P0.23
 *
 * Runs as a bare-metal app at 0x27000 (after SoftDevice S140 v7 region).
 * No SoftDevice is used — direct register access only.
 */

#include <stdint.h>
#include <stdbool.h>

/* ── NRF52840 peripheral base addresses ─────────────────────────────────── */
#define QSPI_BASE       0x40029000UL
#define GPIO0_BASE      0x50000000UL

/* ── QSPI registers ──────────────────────────────────────────────────────── */
typedef struct {
    volatile uint32_t TASKS_ACTIVATE;   /* 0x000 */
    volatile uint32_t TASKS_READSTART;  /* 0x004 */
    volatile uint32_t TASKS_WRITESTART; /* 0x008 */
    volatile uint32_t TASKS_ERASESTART; /* 0x00C */
    volatile uint32_t TASKS_DEACTIVATE; /* 0x010 */
    uint32_t _pad0[59];
    volatile uint32_t EVENTS_READY;     /* 0x100 */
    uint32_t _pad1[127];
    volatile uint32_t INTEN;            /* 0x300 */
    volatile uint32_t INTENSET;
    volatile uint32_t INTENCLR;
    uint32_t _pad2[125];
    volatile uint32_t ENABLE;           /* 0x500 */
    volatile uint32_t READ_SRC;         /* 0x504 */
    volatile uint32_t READ_DST;         /* 0x508 */
    volatile uint32_t READ_CNT;         /* 0x50C */
    volatile uint32_t WRITE_DST;        /* 0x510 */
    volatile uint32_t WRITE_SRC;        /* 0x514 */
    volatile uint32_t WRITE_CNT;        /* 0x518 */
    volatile uint32_t ERASE_PTR;        /* 0x51C */
    volatile uint32_t ERASE_LEN;        /* 0x520 */
    volatile uint32_t PSEL_SCK;         /* 0x524 */
    volatile uint32_t PSEL_CSN;         /* 0x528 */
    uint32_t _pad3;
    volatile uint32_t PSEL_IO0;         /* 0x530 */
    volatile uint32_t PSEL_IO1;         /* 0x534 */
    volatile uint32_t PSEL_IO2;         /* 0x538 */
    volatile uint32_t PSEL_IO3;         /* 0x53C */
    volatile uint32_t XIPOFFSET;        /* 0x540 */
    volatile uint32_t IFCONFIG0;        /* 0x544 */
    uint32_t _pad4[46];
    volatile uint32_t IFCONFIG1;        /* 0x600 */
    volatile uint32_t STATUS;           /* 0x604 */
    uint32_t _pad5[3];
    volatile uint32_t DPMDUR;           /* 0x614 */
    uint32_t _pad6[3];
    volatile uint32_t ADDRCONF;         /* 0x624 */
    uint32_t _pad7[3];
    volatile uint32_t CINSTRCONF;       /* 0x634 */
    volatile uint32_t CINSTRDAT0;       /* 0x638 */
    volatile uint32_t CINSTRDAT1;       /* 0x63C */
    volatile uint32_t IFTIMING;         /* 0x640 */
} NRF_QSPI_Type;

/* ── POWER.GPREGRET — direct pointer (struct layout is too complex to inline) */
/* POWER base = 0x40000000, GPREGRET at offset 0x51C (confirmed from nrf52840.h) */
#define NRF_POWER_GPREGRET  (*(volatile uint32_t*)0x4000051CUL)

/* ── NVMC registers (needed to set GPREGRET via NRF_POWER) ───────────────── */
/* We use SCB->AIRCR for reset instead */
#define SCB_AIRCR   (*(volatile uint32_t*)0xE000ED0CUL)
#define AIRCR_VECTKEY       0x05FA0000UL
#define AIRCR_SYSRESETREQ   (1UL << 2)

#define NRF_QSPI    ((NRF_QSPI_Type*)QSPI_BASE)

/* ── Pin encoding: port<<5 | pin ─────────────────────────────────────────── */
#define PIN(port, pin)  ((uint32_t)(((port) << 5) | (pin)))
#define PSEL_CONNECT(p) ((p) & 0x3F)   /* connected = bit31 clear */

/* Badge QSPI pins */
#define QSPI_CS_PIN     PIN(0, 17)
#define QSPI_SCK_PIN    PIN(0, 19)
#define QSPI_IO0_PIN    PIN(0, 20)
#define QSPI_IO1_PIN    PIN(0, 21)
#define QSPI_IO2_PIN    PIN(0, 22)
#define QSPI_IO3_PIN    PIN(0, 23)

/* W25Q128: 16MB, 256 x 64KB blocks. Erase first 4 blocks (256KB) — covers
 * the FAT superblock, FAT tables, and root directory that Zephyr wrote. */
#define ERASE_BLOCK_SIZE    (64 * 1024)
#define ERASE_BLOCKS        4           /* 256KB total */

/* GPREGRET value to tell bootloader to enter DFU/UF2 mode */
#define BOOTLOADER_DFU_START    0x57

static void qspi_wait_ready(void) {
    while (NRF_QSPI->EVENTS_READY == 0) {}
    NRF_QSPI->EVENTS_READY = 0;
}

static void delay_ms(uint32_t ms) {
    /* crude busy-wait at ~64MHz */
    for (uint32_t i = 0; i < ms * 16000; i++) {
        __asm volatile("nop");
    }
}

static void reset_to_bootloader(void) {
    /* Tell the Adafruit bootloader to enter UF2 DFU mode on next boot.
     * GPREGRET is at POWER_BASE + 0x51C = 0x4000051C (confirmed from nrf52840.h) */
    NRF_POWER_GPREGRET = BOOTLOADER_DFU_START;
    /* System reset */
    SCB_AIRCR = AIRCR_VECTKEY | AIRCR_SYSRESETREQ;
    while (1) {}
}

/* NeoPixel (P0.12) — blink to show progress, no driver needed */
#define GPIO0_DIRSET (*(volatile uint32_t*)(GPIO0_BASE + 0x518))
#define GPIO0_OUT    (*(volatile uint32_t*)(GPIO0_BASE + 0x504))
#define GPIO0_OUTSET (*(volatile uint32_t*)(GPIO0_BASE + 0x508))
#define GPIO0_OUTCLR (*(volatile uint32_t*)(GPIO0_BASE + 0x50C))

/* User LED P0.13 — active HIGH (LED_STATE_ON = 1, per bootloader board.h) */
static void led_init(void) {
    GPIO0_DIRSET = (1u << 13);  /* P0.13 output */
    GPIO0_OUTSET = (1u << 13);  /* LED on (active high) */
}

static void led_off(void) {
    GPIO0_OUTCLR = (1u << 13);  /* LED off */
}

int main(void) {
    led_init();

    /* ── Configure QSPI peripheral ─────────────────────────────────────── */
    NRF_QSPI->PSEL_SCK = PSEL_CONNECT(QSPI_SCK_PIN);
    NRF_QSPI->PSEL_CSN = PSEL_CONNECT(QSPI_CS_PIN);
    NRF_QSPI->PSEL_IO0 = PSEL_CONNECT(QSPI_IO0_PIN);
    NRF_QSPI->PSEL_IO1 = PSEL_CONNECT(QSPI_IO1_PIN);
    NRF_QSPI->PSEL_IO2 = PSEL_CONNECT(QSPI_IO2_PIN);
    NRF_QSPI->PSEL_IO3 = PSEL_CONNECT(QSPI_IO3_PIN);

    /* IFCONFIG0: read mode FASTREAD (0), write mode PP (0), addr mode 24-bit (0)
     * DPMEN=0, PPSIZE=256B (0), freq div=2 (32MHz / 2 = 16MHz) */
    NRF_QSPI->IFCONFIG0 = 0
        | (0 << 0)   /* READOC: FASTREAD (single SPI) */
        | (0 << 3)   /* WRITEOC: PP (single SPI) */
        | (0 << 6)   /* ADDRMODE: 24-bit */
        | (0 << 7)   /* MEMTYPE: standard (not deep power down) */
        | (0 << 12); /* PPSIZE: 256 bytes */

    /* IFCONFIG1: SCK delay=1, SCKFREQ=3 → 32MHz/(3+1) = 8MHz (safe for all flash) */
    NRF_QSPI->IFCONFIG1 = 0
        | (1 << 0)   /* SCKDELAY */
        | (0 << 7)   /* DPMEN: disable deep power down on deactivate */
        | (0 << 8)   /* SPIMODE: mode 0 */
        | (3 << 28); /* SCKFREQ: div 4 → 8MHz */

    NRF_QSPI->ENABLE = 1;

    /* Activate QSPI (drives pins, releases flash from reset state) */
    NRF_QSPI->EVENTS_READY = 0;
    NRF_QSPI->TASKS_ACTIVATE = 1;
    qspi_wait_ready();

    /* ── Erase blocks ───────────────────────────────────────────────────── */
    /* ERASE_LEN encoding (from nrf_qspi.h):
     *   0 = 4 KB   (NRF_QSPI_ERASE_LEN_4KB)
     *   1 = 64 KB  (NRF_QSPI_ERASE_LEN_64KB)  ← we use this
     *   2 = chip erase (NRF_QSPI_ERASE_LEN_ALL)
     * Erasing 4 × 64KB = 256KB covers the entire Zephyr FAT filesystem. */
    NRF_QSPI->ERASE_LEN = 1;  /* 64KB block erase */

    for (uint32_t block = 0; block < ERASE_BLOCKS; block++) {
        NRF_QSPI->EVENTS_READY = 0;
        NRF_QSPI->ERASE_PTR = block * ERASE_BLOCK_SIZE;
        NRF_QSPI->TASKS_ERASESTART = 1;
        /* 64KB block erase takes up to 2s on W25Q128 — wait with timeout */
        for (uint32_t t = 0; t < 5000; t++) {
            if (NRF_QSPI->EVENTS_READY) break;
            delay_ms(1);
        }
        NRF_QSPI->EVENTS_READY = 0;
        /* Blink LED between blocks */
        led_off();
        delay_ms(100);
        led_init();
    }

    /* ── Done — deactivate and reset to bootloader ──────────────────────── */
    NRF_QSPI->TASKS_DEACTIVATE = 1;
    delay_ms(50);

    /* LED off = done */
    led_off();
    delay_ms(500);

    reset_to_bootloader();
    return 0;
}
