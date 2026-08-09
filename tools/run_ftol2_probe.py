#!/usr/bin/env python3
"""Execute the pinned TH06 __ftol2 bytes without redistributing them."""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import random
import shutil
import struct
import subprocess
import tempfile


EXECUTABLE_SHA256 = "9f76483c46256804792399296619c1274363c31cd8f1775fafb55106fb852245"
HELPER_VIRTUAL_ADDRESS = 0x0045BA78
HELPER_SIZE = 0x75
HELPER_SHA256 = "5333b186c02836974c6f792303aeb2c00d856316b93ccbbe65f51def6ae661b4"
TARGET_CONTROL_WORD = 0x027F
X87_TOP_MASK = 0x3800


class ProbeError(RuntimeError):
    """An expected extraction, build, or execution failure."""


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def positive_count(text: str) -> int:
    try:
        value = int(text, 0)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if value < 0:
        raise argparse.ArgumentTypeError("must be non-negative")
    return value


def extract_pe_range(image: bytes, virtual_address: int, size: int) -> bytes:
    """Resolve one PE32 virtual-address range through its section table."""
    if len(image) < 0x40:
        raise ProbeError("input is too short to contain a DOS header")
    pe_offset = struct.unpack_from("<I", image, 0x3C)[0]
    if image[pe_offset : pe_offset + 4] != b"PE\0\0":
        raise ProbeError("input has no PE signature")
    section_count = struct.unpack_from("<H", image, pe_offset + 6)[0]
    optional_size = struct.unpack_from("<H", image, pe_offset + 20)[0]
    optional_offset = pe_offset + 24
    if struct.unpack_from("<H", image, optional_offset)[0] != 0x10B:
        raise ProbeError("input is not PE32")
    image_base = struct.unpack_from("<I", image, optional_offset + 28)[0]
    relative_address = virtual_address - image_base
    section_offset = optional_offset + optional_size

    for index in range(section_count):
        offset = section_offset + index * 40
        virtual_size, section_rva, raw_size, raw_offset = struct.unpack_from(
            "<IIII", image, offset + 8
        )
        extent = max(virtual_size, raw_size)
        if section_rva <= relative_address and relative_address + size <= section_rva + extent:
            file_offset = raw_offset + relative_address - section_rva
            result = image[file_offset : file_offset + size]
            if len(result) != size:
                raise ProbeError("resolved PE range extends past end of file")
            return result
    raise ProbeError(f"virtual address 0x{virtual_address:08x} is outside file-backed sections")


def ext80(sign: int, exponent: int, significand: int) -> bytes:
    return struct.pack("<QH", significand, (sign << 15) | exponent)


def finite_f32_to_ext80(bits: int) -> bytes:
    sign = bits >> 31
    exponent = (bits >> 23) & 0xFF
    fraction = bits & 0x7FFFFF
    if exponent == 0xFF:
        raise ValueError("finite_f32_to_ext80 requires a finite input")
    if exponent == 0:
        if fraction == 0:
            return ext80(sign, 0, 0)
        leading = fraction.bit_length() - 1
        unbiased = leading - 149
        return ext80(sign, unbiased + 16383, fraction << (63 - leading))
    return ext80(sign, exponent - 127 + 16383, ((1 << 23) | fraction) << 40)


def trunc_ext80(value: bytes) -> int:
    """Exact truncation for a canonical finite ext80 value in signed-i64 range."""
    significand, sign_exp = struct.unpack("<QH", value)
    sign = sign_exp >> 15
    exponent = sign_exp & 0x7FFF
    if exponent == 0:
        magnitude = 0
    else:
        unbiased = exponent - 16383
        if unbiased < 0:
            magnitude = 0
        elif unbiased < 63:
            magnitude = significand >> (63 - unbiased)
        else:
            magnitude = significand << (unbiased - 63)
    result = -magnitude if sign else magnitude
    if not -(1 << 63) <= result < (1 << 63):
        raise ValueError("input is outside the signed-i64 range")
    return result


def fixed_inputs() -> list[bytes]:
    values = [
        ext80(0, 0, 0),
        ext80(1, 0, 0),
        ext80(0, 0, 0x7FFFFFFFFFFFF800),
        ext80(1, 0, 0x7FFFFFFFFFFFF800),
        ext80(0, 0x3FFE, 0xFFFFFFFFFFFFF800),
        ext80(1, 0x3FFE, 0xFFFFFFFFFFFFF800),
        ext80(0, 0x3FFF, 0x8000000000000000),
        ext80(1, 0x3FFF, 0x8000000000000000),
        ext80(0, 0x3FFF, 0xC000000000000000),
        ext80(1, 0x3FFF, 0xC000000000000000),
        ext80(0, 0x401D, 0xFFFFFFFE00000000),
        ext80(0, 0x401D, 0xFFFFFFFF00000000),
        ext80(1, 0x401E, 0x8000000000000000),
        ext80(1, 0x403E, 0x8000000000000000),
    ]
    return values


def random_inputs(count: int) -> list[bytes]:
    generator = random.Random(0x5A17C9E3)
    values: list[bytes] = []
    while len(values) < count:
        if generator.randrange(2) == 0:
            bits = generator.getrandbits(32)
            if bits & 0x7F800000 == 0x7F800000:
                continue
            value = finite_f32_to_ext80(bits)
        else:
            sign = generator.randrange(2)
            exponent = generator.randrange(0x0000, 0x403F)
            significand = generator.getrandbits(53) << 11
            if exponent:
                significand |= 1 << 63
            else:
                significand &= (1 << 63) - 1
            value = ext80(sign, exponent, significand)
        try:
            trunc_ext80(value)
        except ValueError:
            continue
        values.append(value)
    return values


def build_harness(root: Path, helper: bytes, temporary: Path) -> Path:
    assembler = shutil.which("as")
    linker = shutil.which("ld")
    if assembler is None or linker is None:
        raise ProbeError("GNU as and ld are required")
    source = root / "arithmetic" / "ftol2_harness.S"
    if not source.is_file():
        raise ProbeError(f"harness source not found: {source}")
    local_source = temporary / source.name
    shutil.copyfile(source, local_source)
    (temporary / "ftol2.bin").write_bytes(helper)
    object_file = temporary / "ftol2_harness.o"
    executable = temporary / "ftol2_harness"
    subprocess.run([assembler, "--32", "-o", object_file.name, local_source.name],
                   cwd=temporary, check=True)
    subprocess.run([linker, "-m", "elf_i386", "-o", executable.name, object_file.name],
                   cwd=temporary, check=True)
    return executable


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path, help="verified Japanese TH06 v1.02h PE")
    parser.add_argument("--cases", type=positive_count, default=1_000_000)
    args = parser.parse_args()

    image = args.executable.read_bytes()
    if sha256(image) != EXECUTABLE_SHA256:
        raise ProbeError("executable SHA-256 does not match the pinned Japanese v1.02h image")
    helper = extract_pe_range(image, HELPER_VIRTUAL_ADDRESS, HELPER_SIZE)
    if sha256(helper) != HELPER_SHA256:
        raise ProbeError("extracted __ftol2 helper SHA-256 does not match the pinned body")

    inputs = fixed_inputs() + random_inputs(args.cases)
    with tempfile.TemporaryDirectory(prefix="zkth06-ftol2-") as directory:
        harness = build_harness(root, helper, Path(directory))
        try:
            completed = subprocess.run(
                [os.fspath(harness)], input=b"".join(inputs),
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
        except OSError as exc:
            raise ProbeError(f"could not execute the freestanding i386 harness: {exc}") from exc
    if completed.returncode != 0:
        raise ProbeError(
            f"freestanding i386 harness exited with {completed.returncode}: "
            f"{completed.stderr.decode(errors='replace').strip()}"
        )
    if len(completed.stdout) != 10 * len(inputs):
        raise ProbeError(
            f"harness returned {len(completed.stdout)} bytes for {len(inputs)} inputs"
        )

    inexact = 0
    for index, value in enumerate(inputs):
        result_bits, status = struct.unpack_from("<QH", completed.stdout, index * 10)
        expected = trunc_ext80(value) & 0xFFFFFFFFFFFFFFFF
        if result_bits != expected or status & X87_TOP_MASK:
            significand, sign_exp = struct.unpack("<QH", value)
            raise ProbeError(
                f"mismatch at case {index}: input={sign_exp:04x}:{significand:016x} "
                f"result={result_bits:016x} expected={expected:016x} status={status:04x}"
            )
        if status & (1 << 5):
            inexact += 1

    print(f"executable SHA-256: {EXECUTABLE_SHA256}")
    print(f"__ftol2 address/size: 0x{HELPER_VIRTUAL_ADDRESS:08x}/{HELPER_SIZE}")
    print(f"__ftol2 body SHA-256: {HELPER_SHA256}")
    print(f"control word: 0x{TARGET_CONTROL_WORD:04x}")
    print(
        f"matched {len(inputs)} in-domain full EDX:EAX results against exact dyadic "
        "truncation; x87 stack returned empty"
    )
    print(f"inexact status observed in {inexact} cases")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ProbeError as error:
        raise SystemExit(f"error: {error}") from error
