"""
api.py - FastAPI backend for the sleeve checker project.

Run with:
    uvicorn api:app --reload --port 8000
"""

from __future__ import annotations

import dataclasses
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from sleeve_checker.checks import run_all_checks
from sleeve_checker.models import FloorData
from sleeve_checker.parser import parse_dxf

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(title="Sleeve Checker API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://localhost:5175"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DXF_DIR = Path("dxf_output")

# Map filename stems to short IDs
_FLOOR_ID_MAP: dict[str, str] = {
    "1階床スリーブ図": "1f",
    "2階床スリーブ図": "2f",
}
# Reverse map: id -> stem
_ID_TO_STEM: dict[str, str] = {v: k for k, v in _FLOOR_ID_MAP.items()}

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


def _get_or_parse(filepath: Path) -> FloorData:
    """Return cached FloorData or parse and cache it."""
    key = str(filepath.resolve())
    if key not in _parse_cache:
        _parse_cache[key] = parse_dxf(str(filepath))
    return _parse_cache[key]


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
    step_threshold: float | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/floors")
def list_floors() -> list[dict]:
    """Return all available DXF files in dxf_output/."""
    if not DXF_DIR.exists():
        return []

    floors = []
    for dxf_file in sorted(DXF_DIR.glob("*.dxf")):
        stem = dxf_file.stem
        floor_id = _FLOOR_ID_MAP.get(stem, stem)
        floors.append(
            {
                "id": floor_id,
                "name": stem,
                "path": str(dxf_file).replace("\\", "/"),
            }
        )
    return floors


@app.post("/api/parse")
def parse_floor(request: ParseRequest) -> dict:
    """Parse a DXF file and return FloorData as JSON (result is cached)."""
    filepath = _get_floor_path(request.floor_id, request.path)
    floor_data = _get_or_parse(filepath)
    return _floor_data_to_dict(floor_data)


@app.post("/api/check")
def run_checks(request: CheckRequest) -> dict:
    """Run all sleeve checks and return results with a summary."""
    # Resolve 2F path (required)
    floor_2f_path = _get_floor_path(request.floor_2f_id, request.floor_2f_path)
    floor_2f = _get_or_parse(floor_2f_path)

    # Resolve 1F path (optional — for lower-wall check)
    floor_1f: FloorData | None = None
    if request.floor_1f_id is not None or request.floor_1f_path is not None:
        floor_1f_path = _get_floor_path(request.floor_1f_id, request.floor_1f_path)
        floor_1f = _get_or_parse(floor_1f_path)

    check_results = run_all_checks(
        floor_2f=floor_2f,
        floor_1f=floor_1f,
        wall_thickness=request.wall_thickness,
        step_threshold=request.step_threshold,
    )

    results_list = [_check_result_to_dict(cr) for cr in check_results]

    summary = {"ng": 0, "warning": 0, "ok": 0}
    for cr in check_results:
        key = cr.severity.lower()
        if key in summary:
            summary[key] += 1

    return {"results": results_list, "summary": summary}
