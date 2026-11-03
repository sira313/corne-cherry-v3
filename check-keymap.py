#!/usr/bin/env python3
"""
Bandingkan baris comment (`// | ... |`) dengan baris `bindings` di keymap ZMK,
lalu bandingkan juga label di map.svg dengan comment yang sama.

Pakai: python3 check-keymap.py [path-keymap] [path-svg]
Exit 0 = semua cocok, 1 = ada sel yang beda.
"""
import re
import sys
import xml.etree.ElementTree as ET

SVG = "{http://www.w3.org/2000/svg}"

MAP = {
    "BSPC": "&kp BSPC", "TAB": "&kp TAB", "SHFT": "&kp LSHFT", "CTRL": "&kp LCTRL",
    "ALT": "&kp LALT", "OPT": "&kp LALT", "MENU": "&kp K_CONTEXT_MENU", "GUI": "&kp LGUI", "ENT": "&kp RET", "RSE": "&mo 2",
    "LWR": "&mo 1", "&mo3": "&mo 3", "SPC": "&kp SPACE",
    "CAPS": "&kp CAPS", "DEL": "&kp DEL", "PRTSC": "&kp PRINTSCREEN",
    "PgUp": "&kp PG_UP", "PgDn": "&kp PG_DN",
    "BRUP": "&kp C_BRI_UP", "BRDN": "&kp C_BRI_DN",
    "VOLUP": "&kp K_VOL_UP", "VOLDN": "&kp K_VOL_DN",
    "UNLK": "&studio_unlock", "BTCLR": "&bt BT_CLR", "TOG3": "&tog 3",
    "PIPE": "&kp PIPE", "BSLH": "&kp BSLH",
    "LEFT": "&kp LEFT", "RIGHT": "&kp RIGHT", "UP": "&kp UP", "DOWN": "&kp DOWN",
    "LCLK": "&mkp LCLK", "RCLK": "&mkp RCLK",
    "MOVEU": "&mmv MOVE_UP", "MOVEL": "&mmv MOVE_LEFT",
    "MOVED": "&mmv MOVE_DOWN", "MOVER": "&mmv MOVE_RIGHT",
    "SCRLU": "&msc SCRL_UP", "SCRLD": "&msc SCRL_DOWN",
    "SCRLL": "&msc SCRL_LEFT", "SCRLR": "&msc SCRL_RIGHT",
}
MAP.update({f"BT{i}": f"&bt BT_SEL {i - 1}" for i in range(1, 6)})
MAP.update({f"MB{i}": f"&mkp MB{i}" for i in range(3, 6)})
MAP.update({c: f"&kp {c}" for c in "QWERTYUIOPASDFGHJKLZXCVBNM"})
MAP.update({str(n): f"&kp N{n}" for n in range(1, 10)})
MAP["0"] = "&kp N0"
MAP.update({
    "'": "&kp SQT", "'/SFT": "&mt LSHFT SQT", "ES/CTL": "&mt LCTRL ESC",
    ";": "&kp SEMI", ",": "&kp COMMA", ".": "&kp DOT", "/": "&kp FSLH",
    "!": "&kp EXCL", "@": "&kp AT", "#": "&kp HASH", "$": "&kp DLLR",
    "%": "&kp PRCNT", "^": "&kp CARET", "&": "&kp AMPS", "*": "&kp ASTRK",
    "(": "&kp LPAR", ")": "&kp RPAR", "-": "&kp MINUS", "=": "&kp EQUAL",
    "[": "&kp LBKT", "]": "&kp RBKT", "`": "&kp GRAVE", "_": "&kp UNDER",
    "+": "&kp PLUS", "{": "&kp LBRC", "}": "&kp RBRC", "~": "&kp TILDE",
})


def parse_bindings(line):
    """'&kp A &mt LSHFT SQT' -> ['&kp A', '&mt LSHFT SQT']"""
    out = []
    for tok in line.split():
        if tok.startswith("&"):
            out.append(tok)
        elif out:
            out[-1] += " " + tok
    return out


def comment_cells(path):
    """-> [(layer_name, [label per key])] dari diagram comment, urut layer di file."""
    src = open(path).read()
    out = []
    for name, body in re.findall(r"(\w+_layer)\s*\{(.*?)\n                \};", src, re.S):
        cells = []
        for line in body.splitlines():
            s = line.strip()
            if s.startswith("//"):
                cells += [(c.strip() or "-") for c in s.split("//", 1)[1].split("|")[1:-1]]
        out.append((name, cells))
    return out


def svg_labels(path):
    """-> [(layer_title, [label per key])] dari map.svg, urut dokumen."""
    root = ET.parse(path).getroot()
    out, title, labels = [], None, []
    for g in root.iter():
        if g.tag == SVG + "text" and g.get("font-weight") == "bold":
            if title is not None:
                out.append((title, labels))
            title, labels = (g.text or "").strip(), []
        elif g.tag == SVG + "g":
            for t in g.iter(SVG + "text"):
                labels.append((t.text or "").strip() or "-")
    if title is not None:
        out.append((title, labels))
    return out


def check_svg(keymap, svg):
    bad = 0
    km, sv = comment_cells(keymap), svg_labels(svg)
    if len(km) != len(sv):
        print(f"[svg] {len(km)} layer di keymap, {len(sv)} di svg -> JUMLAH BEDA")
        bad += 1
    for (name, want), (title, have) in zip(km, sv):
        if len(want) != len(have):
            print(f"[svg] '{title}': {len(have)} key, keymap punya {len(want)} -> JUMLAH BEDA")
            bad += 1
            continue
        for i, (w, h) in enumerate(zip(want, have), start=1):
            if w != h:
                print(f"[svg] '{title}' key {i}: keymap '{w}', svg '{h}'")
                bad += 1
    return bad


def main(path, svg_path):
    src = open(path).read()
    bad = 0
    for name, body in re.findall(r"(\w+_layer)\s*\{(.*?)\n                \};", src, re.S):
        lines = body.splitlines()
        comments = [l for l in lines if l.strip().startswith("//")]
        binds = [parse_bindings(l) for l in lines if l.strip().startswith("&")]
        for i, (cline, brow) in enumerate(zip(comments, binds)):
            cells = cline.split("//", 1)[1].split("|")[1:-1]
            if len(cells) != len(brow):
                print(f"[{name}] baris {i}: comment {len(cells)} sel, binding {len(brow)} -> JUMLAH BEDA")
                bad += 1
                continue
            for col, (cell, have) in enumerate(zip(cells, brow), start=1):
                label = cell.strip()
                # ponytail: sel kosong terima &trans atau &none; kalau butuh
                # Bedakan strict, ganti label kosong jadi "NONE" + MAP["NONE"].
                want = ({MAP[label]} if label in MAP
                        else {"&trans", "&none"} if not label else {"&trans"})
                if have not in want:
                    print(f"[{name}] baris {i} kolom {col}: comment "
                          f"'{label or '-'}' -> harus {'/'.join(sorted(want))}, di file {have}")
                    bad += 1
    bad += check_svg(path, svg_path)
    print("SEMUA COCOK" if not bad else f"{bad} sel beda")
    return 1 if bad else 0


if __name__ == "__main__":
    argv = sys.argv[1:]
    sys.exit(main(argv[0] if argv else "config/corne_left.keymap",
                  argv[1] if len(argv) > 1 else "map.svg"))