#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

uint32_t ecall_func(uint32_t num, uint32_t a0, uint32_t a1, uint32_t a2)
{
    uint32_t res;
    __asm__("mv	a7, %1\n\t"
        "mv	a0, %2\n\t"
        "mv	a1, %3\n\t"
        "mv	a2, %4\n\t"
        "ecall\n\t"
        "mv %0, a0"
        : "=r" (res)
        : "r" (num), "r" (a0), "r" (a1), "r" (a2)
    );
    return res;
}

int main() {
    uint32_t ret = ecall_func(0xbeef0, 0, 0, 0);
    printf("ret value was: %d\n", ret);
    return 0;
}