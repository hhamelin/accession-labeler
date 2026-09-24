"""
Rendering module for Accession Label Generator.
Handles 1-bit monochrome PIL rendering, SVG template generation, SVG to PNG conversion,
font path resolution, and design constants.
"""

import functools
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# Project paths (root project directory is parent of accession_labeler package)
PACKAGE_DIR = Path(__file__).parent.resolve()
SCRIPT_DIR = PACKAGE_DIR.parent.resolve()
FONTS_DIR = SCRIPT_DIR / "fonts"
LABELS_DIR = SCRIPT_DIR / "labels"
DROID_SANS_TTF = FONTS_DIR / "DroidSans.ttf"
DROID_MONO_TTF = FONTS_DIR / "DroidSansMono.ttf"

# Template search paths
SVG_TEMPLATE_PATHS = [
    SCRIPT_DIR / "label.svg",
    SCRIPT_DIR / "label_template.svg",
]

# Design specification constants (from label.xcf / label.svg)
CANVAS_HEIGHT = 76
DEFAULT_MIN_WIDTH = 112
MARGIN_HORIZONTAL = 10
MARGIN_VERTICAL = 4
PADDING_HORIZONTAL = 10

# Pixel-exact integer baseline vertical placement offsets
DEFAULT_YEAR_Y_BASELINE = 40
DEFAULT_IDENTIFIER_Y_BASELINE = 62

# Background line specs
TOP_LINES = [
    (4, 3),   # y=4, height=3 (y=4, 5, 6)
    (8, 2),   # y=8, height=2 (y=8, 9)
    (11, 1),  # y=11, height=1
]

BOTTOM_LINES = [
    (64, 1),  # y=64, height=1
    (66, 2),  # y=66, height=2 (y=66, 67)
    (69, 3),  # y=69, height=3 (y=69, 70, 71)
]


def load_template_text_baselines():
    """
    Parses y attributes for text-year and text-identifier from template SVG if present,
    rounded to pixel-exact integer coordinates.
    """
    year_y = DEFAULT_YEAR_Y_BASELINE
    id_y = DEFAULT_IDENTIFIER_Y_BASELINE

    template_file = None
    for p in SVG_TEMPLATE_PATHS:
        if p.exists():
            template_file = p
            break

    if template_file:
        try:
            tree = ET.parse(template_file)
            root = tree.getroot()
            for elem in root.iter():
                elem_id = elem.attrib.get("id", "")
                if elem_id == "text-year" and "y" in elem.attrib:
                    year_y = int(round(float(elem.attrib["y"])))
                elif elem_id == "text-identifier" and "y" in elem.attrib:
                    id_y = int(round(float(elem.attrib["y"])))
        except Exception as e:
            print(f"Warning: Could not parse text baselines from {template_file}: {e}", file=sys.stderr)

    return year_y, id_y


@functools.lru_cache(maxsize=None)
def resolve_font_path(filename, family_name=None):
    """
    Resolves the font path:
    1. Checks the local fonts/ folder first.
    2. If not found locally, searches system fonts (via fontconfig, standard directories, or Pillow).
    Returns the resolved Path or raises FileNotFoundError.
    """
    local_path = FONTS_DIR / filename
    if local_path.is_file():
        return local_path
    if FONTS_DIR.is_dir():
        for f in FONTS_DIR.iterdir():
            if f.is_file() and f.name.lower() == filename.lower():
                return f

    if family_name:
        try:
            res = subprocess.run(
                ["fc-match", "-f", "%{family}::%{file}", family_name],
                capture_output=True, text=True, check=True
            )
            out = res.stdout.strip()
            if "::" in out:
                matched_family, matched_file = out.split("::", 1)
                norm_query = family_name.lower().replace(" ", "")
                norm_family = matched_family.lower().replace(" ", "")
                if norm_query in norm_family or filename.lower() in matched_file.lower():
                    p = Path(matched_file)
                    if p.is_file():
                        return p
        except Exception:
            pass

    try:
        res = subprocess.run(
            ["fc-list", "-f", "%{file}\n"],
            capture_output=True, text=True, check=True
        )
        fn_lower = filename.lower()
        for line in res.stdout.splitlines():
            line = line.strip()
            if line and Path(line).name.lower() == fn_lower:
                p = Path(line)
                if p.is_file():
                    return p
    except Exception:
        pass

    system_font_dirs = [
        Path("/usr/share/fonts"),
        Path("/usr/local/share/fonts"),
        Path.home() / ".local/share/fonts",
        Path.home() / ".fonts",
        Path("/Library/Fonts"),
        Path("/System/Library/Fonts"),
        Path.home() / "Library/Fonts",
        Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts",
    ]
    fn_lower = filename.lower()
    for d in system_font_dirs:
        if d.is_dir():
            try:
                for p in d.rglob("*.ttf"):
                    if p.name.lower() == fn_lower:
                        return p
            except Exception:
                continue

    try:
        font = ImageFont.truetype(filename, 10)
        if hasattr(font, "path") and font.path and Path(font.path).is_file():
            return Path(font.path)
    except Exception:
        pass

    raise FileNotFoundError(
        f"Font '{filename}' not found in local directory ({FONTS_DIR}) or system font directories. "
        f"Please install '{family_name or filename}' or place '{filename}' in '{FONTS_DIR}'."
    )


@functools.lru_cache(maxsize=None)
def get_fonts():
    """
    Loads fonts:
    - Upper text (Year): Droid Sans Mono 36px
    - Lower text (Identifier): Droid Sans Regular 24px
    """
    mono_path = resolve_font_path("DroidSansMono.ttf", family_name="Droid Sans Mono")
    sans_path = resolve_font_path("DroidSans.ttf", family_name="Droid Sans")

    font_year = ImageFont.truetype(str(mono_path), 36)
    font_id = ImageFont.truetype(str(sans_path), 24)
    return font_year, font_id


def calculate_label_width(year_str, rest_str, font_year, font_id, user_width="auto"):
    """Calculates dynamic label width based on text measurements."""
    if user_width != "auto":
        return int(user_width)

    bbox_year = font_year.getbbox(year_str)
    bbox_id = font_id.getbbox(rest_str)

    width_year = bbox_year[2] - bbox_year[0]
    width_id = bbox_id[2] - bbox_id[0]

    max_content_width = max(width_year, width_id)
    calculated_width = max_content_width + (PADDING_HORIZONTAL * 2) + (MARGIN_HORIZONTAL * 2)

    final_width = max(DEFAULT_MIN_WIDTH, int(calculated_width))
    return final_width


def render_pillow(year_str, rest_str, width, year_y, id_y):
    """
    Renders label image natively in 1-bit mode ('1') using pixel-exact integer coordinates.
    Draws text directly onto 1-bit binary canvas without anti-aliasing.
    """
    font_year, font_id = get_fonts()

    img = Image.new("1", (width, CANVAS_HEIGHT), 1)
    draw = ImageDraw.Draw(img)

    x_start = MARGIN_HORIZONTAL
    x_end = width - MARGIN_HORIZONTAL

    for y_top, h in TOP_LINES:
        draw.rectangle([x_start, y_top, x_end - 1, y_top + h - 1], fill=0)

    for y_bot, h in BOTTOM_LINES:
        draw.rectangle([x_start, y_bot, x_end - 1, y_bot + h - 1], fill=0)

    center_x = int(round(width / 2.0))
    draw.text((center_x, year_y), year_str, font=font_year, fill=0, anchor="ms")
    draw.text((center_x, id_y), rest_str, font=font_id, fill=0, anchor="ms")

    return img


def generate_svg(year_str, rest_str, width, year_y, id_y):
    """Generates SVG string with dynamic width, pattern tiling, and pixel-exact integer baseline text."""
    bg_width = width - (MARGIN_HORIZONTAL * 2)
    center_x = int(round(width / 2.0))

    svg_content = f'''<svg width="{width}" height="{CANVAS_HEIGHT}" viewBox="0 0 {width} {CANVAS_HEIGHT}" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <!-- Background pattern (1px wide x 76px high tile) -->
    <pattern id="bg-pattern" width="1" height="{CANVAS_HEIGHT}" patternUnits="userSpaceOnUse">
      <!-- Top diminishing lines -->
      <rect y="4" width="1" height="3" fill="black"/>
      <rect y="8" width="1" height="2" fill="black"/>
      <rect y="11" width="1" height="1" fill="black"/>
      <!-- Bottom diminishing lines -->
      <rect y="64" width="1" height="1" fill="black"/>
      <rect y="66" width="1" height="2" fill="black"/>
      <rect y="69" width="1" height="3" fill="black"/>
    </pattern>
  </defs>

  <!-- Background pattern region bounded between left and right margins -->
  <rect id="bg-region" x="{MARGIN_HORIZONTAL}" y="0" width="{bg_width}" height="{CANVAS_HEIGHT}" fill="url(#bg-pattern)"/>

  <!-- Centered Year text (Upper: Droid Sans Mono 36px) -->
  <text id="text-year" x="{center_x}" y="{year_y}" text-anchor="middle" font-family="Droid Sans Mono, monospace" font-size="36" fill="black">{year_str}</text>

  <!-- Centered Identifier text (Lower: Droid Sans 24px) -->
  <text id="text-identifier" x="{center_x}" y="{id_y}" text-anchor="middle" font-family="Droid Sans, sans-serif" font-size="24" fill="black">{rest_str}</text>
</svg>'''
    return svg_content


def render_svg_to_png(svg_filepath, output_filepath):
    """Converts SVG to PNG in strict 1-bit monochrome mode without anti-aliasing."""
    cmd_magick = ["magick", "convert", str(svg_filepath), "+antialias", "-monochrome", str(output_filepath)]
    cmd_convert = ["convert", str(svg_filepath), "+antialias", "-monochrome", str(output_filepath)]
    cmd_rsvg = ["rsvg-convert", "-o", str(output_filepath), str(svg_filepath)]

    rendered = False
    for cmd in [cmd_magick, cmd_convert, cmd_rsvg]:
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if res.returncode == 0:
                rendered = True
                break
        except FileNotFoundError:
            continue

    if not rendered:
        raise RuntimeError("No SVG-to-PNG renderer found (tried ImageMagick 'convert'/'magick' and 'rsvg-convert').")

    if Path(output_filepath).exists():
        im = Image.open(output_filepath).convert("1")
        im.save(output_filepath)
