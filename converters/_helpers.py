"""Byte-level helpers that real game converters often need."""
from __future__ import annotations

import struct
import zlib
import hashlib


def swap32(data: bytes) -> bytes:
    """Reverse the byte order of every 32-bit word (little <-> big endian)."""
    n = len(data) - len(data) % 4
    words = struct.unpack(f"<{n // 4}I", data[:n])
    return struct.pack(f">{n // 4}I", *words) + data[n:]


def swap16(data: bytes) -> bytes:
    n = len(data) - len(data) % 2
    words = struct.unpack(f"<{n // 2}H", data[:n])
    return struct.pack(f">{n // 2}H", *words) + data[n:]


def crc32(data: bytes) -> int:
    return zlib.crc32(data) & 0xFFFFFFFF


def md5(data: bytes) -> bytes:
    return hashlib.md5(data).digest()


def sha1(data: bytes) -> bytes:
    return hashlib.sha1(data).digest()


def put_u32(buf: bytearray, offset: int, value: int, big_endian: bool = False) -> None:
    struct.pack_into(">I" if big_endian else "<I", buf, offset, value)


def get_u32(buf: bytes, offset: int, big_endian: bool = False) -> int:
    return struct.unpack_from(">I" if big_endian else "<I", buf, offset)[0]


def pad_to(data: bytes, size: int, fill: bytes = b"\x00") -> bytes:
    """Pad (or refuse to truncate) data to a fixed size the PS4 version expects."""
    if len(data) > size:
        raise ValueError(f"data is {len(data)} bytes, larger than target {size}")
    return data + fill * (size - len(data))
