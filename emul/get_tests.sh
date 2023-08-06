#!/bin/bash

# https://github.com/stnolting/riscv-gcc-prebuilt
# Grab a prebuilt risc-v cross compiler toolchain
cd /opt/riscv
wget https://github.com/stnolting/riscv-gcc-prebuilt/releases/download/rv32i-4.0.0/riscv32-unknown-elf.gcc-12.1.0.tar.gz
sudo tar -zxvf riscv32-unknown-elf.gcc-12.1.0.tar.gz -C /opt/riscv/

# Get the risc-v tests and build them with the toolchain
git clone https://github.com/riscv/riscv-tests.git
cd riscv-tests
git submodule update --init --recursive
autoconf
./configure --target=riscv32-unknown-elf
make -j