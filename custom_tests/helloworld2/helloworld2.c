#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main() {
    FILE* f = fopen("doom1.wad", "rb");
    int buffer_len = 20224;
    char* buffer = malloc(buffer_len);
    fseek(f, 4175796, SEEK_SET);
    size_t sz = fread(buffer, 1, buffer_len, f);
    printf("size read: %ld\n", sz);
    fclose(f);
    return 0;
}