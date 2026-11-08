#!/usr/bin/env python3
"""Build dist/ from src/.

Usage:
  python3 tools/build.py
      Writes dist/dry.css, dist/dry.min.css, dist/dry.icons.css and
      dist/dry.icons.min.css, and refreshes the icon cheat sheet in docs.html
      (and templates/showcase.html when present). Needs only Python 3.

  python3 tools/build.py --fonts <fonts-dir> [<symbols-nerd-font.ttf>]
      Same, after re-subsetting the fonts first (needs fonttools and brotli):
        - Hanken Grotesk 450, 450 italic and 600, and JetBrains Mono 450 -> dist/fonts/
      With the Symbols Nerd Font file as the second argument, the icons are
      rebuilt too:
        - the icons listed in tools/icons.txt -> src/dry-icons.woff2
        - dist/icons.json (name -> code)
      <fonts-dir> holds the variable font files, under these names:
        HankenGrotesk[wght].ttf, HankenGrotesk-Italic[wght].ttf, JetBrainsMono[wght].ttf
      (from https://github.com/google/fonts, folders ofl/hankengrotesk and ofl/jetbrainsmono).
      The weights are pinned to fixed values and the glyphs cut down to Latin.

Sources: src/dry.css (hand-edited), src/dry.icons.css (template), src/dry-icons.woff2.
"""
import base64
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
DIST = os.path.join(ROOT, "dist")
EMBED_LIMIT = 30 * 1024

TEXT_RANGE = (
    "U+0000-00FF,U+0100-017F,U+0131,U+0152-0153,U+02C6,U+02DA,U+02DC,"
    "U+2000-206F,U+20A0-20CF,U+2100-215F,U+2190-21FF,U+2212,U+2215,"
    "U+2264-2265,U+2713,U+FEFF,U+FFFD"
)

LAYOUT_FEATURES = "kern,liga,ccmp,locl,mark,mkmk,tnum,case"

TEXT_FONTS = [
    # (source file, weight, output name)
    ("HankenGrotesk[wght].ttf", 450, "hanken-grotesk-450"),
    ("HankenGrotesk-Italic[wght].ttf", 450, "hanken-grotesk-450i"),
    ("HankenGrotesk[wght].ttf", 600, "hanken-grotesk-600"),
    ("JetBrainsMono[wght].ttf", 450, "jetbrains-mono-450"),
]


# ---------- fonts (optional step) ----------

def subset(src, out, unicodes=None, glyph_unicodes=None, features=LAYOUT_FEATURES):
    args = ["pyftsubset", src, f"--output-file={out}", "--flavor=woff2",
            f"--layout-features={features}", "--no-hinting", "--desubroutinize"]
    if unicodes:
        args.append(f"--unicodes={unicodes}")
    if glyph_unicodes:
        args.append("--unicodes=" + ",".join(f"U+{c:X}" for c in glyph_unicodes))
    subprocess.run(args, check=True)


def read_icons():
    icons = []
    with open(os.path.join(ROOT, "tools", "icons.txt")) as fh:
        group = ""
        for line in fh:
            line = line.strip()
            if line.startswith("# ") and not line.startswith("# alias"):
                group = line[2:]
            if not line or line.startswith("#"):
                continue
            alias, glyph = line.split()
            icons.append((group, alias, glyph))
    return icons


def build_fonts(fonts_dir):
    from fontTools.ttLib import TTFont

    fonts = os.path.join(DIST, "fonts")
    os.makedirs(fonts, exist_ok=True)

    import tempfile
    from fontTools.varLib import instancer

    with tempfile.TemporaryDirectory() as tmp:
        for src, weight, out in TEXT_FONTS:
            path = os.path.join(fonts_dir, src)
            if not os.path.exists(path):
                sys.exit(f"missing {path}")
            font = TTFont(path)
            pinned = {a.axisTag: a.defaultValue for a in font["fvar"].axes}
            pinned["wght"] = weight
            static = os.path.join(tmp, out + ".ttf")
            instancer.instantiateVariableFont(font, pinned).save(static)
            subset(static, os.path.join(fonts, out + ".woff2"), unicodes=TEXT_RANGE)
    print(f"fonts: {len(TEXT_FONTS)} text fonts")


def build_icons(symbols):
    from fontTools.ttLib import TTFont

    by_name = {}
    for code, name in TTFont(symbols).getBestCmap().items():
        by_name.setdefault(name, code)
    icons = read_icons()
    missing = [g for _, _, g in icons if g not in by_name]
    if missing:
        sys.exit("icons not in font: " + ", ".join(missing))
    codes = sorted({by_name[g] for _, _, g in icons})
    subset(symbols, os.path.join(SRC, "dry-icons.woff2"), glyph_unicodes=codes, features="")

    data = [{"group": g, "name": a, "code": f"{by_name[n]:X}", "glyph": n} for g, a, n in icons]
    with open(os.path.join(DIST, "icons.json"), "w") as fh:
        json.dump(data, fh, indent=1)
    print(f"icons: {len(icons)} icons")


# ---------- css ----------

def minify(css):
    """Drop comments (except /*! banners) and needless whitespace. Strings and url() are kept as they are."""
    keep = []

    def protect(m):
        text = m.group(0)
        if text.startswith("/*") and not text.startswith("/*!"):
            return ""
        keep.append(text)
        return f"\x00{len(keep) - 1}\x00"

    css = re.sub(r'/\*.*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|url\([^)]*\)', protect, css, flags=re.S)
    css = re.sub(r"\s+", " ", css)
    css = re.sub(r" ?([{};,]) ?", r"\1", css)       # around braces, semicolons, commas
    css = re.sub(r":\s+", ":", css)                  # after a colon (never before: "a :hover" differs from "a:hover")
    css = css.replace(";}", "}").strip()
    css = re.sub(r"\x00(\d+)\x00", lambda m: keep[int(m.group(1))], css)
    # banners get their own line
    return re.sub(r"(/\*!.*?\*/) ?", r"\1\n", css, flags=re.S)


def write(name, text):
    path = os.path.join(DIST, name)
    with open(path, "w") as fh:
        fh.write(text if text.endswith("\n") else text + "\n")


def build_css():
    os.makedirs(DIST, exist_ok=True)
    core = open(os.path.join(SRC, "dry.css")).read()

    font = open(os.path.join(SRC, "dry-icons.woff2"), "rb").read()
    if len(font) > EMBED_LIMIT:
        sys.exit(f"icon font is {len(font)} bytes; over the {EMBED_LIMIT} byte embed limit")
    face = ("@font-face {\n  font-family: \"DryIcons\";\n  font-display: block;\n"
            f"  src: url(data:font/woff2;base64,{base64.b64encode(font).decode()}) format(\"woff2\");\n"
            "  unicode-range: U+F0000-F1FFF;\n}")
    icons = open(os.path.join(SRC, "dry.icons.css")).read().replace("/*@@ICON_FONT@@*/", face)

    write("dry.css", core)
    write("dry.min.css", minify(core))
    write("dry.icons.css", icons)
    write("dry.icons.min.css", minify(icons))


# ---------- icon cheat sheet ----------

def build_cheatsheet():
    data = json.load(open(os.path.join(DIST, "icons.json")))
    rows, group = [], None
    for d in data:
        if d["group"] != group:
            if group is not None:
                rows.append('        </div>')
            group = d["group"]
            rows.append(f'        <h6>{group}</h6>')
            rows.append('        <div class="grid cols-6 gap-sm">')
        rows.append(f'          <div class="row nowrap gap-sm" data-code="&amp;#x{d["code"]};" title="{d["glyph"]}">'
                    f'<span class="icon-lg">&#x{d["code"]};</span>'
                    f'<span class="text-sm">{d["name"]}<br><code class="text-xs">&amp;#x{d["code"]};</code></span></div>')
    rows.append('        </div>')
    for page in ("docs.html", "templates/showcase.html"):
        path = os.path.join(ROOT, page)
        if not os.path.exists(path):
            continue
        html = open(path).read()
        html = re.sub(r"(<!--@@ICONS-->).*?(<!--@@/ICONS-->)",
                      lambda m: m.group(1) + "\n" + "\n".join(rows) + "\n      " + m.group(2),
                      html, flags=re.S)
        open(path, "w").write(html)


def report():
    import gzip
    for name in ("dry.css", "dry.min.css", "dry.icons.css", "dry.icons.min.css"):
        raw = open(os.path.join(DIST, name), "rb").read()
        print(f"dist/{name}: {len(raw)/1024:.1f} KB, {len(gzip.compress(raw, 9))/1024:.1f} KB gzipped")


def main():
    args = sys.argv[1:]
    if args and args[0] == "--fonts":
        if len(args) not in (2, 3):
            sys.exit(__doc__)
        build_fonts(args[1])
        if len(args) == 3:
            build_icons(args[2])
    elif args:
        sys.exit(__doc__)
    build_css()
    build_cheatsheet()
    report()


if __name__ == "__main__":
    main()
