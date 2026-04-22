"""
api.py - FastAPI backend for the sleeve checker project.

Run with:
    uvicorn api:app --reload --port 8000
"""

from __future__ import annotations

import dataclasses
import os
import re
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from sleeve_checker.checks import run_all_checks
from sleeve_checker.models import (
    FloorData, Sleeve, GridLine, DimLine, WallLine, StepLine,
    ColumnLine, SlabZone, SlabLabel, SlabOutline, PnLabel,
)
from sleeve_checker.parser import parse_dxf
from sleeve_checker.ifc_parser import parse_ifc
from sleeve_checker.dwg_to_dxf import convert_dwg_to_dxf, DwgConversionError

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(title="Sleeve Checker API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5176",
        "http://localhost:5175",
        os.getenv("FRONTEND_URL", ""),
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DXF_DIR = Path("dxf_output")
IFC_DIR = Path("ifc_output")

# Map filename stems to short IDs — built dynamically via _stem_to_floor_id()
_FLOOR_ID_MAP: dict[str, str] = {}
# Reverse map: id -> stem
_ID_TO_STEM: dict[str, str] = {}
# floor_id -> (sleeve_ifc_path, structure_ifc_path_or_None)
_IFC_SOURCES: dict[str, tuple[Path, Path | None]] = {}

_RE_FLOOR = re.compile(r"(B?\d+)階")


def _stem_to_floor_id(stem: str) -> str:
    """Extract floor ID from filename stem (e.g. '2階床スリーブ図' → '2f')."""
    m = _RE_FLOOR.search(stem)
    if m:
        raw = m.group(1)  # "B1", "1", "2", etc.
        return raw.lower() + "f"
    return stem


# Pre-populate maps from existing DXF files on startup
if DXF_DIR.exists():
    for _f in DXF_DIR.glob("*.dxf"):
        _s = _f.stem
        _fid = _stem_to_floor_id(_s)
        _FLOOR_ID_MAP[_s] = _fid
        _ID_TO_STEM[_fid] = _s

# Pre-populate IFC sources by scanning IFC_DIR/<floor_id>/sleeve.ifc on startup
if IFC_DIR.exists():
    for _sub in IFC_DIR.iterdir():
        if not _sub.is_dir():
            continue
        _sleeve = _sub / "sleeve.ifc"
        if not _sleeve.exists():
            continue
        _struct = _sub / "structure.ifc"
        _fid = _sub.name
        _IFC_SOURCES[_fid] = (_sleeve, _struct if _struct.exists() else None)
        _ID_TO_STEM.setdefault(_fid, _fid)
        _FLOOR_ID_MAP.setdefault(_fid, _fid)

# ---------------------------------------------------------------------------
# In-memory parse cache  {filepath_str: FloorData}
# ---------------------------------------------------------------------------

_parse_cache: dict[str, FloorData] = {}


def _get_floor_path(floor_id: str | None, path: str | None) -> Path:
    """Resolve a floor path from either a floor_id or an explicit path string."""
    if path:
        p = Path(path)
        if not p.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {path}")
        return p

    if floor_id:
        stem = _ID_TO_STEM.get(floor_id)
        if stem is None:
            raise HTTPException(
                status_code=404,
                detail=f"Unknown floor_id '{floor_id}'. Valid ids: {list(_ID_TO_STEM)}",
            )
        p = DXF_DIR / f"{stem}.dxf"
        if not p.exists():
            raise HTTPException(status_code=404, detail=f"DXF file not found: {p}")
        return p

    raise HTTPException(
        status_code=422, detail="Provide either 'floor_id' or 'path'."
    )


def _resolve_floor_data(floor_id: str | None, path: str | None) -> FloorData:
    """Unified resolver: returns FloorData for either IFC or DXF sources."""
    # IFC path: floor_id maps to a pair of IFC files
    if floor_id and floor_id in _IFC_SOURCES:
        cache_key = f"ifc::{floor_id}"
        if cache_key in _parse_cache:
            return _parse_cache[cache_key]
        sleeve_p, struct_p = _IFC_SOURCES[floor_id]
        fd = parse_ifc(sleeve_p, struct_p)
        _parse_cache[cache_key] = fd
        return fd
    # DXF path (existing behaviour)
    filepath = _get_floor_path(floor_id, path)
    return _get_or_parse(filepath)


CACHE_DIR = Path(".parse_cache")


def _dict_to_floor_data(d: dict) -> FloorData:
    """Reconstruct FloorData from a JSON-parsed dict."""
    return FloorData(
        sleeves=[Sleeve(
            id=s["id"], center=tuple(s["center"]), diameter=s["diameter"],
            label_text=s.get("label_text"), diameter_text=s.get("diameter_text"),
            fl_text=s.get("fl_text"),
            pn_number=s.get("pn_number"), layer=s.get("layer", ""),
            discipline=s.get("discipline", ""),
            shape=s.get("shape", "round"),
            width=s.get("width", s["diameter"]),
            height=s.get("height", s["diameter"]),
            color=s.get("color"),
            sleeve_type=s.get("sleeve_type", ""),
        ) for s in d.get("sleeves", [])],
        grid_lines=[GridLine(
            axis_label=g["axis_label"], direction=g["direction"], position=g["position"],
        ) for g in d.get("grid_lines", [])],
        dim_lines=[DimLine(
            layer=dl["layer"], measurement=dl["measurement"],
            defpoint1=tuple(dl["defpoint1"]), defpoint2=tuple(dl["defpoint2"]),
            defpoint3=tuple(dl.get("defpoint3", [0, 0])),
            angle=dl.get("angle"), text_override=dl.get("text_override"),
        ) for dl in d.get("dim_lines", [])],
        wall_lines=[WallLine(
            start=tuple(w["start"]), end=tuple(w["end"]),
            layer=w.get("layer", ""), wall_type=w.get("wall_type", ""),
        ) for w in d.get("wall_lines", [])],
        step_lines=[StepLine(
            start=tuple(s["start"]), end=tuple(s["end"]), layer=s.get("layer", ""),
        ) for s in d.get("step_lines", [])],
        column_lines=[ColumnLine(
            start=tuple(c["start"]), end=tuple(c["end"]), layer=c.get("layer", ""),
        ) for c in d.get("column_lines", [])],
        slab_zones=[SlabZone(
            x=z["x"], y=z["y"], fl_text=z["fl_text"], fl_value=z["fl_value"],
        ) for z in d.get("slab_zones", [])],
        slab_outlines=[SlabOutline(
            start=tuple(o["start"]), end=tuple(o["end"]),
        ) for o in d.get("slab_outlines", [])],
        slab_labels=[SlabLabel(
            x=sl["x"], y=sl["y"], slab_no=sl["slab_no"],
            level=sl["level"], thickness=sl["thickness"],
        ) for sl in d.get("slab_labels", [])],
        pn_labels=[PnLabel(
            x=p["x"], y=p["y"], text=p["text"], number=p["number"],
            arrow_verts=[tuple(v) for v in p.get("arrow_verts", [])],
        ) for p in d.get("pn_labels", [])],
        slab_level=d.get("slab_level"),
        has_base_level_def=d.get("has_base_level_def", False),
    )


def _cache_path(filepath: Path) -> Path:
    """Return the JSON cache file path for a given DXF file."""
    CACHE_DIR.mkdir(exist_ok=True)
    return CACHE_DIR / (filepath.stem + ".json")


def _get_or_parse(filepath: Path) -> FloorData:
    """Return cached FloorData or parse and cache it.

    Two-tier cache:
    1. In-memory dict (fastest, lost on restart)
    2. JSON file on disk (fast, survives restarts)
    Falls back to full DXF parse if neither cache is valid.
    """
    import json

    key = str(filepath.resolve())

    # Tier 1: in-memory
    if key in _parse_cache:
        return _parse_cache[key]

    # Tier 2: JSON file cache (check DXF mtime)
    cache_file = _cache_path(filepath)
    dxf_mtime = filepath.stat().st_mtime if filepath.exists() else 0

    if cache_file.exists():
        try:
            cache_mtime = cache_file.stat().st_mtime
            if cache_mtime >= dxf_mtime:
                raw = json.loads(cache_file.read_text(encoding="utf-8"))
                fd = _dict_to_floor_data(raw)
                _parse_cache[key] = fd
                return fd
        except Exception:
            pass  # cache corrupted, re-parse

    # Tier 3: full parse
    fd = parse_dxf(str(filepath))
    _parse_cache[key] = fd

    # Write cache file
    try:
        cache_file.write_text(
            json.dumps(_convert(dataclasses.asdict(fd)), ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        pass  # non-fatal

    return fd


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------

def _convert(obj: Any) -> Any:
    """Recursively convert tuples to lists for JSON-safe output."""
    if isinstance(obj, tuple):
        return [_convert(v) for v in obj]
    if isinstance(obj, list):
        return [_convert(v) for v in obj]
    if isinstance(obj, dict):
        return {k: _convert(v) for k, v in obj.items()}
    return obj


def _floor_data_to_dict(fd: FloorData) -> dict:
    """Convert FloorData dataclass to a JSON-serialisable dict."""
    raw = dataclasses.asdict(fd)
    return _convert(raw)


def _check_result_to_dict(cr) -> dict:
    """Convert a single CheckResult to a JSON-serialisable dict.

    The CheckResult.sleeve field is a Sleeve dataclass; we extract sleeve_id
    and drop the nested object to keep the response flat and frontend-friendly.
    """
    sleeve = cr.sleeve
    return {
        "check_id": cr.check_id,
        "check_name": cr.check_name,
        "severity": cr.severity,
        "sleeve_id": sleeve.id if sleeve is not None else None,
        "message": cr.message,
        "related_coords": _convert(cr.related_coords),
    }


# ---------------------------------------------------------------------------
# Request/Response models
# ---------------------------------------------------------------------------

class ParseRequest(BaseModel):
    floor_id: str | None = None
    path: str | None = None


class CheckRequest(BaseModel):
    floor_2f_id: str | None = None
    floor_1f_id: str | None = None
    floor_2f_path: str | None = None
    floor_1f_path: str | None = None
    wall_thickness: dict[str, float] | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/floors")
def list_floors() -> list[dict]:
    """Return all available floors (DXF + IFC)."""
    floors: list[dict] = []

    if DXF_DIR.exists():
        for dxf_file in sorted(DXF_DIR.glob("*.dxf")):
            stem = dxf_file.stem
            floor_id = _FLOOR_ID_MAP.get(stem) or _stem_to_floor_id(stem)
            _FLOOR_ID_MAP[stem] = floor_id
            _ID_TO_STEM[floor_id] = stem
            floors.append({
                "id": floor_id,
                "name": stem,
                "path": str(dxf_file).replace("\\", "/"),
                "source": "dxf",
            })

    for fid, (sleeve_p, _struct_p) in _IFC_SOURCES.items():
        floors.append({
            "id": fid,
            "name": _ID_TO_STEM.get(fid, fid),
            "path": str(sleeve_p).replace("\\", "/"),
            "source": "ifc",
        })

    return floors


@app.post("/api/upload")
async def upload_dxf(file: UploadFile = File(...), label: str = Form("")):
    """Upload a DXF file and return its floor entry."""
    if not file.filename or not file.filename.lower().endswith(".dxf"):
        raise HTTPException(status_code=400, detail="DXF file required")

    DXF_DIR.mkdir(exist_ok=True)
    stem = Path(file.filename).stem
    dest = DXF_DIR / file.filename
    content = await file.read()
    dest.write_bytes(content)

    floor_id = _FLOOR_ID_MAP.get(stem) or _stem_to_floor_id(stem)
    _FLOOR_ID_MAP[stem] = floor_id
    _ID_TO_STEM[floor_id] = stem

    # Clear cache for this file if it was previously parsed
    key = str(dest.resolve())
    _parse_cache.pop(key, None)

    return {
        "id": floor_id,
        "name": stem,
        "label": label or stem,
        "path": str(dest).replace("\\", "/"),
    }


@app.post("/api/upload_dwg")
async def upload_dwg(file: UploadFile = File(...), label: str = Form("")):
    """Upload a DWG, convert to DXF via ODA File Converter, register as a floor."""
    import tempfile

    if not file.filename or not file.filename.lower().endswith(".dwg"):
        raise HTTPException(status_code=400, detail="DWG file required")

    DXF_DIR.mkdir(exist_ok=True)
    stem = Path(file.filename).stem

    with tempfile.NamedTemporaryFile(suffix=".dwg", delete=False) as tmp:
        tmp.write(await file.read())
        dwg_tmp = Path(tmp.name)

    try:
        dxf_path = convert_dwg_to_dxf(dwg_tmp, DXF_DIR)
    except DwgConversionError as e:
        raise HTTPException(
            status_code=500,
            detail=(
                f"DWG→DXF conversion failed: {e} — "
                "try converting locally with ODA File Converter and upload the DXF."
            ),
        )
    finally:
        dwg_tmp.unlink(missing_ok=True)

    floor_id = _FLOOR_ID_MAP.get(stem) or _stem_to_floor_id(stem)
    _FLOOR_ID_MAP[stem] = floor_id
    _ID_TO_STEM[floor_id] = stem
    _parse_cache.pop(str(dxf_path.resolve()), None)

    return {
        "id": floor_id,
        "name": stem,
        "label": label or stem,
        "path": str(dxf_path).replace("\\", "/"),
        "source": "dwg",
    }


@app.post("/api/upload_ifc")
async def upload_ifc(
    sleeve_ifc: UploadFile = File(...),
    structure_ifc: UploadFile | None = File(None),
    label: str = Form(""),
):
    """Upload a sleeve IFC (and optional structural IFC) and register as a floor."""
    if not sleeve_ifc.filename or not sleeve_ifc.filename.lower().endswith(".ifc"):
        raise HTTPException(status_code=400, detail="Sleeve IFC file (.ifc) required")

    stem = Path(sleeve_ifc.filename).stem
    base_id = _stem_to_floor_id(stem)
    # Disambiguate from DXF namespace so the same stem doesn't clobber an existing DXF
    floor_id = f"{base_id}-ifc"

    IFC_DIR.mkdir(exist_ok=True)
    folder = IFC_DIR / floor_id
    folder.mkdir(exist_ok=True)

    sleeve_path = folder / "sleeve.ifc"
    sleeve_path.write_bytes(await sleeve_ifc.read())

    structure_path: Path | None = None
    if structure_ifc is not None and structure_ifc.filename:
        if not structure_ifc.filename.lower().endswith(".ifc"):
            raise HTTPException(status_code=400, detail="Structure IFC must be .ifc")
        structure_path = folder / "structure.ifc"
        structure_path.write_bytes(await structure_ifc.read())

    _IFC_SOURCES[floor_id] = (sleeve_path, structure_path)
    _ID_TO_STEM[floor_id] = stem
    _parse_cache.pop(f"ifc::{floor_id}", None)

    return {
        "id": floor_id,
        "name": stem,
        "label": label or stem,
        "path": str(sleeve_path).replace("\\", "/"),
        "source": "ifc",
        "has_structure": structure_path is not None,
    }


@app.post("/api/parse")
def parse_floor(request: ParseRequest) -> dict:
    """Parse a floor (DXF or IFC) and return FloorData as JSON (result is cached)."""
    floor_data = _resolve_floor_data(request.floor_id, request.path)
    return _floor_data_to_dict(floor_data)


@app.post("/api/check")
def run_checks(request: CheckRequest) -> dict:
    """Run all sleeve checks and return results with a summary."""
    floor_2f = _resolve_floor_data(request.floor_2f_id, request.floor_2f_path)

    floor_1f: FloorData | None = None
    if request.floor_1f_id is not None or request.floor_1f_path is not None:
        floor_1f = _resolve_floor_data(request.floor_1f_id, request.floor_1f_path)

    check_results = run_all_checks(
        floor_2f=floor_2f,
        floor_1f=floor_1f,
        wall_thickness=request.wall_thickness,
    )

    results_list = [_check_result_to_dict(cr) for cr in check_results]

    summary = {"ng": 0, "warning": 0, "ok": 0}
    for cr in check_results:
        key = cr.severity.lower()
        if key in summary:
            summary[key] += 1

    return {"results": results_list, "summary": summary}


# ---------------------------------------------------------------------------
# Serve frontend static files in production
# ---------------------------------------------------------------------------

_static_dir = Path(__file__).parent / "static"

if _static_dir.is_dir():
    app.mount("/assets", StaticFiles(directory=str(_static_dir / "assets")), name="assets")

    @app.get("/{full_path:path}")
    def serve_spa(full_path: str):
        """Fallback: serve index.html for any non-API route (SPA routing)."""
        file = _static_dir / full_path
        if file.is_file():
            return FileResponse(str(file))
        return FileResponse(str(_static_dir / "index.html"))
