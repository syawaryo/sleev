"""DWG → DXF conversion via ODA File Converter.

Requires the ODAFileConverter binary on PATH. On headless Linux the converter
is a Qt app and needs xvfb-run to provide a display — installed in Dockerfile.
Install locally from: https://www.opendesign.com/guestfiles/oda_file_converter
"""
from __future__ import annotations

import platform
import shutil
import subprocess
import tempfile
from pathlib import Path


class DwgConversionError(RuntimeError):
    """Raised when DWG→DXF conversion fails."""


_CONVERTER_CANDIDATES = (
    "ODAFileConverter",
    "/usr/bin/ODAFileConverter",
)

_INSTALL_HINT = (
    "ODA File Converter not found. Install from "
    "https://www.opendesign.com/guestfiles/oda_file_converter, "
    "or convert DWG→DXF locally and upload the DXF directly."
)


def _locate_converter() -> str | None:
    for name in _CONVERTER_CANDIDATES:
        found = shutil.which(name) if "/" not in name else (name if Path(name).exists() else None)
        if found:
            return found
    return None


def _build_command(converter: str, in_dir: Path, out_dir: Path, dwg_version: str) -> list[str]:
    args = [
        converter,
        str(in_dir),
        str(out_dir),
        dwg_version,
        "DXF",
        "0",  # recurse: off
        "1",  # audit: on
    ]
    if platform.system() == "Linux" and shutil.which("xvfb-run"):
        return ["xvfb-run", "-a", *args]
    return args


def convert_dwg_to_dxf(
    dwg_path: Path,
    out_dir: Path,
    *,
    dwg_version: str = "ACAD2018",
    timeout: int = 300,
) -> Path:
    """Convert a single DWG file to DXF.

    ODA File Converter only accepts directories, so the DWG is staged in a
    temporary directory and the resulting DXF is moved into `out_dir`.

    Returns the path to the produced .dxf file in `out_dir`.
    """
    if not dwg_path.exists():
        raise DwgConversionError(f"DWG file not found: {dwg_path}")

    converter = _locate_converter()
    if converter is None:
        raise DwgConversionError(_INSTALL_HINT)

    out_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        in_dir = tmp_path / "in"
        out_tmp = tmp_path / "out"
        in_dir.mkdir()
        out_tmp.mkdir()

        staged = in_dir / dwg_path.name
        shutil.copy2(dwg_path, staged)

        cmd = _build_command(converter, in_dir, out_tmp, dwg_version)
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as e:
            raise DwgConversionError(
                f"Conversion timed out after {timeout}s: {dwg_path.name}"
            ) from e
        except FileNotFoundError as e:
            raise DwgConversionError(f"Failed to launch converter: {e}") from e

        if result.returncode != 0:
            raise DwgConversionError(
                f"ODAFileConverter exited {result.returncode}: "
                f"{result.stderr.strip() or result.stdout.strip()}"
            )

        produced = list(out_tmp.glob("*.dxf"))
        if not produced:
            raise DwgConversionError(
                "No DXF produced. "
                f"stderr={result.stderr.strip()!r}"
            )

        dxf = produced[0]
        dest = out_dir / (dwg_path.stem + ".dxf")
        shutil.move(str(dxf), dest)
        return dest
