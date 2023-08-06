#!/bin/bash

testname=$1
/opt/riscv/bin/riscv32-unknown-elf-gcc $testname.c -o $testname -g
