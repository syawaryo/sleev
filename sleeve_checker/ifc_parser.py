"""
ifc_parser.py — IFC input path for the sleeve checker.

Reads a sleeve-IFC (and optionally a structural-IFC) and produces a FloorData
object with the same shape as parser.py's DXF output, so checks.py runs
unchanged.

Phase 1 scope (current): extract Sleeves + GridLines.
Phase 2 will add WallLine / SlabOutline / ColumnLine from the structural IFC.
Phase 3 will synthesise dim_lines / slab_labels / step_lines from geometry so
more of the 14 checks can run.
"""
from __future__ import annotations

import re
from pathlib import Path

import ifcopenshell
import ifcopenshell.util.element as _elem_util
import ifcopenshell.util.placement as _place_util
import numpy as np

from .models import FloorData, Sleeve, GridLine, DimLine


# ---------------------------------------------------------------------------
# Sleeve extraction
# ---------------------------------------------------------------------------

_FL_RE = re.compile(r"FL\s*([＋－+\-]?\s*\d+)")
_DISC_KEYWORDS = {"電気": "電気", "衛生": "衛生", "空調": "空調", "建築": "建築"}


def _fmt_fl(raw: str | None) -> str | None:
    """'ﾚﾍﾞﾙ(中心) : FL －785' -> 'FL-785'."""
    if not raw:
        return None
    m = _FL_RE.search(raw)
    if not m:
        return None
    num = m.group(1).replace("＋", "+").replace("－", "-").replace(" ", "")
    if not num.startswith(("+", "-")):
        num = "+" + num
    return f"FL{num}"


def _discipline_from_layer(layer: str | None) -> str:
    if not layer:
        return ""
    for kw, canon in _DISC_KEYWORDS.items():
        if kw in layer:
            return canon
    return ""


def _parse_tfas_point(raw: str | None) -> tuple[float, float, float] | None:
    """Parse a Tfas Pset point string like '75468.0,1030.0,-785.5,' → tuple.

    Returns None if the string is missing or not parseable.
    """
    if not raw:
        return None
    parts = str(raw).split(",")
    try:
        nums = [float(p.strip()) for p in parts if p.strip() != ""]
    except ValueError:
        return None
    if len(nums) < 3:
        return None
    return (nums[0], nums[1], nums[2])


def _profile_and_depth(solid) -> tuple[str, float, float, float] | None:
    """Return (cross_shape, cross_w, cross_h, depth) from an IfcExtrudedAreaSolid.

    cross_shape is the CROSS-SECTION of the sleeve body (perpendicular to the
    extrusion axis). depth is the length along the extrusion axis.
    """
    if not solid.is_a("IfcExtrudedAreaSolid"):
        return None
    prof = solid.SweptArea
    depth = float(solid.Depth)
    if prof.is_a("IfcCircleProfileDef"):
        d = float(prof.Radius) * 2.0
        return ("round", d, d, depth)
    if prof.is_a("IfcRectangleProfileDef"):
        return ("rect", float(prof.XDim), float(prof.YDim), depth)
    return None


def _sleeve_top_view(proxy, main_vecter: str | None) -> tuple[str, float, float]:
    """Resolve the plan-view (top-down) shape of a sleeve.

    - Vertical sleeve (main_vecter Z-dominant) → plan view = cross-section
      profile (circle for round pipes, rectangle for box sleeves).
    - Horizontal sleeve (main_vecter X/Y-dominant) → plan view = rectangle of
      (cross-section diameter) × (extrusion length), with the long axis
      aligned to the main_vecter direction. Even for circular pipes, a
      horizontal penetration reads as a long rectangle on a floor plan
      because you see the pipe's length, not its cross-section circle.
    """
    rep = proxy.Representation
    if rep is None:
        return ("round", 0.0, 0.0)

    info: tuple[str, float, float, float] | None = None
    for r in rep.Representations:
        for item in r.Items:
            inner = item.MappingSource.MappedRepresentation.Items[0] if item.is_a("IfcMappedItem") else item
            got = _profile_and_depth(inner)
            if got is not None:
                info = got
                break
        if info is not None:
            break
    if info is None:
        return ("round", 0.0, 0.0)

    cs_shape, cs_w, cs_h, depth = info

    ax, ay, az = 0.0, 0.0, 1.0
    if main_vecter:
        try:
            parts = [float(v) for v in str(main_vecter).split(",")[:3]]
            if len(parts) == 3:
                ax, ay, az = parts
        except (TypeError, ValueError):
            pass

    # Vertical → plan view is the cross-section as-is
    if abs(az) > max(abs(ax), abs(ay)):
        return (cs_shape, cs_w, cs_h)

    # Horizontal → rectangle of diameter × extrusion length, oriented along
    # the main axis. cs_w == cs_h for circular cross-sections.
    diameter = cs_h  # short side of the rectangle = pipe/duct diameter
    if abs(ax) > abs(ay):
        # Along world X → long side on X
        return ("rect", depth, diameter)
    else:
        # Along world Y → long side on Y
        return ("rect", diameter, depth)


def _extract_sleeves(f) -> list[Sleeve]:
    sleeves: list[Sleeve] = []
    for p in f.by_type("IfcBuildingElementProxy"):
        # Tfas outputs mark sleeves with ObjectType 'ProvisionForVoid'.
        # If ObjectType differs, still accept to be permissive across vendors.
        if p.ObjectType not in (None, "", "ProvisionForVoid") and "Sleeve" not in (p.ObjectType or ""):
            # skip only if clearly not a sleeve
            pass

        try:
            M = _place_util.get_local_placement(p.ObjectPlacement)
        except Exception:
            continue

        psets = _elem_util.get_psets(p) or {}
        basic = psets.get("Pset_Tfas_SystemProperty_Basic", {})
        cable = psets.get("Pset_Tfas_SystemProperty_Cable_Duct_Tray", {})
        plumb = psets.get("Pset_Tfas_SystemProperty_HVAC_Plumbing_Parts", {})
        circ = psets.get("Pset_BE-Bridge_SleeveCircular", {})
        bridge_common = psets.get("Pset_BE-Bridge_Common", {})

        # Tfas places its reference point at one END of the sleeve (= connecting_
        # point_1 / wall face). DXF drafting convention draws the sleeve symbol
        # at the wall centreline = midpoint of the two connecting points. Use the
        # midpoint here so IFC and DXF sleeves align 1:1 on the same drawing.
        cp1 = _parse_tfas_point(bridge_common.get("connecting_point_1"))
        cp2 = _parse_tfas_point(bridge_common.get("connecting_point_2"))
        if cp1 is not None and cp2 is not None:
            x = (cp1[0] + cp2[0]) / 2.0
            y = (cp1[1] + cp2[1]) / 2.0
        else:
            x = float(M[0, 3])
            y = float(M[1, 3])

        # Orientation: main_vecter is the principal axis of the pipe/duct
        # passing through the sleeve. Z-dominant → vertical (縦管), otherwise
        # horizontal (横管). Stored as "(x,y,z)" string in the Tfas export.
        mv_str = bridge_common.get("main_vecter") or bridge_common.get("main_vector") or ""
        orientation = ""
        if mv_str:
            try:
                parts = [float(v) for v in str(mv_str).split(",")[:3]]
                if len(parts) == 3:
                    ax, ay, az = parts
                    orientation = "vertical" if abs(az) > max(abs(ax), abs(ay)) else "horizontal"
            except (TypeError, ValueError):
                pass

        # Plan-view shape: horizontal sleeves become rectangles on the floor
        # plan (diameter × extrusion length) even if their cross-section is
        # circular, matching how DXF drafters draw them.
        shape, width, height = _sleeve_top_view(p, mv_str)
        # For round plan-view: diameter == width == height.
        # For rect plan-view: use the *short* side as the nominal "diameter"
        # (pipe/duct cross-section), with the long side = extrusion depth.
        diameter = min(width, height) if shape == "rect" else width

        # Synthesise the "nominal + outer" diameter_text format that check #3
        # expects. IFC geometry gives us the outer diameter directly; the Tfas
        # Pset doesn't distinguish nominal from outer for these sleeves.
        diameter_text: str | None = None
        if diameter > 0:
            d_int = int(round(diameter))
            diameter_text = f"{d_int}φ 外径{d_int}φ"

        fl_text = _fmt_fl(
            cable.get("connection_line_number_1_centre")
            or plumb.get("connection_point_number_1_elevation")
        )

        label_text = basic.get("figure_name") or p.Name or ""
        layer = basic.get("layer") or ""
        discipline = _discipline_from_layer(layer)

        # For IFC the equipment code (EA/CW/…) is NOT in the geometry label —
        # the figure_name is a generic "鋼製丸スリーブ" / "スリーブ箱". Instead,
        # Tfas encodes the discipline in Pset_Tfas_SystemProperty_Basic.layer
        # ("電気:スリーブ" / "空調:スリーブ" / "衛生:スリーブ"), which maps
        # cleanly to our sleeve_type taxonomy.
        #
        #   衛生 → pipe   (given / drain / chilled-water plumbing)
        #   空調 → duct   (HVAC / smoke-exhaust ducts)
        #   電気 → cable  (cable rack / conduit)
        #
        # We refine with figure_type when it disagrees (rare in practice):
        # figure_type "ﾀﾞｸﾄ･ﾗｯｸ" on a 電気 layer stays "cable" (it is a
        # cable-rack penetration, not an HVAC duct).
        _IFC_DISC_TO_TYPE = {"衛生": "pipe", "空調": "duct", "電気": "cable"}
        sleeve_type = _IFC_DISC_TO_TYPE.get(discipline, "")

        sleeves.append(Sleeve(
            id=p.GlobalId,
            center=(x, y),
            diameter=diameter,
            label_text=label_text,
            diameter_text=diameter_text,
            fl_text=fl_text,
            pn_number=None,  # not present in Tfas IFC; Phase 3 will synthesise
            layer=layer,
            discipline=discipline,
            shape=shape,
            width=width,
            height=height,
            color=None,  # IFC doesn't carry ACI color
            sleeve_type=sleeve_type,
            orientation=orientation,
        ))
    return sleeves


# ---------------------------------------------------------------------------
# Grid extraction
# ---------------------------------------------------------------------------

def _axis_to_gridline(ax, M: np.ndarray) -> GridLine | None:
    curve = ax.AxisCurve
    if not curve.is_a("IfcLine"):
        return None
    px, py = curve.Pnt.Coordinates[:2]
    dx, dy = curve.Dir.Orientation.DirectionRatios[:2]
    p = M @ np.array([px, py, 0.0, 1.0])
    d = M[:3, :3] @ np.array([dx, dy, 0.0])
    if abs(d[0]) > abs(d[1]):  # horizontal line (constant Y)
        return GridLine(axis_label=ax.AxisTag, direction="H", position=float(p[1]))
    return GridLine(axis_label=ax.AxisTag, direction="V", position=float(p[0]))


def _extract_grids(f) -> list[GridLine]:
    out: list[GridLine] = []
    for grid in f.by_type("IfcGrid"):
        try:
            M = _place_util.get_local_placement(grid.ObjectPlacement) if grid.ObjectPlacement else np.eye(4)
        except Exception:
            M = np.eye(4)
        for ax in list(grid.UAxes or []) + list(grid.VAxes or []):
            g = _axis_to_gridline(ax, M)
            if g is not None:
                out.append(g)
    return out


def _grid_bounds(grid_lines: list[GridLine]) -> tuple[float, float, float, float] | None:
    """Return (min_x, max_x, min_y, max_y) of all V/H grid positions, or None."""
    v_pos = [g.position for g in grid_lines if g.direction == "V"]
    h_pos = [g.position for g in grid_lines if g.direction == "H"]
    if not v_pos or not h_pos:
        return None
    return (min(v_pos), max(v_pos), min(h_pos), max(h_pos))


def _within_building_area(center: tuple[float, float], grid_lines: list[GridLine]) -> bool:
    """True if `center` lies within 1.5× the grid extent around the grid centre.

    Tfas IFCs include sleeves for detail/enlarged views placed far outside the
    main building footprint (typically at the drawing's upper corners). Those
    sleeves duplicate real sleeves and confuse per-floor counts / checks. The
    1.5× band keeps perimeter elements while rejecting the detail-view clones.
    """
    b = _grid_bounds(grid_lines)
    if b is None:
        return True  # no grid → don't filter
    min_x, max_x, min_y, max_y = b
    span_x = (max_x - min_x) or 1.0
    span_y = (max_y - min_y) or 1.0
    cx = (min_x + max_x) / 2.0
    cy = (min_y + max_y) / 2.0
    return (
        abs(center[0] - cx) <= span_x * 0.75
        and abs(center[1] - cy) <= span_y * 0.75
    )


# ---------------------------------------------------------------------------
# Synthesis: translate IFC geometry into the DXF-notation fields checks.py
# expects, BUT only when IFC actually carries the underlying fact. If the IFC
# doesn't carry the information at all (e.g. construction-side P-N numbers),
# we leave the field blank so the check can report the missing data honestly.
# ---------------------------------------------------------------------------

def _synthesize_grid_dims(sleeves: list[Sleeve], grids: list[GridLine]) -> list[DimLine]:
    """Create one horizontal + one vertical DimLine per sleeve, anchored to its
    nearest grid axis. Gives check #9 (position determinacy) and #11 (center
    dim traces back to grid) enough structure to resolve every sleeve.
    """
    v_grids = sorted([g for g in grids if g.direction == "V"], key=lambda g: g.position)
    h_grids = sorted([g for g in grids if g.direction == "H"], key=lambda g: g.position)
    if not v_grids and not h_grids:
        return []

    def _nearest(positions: list[float], val: float) -> float | None:
        if not positions:
            return None
        return min(positions, key=lambda p: abs(p - val))

    dims: list[DimLine] = []
    for s in sleeves:
        cx, cy = s.center

        gx = _nearest([g.position for g in v_grids], cx)
        if gx is not None:
            dims.append(DimLine(
                layer="SYNTH_IFC",
                measurement=abs(cx - gx),
                defpoint1=((cx + gx) / 2.0, cy - 500.0),
                defpoint2=(cx, cy),
                defpoint3=(gx, cy),
                angle=0.0,  # horizontal → measures X
            ))

        gy = _nearest([g.position for g in h_grids], cy)
        if gy is not None:
            dims.append(DimLine(
                layer="SYNTH_IFC",
                measurement=abs(cy - gy),
                defpoint1=(cx + 500.0, (cy + gy) / 2.0),
                defpoint2=(cx, cy),
                defpoint3=(cx, gy),
                angle=90.0,  # vertical → measures Y
            ))
    return dims


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------

def parse_ifc(mep_path: str | Path, architecture_path: str | Path | None = None) -> FloorData:
    """Parse a MEP IFC (sleeves + grids) and an architecture IFC (structure) into FloorData.

    Phase 1: only Sleeves and GridLines are populated from the MEP IFC.
    Phase 2 will mine walls / slabs / columns from the architecture IFC.
    """
    mp = Path(mep_path)
    if not mp.exists():
        raise FileNotFoundError(f"MEP IFC not found: {mp}")

    mep_f = ifcopenshell.open(str(mp))

    grid_lines = _extract_grids(mep_f)
    sleeves = _extract_sleeves(mep_f)
    # Drop sleeves placed in enlarged-detail areas (outside 1.5× grid extent).
    # These are drafting duplicates of real sleeves rendered in the sheet's
    # corner mini-maps; filtering them brings IFC counts in line with DXF.
    sleeves = [s for s in sleeves if _within_building_area(s.center, grid_lines)]

    # Phase 2 hook — architecture IFC. Intentionally left empty for now.
    if architecture_path is not None:
        arch_p = Path(architecture_path)
        if arch_p.exists():
            _ = ifcopenshell.open(str(arch_p))  # loaded, not yet mined

    # Synthesis: fill notation-side fields whose semantic truth the IFC
    # already carries (geometry, grid placement). P-N numbers are NOT
    # synthesised because Tfas IFC doesn't carry construction-side P-N
    # labels — leaving pn_number=None lets check #14 report the missing
    # information honestly instead of auto-passing on fabricated data.
    dim_lines = _synthesize_grid_dims(sleeves, grid_lines)

    # IFCBuildingStorey carries Elevation natively, so the "base level is
    # defined" condition (check #8 1st clause) is intrinsically true for IFC.
    has_base_level_def = len(mep_f.by_type("IfcBuildingStorey")) > 0

    return FloorData(
        sleeves=sleeves,
        grid_lines=grid_lines,
        dim_lines=dim_lines,
        has_base_level_def=has_base_level_def,
    )
