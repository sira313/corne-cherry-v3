#!/usr/bin/env python3
"""Convert an image to the right-half OLED logo used by the strata mod.

The mod draws a 32x128 portrait canvas and rotates it 90 deg CW into the
128x32 SSD1306 panel. On the right half the logo sits between the LINK text
(portrait y=1..13) and the battery gauge (portrait y=101..127), so the free
region is portrait rows 14..100 (87 rows).

Without flags the script prints a C snippet for status_screen.c. With --patch
it writes both files in place, so no manual paste is needed:

  - patches/oled-strata.patch   (array, y0, loop bound, hunk header, diffstat)
  - app/app/src/display/status_screen.c

Requires Pillow: python3 -m pip install pillow

Usage:
    python3 tools/convert-oled-logo.py IMAGE [--threshold 80] [--width 32]
    python3 tools/convert-oled-logo.py IMAGE --patch [--invert]
    python3 tools/convert-oled-logo.py IMAGE --patch --dry-run
"""

import argparse
import re
import sys
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent
PATCH_FILE = ROOT / "patches" / "oled-strata.patch"
SOURCE_FILE = ROOT / "app" / "app" / "src" / "display" / "status_screen.c"

# The optional leading comment keeps the whole block replaceable in one go.
LOGO_SOURCE = re.compile(
    r"(?:/\*(?:(?!\*/).)*\*/\s*)?static const uint32_t strata_logo\[\d+\][^;]*?\{.*?\};",
    re.S,
)
LOGO_PATCH = re.compile(
    r"(?:\+/\*(?:(?!\*/).)*\*/\s*)?\+static const uint32_t strata_logo\[\d+\][^;]*?\{.*?\};",
    re.S,
)


def die(message):
    sys.exit(f"error: {message}")


def replace_once(text, pattern, replacement, what):
    updated, count = pattern.subn(lambda _: replacement, text, count=1)
    if count != 1:
        die(f"{what} tidak ditemukan persis sekali (ditemukan {count} kali)")
    return updated


def c_block(width, height, rows, invert=False):
    focus = ", source inverted" if invert else ""
    lines = [
        f"/* OLED logo: {width}x{height} (full width, height from aspect{focus}), centred between",
        " * LINK and battery; inverted 1-bit (bright pixels drawn dark), no pre-rotation so",
        " * the panel shows it 90deg CW. Bit 0 is the leftmost pixel of each row. */",
        f"static const uint32_t strata_logo[{height}] __attribute__((unused)) = {{",
    ]
    for i in range(0, height, 4):
        lines.append("    " + ", ".join(f"0x{v:08x}" for v in rows[i:i + 4]) + ",")
    lines.append("};")
    return "\n".join(lines)


def update_draw_logo(text, y0, height, what):
    updated, count = re.subn(
        r"(const int y0 = )\d+",
        lambda m: m.group(1) + str(y0),
        text,
        count=1,
    )
    if count != 1:
        die(f"{what}:const int y0 tidak ditemukan persis sekali")

    updated, count = re.subn(
        r"(for \(int y = 0; y < )\d+(; y\+\+\) \{)",
        lambda m: m.group(1) + str(height) + m.group(2),
        updated,
        count=1,
    )
    if count != 1:
        die(f"{what}: loop strata_logo tidak ditemukan persis sekali")
    return updated


def update_patch_metadata(text):
    lines = text.splitlines()

    # Recount the first hunk from its body instead of relying on hardcoded
    # base numbers: surrounding code can change independently of the logo.
    start = next((i for i, l in enumerate(lines) if l.startswith("@@ -14,6 +25,")), None)
    if start is None:
        die("header hunk status_screen.c tidak ditemukan")
    end = next(
        (i for i in range(start + 1, len(lines))
         if lines[i].startswith("@@") or lines[i].startswith("diff --git")),
        len(lines),
    )
    body = lines[start + 1:end]
    old_count = sum(1 for l in body if l.startswith(" ") or l.startswith("-"))
    new_count = sum(1 for l in body if l.startswith(" ") or l.startswith("+"))
    if old_count != 6:
        die(f"hunk pertama memiliki {old_count} baris lama, diharapkan 6")
    hunk = f"@@ -14,6 +25,{new_count} @@"

    # Count insertions/deletions per file, ignoring the trailing patch signature.
    per_file = {}
    current = None
    for line in lines:
        if line.startswith("-- "):
            break
        if line.startswith("diff --git"):
            current = line.split(" b/")[-1]
            per_file[current] = [0, 0]
        elif current and line[:1] in ("+", "-") and not line.startswith("+++") and not line.startswith("---"):
            per_file[current][0 if line[0] == "+" else 1] += 1

    status_ins, status_del = per_file.get("app/src/display/status_screen.c", [0, 0])
    total_ins = sum(v[0] for v in per_file.values())
    total_del = sum(v[1] for v in per_file.values())
    stat = f" app/src/display/status_screen.c             | {status_ins + status_del} +++++++++++++++++++-"
    total = f" 6 files changed, {total_ins} insertions(+), {total_del} deletions(-)"

    updated, count = re.subn(
        r"(?m)^@@ -14,6 \+25,\d+ @@$",
        lambda _: hunk,
        text,
        count=1,
    )
    if count != 1:
        die("header hunk status_screen.c tidak ditemukan persis sekali")

    updated, count = re.subn(
        r"(?m)^( app/src/display/status_screen\.c\s+\| )\d+( .*)$",
        lambda m: m.group(1) + str(status_ins + status_del) + m.group(2),
        updated,
        count=1,
    )
    if count != 1:
        die("baris diffstat status_screen.c tidak ditemukan persis sekali")

    updated, count = re.subn(
        rf"(?m)^( 6 files changed, )\d+( insertions\(\+\), {total_del} deletions\(-\))$",
        lambda m: m.group(1) + str(total_ins) + m.group(2),
        updated,
        count=1,
    )
    if count != 1:
        die("baris total diffstat tidak ditemukan persis sekali")

    updated, count = re.subn(
        r"(?m)^- right: pixel logo.*$",
        lambda _: "- right: pixel logo, split LINK status, battery gauge",
        updated,
        count=1,
    )
    if count != 1:
        die("bullet logo di commit message tidak ditemukan persis sekali")

    return updated, hunk, stat, total


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("image", help="source image (png/jpg/webp/...)")
    ap.add_argument("--width", type=int, default=32,
                    help="portrait width; maps to the full 32 px panel height")
    ap.add_argument("--threshold", type=int, default=80,
                    help="luminance above this is drawn dark (inverted logo), default 80")
    ap.add_argument("--top", type=int, default=14, help="first usable portrait row (after LINK)")
    ap.add_argument("--bottom", type=int, default=100,
                    help="last usable portrait row (before battery)")
    ap.add_argument("--patch", action="store_true",
                    help="write the logo into the patch file AND the live source")
    ap.add_argument("--invert", action="store_true",
                    help="invert the source first: white becomes black, black becomes white")
    ap.add_argument("--dry-run", action="store_true",
                    help="with --patch: print what would change without writing")
    args = ap.parse_args()

    if args.width < 1 or args.width > 32:
        ap.error("--width harus antara 1 dan 32 (array disimpan sebagai uint32_t)")

    available = args.bottom - args.top + 1
    if available < 1:
        ap.error("--bottom must be >= --top")
    if args.dry_run and not args.patch:
        ap.error("--dry-run hanya bisa dipakai bersama --patch")

    im = Image.open(args.image).convert("L")
    if args.invert:
        im = ImageOps.invert(im)
    height = round(args.width * im.height / im.width)
    if height > available:
        print(
            f"warning: ratio gives {height} rows but only {available} fit between "
            f"LINK and battery; clamping to {available} (aspect will change)",
            file=sys.stderr,
        )
        height = available
    if height < 1:
        ap.error("gambar terlalu kecil untuk dijadikan logo")

    im = im.resize((args.width, height), Image.LANCZOS)
    px = im.load()
    y0 = args.top + (available - height) // 2

    rows = []
    for y in range(height):
        bits = 0
        for x in range(args.width):
            if px[x, y] > args.threshold:
                # bit 0 is the leftmost pixel of the row
                bits |= 1 << (args.width - 1 - x)
        rows.append(bits)

    if not args.patch:
        print(f"// {args.image}: {args.width}x{height}, y0={y0}, threshold={args.threshold}")
        print(c_block(args.width, height, rows, args.invert))
        print(f"// strata_draw_logo(): const int y0 = {y0};")
        print(f"//                     for (int y = 0; y < {height}; y++)")
        return

    block = c_block(args.width, height, rows, args.invert)
    patch_block = "\n".join("+" + line for line in block.splitlines())

    for path in (SOURCE_FILE, PATCH_FILE):
        if not path.is_file():
            die(f"{path} tidak ditemukan; jalankan setup west dulu")

    source = SOURCE_FILE.read_text(encoding="utf-8")
    source = replace_once(source, LOGO_SOURCE, block, "source: blok strata_logo")
    source = update_draw_logo(source, y0, height, "source")

    patch = PATCH_FILE.read_text(encoding="utf-8")
    patch = replace_once(patch, LOGO_PATCH, patch_block, "patch: blok strata_logo")
    patch = update_draw_logo(patch, y0, height, "patch")

    patch, hunk, stat, total = update_patch_metadata(patch)

    print(f"gambar: {args.width}x{height}, y0={y0}, threshold={args.threshold}, invert={'ya' if args.invert else 'tidak'}")
    print(hunk)
    print(stat)
    print(total)

    if args.dry_run:
        print("dry-run: tidak ada file yang ditulis")
        return

    SOURCE_FILE.write_text(source, encoding="utf-8")
    PATCH_FILE.write_text(patch, encoding="utf-8")
    print(f"ditulis: {SOURCE_FILE.relative_to(ROOT)}")
    print(f"ditulis: {PATCH_FILE.relative_to(ROOT)}")
    print("lanjut: ./apply-oled-mod.sh && ./build.sh right")


if __name__ == "__main__":
    main()
