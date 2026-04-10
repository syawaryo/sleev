from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class Sleeve:
    id: str
    center: tuple[float, float]
    diameter: float
    label_text: str | None = None
    diameter_text: str | None = None
    fl_text: str | None = None
    pn_number: str | None = None
    layer: str = ""
    discipline: str = ""


@dataclass
class GridLine:
    axis_label: str
    direction: str  # "H" or "V"
    position: float


@dataclass
class DimLine:
    layer: str
    measurement: float
    defpoint1: tuple[float, float]   # defpoint (10): dimension line position
    defpoint2: tuple[float, float]   # defpoint2 (13): 1st extension line origin
    defpoint3: tuple[float, float] = (0.0, 0.0)  # defpoint3 (14): 2nd extension line origin
    angle: float | None = None       # rotation angle (group 50), None = auto
    text_override: str | None = None


@dataclass
class WallLine:
    start: tuple[float, float]
    end: tuple[float, float]
    layer: str = ""
    wall_type: str = "不明"


@dataclass
class StepLine:
    start: tuple[float, float]
    end: tuple[float, float]
    layer: str = ""


@dataclass
class ColumnLine:
    start: tuple[float, float]
    end: tuple[float, float]
    layer: str = ""


@dataclass
class SlabZone:
    x: float
    y: float
    fl_text: str  # e.g. "FL+40", "FL-360"
    fl_value: int  # numeric mm value, e.g. +40, -360


@dataclass
class PnLabel:
    x: float
    y: float
    text: str     # "P-N-1"
    number: int
    arrow_verts: list[tuple[float, float]] = field(default_factory=list)  # triangle vertices, empty if no arrow


@dataclass
class SlabLabel:
    x: float
    y: float
    slab_no: str       # "S16", "DS16"
    level: str         # "-60" or "-545～-600"
    thickness: str     # "165"


@dataclass
class SlabOutline:
    start: tuple[float, float]
    end: tuple[float, float]


@dataclass
class WaterGradient:
    x: float
    y: float
    direction: str = ""  # "→", "←", "↑", "↓" or empty


@dataclass
class FloorData:
    sleeves: list[Sleeve] = field(default_factory=list)
    grid_lines: list[GridLine] = field(default_factory=list)
    dim_lines: list[DimLine] = field(default_factory=list)
    wall_lines: list[WallLine] = field(default_factory=list)
    step_lines: list[StepLine] = field(default_factory=list)
    column_lines: list[ColumnLine] = field(default_factory=list)
    slab_zones: list[SlabZone] = field(default_factory=list)
    slab_outlines: list[SlabOutline] = field(default_factory=list)
    slab_labels: list[SlabLabel] = field(default_factory=list)
    pn_labels: list[PnLabel] = field(default_factory=list)
    water_gradients: list[WaterGradient] = field(default_factory=list)
    slab_level: str | None = None
    has_base_level_def: bool = False


@dataclass
class CheckResult:
    check_id: int
    check_name: str
    severity: str  # "NG" / "WARNING" / "OK"
    sleeve: Sleeve | None = None
    message: str = ""
    related_coords: list[tuple[float, float]] = field(default_factory=list)
