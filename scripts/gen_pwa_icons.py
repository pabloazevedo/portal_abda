"""Gera ícones PNG do PWA (stdlib, sem Pillow), incluindo variante maskable."""
from __future__ import annotations

import struct
import zlib
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "static" / "pwa" / "icons"
NAVY = (0x1A, 0x36, 0x5C)
GOLD = (0xC4, 0xA3, 0x5A)


def _chunk(tag: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)


def write_png(path: Path, size: int, pixels: list[tuple[int, int, int]]) -> None:
    raw = bytearray()
    for y in range(size):
        raw.append(0)
        for x in range(size):
            r, g, b = pixels[y * size + x]
            raw.extend((r, g, b))
    ihdr = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    data = (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + _chunk(b"IEND", b"")
    )
    path.write_bytes(data)


def rounded_rect_mask(size: int, pad: int, radius: int) -> list[bool]:
    left = pad
    top = pad
    right = size - pad - 1
    bottom = size - pad - 1
    mask = [False] * (size * size)
    for y in range(size):
        for x in range(size):
            if x < left or x > right or y < top or y > bottom:
                continue
            corners = (
                (left + radius, top + radius, x <= left + radius and y <= top + radius),
                (right - radius, top + radius, x >= right - radius and y <= top + radius),
                (left + radius, bottom - radius, x <= left + radius and y >= bottom - radius),
                (right - radius, bottom - radius, x >= right - radius and y >= bottom - radius),
            )
            inside = True
            for cx, cy, in_corner in corners:
                if in_corner and (x - cx) ** 2 + (y - cy) ** 2 > radius**2:
                    inside = False
                    break
            mask[y * size + x] = inside
    return mask


def badge_pixels(size: int, pad: int = 0) -> list[tuple[int, int, int]]:
    radius = max(8, (size - 2 * pad) // 8)
    mask = rounded_rect_mask(size, pad + size // 10, radius)
    return [GOLD if mask[i] else NAVY for i in range(size * size)]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for size in (192, 512):
        write_png(OUT / f"icon-{size}.png", size, badge_pixels(size, 0))
    write_png(OUT / "icon-512-maskable.png", 512, badge_pixels(512, int(512 * 0.1)))
    print("wrote", sorted(p.name for p in OUT.iterdir()))


if __name__ == "__main__":
    main()
