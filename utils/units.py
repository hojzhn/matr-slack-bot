MM_PER_INCH = 25.4
POINTS_PER_INCH = 72.0
DEFAULT_DPI = 150


def inch_to_mm(inches):
    return inches * MM_PER_INCH


def mm_to_inch(mm):
    return mm / MM_PER_INCH


def pt_to_mm(points):
    return points / POINTS_PER_INCH * MM_PER_INCH


def mm_to_pt(mm):
    return mm / MM_PER_INCH * POINTS_PER_INCH


def px_to_mm(pixels, dpi=DEFAULT_DPI):

    return pixels / dpi * MM_PER_INCH


def mm_to_px(mm, dpi=DEFAULT_DPI):

    return mm / MM_PER_INCH * dpi


_TO_MM = {
    "mm": lambda v, dpi: v,
    "cm": lambda v, dpi: v * 10.0,
    "inch": lambda v, dpi: inch_to_mm(v),
    "in": lambda v, dpi: inch_to_mm(v),
    "pt": lambda v, dpi: pt_to_mm(v),
    "px": lambda v, dpi: px_to_mm(v, dpi),
}
_FROM_MM = {
    "mm": lambda v, dpi: v,
    "cm": lambda v, dpi: v / 10.0,
    "inch": lambda v, dpi: mm_to_inch(v),
    "in": lambda v, dpi: mm_to_inch(v),
    "pt": lambda v, dpi: mm_to_pt(v),
    "px": lambda v, dpi: mm_to_px(v, dpi),
}


def convert(value, from_unit, to_unit, dpi=DEFAULT_DPI):

    from_unit, to_unit = from_unit.lower(), to_unit.lower()
    if from_unit not in _TO_MM:
        raise ValueError(f"unknown from_unit: {from_unit!r}")
    if to_unit not in _FROM_MM:
        raise ValueError(f"unknown to_unit: {to_unit!r}")
    return _FROM_MM[to_unit](_TO_MM[from_unit](value, dpi), dpi)
