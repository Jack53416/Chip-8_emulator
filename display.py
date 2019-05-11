from typing import List, Callable

BYTE_SIZE = 8


class Display(object):
    def __init__(self, width: int, height: int):
        width //= BYTE_SIZE
        self._collision: bool = False
        self._width, self._height = width, height
        self._data = [bytearray(width) for i in range(height)]
        self._onDraw = None

    def draw(self, x: int, y: int, sprite: List[int]):
        idx, r = divmod(x, BYTE_SIZE)

        mask = 0xFF << (BYTE_SIZE - r) & 0xFF if r > 0 else 0x0
        next_idx = (idx + 1) % self._width

        if idx > self._width:
            raise ValueError("Display Error: Invalid x coordinate")
        if y > self._height:
            raise ValueError("Display Error: Invalid y coordinate")

        for sprite_part in sprite:
            disp_val = (self._data[y][idx] << r) | (self._data[y][next_idx] >> (BYTE_SIZE - r))

            disp_val &= sprite_part

            if disp_val != 0:
                self._collision = True
            else:
                self._collision = False

            self._data[y][idx] ^= sprite_part >> r
            self._data[y][next_idx] ^= (sprite_part << (BYTE_SIZE - r)) & 0xFF

            y = (y + 1) % self._height

        if self.on_draw:
            self.on_draw()

    def clear(self):
        self._data = self._data = [bytearray(self._width) for i in range(self._height)]

    @property
    def collision(self):
        return self._collision

    @property
    def width(self):
        return self._width * BYTE_SIZE

    @property
    def height(self):
        return self._height

    @property
    def on_draw(self):
        return self._onDraw

    @on_draw.setter
    def on_draw(self, handler: Callable[[int, int, int], None]):
        self._onDraw = handler

    def __setitem__(self, key, value):
        self._data[key] = value

    def __getitem__(self, item):
        return self._data[item]

    def __str__(self):
        return "".join(["".join(line) for line in self.print()])

    def print(self):
        for line in self._data:
            str_line = []
            for byte in line:
                str_line.append(f"{byte:08b}".replace("0", " ").replace("1", "*"))
            str_line.append("\r\n")
            yield str_line


def test02(disp: Display):
    disp.clear()
    disp.draw(1, 0, [0x80,
                     0x80,
                     0x80])

    disp.draw(63, 0, [0x80,
                      0x80,
                      0x80])
    print(disp)


def test01(disp: Display):
    disp.clear()
    disp.draw(59, 0, [0x3C,
                      0xC3,
                      0xFF])
    print(disp)


if __name__ == "__main__":
    disp = Display(64, 4)
    test01(disp)
    test02(disp)
