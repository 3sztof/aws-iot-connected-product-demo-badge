/**
 * SoftDevice Probe for AWS IoT Demo Badge 2023 (nRF52840)
 *
 * Reads flash at 0x1000 (start of SoftDevice region) and signals the result
 * via the user LED (P0.13, active HIGH per bootloader board.h):
 *
 *   SLOW blink (500ms on / 500ms off) × 5  = SoftDevice signature found
 *   FAST blink (100ms on / 100ms off) × 20 = Flash is erased (0xFFFFFFFF) — SD MISSING
 *   MEDIUM blink (200ms on / 200ms off) × 10 = Unknown content (SD corrupt/wrong)
 *
 * After signalling, resets back to BADGE_BOOT.
 *
 * The S140 SoftDevice starts with the MBR's "forward" word at 0x1000.
 * A valid S140 v7.x has a non-0xFF, non-0x00 value there (it's an ARM
 * vector table or SoftDevice info struct).
 * We check:
 *   - 0xFFFFFFFF at 0x1000 → erased flash → SD missing
 *   - 0x00000000 at 0x1000 → all zeros → SD region zeroed
 *   - anything else → SD likely present (check also 0x3000 for SD info struct)
 *
 * The Nordic SoftDevice info struct is at a fixed offset of 0x3000 from
 * the SoftDevice start (0x1000 + 0x2000 = 0x3008 for the magic word 0x51B1E5DB).
 */

#include <stdint.h>
#include <stdbool.h>

/* ── GPIO ─────────────────────────────────────────────────────────────────── */
#define GPIO0_BASE      0x50000000UL
#define GPIO0_DIRSET (*(volatile uint32_t*)(GPIO0_BASE + 0x518))
#define GPIO0_OUTSET (*(volatile uint32_t*)(GPIO0_BASE + 0x508))
#define GPIO0_OUTCLR (*(volatile uint32_t*)(GPIO0_BASE + 0x50C))

/* User LED P0.13 — active HIGH */
#define LED_ON()    GPIO0_OUTSET = (1u << 13)
#define LED_OFF()   GPIO0_OUTCLR = (1u << 13)

/* ── Reset to bootloader ──────────────────────────────────────────────────── */
#define SCB_AIRCR           (*(volatile uint32_t*)0xE000ED0CUL)
#define AIRCR_VECTKEY       0x05FA0000UL
#define AIRCR_SYSRESETREQ   (1UL << 2)
#define NRF_POWER_GPREGRET  (*(volatile uint32_t*)0x4000051CUL)
#define BOOTLOADER_DFU_START 0x57

/* ── Flash read ───────────────────────────────────────────────────────────── */
/* The nRF52840 internal flash is memory-mapped read-only at 0x00000000.
 * We can read it directly as a pointer. */
#define SOFTDEVICE_START    0x1000UL
#define SOFTDEVICE_INFO_MAGIC_ADDR  0x3008UL    /* SD info struct magic word */
#define SOFTDEVICE_INFO_MAGIC       0x51B1E5DBUL /* Nordic SD info magic */

static void delay_ms(uint32_t ms) {
    for (uint32_t i = 0; i < ms * 16000; i++) {
        __asm volatile("nop");
    }
}

static void blink(uint32_t on_ms, uint32_t off_ms, uint32_t count) {
    for (uint32_t i = 0; i < count; i++) {
        LED_ON();
        delay_ms(on_ms);
        LED_OFF();
        delay_ms(off_ms);
    }
}

static void reset_to_bootloader(void) {
    NRF_POWER_GPREGRET = BOOTLOADER_DFU_START;
    SCB_AIRCR = AIRCR_VECTKEY | AIRCR_SYSRESETREQ;
    while (1) {}
}

int main(void) {
    GPIO0_DIRSET = (1u << 13);
    LED_OFF();
    delay_ms(500);  /* brief pause so we can observe the start */

    /* Read the first word at the SoftDevice start address */
    uint32_t sd_word0 = *(volatile uint32_t*)SOFTDEVICE_START;

    /* Read the Nordic SD info magic word at 0x3008 */
    uint32_t sd_magic = *(volatile uint32_t*)SOFTDEVICE_INFO_MAGIC_ADDR;

    if (sd_word0 == 0xFFFFFFFFUL) {
        /* Erased flash — SoftDevice definitely missing */
        /* FAST blink × 20 */
        blink(100, 100, 20);
    } else if (sd_magic == SOFTDEVICE_INFO_MAGIC) {
        /* Nordic SD info struct magic found — SoftDevice is present */
        /* SLOW blink × 5 */
        blink(500, 500, 5);
    } else {
        /* Something is there but not a valid SoftDevice */
        /* MEDIUM blink × 10 */
        blink(200, 200, 10);
    }

    /* 1 second pause, then reset to BADGE_BOOT */
    delay_ms(1000);
    reset_to_bootloader();
    return 0;
}
