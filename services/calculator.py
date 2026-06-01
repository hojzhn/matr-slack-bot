

from dataclasses import dataclass

from utils.units import mm_to_inch

DEFAULT_X0_MM = 409.0
DEFAULT_Y0_MM = 98.0


@dataclass
class PositionResult:
    x_pos_mm: float
    y_pos_mm: float
    adj_width_mm: float
    adj_height_mm: float

    @property
    def adj_width_in(self):
        return mm_to_inch(self.adj_width_mm)

    @property
    def adj_height_in(self):
        return mm_to_inch(self.adj_height_mm)


def calculate_position(
    width_mm,
    height_mm,
    margin_mm,
    delta_x_mm,
    delta_y_mm,
    x0_mm=DEFAULT_X0_MM,
    y0_mm=DEFAULT_Y0_MM,
):

    if width_mm <= 0 or height_mm <= 0:
        raise ValueError("width and height must be positive")
    if margin_mm < 0:
        raise ValueError("margin cannot be negative")

    longer_mm = max(width_mm, height_mm)
    scale = (longer_mm + margin_mm) / longer_mm

    adj_width_mm = width_mm * scale
    adj_height_mm = height_mm * scale

    x_pos_mm = x0_mm + delta_x_mm - (adj_width_mm - width_mm) / 2
    y_pos_mm = y0_mm + delta_y_mm - (adj_height_mm - height_mm) / 2

    return PositionResult(
        x_pos_mm=x_pos_mm,
        y_pos_mm=y_pos_mm,
        adj_width_mm=adj_width_mm,
        adj_height_mm=adj_height_mm,
    )
