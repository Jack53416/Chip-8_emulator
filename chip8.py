import os
import struct

from typing import List, Generator, Dict, Callable


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

        self._delayTimer: int = 0
        self._soundTimer: int = 0

        self._stack: List[int] = [0] * 16
        self._stackPtr: int = 0

        self._memory: bytearray = bytearray(Chip8.MEM_SIZE)
        self._registers: List[bytes] = [bytes(Chip8.REG_SIZE)] * Chip8.REG_NUM
        self._decoder: Dict[int, Callable[[int], None]] = {}

        self._init()

    def _init(self):
        self._memory[0:0x50] = Chip8.FONT_SET

        self._decoder = {
            0x00e0: self.clear_scr,
            0x00ee: self.ret_from_sub,

            0x1: self.jump,                 # 1nnn
            0x2: self.jsr,                  # 2nnn
            0x3: self.skip_equal,           # 3xkk
            0x4: self.skip_nequal,          # 4xkk
            0x5: self.skip_reg_equal,       # 5xy0
            0x6: self.mov,                  # 6xkk
            0x7: self.add_constant,         # 7xkk

            0x8: self._decode_arithmetic,

            0x80: self.mov_reg,             # 0x8xy0
            0x81: self.logic_or,            # 0x8xy1
            0x82: self.logic_and,           # 0x8xy2
            0x83: self.logic_xor,           # 0x8xy3
            0x84: self.add,                 # 0x8xy4
            0x85: self.sub,                 # 0x8xy5
            0x86: self.shift_right,         # 0x8xy6
            0x87: self.rsb,                 # 0x8xy7
            0x8e: self.shift_left,          # 0x8xyE

            0x9: self.skip_on_reg_neq,      # 0x9xy0
            0xa: self.mvi,                  # 0xAnnn
            0xb: self.jump_i,               # 0xBnnn
            0xc: self.rand,                 # 0xCxkk
            0xd: self.draw_sprite,          # 0xDxyn

            0xE: self._decode_keys,

            0xE9e: self.skip_if_pressed,    # 0xEx9E
            0xEa1: self.skip_if_npressed,   # 0xExA1

            0xf: self._decode_system,

            0xf07: self.get_delay_timer,    # 0xFx07
            0xf0a: self.await_key,          # 0xFx0A
            0xf15: self.set_delay_timer,    # 0xFx15
            0xf18: self.set_sound_timer,    # 0xFx18
            0xf1e: self.add_index,          # 0xFx1E
            0xf29: self.font,               # 0xFx29
            0xf33: self.store_bcd,          # 0xFx33
            0xf55: self.store_regs,         # 0xFx55
            0xf65: self.load_regs,          # 0xFx65
        }

    @property
    def memory_dump(self) -> Generator[str, None, None]:
        unpacked = struct.unpack(">{}H".format(Chip8.MEM_SIZE // 2), self._memory)
        mem_view = ("{:04x} --- {:04x}".format(idx * 2, val) for idx, val in enumerate(unpacked))
        return mem_view

    @property
    def register_dump(self) -> Generator[str, None, None]:
        return ("V{} --- {:02x}".format(idx, int.from_bytes(val, byteorder='big'))
                for idx, val in enumerate(self._registers))

    def load_rom(self, file_name: str):
        with open(file_name, "rb") as f:
            rom = f.read()
            self._memory[0x200:0x200 + len(rom)] = rom

    def emulate_cycle(self):
        pass

    def _fetch(self):
        pass

    def _decode(self):
        pass

    def _decode_arithmetic(self, params: bytes):
        x: int = params[0] & 0x0F
        y: int = params[1] & 0xF0

        code = 0x8 << 4 | (params[1] & 0x0F)

        return self._decoder[code](x, y)

    def _decode_keys(self, params: bytes):
        code = 0xE << 4 | params[1]
        x = params[0] & 0x0F

        return self._decoder[code](x)

    def _decode_system(self, params: bytes):
        code = 0xF << 4 | params[1]
        x = params[0] & 0x0F

        return self._decoder[code](x)

    def clear_scr(self, params: bytes):
        """00E0 Clear the screen"""
        pass

    def ret_from_sub(self, params: bytes):
        """00EE return from subroutine call"""
        pass

    def jump(self, params: bytes):
        """1xxx jum to address xxx"""
        pass

    def jsr(self, params: bytes):
        """2xxx jump to subroutine at address xxx """
        pass

    def skip_equal(self, params: bytes):
        """3rxx skip if register r = constant xx """
        pass

    def skip_nequal(self, params: bytes):
        """4rxx Skip if register r != constant xx"""
        pass

    def skip_reg_equal(self, params: bytes):
        """5ry0 Skip if register r = register y"""
        pass

    def mov(self, params: bytes):
        """6rxxx move constant xxx to register r"""
        pass

    def add_constant(self, params: bytes):
        """7rxx add constant to register r, No carry generated"""
        pass

    def mov_reg(self, params: bytes):
        """8ry0 move register vy into vr"""
        pass

    def logic_or(self, params: bytes):
        """8ry1 OR register vy into register vx"""
        pass

    def logic_and(self, params: bytes):
        """8ry2 AND register vy into register vx"""
        pass

    def logic_xor(self, params: bytes):
        """8ry3 XOR register ry into register rx"""

    def add(self, params: bytes):
        """8ry4 add register vy to vr,carry in vf """
        pass

    def sub(self, params: bytes):
        """8ry5 subtract register vy from vr,borrow in vf, 	vf set to 1 if borrows"""
        pass

    def shift_right(self, params: bytes):
        """8r06 shift register vy right, bit 0 goes into register vf"""
        pass

    def rsb(self, params: bytes):
        """8ry7 subtract register vr from register vy, result in vr, 	vf set to 1 if borrows"""
        pass

    def shift_left(self, params: bytes):
        """8r0e	shift register vr left, bit 7 goes into register vf"""
        pass

    def skip_on_reg_neq(self, params: bytes):
        """9ry0 skip if register rx != register ry"""
        pass

    def mvi(self, params: bytes):
        """axxx Load index register with constant xxx"""
        pass

    def jump_i(self, params: bytes):
        """bxxx Jump to address xxx+register v0"""
        pass

    def rand(self, params: bytes):
        """crxx vr = random number less than or equal to xxx"""
        pass

    def draw_sprite(self, params: bytes):
        """drys Draw sprite at screen location rx,ry height s"""
        pass

    def skip_if_pressed(self, params: bytes):
        """ek9e skip if key (register rk) pressed"""
        pass

    def skip_if_npressed(self, params: bytes):
        """eka1 skip if key (register rk) not pressed"""
        pass

    def get_delay_timer(self, params: bytes):
        """fr07 get delay timer into vr"""
        pass

    def await_key(self, params: bytes):
        """fr0a wait for for keypress,put key in register vr"""
        pass

    def set_delay_timer(self, params: bytes):
        """set the delay timer to vr"""
        pass

    def set_sound_timer(self, params: bytes):
        """fr18 set the sound timer to vr"""
        pass

    def add_index(self, params: bytes):
        """fr1e add register vr to the index register"""
        pass

    def font(self, params: bytes):
        """fr29 point I to the sprite for hexadecimal character in vr"""
        pass

    def store_bcd(self, params: bytes):
        """fr33 store the bcd representation of register vr at location I,I+1,I+2"""
        pass

    def store_regs(self, params: bytes):
        """fr55 store registers v0-vr at location I onwards"""
        pass

    def load_regs(self, params: bytes):
        """fx65 load registers v0-vr from location I onwards"""
        pass


if __name__ == "__main__":
    emulator = Chip8()

    rom_list = [os.path.join(r, f[0]) for r, d, f in os.walk("./roms")]
    emulator.load_rom(rom_list[0])

    for val in emulator.memory_dump:
        print(val)

    print("--------------------\nRegisters: ")
    for val in emulator.register_dump:
        print(val)

    print(hex(emulator._memory[0x200]))