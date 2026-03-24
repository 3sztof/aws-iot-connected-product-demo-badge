/* Minimal startup for nRF52840 bare-metal app */
    .syntax unified
    .cpu cortex-m4
    .thumb

    .section .isr_vector, "a", %progbits
    .align 2
    .globl __isr_vector
__isr_vector:
    .word   _estack             /* Initial stack pointer */
    .word   Reset_Handler       /* Reset handler */
    .word   Default_Handler     /* NMI */
    .word   Default_Handler     /* HardFault */
    .word   Default_Handler     /* MemManage */
    .word   Default_Handler     /* BusFault */
    .word   Default_Handler     /* UsageFault */
    .word   0
    .word   0
    .word   0
    .word   0
    .word   Default_Handler     /* SVCall */
    .word   Default_Handler     /* Debug Monitor */
    .word   0
    .word   Default_Handler     /* PendSV */
    .word   Default_Handler     /* SysTick */
    /* External interrupts — all default */
    .rept   64
    .word   Default_Handler
    .endr

    .section .text.Reset_Handler
    .thumb_func
    .globl  Reset_Handler
Reset_Handler:
    /* Copy .data from FLASH to RAM */
    ldr     r0, =_sdata
    ldr     r1, =_edata
    ldr     r2, =_sidata
    b       2f
1:  ldr     r3, [r2], #4
    str     r3, [r0], #4
2:  cmp     r0, r1
    blo     1b

    /* Zero .bss */
    ldr     r0, =_sbss
    ldr     r1, =_ebss
    mov     r2, #0
    b       4f
3:  str     r2, [r0], #4
4:  cmp     r0, r1
    blo     3b

    /* Jump to main */
    bl      main
    b       .

    .section .text.Default_Handler
    .thumb_func
Default_Handler:
    b       .
