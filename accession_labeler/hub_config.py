"""
Configuration and geometry definitions for Disc Hub Label sheets.
Default template: Compulabel #312862 (Letter sheet with 26 disc hub labels).
Matches SureThing Disc Labeler 6 specifications.
"""

from dataclasses import dataclass, field
from typing import List, Tuple

INCH_TO_PT = 72.0


@dataclass
class DiscHubSpec:
    """Dimensions and rendering specs for an individual disc hub label."""
    outer_diameter_in: float = 1.30      # 1.30 in (radius = 0.65 in)
    hole_diameter_in: float = 0.67       # 0.67 in (radius = 0.335 in)
    bleed_in: float = 0.08              # 0.08 in
    hole_bleed_in: float = 0.08         # 0.08 in

    # Typography matching SureThing Disc Labeler 6 visuals (Verdana Bold 12pt equivalent)
    font_name: str = "Verdana-Bold"     # Default font family (falls back to DejaVuSans-Bold / DroidSans-Bold / Helvetica-Bold)
    font_size: float = 12.0             # 12pt (equivalent to Verdana Bold 12pt at 300 DPI)

    # Render mode: "arc" (wrapped along circular arc) or "stacked" (top/bottom lines)
    render_mode: str = "arc"

    # Circular Arc Parameters (for "arc" mode)
    # Mid-radius between inner hole (0.335 in) and outer edge (0.65 in) is 0.4925 in (35.46 pt)
    arc_radius_in: float = 0.4925       # Radius of circular text path in inches
    arc_center_angle_deg: float = 90.0  # Center angle of text arc (90° = top / 12 o'clock)

    # Legacy stacked offsets (for "stacked" mode)
    year_font_size: float = 9.0
    identifier_font_size: float = 8.0
    year_offset_y_in: float = 0.42
    identifier_offset_y_in: float = -0.42

    # Hardware printer alignment fine-tuning adjustments (in inches)
    offset_x_in: float = 0.0            # Global X shift (+ is right, - is left)
    offset_y_in: float = 0.0            # Global Y shift (+ is up, - is down)

    @property
    def outer_radius_pt(self) -> float:
        return (self.outer_diameter_in / 2.0) * INCH_TO_PT

    @property
    def hole_radius_pt(self) -> float:
        return (self.hole_diameter_in / 2.0) * INCH_TO_PT

    @property
    def arc_radius_pt(self) -> float:
        return self.arc_radius_in * INCH_TO_PT



@dataclass
class SheetBlockSpec:
    """
    Grid block spec matching SureThing 6 layout model:
    - across, down: number of columns and rows in block
    - start_left_in: distance from left edge of page to left edge of first label (in)
    - start_top_in: distance from top edge of page to top edge of first label (in)
    - label_span_h_in: span from left edge of col 1 to right edge of last col (in)
    - label_span_v_in: span from top edge of row 1 to bottom edge of last row (in)
    """
    across: int
    down: int
    start_left_in: float
    start_top_in: float
    label_span_h_in: float
    label_span_v_in: float

    def get_center_positions_in(self, label_width_in: float = 1.30, label_height_in: float = 1.30) -> List[Tuple[float, float]]:
        """
        Calculates (center_x_in, center_top_y_in) from top-left page origin in inches.
        center_top_y_in is distance in inches FROM THE TOP OF THE PAGE.
        """
        radius_x = label_width_in / 2.0
        radius_y = label_height_in / 2.0

        if self.across > 1:
            col_pitch = (self.label_span_h_in - label_width_in) / (self.across - 1)
        else:
            col_pitch = 0.0

        if self.down > 1:
            row_pitch = (self.label_span_v_in - label_height_in) / (self.down - 1)
        else:
            row_pitch = 0.0

        positions = []
        for r in range(self.down):
            top_y = self.start_top_in + (r * row_pitch) + radius_y
            for c in range(self.across):
                left_x = self.start_left_in + (c * col_pitch) + radius_x
                positions.append((left_x, top_y))
        return positions


@dataclass
class Compulabel312862Config:
    """
    Page and template configuration for Compulabel #312862 (26 Disc Hub Labels on Letter).
    Page size: 8.5 x 11 inches.
    """
    page_width_in: float = 8.5
    page_height_in: float = 11.0
    disc_spec: DiscHubSpec = field(default_factory=DiscHubSpec)

    # 4 blocks defined in SureThing Disc Labeler 6 template
    blocks: List[SheetBlockSpec] = field(default_factory=lambda: [
        # Block 1: 3x3 top left/right outer columns
        SheetBlockSpec(across=3, down=3, start_left_in=0.75, start_top_in=0.60, label_span_h_in=7.13, label_span_v_in=4.29),
        # Block 2: 3x3 bottom left/right outer columns
        SheetBlockSpec(across=3, down=3, start_left_in=0.75, start_top_in=6.11, label_span_h_in=7.13, label_span_v_in=4.29),
        # Block 3: 2x2 top middle staggered columns
        SheetBlockSpec(across=2, down=2, start_left_in=2.20, start_top_in=1.35, label_span_h_in=4.21, label_span_v_in=2.80),
        # Block 4: 2x2 bottom middle staggered columns
        SheetBlockSpec(across=2, down=2, start_left_in=2.20, start_top_in=6.85, label_span_h_in=4.21, label_span_v_in=2.80),
    ])

    def get_sheet_label_centers_pt(self) -> List[Tuple[float, float]]:
        """
        Returns list of 26 (center_x_pt, center_y_pt) in standard PDF points
        where Y=0 is AT THE BOTTOM OF THE PAGE.
        Ordered logically from top-of-page to bottom-of-page.
        """
        all_centers = []
        for block in self.blocks:
            centers_in = block.get_center_positions_in(
                label_width_in=self.disc_spec.outer_diameter_in,
                label_height_in=self.disc_spec.outer_diameter_in
            )
            all_centers.extend(centers_in)

        # Sort center positions by Top Y (ascending), then Left X (ascending)
        # to get natural row-by-row reading order (1 to 26)
        all_centers.sort(key=lambda pos: (round(pos[1], 2), round(pos[0], 2)))

        centers_pt = []
        for cx_in, cy_top_in in all_centers:
            # Apply global calibration offsets
            calibrated_cx_in = cx_in + self.disc_spec.offset_x_in
            calibrated_cy_top_in = cy_top_in - self.disc_spec.offset_y_in

            cx_pt = calibrated_cx_in * INCH_TO_PT
            # Convert top-down Y to PDF bottom-up Y (PageHeight - TopY)
            cy_pt = (self.page_height_in - calibrated_cy_top_in) * INCH_TO_PT
            centers_pt.append((cx_pt, cy_pt))

        return centers_pt
