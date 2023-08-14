#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

#define DOOMGENERIC_RESX 640
#define DOOMGENERIC_RESY 400

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
    char* DG_ScreenBuffer = malloc(DOOMGENERIC_RESX * DOOMGENERIC_RESY * sizeof(uint32_t));
    uint32_t ret = ecall_func(0xbeef0, 0, 0, 0);
    printf("ret value from init was: %d\n", ret);
    ecall_func(0xbeef1, (uint32_t)DG_ScreenBuffer, DOOMGENERIC_RESX, DOOMGENERIC_RESY);
    return 0;
}