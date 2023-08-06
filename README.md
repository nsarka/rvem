# rvem: a RISC-V Emulator

So far, this is based on George Hotz' emulator here: https://github.com/nsarka/twitchcore/blob/master/cpu.py

## Setup for Ubuntu WSL

I am using Ubuntu WSL on Windows. These same steps should work on Ubuntu native.

### Grab a prebuilt risc-v cross compiler toolchain (or optionally build it yourself)

https://github.com/stnolting/riscv-gcc-prebuilt

```
cd /opt/riscv
wget https://github.com/stnolting/riscv-gcc-prebuilt/releases/download/rv32i-4.0.0/riscv32-unknown-elf.gcc-12.1.0.tar.gz
sudo tar -zxvf riscv32-unknown-elf.gcc-12.1.0.tar.gz -C /opt/riscv/
export PATH=/opt/riscv/bin:$PATH
```

### Get the risc-v tests and build them with the toolchain

```
git submodule update --init --recursive
cd riscv-tests
autoupdate
autoconf
./configure --target=riscv32-unknown-elf CC=/opt/riscv/bin/riscv32-unknown-elf-gcc
make -j
```

Make sure `/opt/riscv/bin` is in your path before running `make -j`. I don't know why it doesn't just use CC, but it didn't seem to work without passing CC either.


### Run a test

```
cd custom_tests
./build.sh rsort/rsort
cd ../emul
python3 rvem.py ../custom_tests/rsort/rsort
```