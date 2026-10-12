"""Build the exhibition snapshot from real DXFs and the builtin checklist.

Run from the repository root: python scripts/export_demo.py
No API server, external AI calls, or mutable parse caches are used.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sleeve_checker.check_registry import default_defs, run_registry_checks
from sleeve_checker.parser import parse_dxf
from sleeve_checker.universal_parser import flatten
from sleeve_checker.layer_classifier import classify_layers


def compact(value):
    # Rounding is for display only; checks run first at original precision.
    if isinstance(value, float):
        return round(value, 3)
    if isinstance(value, dict):
        return {k: compact(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [compact(v) for v in value]
    return value


def result_dict(result):
    data = dataclasses.asdict(result)
    data["sleeve_id"] = result.sleeve.id if result.sleeve else None
    data.pop("sleeve", None)
    return data


def export_entities(source: Path, floor_id: str, output: Path):
    """Keep every source entity; omit geometry props unused by the data table."""
    dump = flatten(source)
    classifications = classify_layers(
        [{"name": layer} for layer in sorted({e.layer for e in dump.entities})],
        use_llm=False,
    )
    data = {
        "summary": dump.summary,
        "entities": [{
            "handle": e.handle, "layer": e.layer, "type": e.type,
            "subtype": e.subtype, "pos": e.pos,
            "props": {"measurement": e.props["measurement"]} if "measurement" in e.props else {},
        } for e in dump.entities],
        "layer_categories": {name: row["category"] for name, row in classifications.items()},
    }
    blob = json.dumps(compact(data), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    filename = f"{floor_id}-entities-{hashlib.sha256(blob).hexdigest()[:12]}.json"
    (output / filename).write_bytes(blob)
    print(f"{floor_id}: {len(dump.entities):,} data entities, {len(blob):,} bytes", flush=True)
    return filename


def export_demo(output: Path = ROOT / "frontend/public/demo"):
    output.mkdir(parents=True, exist_ok=True)
    definitions = default_defs()
    sources = [("1f", ROOT / "dxf_output/1階床スリーブ図.dxf"),
               ("2f", ROOT / "dxf_output/2階床スリーブ図.dxf")]
    floors = {}
    for floor_id, source in sources:
        print(f"Parsing {source.name}", flush=True)
        floors[floor_id] = parse_dxf(str(source))

    manifest = {"schemaVersion": 1, "generatedAt": datetime.now(timezone.utc).isoformat(),
                "checklistName": "スリーブ図チェックリスト", "checklistNote":
                "本デモで使用する13項目と判定基準。先方の原本との対応は確認中です。",
                "checks": [d.to_public_dict() for d in definitions], "floors": []}
    for floor_id, source in sources:
        floor = floors[floor_id]
        lower_id = "1f" if floor_id == "2f" else None
        results = run_registry_checks(floor, floors.get(lower_id), registry=definitions)
        errors = [r.message for r in results if r.message.startswith("チェック実行エラー:")]
        if errors:
            raise RuntimeError("Snapshot contains failed checks: " + "; ".join(errors))
        drawing = dataclasses.asdict(floor)
        # Raw CAD entities are unused by the six exhibition layer controls.
        drawing.pop("raw_lines", None)
        drawing.pop("raw_texts", None)
        drawing = compact(drawing)
        blob = json.dumps(drawing, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        filename = f"{floor_id}-{hashlib.sha256(blob).hexdigest()[:12]}.json"
        (output / filename).write_bytes(blob)
        manifest["floors"].append({
            "id": floor_id, "label": source.name, "source": "dxf", "lowerFloorId": lower_id,
            "sourceSha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "drawingFile": filename, "sleeves": drawing["sleeves"],
            "entitiesFile": export_entities(source, floor_id, output),
            "results": compact([result_dict(r) for r in results]),
        })
        print(f"{floor_id}: {len(floor.sleeves)} sleeves, {len(results)} results, {len(blob):,} drawing bytes", flush=True)
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    export_demo()
