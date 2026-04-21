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

from .models import FloorData, Sleeve, GridLine


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


def _profile_diameter(solid) -> float | None:
    """Pull a representative diameter from an IfcExtrudedAreaSolid."""
    if not solid.is_a("IfcExtrudedAreaSolid"):
        return None
    prof = solid.SweptArea
    if prof.is_a("IfcCircleProfileDef"):
        return float(prof.Radius) * 2.0
    if prof.is_a("IfcRectangleProfileDef"):
        # treat rectangle as equivalent-diameter = (X+Y)/2
        return (float(prof.XDim) + float(prof.YDim)) / 2.0
    return None


def _sleeve_diameter(proxy) -> float:
    """Resolve diameter from representation (handles IfcMappedItem indirection)."""
    rep = proxy.Representation
    if rep is None:
        return 0.0
    for r in rep.Representations:
        for item in r.Items:
            if item.is_a("IfcMappedItem"):
                mapped = item.MappingSource.MappedRepresentation
                for inner in mapped.Items:
                    d = _profile_diameter(inner)
                    if d is not None:
                        return d
            else:
                d = _profile_diameter(item)
                if d is not None:
                    return d
    return 0.0


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
        x = float(M[0, 3])
        y = float(M[1, 3])

        psets = _elem_util.get_psets(p) or {}
        basic = psets.get("Pset_Tfas_SystemProperty_Basic", {})
        cable = psets.get("Pset_Tfas_SystemProperty_Cable_Duct_Tray", {})
        plumb = psets.get("Pset_Tfas_SystemProperty_HVAC_Plumbing_Parts", {})
        circ = psets.get("Pset_BE-Bridge_SleeveCircular", {})

        diameter = _sleeve_diameter(p)

        diameter_text = None
        d_pset = cable.get("diameter") or plumb.get("connection_point_number_1_size") or circ.get("d")
        if d_pset:
            diameter_text = str(d_pset)

        fl_text = _fmt_fl(
            cable.get("connection_line_number_1_centre")
            or plumb.get("connection_point_number_1_elevation")
        )

        label_text = basic.get("figure_name") or p.Name or ""
        layer = basic.get("layer") or ""
        discipline = _discipline_from_layer(layer)

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


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------

def parse_ifc(sleeve_path: str | Path, structure_path: str | Path | None = None) -> FloorData:
    """Parse a Tfas-output sleeve IFC (and optional structural IFC) into FloorData.

    Phase 1: only Sleeves and GridLines are populated. Structural IFC handling
    is a stub that will be expanded in Phase 2.
    """
    sp = Path(sleeve_path)
    if not sp.exists():
        raise FileNotFoundError(f"Sleeve IFC not found: {sp}")

    sleeve_f = ifcopenshell.open(str(sp))

    sleeves = _extract_sleeves(sleeve_f)
    grid_lines = _extract_grids(sleeve_f)

    # Phase 2 hook — structural IFC. Intentionally left empty for now.
    if structure_path is not None:
        struct_p = Path(structure_path)
        if struct_p.exists():
            _ = ifcopenshell.open(str(struct_p))  # loaded, not yet mined

    return FloorData(sleeves=sleeves, grid_lines=grid_lines)
