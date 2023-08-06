//   riscv64-unknown-elf-gcc -march=rv32i -mabi=ilp32 main.c -o helloworld


/*
 Test inline assembly
*/

#include <stdio.h>
#include <stdint.h>
#include <string.h>


void ecall_func(uint32_t num, uint32_t a0, uint32_t a1, uint32_t a2)
{
    __asm__("mv	a7, %0\n\t"
        "mv	a0, %1\n\t"
        "mv	a1, %2\n\t"
        "mv	a2, %3\n\t"
        "ecall\n\t"
        //: // no input operands
        :: "r" (num), "r" (a0), "r" (a1), "r" (a2));
}

int main(int argc, const char** args)
{
    printf("Hello World!\n");

    char* str = "ecall test\n";
    ecall_func(64, 1, (uint32_t)str, strlen(str) + 1);

    return 0;
}
