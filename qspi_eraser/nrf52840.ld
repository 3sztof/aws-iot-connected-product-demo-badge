/* Linker script for nRF52840 bare-metal app at 0x27000
 * (after Adafruit bootloader + SoftDevice S140 v7 region)
 * Stack at top of 256KB RAM.
 */

MEMORY
{
  FLASH (rx)  : ORIGIN = 0x00027000, LENGTH = 0xD9000   /* ~868KB app region */
  RAM   (rwx) : ORIGIN = 0x20000000, LENGTH = 0x40000   /* 256KB */
}

ENTRY(Reset_Handler)

SECTIONS
{
  .text :
  {
    KEEP(*(.isr_vector))
    *(.text*)
    *(.rodata*)
    . = ALIGN(4);
  } > FLASH

  .data :
  {
    _sdata = .;
    *(.data*)
    . = ALIGN(4);
    _edata = .;
  } > RAM AT > FLASH

  _sidata = LOADADDR(.data);

  .bss :
  {
    _sbss = .;
    *(.bss*)
    *(COMMON)
    . = ALIGN(4);
    _ebss = .;
  } > RAM

  .stack (NOLOAD) :
  {
    . = ALIGN(8);
    . += 0x1000;   /* 4KB stack */
    _estack = .;
  } > RAM
}
