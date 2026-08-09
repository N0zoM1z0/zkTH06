/*
 * Copyright (C) 2026 N0zoM1z0
 *
 * Freestanding i386 stream harness for a locally extracted __ftol2 body.
 * The runner supplies ftol2.bin in a temporary directory.  No original-game
 * bytes are present in this source or retained by the repository.
 */

    .section .data
control_word:
    .short 0x027f

    .section .bss
    .align 16
input_value:
    .skip 10
output_value:
    .skip 10

    .section .text
    .global _start
_start:
    fninit
    fldcw control_word

read_record:
    movl $input_value, %edi
    movl $10, %esi

read_more:
    movl $3, %eax
    xorl %ebx, %ebx
    movl %edi, %ecx
    movl %esi, %edx
    int $0x80
    testl %eax, %eax
    js io_error
    jnz read_progress
    cmpl $10, %esi
    je clean_exit
    jmp io_error

read_progress:
    addl %eax, %edi
    subl %eax, %esi
    jnz read_more

    fnclex
    fldt input_value
    call ftol2_body
    movl %eax, output_value
    movl %edx, output_value + 4
    fnstsw %ax
    movw %ax, output_value + 8

    movl $output_value, %edi
    movl $10, %esi

write_more:
    movl $4, %eax
    movl $1, %ebx
    movl %edi, %ecx
    movl %esi, %edx
    int $0x80
    testl %eax, %eax
    jle io_error
    addl %eax, %edi
    subl %eax, %esi
    jnz write_more
    jmp read_record

clean_exit:
    xorl %ebx, %ebx
    jmp exit

io_error:
    movl $2, %ebx

exit:
    movl $1, %eax
    int $0x80

    .align 16
ftol2_body:
    .incbin "ftol2.bin"
