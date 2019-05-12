from typing import List


class RegisterManager(object):

    def __init__(self, reg_count: int, reg_bits: int):
        self._reg_bit_count: int = reg_bits
        self._data: List[int] = [0] * reg_count
        self._overflow: bool = False

    def __getitem__(self, item: int):
        return self._data[item]

    def __setitem__(self, key: int, value):
        self._data[key] = self.register(value, self._reg_bit_count)

    def __iter__(self):
        for elem in self._data:
            yield elem

    def register(self, value: int, reg_bit_count: int):
        base = 1 << reg_bit_count
        if value > base - 1 or value < 0:
            self._overflow = True
        else:
            self._overflow = False
        value %= base
        return value

    @property
    def overflow(self) -> bool:
        return self._overflow


if __name__ == '__main__':
    regMan = RegisterManager(16, 8)

    regMan[0] = 0xFFF
    regMan[0] += 1
    regMan[0] = 55
    regMan[1] -= 2
    regMan[3] = 10
