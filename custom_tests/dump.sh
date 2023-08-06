#!/bin/bash

testname=$1
/opt/riscv/bin/riscv32-unknown-elf-objdump $testname -S | tee $testname.disassembly
