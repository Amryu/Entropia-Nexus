"""STPK v2 (String Template Pack) reader.

Reads .stpk binary files containing pre-rendered Scaleform font templates
for OCR matching. Each template contains:
  - text: the string (skill name, rank, or digit string)
  - grid: 4-bit lightness grid (values 0-15)
  - bitmap: 8-bit anti-aliased bitmap (values 0-255)
  - content_w, content_h: actual text bounds
"""

from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path

import numpy as np

# STPK v2 format constants
MAGIC = b"STPK"
VERSION = 2
HEADER_SIZE = 32
DIR_ENTRY_SIZE = 16
FLAG_RIGHT_ALIGN = 0x0100


def _unpack_grid_4bit(data: bytes, grid_w: int, grid_h: int) -> np.ndarray:
    """Unpack 4-bit nibble-packed data into a 2D uint8 grid (values 0-15)."""
    bytes_per_row = math.ceil(grid_w / 2)
    grid = np.zeros((grid_h, grid_w), dtype=np.uint8)

    for r in range(grid_h):
        row_offset = r * bytes_per_row
        for c in range(0, grid_w, 2):
            byte_val = data[row_offset + c // 2]
            grid[r, c] = (byte_val >> 4) & 0x0F
            if c + 1 < grid_w:
                grid[r, c + 1] = byte_val & 0x0F

    return grid


def read_stpk(path: str | Path) -> tuple[dict, list[dict]]:
    """Read a .stpk v2 file.

    Returns:
        (header_dict, list_of_entry_dicts) where each entry has:
        - text: str
        - grid: np.ndarray (grid_h x grid_w, values 0-15)
        - bitmap: np.ndarray (bitmap_h x bitmap_w, values 0-255) or None
        - bitmap_w, bitmap_h: int
        - content_w, content_h: int
    """
    path = Path(path)
    raw = path.read_bytes()

    magic = raw[0:4]
    if magic != MAGIC:
        raise ValueError(f"Bad magic: {magic!r}, expected {MAGIC!r}")

    (
        version,
        num_entries,
        grid_w,
        grid_h,
        font_size,
        bpp_and_flags,
        x_offset_fp,
        y_offset_fp,
        font_name_len,
        string_table_size,
        uncompressed_size,
    ) = struct.unpack_from("<HHHHHHHHIII", raw, 4)

    if version != VERSION:
        raise ValueError(f"Unsupported version {version} (expected {VERSION})")

    bits_per_pixel = bpp_and_flags & 0xFF
    right_align = bool(bpp_and_flags & FLAG_RIGHT_ALIGN)

    # Decompress payload if compressed (uncompressed_size > 0)
    if uncompressed_size > 0:
        payload = zlib.decompress(raw[HEADER_SIZE:])
        if len(payload) != uncompressed_size:
            raise ValueError(
                f"Decompressed size mismatch: {len(payload)} != {uncompressed_size}"
            )
    else:
        payload = raw[HEADER_SIZE:]

    # Prefix header back so offset arithmetic stays the same
    data = raw[:HEADER_SIZE] + payload

    header = {
        "version": version,
        "num_entries": num_entries,
        "grid_w": grid_w,
        "grid_h": grid_h,
        "font_size": font_size,
        "bits_per_pixel": bits_per_pixel,
        "right_align": right_align,
        "x_offset": x_offset_fp / 10000.0,
        "y_offset": y_offset_fp / 10000.0,
    }

    offset = HEADER_SIZE

    # FONT NAME
    font_name = data[offset : offset + font_name_len].decode("utf-8")
    header["font_name"] = font_name
    offset += font_name_len

    # STRING TABLE
    string_table_data = data[offset : offset + string_table_size]
    offset += string_table_size

    # ENTRY DIRECTORY
    dir_entries = []
    for _ in range(num_entries):
        str_off, bw, bh, bmp_off, cw, ch = struct.unpack_from(
            "<IHHIHH", data, offset
        )
        str_len = struct.unpack_from("<H", string_table_data, str_off)[0]
        text = string_table_data[str_off + 2 : str_off + 2 + str_len].decode(
            "utf-8"
        )
        dir_entries.append(
            {
                "text": text,
                "bitmap_w": bw,
                "bitmap_h": bh,
                "bitmap_offset": bmp_off,
                "content_w": cw,
                "content_h": ch,
            }
        )
        offset += DIR_ENTRY_SIZE

    # GRID DATA (4-bit packed)
    bytes_per_row = math.ceil(grid_w / 2)
    grid_size_per_entry = grid_h * bytes_per_row
    grid_section_start = offset
    grids = []
    for i in range(num_entries):
        entry_start = grid_section_start + i * grid_size_per_entry
        entry_data = data[entry_start : entry_start + grid_size_per_entry]
        grid = _unpack_grid_4bit(entry_data, grid_w, grid_h)
        grids.append(grid)
    offset = grid_section_start + num_entries * grid_size_per_entry

    # BITMAP DATA
    bitmap_section_start = offset

    # Assemble entries
    entries = []
    for i, de in enumerate(dir_entries):
        bw, bh = de["bitmap_w"], de["bitmap_h"]
        if bw > 0 and bh > 0:
            bmp_start = bitmap_section_start + de["bitmap_offset"]
            bmp_end = bmp_start + bw * bh
            bitmap = np.frombuffer(
                data[bmp_start:bmp_end], dtype=np.uint8
            ).reshape(bh, bw)
        else:
            bitmap = None

        entries.append(
            {
                "text": de["text"],
                "grid": grids[i],
                "bitmap": bitmap,
                "bitmap_w": bw,
                "bitmap_h": bh,
                "content_w": de["content_w"],
                "content_h": de["content_h"],
            }
        )

    return header, entries
