#!/usr/bin/env python3

from enum import Enum
import argparse
import sys
import os
import struct
from elftools.elf.elffile import ELFFile

parser = argparse.ArgumentParser(
    prog='rvem',
    description='RISC-V Emulator',
    epilog='Contact: nsarka00@gmail.com')

parser.add_argument('binary')           # positional argument
parser.add_argument('-v', '--verbose',
                    action='store_true')  # on/off flag

args = parser.parse_args()

rvem = "[RVEM]"
print(rvem, "Running test", args.binary, "with verbose set to", args.verbose)

needs_break = False

# start of geohot emul program


regnames = \
    ['x0', 'ra', 'sp', 'gp', 'tp'] + ['t%d' % i for i in range(0, 3)] + ['s0', 's1'] +\
    ['a%d' % i for i in range(0, 8)] +\
    ['s%d' % i for i in range(2, 12)] +\
    ['t%d' % i for i in range(3, 7)] + ["PC"]

PC = 32


class Regfile:
    def __init__(self):
        self.regs = [0]*33

    def __getitem__(self, key):
        return self.regs[key]

    def __setitem__(self, key, value):
        if key == 0:
            return
        self.regs[key] = value & 0xFFFFFFFF

    def get(self, name):
        # read by name
        i = regnames.index(name)
        return self.regs[i]

    def set(self, name, val):
        # write by name
        i = regnames.index(name)
        self.regs[i] = val


class OldMemory:
    def __init__(self):
        self.memory = b'\x00'*0x4000

    def write(self, addr, dat):
        addr -= 0x80000000
        assert addr >= 0 and addr < len(memory)
        self.memory = self.memory[:addr] + dat + self.memory[addr+len(dat):]

    def read(self, addr, sz):
        addr -= 0x80000000
        return self.memory[addr:addr+sz]

    def __len__(self):
        return len(self.memory)

regfile = None
memory = None
original_break_addr = 0 # where the data segment ends and the heap begins

class Memory:
    def __init__(self):
        self.mem = {}
        self.page_size = 4096
        self.break_addr = original_break_addr

    def set_brk(self, set_to):
        # what is this *facepalm*
        # this is not what the docs say for how brk should work
        if set_to != 0:
            self.break_addr = set_to
        return self.break_addr

    def get_nth_page_addr(self, addr, i):
        # get the starting address of the nth page after the one addr is in
        return addr - (addr % self.page_size) + (i * self.page_size)

    def read(self, addr, sz):
        # Split up into 3 phases--beginning page, n middle pages, and a last page
        page = self.get_nth_page_addr(addr, 0)
        if page not in self.mem:
            print(rvem,
                f"PC {hex(regfile[PC])}: Uninitialized read of size {sz} at address {hex(addr)} in page {hex(page)}")
            self.mem[page] = b'\x00'*self.page_size
        next_page = self.get_nth_page_addr(addr, 1)
        offset_in_begin_page = addr - page
        begin_sz = min(sz, self.page_size - offset_in_begin_page)
        r = self.mem[page][offset_in_begin_page:(
            offset_in_begin_page+begin_sz)]
        sz -= begin_sz

        # n middle pages
        pages_read = 1
        while sz > self.page_size:
            page = self.get_nth_page_addr(addr, pages_read)
            if page not in self.mem:
                # print(f"PC {hex(regfile[PC])}: Uninitialized read of size {sz} at address {hex(addr)} in page {hex(page)}")
                self.mem[page] = b'\x00'*self.page_size
            r += self.mem[page]
            pages_read += 1
            sz -= self.page_size

        # last page
        if sz > 0:
            page = self.get_nth_page_addr(addr, pages_read)
            if page not in self.mem:
                # print(f"PC {hex(regfile[PC])}: Uninitialized read of size {sz} at address {hex(addr)} in page {hex(page)}")
                self.mem[page] = b'\x00'*self.page_size
            r += self.mem[page][:sz]

        return r

    def write(self, addr, data):
        sz = len(data)

        # Split up into 3 phases--beginning page, n middle pages, and a last page
        page = self.get_nth_page_addr(addr, 0)
        next_page = self.get_nth_page_addr(addr, 1)
        offset_in_begin_page = addr - page
        begin_sz = min(sz, self.page_size - offset_in_begin_page)
        if page not in self.mem:
            self.mem[page] = b'\x00'*self.page_size
        self.mem[page] = self.mem[page][:offset_in_begin_page] + \
            data[:begin_sz] + \
            self.mem[page][(offset_in_begin_page + begin_sz):]
        sz -= begin_sz
        data = data[begin_sz:]

        # n middle pages
        pages_written = 1
        while sz > self.page_size:
            page = self.get_nth_page_addr(addr, pages_written)
            self.mem[page] = data[:self.page_size]
            pages_written += 1
            sz -= self.page_size
            data = data[self.page_size:]

        # last page
        if sz > 0:
            page = self.get_nth_page_addr(addr, pages_written)
            if page not in self.mem:
                self.mem[page] = b'\x00'*self.page_size
            self.mem[page] = data[:sz] + self.mem[page][sz:]


def reset():
    global regfile, memory
    regfile = Regfile()
    regfile.set("sp", 0xffffffff) # stack pointer reset to the highest address
    memory = Memory()  # OldMemory()


# RV32I Base Instruction Set


class Ops(Enum):
    LUI = 0b0110111    # load upper immediate
    LOAD = 0b0000011
    STORE = 0b0100011

    AUIPC = 0b0010111  # add upper immediate to pc
    BRANCH = 0b1100011
    JAL = 0b1101111
    JALR = 0b1100111

    IMM = 0b0010011
    OP = 0b0110011

    MISC = 0b0001111
    SYSTEM = 0b1110011


class Funct3(Enum):
    ADD = SUB = ADDI = 0b000
    SLLI = 0b001
    SLT = SLTI = 0b010
    SLTU = SLTIU = 0b011

    XOR = XORI = 0b100
    SRL = SRLI = SRA = SRAI = 0b101
    OR = ORI = 0b110
    AND = ANDI = 0b111

    BEQ = 0b000
    BNE = 0b001
    BLT = 0b100
    BGE = 0b101
    BLTU = 0b110
    BGEU = 0b111

    LB = SB = 0b000
    LH = SH = 0b001
    LW = SW = 0b010
    LBU = 0b100
    LHU = 0b101

    # stupid instructions below this line
    ECALL = 0b000
    CSRRW = 0b001
    CSRRS = 0b010
    CSRRC = 0b011
    CSRRWI = 0b101
    CSRRSI = 0b110
    CSRRCI = 0b111


class Syscall(Enum):
    SYS_getcwd = 17
    SYS_dup = 23
    SYS_fcntl = 25
    SYS_faccessat = 48
    SYS_chdir = 49
    SYS_openat = 56
    SYS_close = 57
    SYS_getdents = 61
    SYS_lseek = 62
    SYS_read = 63
    SYS_write = 64
    SYS_writev = 66
    SYS_pread = 67
    SYS_pwrite = 68
    SYS_fstatat = 79
    SYS_fstat = 80
    SYS_exit = 93
    SYS_exit_group = 94
    SYS_kill = 129
    SYS_rt_sigaction = 134
    SYS_times = 153
    SYS_uname = 160
    SYS_gettimeofday = 169
    SYS_getpid = 172
    SYS_getuid = 174
    SYS_geteuid = 175
    SYS_getgid = 176
    SYS_getegid = 177
    SYS_brk = 214 # or should this be sbrk? or should sbrk be its own syscall?
    SYS_munmap = 215
    SYS_mremap = 216
    SYS_mmap = 222
    SYS_open = 1024
    SYS_link = 1025
    SYS_unlink = 1026
    SYS_mkdir = 1030
    SYS_access = 1033
    SYS_stat = 1038
    SYS_lstat = 1039
    SYS_time = 1062
    SYS_getmainvars = 2011
    SYS_isatty = -1
    SYS_init = 0xbeef0 # init
    SYS_draw = 0xbeef1 # draw


def syscall(s, a0=0, a1=0, a2=0, a3=0, a4=0, a5=0):
    # args are passed a0 through a5
    # syscall number is passed in a7
    ret = 0
    if s == Syscall.SYS_close:
        print(rvem, "ecall close")
    elif s == Syscall.SYS_open:
        print(rvem, "ecall open")
    elif s == Syscall.SYS_fstat:
        print(rvem, "ecall fstat")
    elif s == Syscall.SYS_isatty:
        raise Exception(
            "What is the system call isatty from puts.c in newlib? It didnt seem to be called but here we are. I added SYS_isatty = -1 just so it can be caught here")
    elif s == Syscall.SYS_lseek:
        print(rvem, "ecall lseek")
    elif s == Syscall.SYS_read:
        print(rvem, "ecall read")
    elif s == Syscall.SYS_brk:
        set_to = a0
        #print("  ecall brk:\n    a0: %d" % (set_to))
        ret = memory.set_brk(set_to)
    elif s == Syscall.SYS_write:
        handle = a0
        buffer = a1
        count = a2
        #print("  ecall write:\n    handle: %d\n    buffer: 0x%x\n    count: %d" % (handle, buffer, count))
        buffer = memory.read(buffer, count)
        print(buffer.decode(), end="")
        ret = count
    elif s == Syscall.SYS_mkdir:
        #path = memory.read()
        print(rvem, "ecall mkdir")
    elif s == Syscall.SYS_init:
        print(rvem, "ecall init")
    elif s == Syscall.SYS_draw:
        print(rvem, "ecall draw")
    elif s == Syscall.SYS_exit:
        print(rvem, "ecall exit")
        sys.exit()
    else:
        raise Exception("Unimplemented system call %d" % s.value)
    return ret  # return value goes into a0


def ws(addr, dat):
    global memory
    if addr < 0:
        print("Error...dumping")
        dump()
        raise Exception("PC: 0x%x write out of bounds 0x%x" % (regfile[PC], addr))
    memory.write(addr, dat)


def r32(addr):
    if addr < 0:
        print("Error...dumping")
        dump()
        raise Exception("PC: 0x%x read out of bounds 0x%x" % (regfile[PC], addr))
    return struct.unpack("<I", memory.read(addr, 4))[0]


def dump():
    pp = []
    for i in range(33):
        if i != 0 and i % 8 == 0:
            pp += "\n"
        pp += " %3s: %08x" % (regnames[i], regfile[i])
    print(''.join(pp))


def sign_extend(x, l):
    if x >> (l-1) == 1:
        return -((1 << l) - x)
    else:
        return x


def arith(funct3, x, y, alt):
    if funct3 == Funct3.ADDI:
        if alt:
            return x-y
        else:
            return x+y
    elif funct3 == Funct3.SLLI:
        return x << (y & 0x1f)
    elif funct3 == Funct3.SRLI:
        if alt:
            # this is srai
            sb = x >> 31
            out = x >> (y & 0x1f)
            out |= (0xFFFFFFFF * sb) << (32-(y & 0x1f))
            return out
        else:
            return x >> (y & 0x1f)
    elif funct3 == Funct3.ORI:
        return x | y
    elif funct3 == Funct3.XORI:
        return x ^ y
    elif funct3 == Funct3.ANDI:
        return x & y
    elif funct3 == Funct3.SLT:
        return int(sign_extend(x, 32) < sign_extend(y, 32))
    elif funct3 == Funct3.SLTU:
        return int(x & 0xFFFFFFFF < y & 0xFFFFFFFF)
    else:
        dump()
        raise Exception("write arith funct3 %r" % funct3)


def cond(funct3, vs1, vs2):
    ret = False
    if funct3 == Funct3.BEQ:
        ret = vs1 == vs2
    elif funct3 == Funct3.BNE:
        ret = vs1 != vs2
    elif funct3 == Funct3.BLT:
        ret = sign_extend(vs1, 32) < sign_extend(vs2, 32)
    elif funct3 == Funct3.BGE:
        ret = sign_extend(vs1, 32) >= sign_extend(vs2, 32)
    elif funct3 == Funct3.BLTU:
        ret = vs1 < vs2
    elif funct3 == Funct3.BGEU:
        ret = vs1 >= vs2
    else:
        dump()
        raise Exception("write funct3 %r" % (funct3))
    return ret


def step():
    # *** Instruction Fetch ***
    ins = r32(regfile[PC])

    # *** Instruction decode and register fetch ***
    def gibi(s, e):
        return (ins >> e) & ((1 << (s-e+1))-1)
    opcode = Ops(gibi(6, 0))
    funct3 = Funct3(gibi(14, 12))
    funct7 = gibi(31, 25)
    imm_i = sign_extend(gibi(31, 20), 12)
    imm_s = sign_extend(gibi(31, 25) << 5 | gibi(11, 7), 12)
    imm_b = sign_extend((gibi(32, 31) << 12) | (gibi(30, 25) << 5) | (
        gibi(11, 8) << 1) | (gibi(8, 7) << 11), 13)
    imm_u = sign_extend(gibi(31, 12) << 12, 32)
    imm_j = sign_extend((gibi(32, 31) << 20) | (gibi(30, 21) << 1) | (
        gibi(21, 20) << 11) | (gibi(19, 12) << 12), 21)

    # register write set up
    rd = gibi(11, 7)

    # register reads
    vs1 = regfile[gibi(19, 15)]
    vs2 = regfile[gibi(24, 20)]
    vpc = regfile[PC]

    # *** Execute ***
    reg_writeback = opcode in [Ops.JAL, Ops.JALR,
                               Ops.AUIPC, Ops.LUI, Ops.OP, Ops.IMM, Ops.LOAD]
    do_load = opcode == Ops.LOAD
    do_store = opcode == Ops.STORE

    alt = (funct7 == 0b0100000) and (opcode == Ops.OP or (
        opcode == Ops.IMM and funct3 == Funct3.SRAI))
    imm = {Ops.JAL: imm_j, Ops.JALR: imm_i, Ops.BRANCH: imm_b, Ops.AUIPC: imm_u,
           Ops.LUI: imm_u, Ops.OP: vs2, Ops.IMM: imm_i, Ops.LOAD: imm_i, Ops.STORE: imm_s,
           Ops.SYSTEM: imm_i, Ops.MISC: imm_i}[opcode]
    arith_left = vpc if opcode in [Ops.JAL, Ops.BRANCH, Ops.AUIPC] else (
        0 if opcode == Ops.LUI else vs1)
    arith_func = funct3 if opcode in [Ops.OP, Ops.IMM] else Funct3.ADD
    pend_is_new_pc = opcode in [Ops.JAL, Ops.JALR] or (
        opcode == Ops.BRANCH and cond(funct3, vs1, vs2))
    pend = arith(arith_func, arith_left, imm, alt)

    if opcode == Ops.SYSTEM:
        sys_imm = gibi(31, 20)
        if sys_imm == 0:
            syscall_num = regfile.get("a7")
            ret = syscall(Syscall(syscall_num), regfile.get("a0"), regfile.get(
                "a1"), regfile.get("a2"), regfile.get("a3"), regfile.get("a4"), regfile.get("a5"))
            regfile.set("a0", ret)
        elif sys_imm == 1:
            # wait for user input for ebreak
            input("  ebreak")

    # *** Memory access ***
    if do_load:
        if funct3 == Funct3.LB:
            pend = sign_extend(r32(pend) & 0xFF, 8)
        elif funct3 == Funct3.LH:
            pend = sign_extend(r32(pend) & 0xFFFF, 16)
        elif funct3 == Funct3.LW:
            pend = r32(pend)
        elif funct3 == Funct3.LBU:
            pend = r32(pend) & 0xFF
        elif funct3 == Funct3.LHU:
            pend = r32(pend) & 0xFFFF
    elif do_store:
        if funct3 == Funct3.SB:
            ws(pend, struct.pack("B", vs2 & 0xFF))
        elif funct3 == Funct3.SH:
            ws(pend, struct.pack("H", vs2 & 0xFFFF))
        elif funct3 == Funct3.SW:
            ws(pend, struct.pack("I", vs2))

    # *** Register write back ***
    if pend_is_new_pc:
        if reg_writeback:
            regfile[rd] = vpc + 4
        regfile[PC] = pend
    else:
        if reg_writeback:
            regfile[rd] = pend
        regfile[PC] = vpc + 4
    return True


if __name__ == "__main__":
    with open(args.binary, 'rb') as f:
        reset()
        e = ELFFile(f)
        for s in e.iter_segments():
            ws(s.header.p_paddr, s.data())
            if s.header.p_flags == 6:
                # if flags RW were set (out of RWE with R=4, W=2, E=1?) in this segment, it's the segment with the data section
                # find the heap address and set it to the break address (fancy name for "end of segment with the data section")
                original_break_addr = s.header.p_offset + s.header.p_memsz
                memory.break_addr = original_break_addr
                print(rvem, "Heap start is 0x%x" % original_break_addr)

        print(rvem, "Entry point is", hex(e.header.e_entry))
        regfile[PC] = e.header.e_entry
        INSCOUNT = 0
        hit_bp = False
        needs_break = False
        while step():
            if hit_bp or needs_break: # regfile[PC] == 0x20110 or 
                hit_bp = True
                print(rvem, "Breakpoint")
                dump()
                input()
            INSCOUNT += 1
            if INSCOUNT % 100000 == 0:
                print(rvem, "Ran %d instructions" % INSCOUNT)
        print(rvem, "  ran %d instructions" % INSCOUNT)
