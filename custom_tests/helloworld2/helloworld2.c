//   riscv64-unknown-elf-gcc -march=rv32i -mabi=ilp32 main.c -o helloworld


/*
 Test inline assembly
*/

#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <stdlib.h>


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
    char* heap_str = malloc(64);

    if (heap_str == NULL) {
        printf("failure: x null\n");
        return 1;
    }

    char* str = "ecall test123\n";
    strcpy(heap_str, str);

    //printf("printing string at address 0x%x\n", heap_str);
    ecall_func(64, 1, (uint32_t)heap_str, strlen(heap_str) + 1);

    /*
        for (int i = 0; i < 100; i++) {
            char* x = malloc(1);
            if (x == NULL) {
                printf("failure: x null\n");
                return 1;
            }
            printf("%c\n", x);
        }

        printf("success\n");
        free(heap_str);
    */

    return 0;
}
