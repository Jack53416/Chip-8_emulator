import os
import struct
import random
import time
from functools import partial

from typing import List, Generator, Dict, Callable

from display import Display
from registerManager import RegisterManager
from hwTimer import  HwTimer


def print_cb_name(fun):

    def wrapper(*args):
        print(args[1].__name__, end=" ")
        return fun(*args)
    return wrapper


class Chip8(object):
    MEM_SIZE = 4096
    ROM_START = 0x200
    RAM_SIZE = MEM_SIZE - ROM_START  # bytes
    INSTRUCTION_SIZE = 2  # bytes
    REG_NUM = 16
    REG_SIZE = 1  # bytes

    FONT_SET = [
        0xF0, 0x90, 0x90, 0x90, 0xF0,  # 0
        0x20, 0x60, 0x20, 0x20, 0x70,  # 1
        0xF0, 0x10, 0xF0, 0x80, 0xF0,  # 2
        0xF0, 0x10, 0xF0, 0x10, 0xF0,  # 3
        0x90, 0x90, 0xF0, 0x10, 0x10,  # 4
        0xF0, 0x80, 0xF0, 0x10, 0xF0,  # 5
        0xF0, 0x80, 0xF0, 0x90, 0xF0,  # 6
        0xF0, 0x10, 0x20, 0x40, 0x40,  # 7
        0xF0, 0x90, 0xF0, 0x90, 0xF0,  # 8
        0xF0, 0x90, 0xF0, 0x10, 0xF0,  # 9
        0xF0, 0x90, 0xF0, 0x90, 0x90,  # A
        0xE0, 0x90, 0xE0, 0x90, 0xE0,  # B
        0xF0, 0x80, 0x80, 0x80, 0xF0,  # C
        0xE0, 0x90, 0x90, 0x90, 0xE0,  # D
        0xF0, 0x80, 0xF0, 0x80, 0xF0,  # E
        0xF0, 0x80, 0xF0, 0x80, 0x80  # F
    ]

    def __init__(self):
        self._opCode: bytes = bytes(2)
        self._pc: int = 0x200
        self._index: int = 0

        self._delayTimer: HwTimer = HwTimer()
        self._soundTimer: HwTimer = HwTimer()

        self._stack: List[int] = [0] * 16
        self._stackPtr: int = 0

        self._memory: bytearray = bytearray(Chip8.MEM_SIZE)
        self._registers: RegisterManager = RegisterManager(self.REG_NUM, self.REG_SIZE * 8)
        self._decoder: Dict[int, Callable[[int], None]] = {}

        self._display = Display(64, 32)
        self._init()

    def _init(self):
        self._memory[0:0x50] = Chip8.FONT_SET

        self._decoder = {
            0x0: lambda: self._decoder[self._opCode[1]](),
            0x00e0: self.clear_scr,
            0x00ee: self.ret_from_sub,

            0x1: partial(self._decode_address, self.jump),                # 0x1nnn
            0x2: partial(self._decode_address, self.jsr),                 # 0x2nnn
            0x3: partial(self._decode_reg_const, self.skip_equal),        # 0x3xkk
            0x4: partial(self._decode_reg_const, self.skip_nequal),       # 0x4xkk
            0x5: partial(self._decode_two_regs, self.skip_reg_equal),     # 0x5xy0
            0x6: partial(self._decode_reg_const, self.mov),               # 0x6xkk
            0x7: partial(self._decode_reg_const, self.add_constant),      # 0x7xkk

            0x8: self._decode_arithmetic,

            0x80: self.mov_reg,                                           # 0x8xy0
            0x81: self.logic_or,                                          # 0x8xy1
            0x82: self.logic_and,                                         # 0x8xy2
            0x83: self.logic_xor,                                         # 0x8xy3
            0x84: self.add,                                               # 0x8xy4
            0x85: self.sub,                                               # 0x8xy5
            0x86: self.shift_right,                                       # 0x8xy6
            0x87: self.rsb,                                               # 0x8xy7
            0x8e: self.shift_left,                                        # 0x8xyE

            0x9: partial(self._decode_two_regs, self.skip_on_reg_neq),    # 0x9xy0
            0xa: partial(self._decode_address, self.mvi),                 # 0xAnnn
            0xb: partial(self._decode_address, self.jump_i),              # 0xBnnn
            0xc: partial(self._decode_reg_const, self.rand),              # 0xCxkk
            0xd: self._decode_draw,                                       # 0xDxyn

            0xE: self._decode_keys,

            0xE9e: self.skip_if_pressed,                                  # 0xEx9E
            0xEa1: self.skip_if_npressed,                                 # 0xExA1

            0xf: self._decode_system,

            0xf07: self.get_delay_timer,                                  # 0xFx07
            0xf0a: self.await_key,                                        # 0xFx0A
            0xf15: self.set_delay_timer,                                  # 0xFx15
            0xf18: self.set_sound_timer,                                  # 0xFx18
            0xf1e: self.add_index,                                        # 0xFx1E
            0xf29: self.font,                                             # 0xFx29
            0xf33: self.store_bcd,                                        # 0xFx33
            0xf55: self.store_regs,                                       # 0xFx55
            0xf65: self.load_regs,                                        # 0xFx65
        }

    @property
    def memory_dump(self) -> Generator[str, None, None]:
        unpacked = struct.unpack(">{}H".format(Chip8.MEM_SIZE // 2), self._memory)
        mem_view = ("{:04x} --- {:04x}".format(idx * 2, val) for idx, val in enumerate(unpacked))
        return mem_view

    @property
    def register_dump(self) -> Generator[str, None, None]:
        return ("V{} --- {:02x}".format(idx, val)
                for idx, val in enumerate(self._registers))

    def load_rom(self, file_name: str):
        with open(file_name, "rb") as f:
            rom = f.read()
            self._memory[0x200:0x200 + len(rom)] = rom

    def emulate_cycle(self):
        self._fetch()
        print(self._opCode.hex())
        self._decode()

    def _fetch(self):
        self._opCode = bytes(self._memory[self._pc: self._pc + self.INSTRUCTION_SIZE])
        self._pc += self.INSTRUCTION_SIZE

    def _decode(self):
        code = self._opCode[0] >> 4
        try:
            self._decoder[code]()
        except KeyError:
            # invalid instruction
            print("Invalid op-code: {}!!".format(self._opCode.hex()))
        except TypeError:
            # invalid nr of arguments
            print("Invalid op-code parameters!")

    @print_cb_name
    def _decode_two_regs(self, instruction: Callable[[int, int], None]):
        reg_x = self._opCode[0] & 0x0F
        reg_y = self._opCode[1] >> 4

        print("{:x},  {:x}".format(reg_x, reg_y))
        instruction(reg_x, reg_y)

    @print_cb_name
    def _decode_reg_const(self, instruction: Callable[[int, int], None]):
        reg = self._opCode[0] & 0x0F
        const = self._opCode[1]

        print("{:x},  {:x}".format(reg, const))
        instruction(reg, const)

    @print_cb_name
    def _decode_address(self, instruction: Callable[[int], None]):

        address = ((self._opCode[0] & 0x0F) << 8) | self._opCode[1]

        print("{:x}".format(address))
        instruction(address)

    def _decode_draw(self):
        x = self._opCode[0] & 0x0F
        y = (self._opCode[1] & 0xF0) >> 4
        n_bytes = self._opCode[1] & 0x0F

        self.draw_sprite(x, y, n_bytes)

    def _decode_arithmetic(self):

        code = 0x8 << 4 | (self._opCode[1] & 0x0F)

        return self._decode_two_regs(self._decoder[code])

    def _decode_keys(self):
        code = 0xE << 8 | self._opCode[1]
        x = self._opCode[0] & 0x0F

        return self._decoder[code](x)

    def _decode_system(self):
        code = 0xF << 8 | self._opCode[1]
        x = self._opCode[0] & 0x0F

        return self._decoder[code](x)

    def clear_scr(self):
        """00E0 Clear the screen"""
        self._display.clear()

    def ret_from_sub(self):
        """00EE return from subroutine call"""

        self._pc = self._stack.pop()
        self._stackPtr = self._stackPtr - 1

    def jump(self, address: int):
        """1xxx jump to address xxx"""

        self._pc = address

    def jsr(self, address: int):
        """2xxx jump to subroutine at address xxx """

        self._stackPtr = self._stackPtr + 1
        self._stack.append(self._pc)
        self._pc = address

    def skip_equal(self, reg: int, value: int):
        """3rxx skip if register r = constant xx """

        if self._registers[reg] == value:
            self._pc = self._pc + 2

    def skip_nequal(self, reg: int, value: int):
        """4rxx Skip if register r != constant xx"""

        if self._registers[reg] != value:
            self._pc = self._pc + 2

    def skip_reg_equal(self, r1: int, r2: int):
        """5ry0 Skip if register r = register y"""

        if self._registers[r1] == self._registers[r2]:
            self._pc = self._pc + 2

    def mov(self, reg: int, const: int):
        """6rxx move constant xxx to register r"""
        # Error Handling !!

        self._registers[reg] = const

    def add_constant(self, reg: int, const: int):
        """7rxx add constant to register r, No carry generated"""

        self._registers[reg] += const

    def mov_reg(self, reg_x: int, reg_y: int):
        """8xy0 move register vy into vx"""
        
        self._registers[reg_x] = self._registers[reg_y]

    def logic_or(self, reg_x: int, reg_y: int):
        """8xy1 OR register vy into register vx"""
        
        self._registers[reg_x] |= self._registers[reg_y]

    def logic_and(self, reg_x: int, reg_y: int):
        """8xy2 AND register vy into register vx"""
        
        self._registers[reg_x] &= self._registers[reg_y]

    def logic_xor(self, reg_x: int, reg_y: int):
        """8xy3 XOR register ry into register rx"""
        
        self._registers[reg_x] ^= self._registers[reg_y]

    def add(self, reg_x: int, reg_y: int):
        """8ry4 add register vy to vr,carry in vf """
        
        self._registers[reg_x] += self._registers[reg_y]
        if self._registers.overflow:
            self._registers[0xF] = 1

    def sub(self, reg_x: int, reg_y: int):
        """8ry5 subtract register vy from vr,borrow in vf, 	vf set to 1 if borrows"""
        
        self._registers[reg_x] -= self._registers[reg_y]
        if self._registers.overflow:
            self._registers[0xF] = 1

    def shift_right(self, reg_x: int, reg_y: int):
        """8r06 shift register vy right, bit 0 goes into register vf"""

        self._registers[0xF] = self._registers[reg_x] & 0x01
        self._registers[reg_x] >>= 1

    def rsb(self, reg_x: int, reg_y: int):
        """8ry7 subtract register vr from register vy, result in vr, vf set to 1 if borrows"""

        self._registers[reg_x] = self._registers[reg_y] - self._registers[reg_x]
        if self._registers.overflow:
            self._registers[0xF] = 1

    def shift_left(self, reg_x: int, reg_y: int):
        """8r0e	shift register vr left, bit 7 goes into register vf"""

        self._registers[0xF] = self._registers[reg_x] & 0x80
        self._registers[reg_x] <<= 1

    def skip_on_reg_neq(self, reg_x: int, reg_y: int):
        """9ry0 skip if register rx != register ry"""

        if self._registers[reg_x] != self._registers[reg_y]:
            self._pc += self.INSTRUCTION_SIZE

    def mvi(self, value: int):
        """axxx Load index register with constant xxx"""

        # What about overflow ?
        self._index = value

    def jump_i(self, address: int):
        """bxxx Jump to address xxx+register v0"""

        self._pc = address + self._registers[0]

    def rand(self, reg: int, const: int):
        """crxx vr = random number less than or equal to xxx"""

        self._registers[reg] = random.randint(0, const)

    def draw_sprite(self, reg_x: int, reg_y: int, n_bytes: int):
        """drys Draw sprite at screen location rx,ry height s"""
        sprite = self._memory[self._index: self._index + n_bytes]
        x, y = self._registers[reg_x], self._registers[reg_y]
        self._display.draw(x, y, sprite)
        if self._display.collision:
            self._registers[0xF] = 0x01
        print(self._display)

    def skip_if_pressed(self, params: bytes):
        """ek9e skip if key (register rk) pressed"""
        print("skip if pressed")
        pass

    def skip_if_npressed(self, params: bytes):
        """eka1 skip if key (register rk) not pressed"""
        print("skip if not pressed")
        pass

    def get_delay_timer(self, reg: int):
        """fr07 get delay timer into vr"""
        time.sleep(0.1)
        self._registers[reg] = self._delayTimer.value

    def await_key(self, params: bytes):
        """fr0a wait for for keypress,put key in register vr"""
        pass

    def set_delay_timer(self, reg: int):
        """set the delay timer to vr"""
        print("{} {}".format("set_delay_timer", reg))
        try:
            self._delayTimer.value = self._registers[reg]
            self._delayTimer.start()
        except RuntimeError:
            self._delayTimer = HwTimer()
            self._delayTimer.value = self._registers[reg]
            self._delayTimer.start()

    def set_sound_timer(self, reg: int):
        """fr18 set the sound timer to vr"""

        try:
            self._soundTimer.value = self._registers[reg]
            self._soundTimer.start()
        except RuntimeError:
            self._soundTimer = HwTimer()
            self._soundTimer.value = self._registers[reg]
            self._soundTimer.start()

    def add_index(self, reg: int):
        """fr1e add register vr to the index register"""

        self._index += self._registers[reg]

    def font(self, reg: int):
        """fr29 point I to the sprite for hexadecimal character in vr"""
        if self._registers[reg] > 0xF:
            raise ValueError("Invalid font!")

        val = self._registers[reg] * 5
        self._index = val

    def store_bcd(self, reg: int):
        """fr33 store the bcd representation of register vr at location I,I+1,I+2"""

        value = self._registers[reg]
        h = value // 100
        t = (value % 100) // 10
        d = value % 100 % 10

        self._memory[self._index] = h
        self._memory[self._index + 1] = t
        self._memory[self._index + 2] = d

    def store_regs(self, reg: int):
        """fr55 store registers v0-vr at location I onwards"""

        for idx, reg_val in enumerate(self._registers[0: reg + 1]):
            self._memory[self._index + idx] = reg_val

    def load_regs(self, reg: int):
        """fx65 load registers v0-vr from location I onwards"""

        for i in range(0, reg + 1):
            self._registers[i] = self._memory[self._index + i]


if __name__ == "__main__":
    emulator = Chip8()

    rom_list = [os.path.join(r, f[0]) for r, d, f in os.walk("./roms")]
    emulator.load_rom(rom_list[0])

    for val in emulator.memory_dump:
        print(val)

    print("--------------------\nRegisters: ")
    for val in emulator.register_dump:
        print(val)

    while True:
        emulator.emulate_cycle()