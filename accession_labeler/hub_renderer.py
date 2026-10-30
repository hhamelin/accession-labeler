"""
PDF vector rendering engine for Disc Hub Labels on Compulabel #312862 sheets.
Uses ReportLab to generate exact inch-dimensioned vector PDF files.
Supports circular arc text wrapping centered inside the 0.315" printable ring.
"""

import math
from pathlib import Path
from typing import List, Tuple, Optional
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from accession_labeler.hub_config import Compulabel312862Config, DiscHubSpec, INCH_TO_PT
from accession_labeler.renderer import resolve_font_path

_REGISTERED_FONTS = {}


def get_registered_font(requested_font_name: str = "Verdana-Bold") -> str:
    """
    Resolves and registers a TTF font in ReportLab metrics.
    Tries requested font (e.g. Verdana-Bold), then system/local bold fonts (DejaVuSans-Bold, DroidSans-Bold),
    falling back to built-in 'Helvetica-Bold'.
    """
    if requested_font_name in _REGISTERED_FONTS:
        return _REGISTERED_FONTS[requested_font_name]

    if requested_font_name in ("Helvetica", "Helvetica-Bold", "Times-Roman", "Courier"):
        _REGISTERED_FONTS[requested_font_name] = requested_font_name
        return requested_font_name

    search_files = ["Verdana-Bold.ttf", "verdanab.ttf", "Verdana_Bold.ttf", "DejaVuSans-Bold.ttf", "DroidSans-Bold.ttf"]
    search_families = ["Verdana", "DejaVu Sans", "Droid Sans"]

    font_file = None
    for fn in search_files:
        try:
            font_file = resolve_font_path(fn, family_name="Verdana")
            if font_file and font_file.is_file():
                break
        except Exception:
            continue

    if not font_file or not font_file.is_file():
        for family in search_families:
            for fn in ["DejaVuSans-Bold.ttf", "DroidSans-Bold.ttf"]:
                try:
                    font_file = resolve_font_path(fn, family_name=family)
                    if font_file and font_file.is_file():
                        break
                except Exception:
                    continue
            if font_file and font_file.is_file():
                break

    if font_file and font_file.is_file():
        reg_name = f"Registered_{font_file.stem}"
        try:
            pdfmetrics.registerFont(TTFont(reg_name, str(font_file)))
            _REGISTERED_FONTS[requested_font_name] = reg_name
            return reg_name
        except Exception:
            pass

    _REGISTERED_FONTS[requested_font_name] = "Helvetica-Bold"
    return "Helvetica-Bold"


def render_curved_text(
    c: canvas.Canvas,
    cx: float,
    cy: float,
    text_str: str,
    font_name: str,
    font_size: float,
    arc_radius_pt: float,
    center_angle_deg: float = 90.0
):
    """
    Renders text_str as one continuous string wrapped along a circular arc path
    centered at (cx, cy) with radius `arc_radius_pt` (points).
    The middle of the string is centered at `center_angle_deg` (default 90° = 12 o'clock top of circle).
    """
    if not text_str:
        return

    reg_font = get_registered_font(font_name)
    c.setFont(reg_font, font_size)

    char_widths = [c.stringWidth(ch, reg_font, font_size) for ch in text_str]
    total_width = sum(char_widths)

    if total_width == 0:
        return

    total_angle_rad = total_width / arc_radius_pt
    total_angle_deg = total_angle_rad * (180.0 / math.pi)

    # If text is too long for arc (exceeds 240 degrees), scale down font size proportionally
    max_allowed_angle_deg = 240.0
    if total_angle_deg > max_allowed_angle_deg:
        scale_factor = max_allowed_angle_deg / total_angle_deg
        font_size = font_size * scale_factor
        c.setFont(reg_font, font_size)
        char_widths = [c.stringWidth(ch, reg_font, font_size) for ch in text_str]
        total_width = sum(char_widths)
        total_angle_rad = total_width / arc_radius_pt
        total_angle_deg = total_angle_rad * (180.0 / math.pi)

    start_angle_deg = center_angle_deg + (total_angle_deg / 2.0)
    current_angle_deg = start_angle_deg

    c.setFillColorRGB(0, 0, 0)

    for ch, w_ch in zip(text_str, char_widths):
        if w_ch == 0:
            continue

        half_char_angle_deg = (w_ch / (2.0 * arc_radius_pt)) * (180.0 / math.pi)
        char_center_deg = current_angle_deg - half_char_angle_deg
        char_center_rad = math.radians(char_center_deg)

        x = cx + (arc_radius_pt * math.cos(char_center_rad))
        y = cy + (arc_radius_pt * math.sin(char_center_rad))

        rotation_deg = char_center_deg - 90.0

        c.saveState()
        c.translate(x, y)
        c.rotate(rotation_deg)
        c.drawCentredString(0, - (font_size * 0.35), ch)
        c.restoreState()

        current_angle_deg -= (w_ch / arc_radius_pt) * (180.0 / math.pi)


def render_hub_label(
    c: canvas.Canvas,
    cx: float,
    cy: float,
    year_str: str,
    rest_str: str,
    spec: DiscHubSpec,
    draw_guides: bool = False
):
    """
    Renders text and optional alignment guides for a single disc hub label at center (cx, cy).
    """
    c.saveState()

    if draw_guides:
        # Draw light gray outer label outline (1.30 in / 93.6 pt diameter)
        c.setStrokeColor(HexColor("#AAAAAA"))
        c.setLineWidth(0.5)
        c.circle(cx, cy, spec.outer_radius_pt, stroke=1, fill=0)

        # Draw light gray center hole outline (0.67 in / 48.24 pt diameter)
        c.setStrokeColor(HexColor("#888888"))
        c.setLineWidth(0.5)
        c.circle(cx, cy, spec.hole_radius_pt, stroke=1, fill=0)

        # Draw subtle center crosshair lines inside the hole
        cross_r = spec.hole_radius_pt * 0.5
        c.setStrokeColor(HexColor("#CCCCCC"))
        c.setLineWidth(0.3)
        c.line(cx - cross_r, cy, cx + cross_r, cy)
        c.line(cx, cy - cross_r, cx, cy + cross_r)

    # Format year text (pad to 4 digits if numeric)
    if year_str.isdigit():
        year_str = year_str.zfill(4)

    full_identifier = f"{year_str}.{rest_str}"

    if spec.render_mode == "arc":
        # Wrap full identifier as one long continuous string along circular arc
        render_curved_text(
            c,
            cx,
            cy,
            full_identifier,
            spec.font_name,
            spec.font_size,
            spec.arc_radius_pt,
            spec.arc_center_angle_deg
        )
    else:
        # Legacy stacked text mode (upper year, lower rest_identifier)
        reg_font = get_registered_font(spec.font_name)
        year_y = cy + (spec.year_offset_y_in * INCH_TO_PT)
        id_y = cy + (spec.identifier_offset_y_in * INCH_TO_PT)

        c.setFillColorRGB(0, 0, 0)
        c.setFont(reg_font, spec.year_font_size)
        c.drawCentredString(cx, year_y, year_str)

        c.setFont(reg_font, spec.identifier_font_size)
        c.drawCentredString(cx, id_y, rest_str)

    c.restoreState()


def generate_hub_pdf(
    label_queue: List[Tuple[str, str]],
    output_path: str,
    start_pos: int = 1,
    draw_guides: bool = False,
    config: Optional[Compulabel312862Config] = None
) -> str:
    """
    Generates a PDF containing disc hub labels for all (year, rest_identifier) tuples in queue.
    Supports starting at slot `start_pos` (1-26) and multi-page sheet overflows.
    Returns absolute output file path string.
    """
    if config is None:
        config = Compulabel312862Config()

    out_file = Path(output_path).resolve()
    out_file.parent.mkdir(parents=True, exist_ok=True)

    page_w_pt = config.page_width_in * INCH_TO_PT
    page_h_pt = config.page_height_in * INCH_TO_PT
    sheet_centers = config.get_sheet_label_centers_pt()
    labels_per_sheet = len(sheet_centers)  # 26

    start_pos = max(1, min(start_pos, labels_per_sheet))

    c = canvas.Canvas(str(out_file), pagesize=(page_w_pt, page_h_pt))
    c.setTitle("Accession Disc Hub Labels - Compulabel 312862")
    c.setCreator("accession-labeler")

    current_page = 0

    for idx, (year_str, rest_str) in enumerate(label_queue):
        global_slot = (start_pos - 1) + idx
        target_page = global_slot // labels_per_sheet
        slot_on_page = global_slot % labels_per_sheet

        while current_page < target_page:
            c.showPage()
            current_page += 1

        cx, cy = sheet_centers[slot_on_page]
        render_hub_label(c, cx, cy, year_str, rest_str, config.disc_spec, draw_guides=draw_guides)

    c.save()
    return str(out_file)
